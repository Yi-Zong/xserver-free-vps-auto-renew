#!/usr/bin/env python3
import os
import re
import sys
import json
import mimetypes
import subprocess
from urllib import request, parse, error
from datetime import datetime
from pathlib import Path
from uuid import uuid4

BOT_TOKEN = os.getenv('TG_BOT_TOKEN', '')
CHAT_ID = os.getenv('TG_CHAT_ID', '')
WORKDIR = '/root/.openclaw/workspace/xserver'
LOG_DIR = '/root/.openclaw/workspace/logs'
WORKSPACE = Path('/root/.openclaw/workspace')
UPLOAD_ENDPOINT = os.getenv('XSERVER_IMAGE_UPLOAD_URL', 'https://111666.best/api/upload')
UPLOAD_REFERER = os.getenv('XSERVER_IMAGE_UPLOAD_REFERER', 'https://111666.best')

IMAGE_CANDIDATES = [
    WORKSPACE / 'final_result.png',
    WORKSPACE / 'SUCCESS_RENEWAL_FINAL.png',
    WORKSPACE / 'SUCCESS_XVFB.png',
    WORKSPACE / 'xserver_final.png',
    WORKSPACE / 'xserver_final_push.png',
    WORKSPACE / 'FAIL_FINAL.png',
    WORKSPACE / 'STILL_STUCK.png',
    WORKSPACE / 'no_renew_redirect.png',
    WORKSPACE / 'xserver' / 'skip_renewal.png',
    WORKSPACE / 'xserver' / 'before_click.png',
]


def http_post(url: str, data: bytes = None, headers: dict | None = None, timeout: int = 30):
    req = request.Request(url, data=data, headers=headers or {})
    with request.urlopen(req, timeout=timeout) as resp:
        body = resp.read()
        return body.decode('utf-8', errors='replace'), resp.headers


def tg_send(text: str):
    data = parse.urlencode({'chat_id': CHAT_ID, 'text': text}).encode()
    return http_post(f'https://api.telegram.org/bot{BOT_TOKEN}/sendMessage', data=data)[0]


def tg_send_photo(photo_path: str, caption: str):
    boundary = f'----OpenClawTG{uuid4().hex}'
    p = Path(photo_path)
    mime = mimetypes.guess_type(p.name)[0] or 'application/octet-stream'
    photo_bytes = p.read_bytes()

    parts = []

    def add_field(name: str, value: str):
        parts.append(f'--{boundary}\r\n'.encode())
        parts.append(f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode())
        parts.append(value.encode('utf-8'))
        parts.append(b'\r\n')

    add_field('chat_id', CHAT_ID)
    add_field('caption', caption)

    parts.append(f'--{boundary}\r\n'.encode())
    parts.append(
        f'Content-Disposition: form-data; name="photo"; filename="{p.name}"\r\n'.encode()
    )
    parts.append(f'Content-Type: {mime}\r\n\r\n'.encode())
    parts.append(photo_bytes)
    parts.append(b'\r\n')
    parts.append(f'--{boundary}--\r\n'.encode())

    body = b''.join(parts)
    headers = {'Content-Type': f'multipart/form-data; boundary={boundary}'}
    return http_post(f'https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto', data=body, headers=headers, timeout=60)[0]


def upload_image_to_111666best(photo_path: str):
    p = Path(photo_path)
    boundary = f'----OpenClawUpload{uuid4().hex}'
    mime = mimetypes.guess_type(p.name)[0] or 'application/octet-stream'
    photo_bytes = p.read_bytes()

    parts = []

    def add_field(name: str, value: str):
        parts.append(f'--{boundary}\r\n'.encode())
        parts.append(f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode())
        parts.append(value.encode('utf-8'))
        parts.append(b'\r\n')

    # Lsky Pro / similar image beds usually accept one of these field names; `file` is the most common.
    add_field('strategy_id', os.getenv('XSERVER_IMAGE_STRATEGY_ID', ''))

    parts.append(f'--{boundary}\r\n'.encode())
    parts.append(
        f'Content-Disposition: form-data; name="file"; filename="{p.name}"\r\n'.encode()
    )
    parts.append(f'Content-Type: {mime}\r\n\r\n'.encode())
    parts.append(photo_bytes)
    parts.append(b'\r\n')
    parts.append(f'--{boundary}--\r\n'.encode())
    body = b''.join(parts)

    headers = {
        'Content-Type': f'multipart/form-data; boundary={boundary}',
        'Accept': 'application/json, text/plain, */*',
        'Referer': UPLOAD_REFERER,
        'Origin': UPLOAD_REFERER,
        'User-Agent': 'Mozilla/5.0 OpenClaw XServer notifier',
    }

    raw, _ = http_post(UPLOAD_ENDPOINT, data=body, headers=headers, timeout=90)

    try:
        payload = json.loads(raw)
    except Exception as e:
        raise RuntimeError(f'图床返回非 JSON: {raw[:300]}') from e

    candidates = [
        payload.get('data', {}).get('url') if isinstance(payload.get('data'), dict) else None,
        payload.get('data', {}).get('links', {}).get('url') if isinstance(payload.get('data'), dict) and isinstance(payload.get('data', {}).get('links'), dict) else None,
        payload.get('data', {}).get('links', {}).get('html') if isinstance(payload.get('data'), dict) and isinstance(payload.get('data', {}).get('links'), dict) else None,
        payload.get('url'),
    ]
    image_url = next((x for x in candidates if isinstance(x, str) and x.strip()), None)
    if not image_url:
        raise RuntimeError(f'图床返回里没找到图片链接: {raw[:500]}')
    return image_url, payload


def infer_expiry(text: str):
    patterns = [
        r'利用期限[^\n]*?(\d{4}[/-]\d{1,2}[/-]\d{1,2})',
        r'有効期限[^\n]*?(\d{4}[/-]\d{1,2}[/-]\d{1,2})',
        r'期限[^\n]*?(\d{4}[/-]\d{1,2}[/-]\d{1,2})',
    ]
    for p in patterns:
        m = re.search(p, text)
        if m:
            return m.group(1)
    return '未知'


def pick_screenshot(start_ts: float | None = None):
    candidates = []
    for path in IMAGE_CANDIDATES:
        if path.exists() and path.is_file():
            try:
                stat = path.stat()
                if start_ts is None or stat.st_mtime >= start_ts - 5:
                    candidates.append((stat.st_mtime, str(path)))
            except FileNotFoundError:
                pass

    if not candidates:
        for ext in ('*.png', '*.jpg', '*.jpeg', '*.webp'):
            for path in WORKSPACE.glob(ext):
                try:
                    stat = path.stat()
                    if start_ts is None or stat.st_mtime >= start_ts - 5:
                        candidates.append((stat.st_mtime, str(path)))
                except FileNotFoundError:
                    pass

    if not candidates:
        return None
    candidates.sort(reverse=True)
    return candidates[0][1]


def build_message(label: str, run_ok: bool, need_sign: bool, sign_status: str, expiry: str, screenshot_path: str | None = None, image_url: str | None = None):
    title = '🖥 XServer 续期结果'
    status_line = '✅ 运行成功' if run_ok else '❌ 运行失败'
    need_line = '🟡 今天需要续期' if need_sign else '⚪️ 今天无需续期'

    lines = [
        title,
        f'账号：{label}',
        status_line,
        need_line,
    ]

    if screenshot_path:
        lines.append(f'🖼 截图：{Path(screenshot_path).name}')
    if image_url:
        lines.append(f'🔗 图片链接：{image_url}')

    return '\n'.join(lines)


def run_xserver_once(cmd, run_env, start_ts: float, attempt: int):
    proc = subprocess.run(cmd, cwd=WORKDIR, capture_output=True, text=True, timeout=900, env=run_env)
    out = (proc.stdout or '') + ('\n' + proc.stderr if proc.stderr else '')
    run_ok = proc.returncode == 0
    need_sign = 'SKIP: Renewal is not yet available' not in out
    if 'SKIP: Renewal is not yet available' in out:
        sign_status = '今天无需签到'
    elif 'Final renewal submitted successfully!' in out:
        sign_status = '今天已执行续期'
    elif run_ok:
        sign_status = '运行成功，但未识别到最终续期结果'
    else:
        sign_status = '运行失败'
    return {
        'attempt': attempt,
        'proc': proc,
        'out': out,
        'run_ok': run_ok,
        'need_sign': need_sign,
        'sign_status': sign_status,
        'expiry': infer_expiry(out),
        'screenshot_path': pick_screenshot(start_ts),
    }


def main():
    email = os.getenv('EMAIL', '').strip()
    password = os.getenv('PASSWORD', '').strip()
    label = os.getenv('ACCOUNT_LABEL', email or 'unknown')
    if not email or not password:
        raise SystemExit('EMAIL/PASSWORD missing')

    start_ts = datetime.now().timestamp()
    log_path = os.path.join(LOG_DIR, f"xserver_{re.sub(r'[^a-zA-Z0-9_.-]+', '_', label)}.log")
    run_env = os.environ.copy()
    run_env['EMAIL'] = email
    run_env['PASSWORD'] = password
    cmd = [
        'xvfb-run', '-a', 'bash', '-lc',
        '. .venv/bin/activate; python main.py'
    ]

    os.makedirs(LOG_DIR, exist_ok=True)
    attempts = []
    result_once = run_xserver_once(cmd, run_env, start_ts, 1)
    attempts.append(result_once)

    # If the browser/page run fails once (common with slow XServer pages), retry once automatically.
    if not result_once['run_ok']:
        import time
        time.sleep(8)
        retry_start_ts = datetime.now().timestamp()
        result_once = run_xserver_once(cmd, run_env, retry_start_ts, 2)
        attempts.append(result_once)

    with open(log_path, 'a', encoding='utf-8') as f:
        f.write(f"\n[{datetime.now().isoformat(sep=' ', timespec='seconds')}]\n")
        for attempt_result in attempts:
            f.write(f"--- attempt {attempt_result['attempt']} ---\n")
            f.write(attempt_result['out'])
            if not attempt_result['out'].endswith('\n'):
                f.write('\n')

    run_ok = result_once['run_ok']
    need_sign = result_once['need_sign']
    sign_status = result_once['sign_status']
    expiry = result_once['expiry']
    screenshot_path = result_once['screenshot_path']
    retry_attempted = len(attempts) > 1
    image_url = None

    msg = build_message(label, run_ok, need_sign, sign_status, expiry, screenshot_path=screenshot_path)
    if retry_attempted:
        msg += '\n🔁 首次失败，已自动重试一次'

    sent_via = 'text'
    send_errors = []

    if screenshot_path:
        try:
            tg_send_photo(screenshot_path, msg)
            sent_via = 'telegram-photo'
        except Exception as e:
            send_errors.append(f'TG发图失败: {e}')
            try:
                image_url, _payload = upload_image_to_111666best(screenshot_path)
                fallback_msg = build_message(label, run_ok, need_sign, sign_status, expiry, screenshot_path=screenshot_path, image_url=image_url)
                tg_send(fallback_msg)
                sent_via = 'imagebed-link'
            except Exception as upload_err:
                send_errors.append(f'图床上传失败: {upload_err}')
                tg_send(msg + "\n⚠️ 截图推送失败，仅发送文字。")
                sent_via = 'text-after-failure'
    else:
        tg_send(msg)

    result = {
        'label': label,
        'run_ok': run_ok,
        'need_sign': need_sign,
        'sign_status': sign_status,
        'expiry': expiry,
        'screenshot_path': screenshot_path,
        'image_url': image_url,
        'sent_via': sent_via,
        'retry_attempted': retry_attempted,
        'attempts': len(attempts),
        'errors': send_errors,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
