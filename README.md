# XServer Free VPS Auto Renew

Automates XServer free VPS renewal/sign-in flow with Python + Playwright/Camoufox.

> Use only for your own XServer account. Do not commit credentials, cookies, screenshots, or logs.

## Files

- `main.py` - core browser automation
- `run_xserver_notify.py` - wrapper with optional Telegram notification and retry
- `Dockerfile`, `entrypoint.sh`, `run-docker.sh` - container usage
- `.github/workflows/main.yml` - optional GitHub Actions schedule example
- `.env.example` - example environment variables

## Local usage

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
playwright install chromium
cp .env.example .env
# edit .env
python main.py
```

## With notification wrapper

```bash
EMAIL='your-email@example.com' \
PASSWORD='your-password' \
TG_BOT_TOKEN='123:abc' \
TG_CHAT_ID='123456' \
python3 run_xserver_notify.py
```

`TG_BOT_TOKEN` and `TG_CHAT_ID` are optional environment variables.

## Cron example

```cron
0 8 * * * cd /path/to/xserver-renew && EMAIL='...' PASSWORD='...' python3 run_xserver_notify.py >> logs/xserver.log 2>&1
```

## Security

Never commit:

- `.env`
- real emails/passwords
- Telegram bot tokens/chat IDs
- screenshots/logs containing account details
- virtual environments or browser caches

## Telegram 多用户机器人

新增 `tg_bot.py`：支持陌生人自助绑定多个 XServer 账号；每个账号可单独配置 socks5 代理与每日签到时间（上海时间）。

### 时区说明

- 机器人设置与调度：**上海时间 UTC+8**
- 日本时间：**UTC+9（比上海快 1 小时）**
- 推送给用户的签到进度提示采用上海时间

### 环境变量

- `TG_BOT_TOKEN`：机器人 token（必填）
- `ADMIN_TG_ID`：管理员 TG ID
- `XSERVER_WORKDIR`：项目目录（默认当前目录）
- `BOT_DB_PATH`：SQLite 数据库（默认 `./bot_users.db`）
- `DEFAULT_SIGN_TIME_SH`：默认签到时间（上海时区）

### 启动

```bash
python3 tg_bot.py
```

### 用户命令

- `/start` 查看教程（含 2FA 关闭提醒）
- `/addaccount 邮箱 密码 [socks5://user:pass@ip:port] [备注]`
- `/accounts` 查看全部账号
- `/settime 账号ID HH:MM`（上海时间）
- `/setproxy 账号ID socks5://...`
- `/clearproxy 账号ID`
- `/enable 账号ID on|off`
- `/signnow 账号ID`
- `/status`

### 管理员命令

- `/admin_users` 查看机器人用户
- `/admin_accounts TGID` 查看该用户所有账号与代理
- `/admin_setproxy 账号ID PROXY|none` 配置目标账号代理
- `/admin_enable 账号ID on|off` 配置目标账号是否可签到

### 队列机制

同一用户下多个账号若同一时间触发签到，会自动进入串行队列：**每次只跑一个账号**，其他任务排队等待，避免并发导致错误。
