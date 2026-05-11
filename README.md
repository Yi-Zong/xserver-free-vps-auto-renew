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
