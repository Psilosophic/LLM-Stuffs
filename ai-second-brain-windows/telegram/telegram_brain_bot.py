#!/usr/bin/env python3
"""
telegram_brain_bot.py
=====================

Text your second brain. A dependency-free Telegram relay (Windows-friendly,
stdlib only — no `pip install`, safe even on bleeding-edge Python) that:

  * long-polls Telegram for new messages,
  * accepts messages ONLY from your own Telegram user id,
  * runs `claude -p "<message>"` inside your Brain vault so the answer is
    grounded in CLAUDE.md and the wiki,
  * replies in the same chat.

This is the Windows replacement for the Mac skill's iMessage Channels.

Required environment variables:
  TELEGRAM_BOT_TOKEN        token from @BotFather
  TELEGRAM_ALLOWED_USER_ID  your numeric Telegram user id (from @userinfobot)
Optional:
  BRAIN_DIR                 path to the Brain vault (default: <Desktop>\\Brain)
  CLAUDE_CMD                claude executable name/path (default: "claude")

See README.md for setup and the Task Scheduler "always-on" recipe.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

API = "https://api.telegram.org/bot{token}/{method}"
POLL_TIMEOUT = 50          # seconds for Telegram long-poll
CLAUDE_TIMEOUT = 600       # seconds before we give up on a claude run
TG_LIMIT = 4096            # Telegram max message length


def env(name: str, default: str | None = None, required: bool = False) -> str | None:
    val = os.environ.get(name, default)
    if required and not val:
        sys.exit(
            f"Missing {name}. Set it before launching, e.g.\n"
            f'  setx {name} "your-value-here"\n'
            "(open a new terminal after setx), then re-run."
        )
    return val


def default_brain_dir() -> str:
    # Resolve the real Desktop (handles OneDrive redirection on Windows).
    home = os.path.expanduser("~")
    for candidate in (
        os.path.join(home, "OneDrive", "Desktop", "Brain"),
        os.path.join(home, "Desktop", "Brain"),
    ):
        if os.path.isdir(candidate):
            return candidate
    return os.path.join(home, "Desktop", "Brain")


def tg_call(token: str, method: str, **params) -> dict:
    url = API.format(token=token, method=method)
    data = urllib.parse.urlencode(params).encode()
    req = urllib.request.Request(url, data=data)
    try:
        with urllib.request.urlopen(req, timeout=POLL_TIMEOUT + 10) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.URLError as exc:
        print(f"[warn] telegram {method} failed: {exc}", file=sys.stderr)
        return {"ok": False}


def send(token: str, chat_id: int, text: str) -> None:
    # Telegram caps message length; chunk long answers.
    for i in range(0, len(text) or 1, TG_LIMIT):
        tg_call(token, "sendMessage", chat_id=chat_id, text=text[i : i + TG_LIMIT] or " ")


def ask_claude(brain_dir: str, claude_cmd: str, prompt: str) -> str:
    try:
        result = subprocess.run(
            [claude_cmd, "-p", prompt],
            cwd=brain_dir,
            capture_output=True,
            text=True,
            timeout=CLAUDE_TIMEOUT,
            shell=False,
        )
    except FileNotFoundError:
        return f"Couldn't find '{claude_cmd}'. Is Claude Code installed and on PATH?"
    except subprocess.TimeoutExpired:
        return "Timed out thinking about that one. Try a narrower question."
    out = (result.stdout or "").strip()
    if not out:
        out = (result.stderr or "").strip() or "(no output)"
    return out


def main() -> None:
    token = env("TELEGRAM_BOT_TOKEN", required=True)
    allowed = int(env("TELEGRAM_ALLOWED_USER_ID", required=True))
    brain_dir = env("BRAIN_DIR") or default_brain_dir()
    claude_cmd = env("CLAUDE_CMD", "claude")

    if not os.path.isdir(brain_dir):
        sys.exit(f"Brain folder not found: {brain_dir}\nRun scaffold.ps1 or set BRAIN_DIR.")

    print(f"Brain bot up. Vault: {brain_dir}. Locked to user id {allowed}.")
    offset = 0
    while True:
        resp = tg_call(token, "getUpdates", offset=offset, timeout=POLL_TIMEOUT)
        if not resp.get("ok"):
            time.sleep(3)
            continue
        for update in resp.get("result", []):
            offset = update["update_id"] + 1
            msg = update.get("message") or update.get("edited_message")
            if not msg:
                continue
            user_id = msg.get("from", {}).get("id")
            chat_id = msg["chat"]["id"]
            text = (msg.get("text") or "").strip()
            if user_id != allowed:
                # Silently ignore anyone who isn't you.
                print(f"[ignore] message from unauthorized id {user_id}")
                continue
            if not text:
                send(token, chat_id, "Send me text and I'll ask your brain.")
                continue
            print(f"[ask] {text[:80]}")
            send(token, chat_id, "Thinking…")
            answer = ask_claude(brain_dir, claude_cmd, text)
            send(token, chat_id, answer)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nbye")
