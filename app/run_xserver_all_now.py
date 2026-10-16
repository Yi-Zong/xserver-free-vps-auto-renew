#!/usr/bin/env python3
"""Run every configured XServer account immediately, sequentially."""
from __future__ import annotations
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

WORKSPACE = Path('/opt/xserver/app')
ACCOUNTS = WORKSPACE / 'xserver_accounts.json'
NOTIFY = WORKSPACE / 'run_xserver_notify.py'
LOG_DIR = Path('/opt/xserver/logs')


def main() -> int:
    accounts = json.loads(ACCOUNTS.read_text(encoding='utf-8'))
    if not accounts:
        print('no accounts configured', flush=True)
        return 2
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    result = 0
    print(f'[{datetime.now().isoformat()}] RECOVERY_START accounts={len(accounts)}', flush=True)
    for account in accounts:
        email = account['email']
        env = os.environ.copy()
        env.update({
            'EMAIL': email,
            'PASSWORD': account['password'],
            'ACCOUNT_LABEL': account.get('label') or email,
        })
        print(f'[{datetime.now().isoformat()}] START email={email}', flush=True)
        proc = subprocess.run([sys.executable, str(NOTIFY)], cwd=WORKSPACE, env=env, check=False)
        print(f'[{datetime.now().isoformat()}] DONE email={email} exit={proc.returncode}', flush=True)
        if proc.returncode != 0:
            result = proc.returncode
    print(f'[{datetime.now().isoformat()}] RECOVERY_DONE worst_exit={result}', flush=True)
    return result


if __name__ == '__main__':
    raise SystemExit(main())
