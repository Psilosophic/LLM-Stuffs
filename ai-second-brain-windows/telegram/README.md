# Text your brain — Telegram bot (Windows)

The Windows replacement for the Mac skill's iMessage channel. Pure Python
stdlib, so there's nothing to `pip install` (safe on bleeding-edge Python 3.x).
It only ever answers **you**, and it runs Claude Code against your Brain vault so
replies are grounded in your wiki.

## One-time setup (~3 minutes)

1. **Create the bot.** In Telegram, message **@BotFather** → `/newbot` → pick a
   name and username. Copy the **token** it gives you.
2. **Get your user id.** Message **@userinfobot**; it replies with your numeric
   **Id**.
3. **Store both** (persist them for your user account):
   ```powershell
   setx TELEGRAM_BOT_TOKEN "123456:ABC-yourtoken"
   setx TELEGRAM_ALLOWED_USER_ID "111222333"
   ```
   Open a **new** terminal afterward so the values load. (Optionally
   `setx BRAIN_DIR "C:\path\to\Brain"` if your vault isn't on the Desktop.)
4. **Run it:**
   ```powershell
   python .\telegram_brain_bot.py
   ```
   Message your bot in Telegram. It replies "Thinking…", then the answer.

If a required variable is missing, the bot prints a friendly one-line fix and
exits cleanly — it does not crash.

## Always-on (hidden, starts at logon)

`pythonw.exe` runs the bot with **no console window**, so a single scheduled task
launched at logon keeps your brain reachable 24/7. One line in PowerShell:

```powershell
schtasks /Create /TN "Telegram Brain Bot" /TR "`"$((Get-Command pythonw).Source)`" `"$env:USERPROFILE\.claude\skills\ai-second-brain-windows\telegram\telegram_brain_bot.py`"" /SC ONLOGON /F
```

(Adjust the script path if you didn't install the skill to the default location.)

Start it now without logging out:
```powershell
schtasks /Run /TN "Telegram Brain Bot"
```

For auto-restart if it ever crashes, open the task in Task Scheduler →
**Settings** → tick *If the task fails, restart every 1 minute*.

To stop it for good:
```powershell
schtasks /Delete /TN "Telegram Brain Bot" /F
```
(then end any lingering `pythonw.exe` in Task Manager).

## Security notes
- The bot ignores every Telegram user except `TELEGRAM_ALLOWED_USER_ID`.
- It shells out to `claude -p` with `shell=False` (no shell injection surface).
- Anyone with your bot token could message the bot, but only your id gets a
  reply — still, treat the token like a password.
