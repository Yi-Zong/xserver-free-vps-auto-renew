#!/usr/bin/env python3
import json
import os
import sqlite3
import subprocess
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from queue import Queue
from urllib import parse, request

BOT_TOKEN = os.getenv('TG_BOT_TOKEN', '').strip()
ADMIN_TG_ID = os.getenv('ADMIN_TG_ID', '').strip()
DB_PATH = Path(os.getenv('BOT_DB_PATH', './bot_users.db'))
POLL_TIMEOUT = int(os.getenv('TG_POLL_TIMEOUT', '30'))
WORKDIR = os.getenv('XSERVER_WORKDIR', os.getcwd())
DEFAULT_SIGN_TIME_SH = os.getenv('DEFAULT_SIGN_TIME_SH', '08:00')

TZ_SH = timezone(timedelta(hours=8))  # 上海
TZ_JP = timezone(timedelta(hours=9))  # 日本

USER_QUEUES: dict[str, Queue] = {}
USER_WORKERS: dict[str, threading.Thread] = {}
USER_RUNNING: set[str] = set()
QUEUE_LOCK = threading.Lock()


def now_sh():
    return datetime.now(TZ_SH)


def db_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with db_conn() as conn:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS users (
                tg_id TEXT PRIMARY KEY,
                username TEXT,
                enabled INTEGER DEFAULT 1,
                created_at TEXT,
                updated_at TEXT
            )
        ''')
        conn.execute('''
            CREATE TABLE IF NOT EXISTS accounts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tg_id TEXT NOT NULL,
                account_alias TEXT,
                email TEXT NOT NULL,
                password TEXT NOT NULL,
                proxy_server TEXT,
                sign_time_sh TEXT DEFAULT '08:00',
                enabled INTEGER DEFAULT 1,
                last_sign_date_sh TEXT,
                created_at TEXT,
                updated_at TEXT,
                UNIQUE(tg_id, email)
            )
        ''')


def tg_api(method: str, payload: dict):
    data = parse.urlencode(payload).encode()
    req = request.Request(f'https://api.telegram.org/bot{BOT_TOKEN}/{method}', data=data)
    with request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode('utf-8'))


def send_msg(chat_id: str, text: str):
    return tg_api('sendMessage', {'chat_id': chat_id, 'text': text})


def is_hhmm(s: str):
    if len(s) != 5 or s[2] != ':':
        return False
    h, m = s.split(':')
    return h.isdigit() and m.isdigit() and 0 <= int(h) <= 23 and 0 <= int(m) <= 59


def set_user(tg_id: str, username: str):
    now = datetime.now(timezone.utc).isoformat()
    with db_conn() as conn:
        r = conn.execute('SELECT tg_id FROM users WHERE tg_id=?', (tg_id,)).fetchone()
        if r:
            conn.execute('UPDATE users SET username=?, updated_at=? WHERE tg_id=?', (username, now, tg_id))
        else:
            conn.execute('INSERT INTO users (tg_id, username, enabled, created_at, updated_at) VALUES (?, ?, 1, ?, ?)', (tg_id, username, now, now))


def get_user(tg_id: str):
    with db_conn() as conn:
        return conn.execute('SELECT * FROM users WHERE tg_id=?', (tg_id,)).fetchone()


def upsert_account(tg_id: str, email: str, password: str, proxy_server: str | None, alias: str | None = None):
    now = datetime.now(timezone.utc).isoformat()
    with db_conn() as conn:
        row = conn.execute('SELECT id FROM accounts WHERE tg_id=? AND email=?', (tg_id, email)).fetchone()
        if row:
            conn.execute(
                'UPDATE accounts SET password=?, proxy_server=?, account_alias=COALESCE(?, account_alias), updated_at=? WHERE id=?',
                (password, proxy_server, alias, now, row['id'])
            )
            return row['id']
        cur = conn.execute(
            'INSERT INTO accounts (tg_id, account_alias, email, password, proxy_server, sign_time_sh, enabled, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, 1, ?, ?)',
            (tg_id, alias, email, password, proxy_server, DEFAULT_SIGN_TIME_SH, now, now)
        )
        return cur.lastrowid


def list_accounts(tg_id: str):
    with db_conn() as conn:
        return conn.execute('SELECT * FROM accounts WHERE tg_id=? ORDER BY id', (tg_id,)).fetchall()


def get_account(account_id: int):
    with db_conn() as conn:
        return conn.execute('SELECT * FROM accounts WHERE id=?', (account_id,)).fetchone()


def update_account(account_id: int, field: str, value):
    now = datetime.now(timezone.utc).isoformat()
    with db_conn() as conn:
        conn.execute(f'UPDATE accounts SET {field}=?, updated_at=? WHERE id=?', (value, now, account_id))


def run_sign_for_account(account):
    env = os.environ.copy()
    env['EMAIL'] = account['email']
    env['PASSWORD'] = account['password']
    env['TG_BOT_TOKEN'] = BOT_TOKEN
    env['TG_CHAT_ID'] = account['tg_id']
    env['ACCOUNT_LABEL'] = f"acct#{account['id']}:{account['email']}"
    if account['proxy_server']:
        env['PROXY_SERVER'] = account['proxy_server']
    else:
        env.pop('PROXY_SERVER', None)

    proc = subprocess.run(['python3', 'run_xserver_notify.py'], cwd=WORKDIR, env=env, capture_output=True, text=True, timeout=1200)
    update_account(account['id'], 'last_sign_date_sh', now_sh().date().isoformat())
    return proc.returncode == 0


def help_text():
    return (
        '欢迎使用 XServer 自动签到机器人\n\n'
        '⚠️ 绑定前请先在 XServer 关闭两步验证(2FA)。\n'
        '🕒 本机器人所有设置时间均为【上海时间(UTC+8)】。\n'
        'ℹ️ 日本时间(UTC+9)比上海快1小时。\n\n'
        '【账号命令】\n'
        '/addaccount 邮箱 密码 [socks5代理] [备注]\n'
        '/accounts 查看你所有账号\n'
        '/settime 账号ID HH:MM  (上海时间)\n'
        '/setproxy 账号ID socks5://user:pass@ip:port\n'
        '/clearproxy 账号ID\n'
        '/enable 账号ID on|off\n'
        '/signnow 账号ID\n'
        '/status\n\n'
        '【队列机制】\n同一用户同一时刻只会串行执行一个账号任务；若多个账号同一时间触发会自动排队。'
    )


def enqueue_job(tg_id: str, account_id: int, reason: str):
    with QUEUE_LOCK:
        q = USER_QUEUES.get(tg_id)
        if q is None:
            q = Queue()
            USER_QUEUES[tg_id] = q
        if tg_id not in USER_WORKERS or not USER_WORKERS[tg_id].is_alive():
            t = threading.Thread(target=user_worker, args=(tg_id,), daemon=True)
            USER_WORKERS[tg_id] = t
            t.start()
        q.put((account_id, reason, now_sh().isoformat()))
        pos = q.qsize()
    return pos


def user_worker(tg_id: str):
    while True:
        q = USER_QUEUES[tg_id]
        account_id, reason, created = q.get()
        with QUEUE_LOCK:
            USER_RUNNING.add(tg_id)
        try:
            account = get_account(account_id)
            if not account or account['enabled'] != 1:
                send_msg(tg_id, f'账号#{account_id} 已禁用或不存在，跳过。')
                continue
            send_msg(tg_id, f'开始执行账号#{account_id}({account["email"]}) 签到。触发原因：{reason}\n当前时间(上海): {now_sh().strftime("%Y-%m-%d %H:%M:%S")}')
            ok = run_sign_for_account(account)
            if not ok:
                send_msg(tg_id, f'账号#{account_id} 执行失败，请稍后重试。')
        finally:
            with QUEUE_LOCK:
                USER_RUNNING.discard(tg_id)
            q.task_done()


def handle_command(msg):
    chat_id = str(msg['chat']['id'])
    username = msg.get('from', {}).get('username', '')
    text = (msg.get('text') or '').strip()
    if not text.startswith('/'):
        return
    set_user(chat_id, username)
    parts = text.split()
    cmd = parts[0].lower()

    if cmd == '/start':
        send_msg(chat_id, help_text())
        return

    if cmd == '/addaccount':
        if len(parts) < 3:
            send_msg(chat_id, '用法：/addaccount 邮箱 密码 [socks5代理] [备注]')
            return
        email, password = parts[1], parts[2]
        proxy = parts[3] if len(parts) >= 4 and parts[3].startswith('socks5://') else None
        alias = parts[4] if len(parts) >= 5 else None
        aid = upsert_account(chat_id, email, password, proxy, alias)
        send_msg(chat_id, f'账号已保存，账号ID={aid}。请确保已关闭2FA。')
        return

    if cmd == '/accounts':
        rows = list_accounts(chat_id)
        if not rows:
            send_msg(chat_id, '你还没有添加账号。')
            return
        lines = ['你的账号列表：']
        for r in rows:
            lines.append(f"#{r['id']} {r['email']} | time={r['sign_time_sh']} SH | proxy={'Y' if r['proxy_server'] else 'N'} | enabled={r['enabled']}")
        send_msg(chat_id, '\n'.join(lines[:100]))
        return

    if cmd == '/settime' and len(parts) >= 3:
        aid = int(parts[1])
        hhmm = parts[2]
        if not is_hhmm(hhmm):
            send_msg(chat_id, '时间格式错误，应为 HH:MM（上海时间）。')
            return
        acc = get_account(aid)
        if not acc or acc['tg_id'] != chat_id:
            send_msg(chat_id, '账号ID不存在。')
            return
        update_account(aid, 'sign_time_sh', hhmm)
        send_msg(chat_id, f'账号#{aid} 每日签到时间已设置为 {hhmm}（上海时间 UTC+8，日本时间为 {((int(hhmm[:2])+1)%24):02d}{hhmm[2:]}）。')
        return

    if cmd == '/setproxy' and len(parts) >= 3:
        aid = int(parts[1])
        proxy = parts[2]
        acc = get_account(aid)
        if not acc or acc['tg_id'] != chat_id:
            send_msg(chat_id, '账号ID不存在。')
            return
        update_account(aid, 'proxy_server', proxy)
        send_msg(chat_id, f'账号#{aid} 代理已更新。')
        return

    if cmd == '/clearproxy' and len(parts) >= 2:
        aid = int(parts[1]); acc = get_account(aid)
        if not acc or acc['tg_id'] != chat_id:
            send_msg(chat_id, '账号ID不存在。'); return
        update_account(aid, 'proxy_server', None)
        send_msg(chat_id, f'账号#{aid} 代理已清除。')
        return

    if cmd == '/enable' and len(parts) >= 3:
        aid = int(parts[1]); flag = parts[2].lower()
        acc = get_account(aid)
        if not acc or acc['tg_id'] != chat_id:
            send_msg(chat_id, '账号ID不存在。'); return
        update_account(aid, 'enabled', 1 if flag in ('on', '1', 'true', 'yes') else 0)
        send_msg(chat_id, f'账号#{aid} 启用状态已更新。')
        return

    if cmd == '/signnow' and len(parts) >= 2:
        aid = int(parts[1]); acc = get_account(aid)
        if not acc or acc['tg_id'] != chat_id:
            send_msg(chat_id, '账号ID不存在。'); return
        pos = enqueue_job(chat_id, aid, 'manual')
        send_msg(chat_id, f'账号#{aid} 已加入队列，当前排队位置约: {pos}')
        return

    if cmd == '/status':
        rows = list_accounts(chat_id)
        with QUEUE_LOCK:
            q_size = USER_QUEUES.get(chat_id).qsize() if chat_id in USER_QUEUES else 0
            running = chat_id in USER_RUNNING
        send_msg(chat_id, f'账号数：{len(rows)}\n队列长度：{q_size}\n当前是否执行中：{running}\n当前上海时间：{now_sh().strftime("%Y-%m-%d %H:%M:%S")}')
        return

    if cmd.startswith('/admin_'):
        if chat_id != ADMIN_TG_ID:
            send_msg(chat_id, '你不是管理员。')
            return
        with db_conn() as conn:
            if cmd == '/admin_users':
                rows = conn.execute('SELECT u.tg_id, u.username, COUNT(a.id) AS acct_cnt FROM users u LEFT JOIN accounts a ON a.tg_id=u.tg_id GROUP BY u.tg_id,u.username ORDER BY u.created_at DESC').fetchall()
                lines = ['用户列表：'] + [f"tg:{r['tg_id']} @{r['username'] or '-'} 账号数:{r['acct_cnt']}" for r in rows]
                send_msg(chat_id, '\n'.join(lines[:120]))
                return
            if cmd == '/admin_accounts' and len(parts) >= 2:
                target = parts[1]
                rows = conn.execute('SELECT * FROM accounts WHERE tg_id=? ORDER BY id', (target,)).fetchall()
                lines = [f'tg:{target} 的账号：']
                for r in rows:
                    lines.append(f"#{r['id']} {r['email']} proxy={r['proxy_server'] or 'none'} time={r['sign_time_sh']} enabled={r['enabled']}")
                send_msg(chat_id, '\n'.join(lines[:120]))
                return
            if cmd == '/admin_setproxy' and len(parts) >= 3:
                aid = int(parts[1]); pxy = parts[2]
                update_account(aid, 'proxy_server', None if pxy.lower() == 'none' else pxy)
                send_msg(chat_id, f'已更新账号#{aid}代理。')
                return
            if cmd == '/admin_enable' and len(parts) >= 3:
                aid = int(parts[1]); flg = parts[2].lower()
                update_account(aid, 'enabled', 1 if flg in ('on','1','true','yes') else 0)
                send_msg(chat_id, f'已更新账号#{aid}可用状态。')
                return
        send_msg(chat_id, '管理员命令：/admin_users /admin_accounts TGID /admin_setproxy 账号ID PROXY|none /admin_enable 账号ID on|off')
        return

    send_msg(chat_id, '未知命令，发送 /start 查看教程。')


def run_scheduler():
    now = now_sh()
    hhmm = now.strftime('%H:%M')
    today = now.date().isoformat()
    with db_conn() as conn:
        rows = conn.execute('SELECT * FROM accounts WHERE enabled=1').fetchall()
    for acc in rows:
        if acc['sign_time_sh'] == hhmm and acc['last_sign_date_sh'] != today:
            pos = enqueue_job(acc['tg_id'], acc['id'], f'schedule@{hhmm}(SH)')
            send_msg(acc['tg_id'], f'账号#{acc["id"]} 到达签到时间 {hhmm}(上海)，已入队，排队位置约: {pos}')


def main():
    if not BOT_TOKEN:
        raise SystemExit('TG_BOT_TOKEN missing')
    init_db()
    offset = 0
    while True:
        try:
            res = tg_api('getUpdates', {'timeout': POLL_TIMEOUT, 'offset': offset})
            for item in res.get('result', []):
                offset = item['update_id'] + 1
                if 'message' in item:
                    handle_command(item['message'])
            run_scheduler()
        except Exception:
            time.sleep(3)


if __name__ == '__main__':
    main()
