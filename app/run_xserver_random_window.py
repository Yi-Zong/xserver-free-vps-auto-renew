#!/usr/bin/env python3
"""Run all XServer accounts once inside a random time window.

Usage:
  run_xserver_random_window.py afternoon # 14:00-16:00 Asia/Shanghai

Cron should fire at the window start (14:00 / 20:00). This process stays alive
until every account has been signed inside the window.
"""
from __future__ import annotations

import json
import os
import random
import subprocess
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

TZ = ZoneInfo("Asia/Shanghai")
WORKSPACE = Path("/opt/xserver/app")
XSERVER_DIR = WORKSPACE
ACCOUNTS_FILE = WORKSPACE / "xserver_accounts.json"
NOTIFY_SCRIPT = WORKSPACE / "run_xserver_notify.py"
LOG_DIR = WORKSPACE / "logs"
SCHED_LOG = LOG_DIR / "xserver_random_window.log"

WINDOWS = {
    "afternoon": (14, 0, 16, 0), # 14:00 inclusive -> 16:00 exclusive
    "evening": (20, 0, 22, 0),   # 20:00 inclusive -> 22:00 exclusive
    "morning": (14, 0, 16, 0),   # alias kept for compatibility -> afternoon
}

TG_BOT_TOKEN = os.getenv(
    "TG_BOT_TOKEN",
    "",
)
TG_CHAT_ID = os.getenv("TG_CHAT_ID", "")
def log(msg: str) -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    line = f"[{datetime.now(TZ).strftime('%F %T %z')}] {msg}"
    print(line, flush=True)
    with SCHED_LOG.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def load_accounts() -> list[dict]:
    data = json.loads(ACCOUNTS_FILE.read_text(encoding="utf-8"))
    if not isinstance(data, list) or not data:
        raise SystemExit(f"no accounts in {ACCOUNTS_FILE}")
    return data


def window_bounds(name: str) -> tuple[datetime, datetime]:
    if name not in WINDOWS:
        raise SystemExit(f"unknown window {name!r}; use: {', '.join(WINDOWS)}")
    sh, sm, eh, em = WINDOWS[name]
    now = datetime.now(TZ)
    start = now.replace(hour=sh, minute=sm, second=0, microsecond=0)
    end = now.replace(hour=eh, minute=em, second=0, microsecond=0)
    # If launched a bit early, still use today's named window.
    # If launched after end, refuse rather than silently rolling to next day.
    if now >= end:
        raise SystemExit(
            f"window {name} already ended for today "
            f"({start.strftime('%H:%M')}-{end.strftime('%H:%M')} SH); now={now.isoformat()}"
        )
    if now > start:
        # Late start: randomize only in remaining portion of the window.
        start = now
    return start, end


def pick_run_times(accounts: list[dict], start: datetime, end: datetime) -> list[tuple[datetime, dict]]:
    total_sec = max(1, int((end - start).total_seconds()))
    # Leave a few seconds of headroom so the last job still starts before end.
    usable = max(1, total_sec - 5)
    chosen: list[tuple[datetime, dict]] = []
    used_offsets: set[int] = set()
    for acc in accounts:
        # Prefer unique minute-ish offsets so 3 accounts don't collide hard.
        for _ in range(50):
            off = random.randint(0, usable - 1)
            if off not in used_offsets:
                used_offsets.add(off)
                break
        chosen.append((start + timedelta(seconds=off), acc))
    chosen.sort(key=lambda x: x[0])
    return chosen


def run_one(acc: dict, window: str, planned: datetime) -> int:
    email = acc["email"]
    label = acc.get("label") or email
    log_name = acc.get("log") or f"xserver_{email.replace('@', '_at_').replace('.', '_')}.log"
    account_log = LOG_DIR / log_name
    env = os.environ.copy()
    env.update(
        {
            "TG_BOT_TOKEN": TG_BOT_TOKEN,
            "TG_CHAT_ID": TG_CHAT_ID,
            "EMAIL": email,
            "PASSWORD": acc["password"],
            "ACCOUNT_LABEL": label,
        }
    )
    log(
        f"START window={window} email={email} planned={planned.strftime('%H:%M:%S')} "
        f"actual={datetime.now(TZ).strftime('%H:%M:%S')}"
    )
    with account_log.open("a", encoding="utf-8") as lf:
        lf.write(
            f"\n===== random-window {window} planned={planned.isoformat()} "
            f"started={datetime.now(TZ).isoformat()} =====\n"
        )
        lf.flush()
        proc = subprocess.run(
            [sys.executable, str(NOTIFY_SCRIPT)],
            cwd=str(XSERVER_DIR),
            env=env,
            stdout=lf,
            stderr=subprocess.STDOUT,
            check=False,
        )
    log(f"DONE window={window} email={email} exit={proc.returncode}")
    return proc.returncode


def main() -> int:
    if len(sys.argv) != 2:
        print(f"usage: {sys.argv[0]} morning|afternoon", file=sys.stderr)
        return 2
    window = sys.argv[1].strip().lower()
    accounts = load_accounts()
    start, end = window_bounds(window)
    plan = pick_run_times(accounts, start, end)
    log(
        f"SCHEDULE window={window} accounts={len(plan)} "
        f"range={start.strftime('%H:%M:%S')}-{end.strftime('%H:%M:%S')} SH"
    )
    for when, acc in plan:
        log(f"  plan {acc['email']} @ {when.strftime('%H:%M:%S')}")

    rc_any = 0
    for when, acc in plan:
        now = datetime.now(TZ)
        wait = (when - now).total_seconds()
        if wait > 0:
            log(f"SLEEP {wait:.0f}s until {when.strftime('%H:%M:%S')} for {acc['email']}")
            time.sleep(wait)
        code = run_one(acc, window, when)
        if code != 0:
            rc_any = code
    log(f"WINDOW_DONE window={window} worst_exit={rc_any}")
    return rc_any


if __name__ == "__main__":
    raise SystemExit(main())
