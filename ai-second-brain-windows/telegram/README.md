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

## Always-on (Task Scheduler, hidden, runs at logon)

So your brain is reachable 24/7 without a terminal window sitting open:

1. Save a tiny launcher next to the bot as `run-bot.vbs` (runs Python with no
   visible window):
   ```vbscript
   CreateObject("WScript.Shell").Run "python """ & _
     CreateObject("Scripting.FileSystemObject").GetParentFolderName(WScript.ScriptFullName) & _
     "\telegram_brain_bot.py""", 0, False
   ```
2. **Task Scheduler** → *Create Task* (not Basic):
   - **General:** *Run only when user is logged on*; tick *Hidden*.
   - **Triggers:** New → *At log on* (your user).
   - **Actions:** New → *Start a program* → `wscript.exe`, argument the full path
     to `run-bot.vbs`.
   - **Settings:** untick *Stop the task if it runs longer than…* (it's meant to
     run forever); tick *If the task fails, restart every 1 minute*.
3. Log off/on (or *Run* the task once) to start it.

To stop: end the task in Task Scheduler, or kill the `python.exe`/`wscript.exe`
process.

## Security notes
- The bot ignores every Telegram user except `TELEGRAM_ALLOWED_USER_ID`.
- It shells out to `claude -p` with `shell=False` (no shell injection surface).
- Anyone with your bot token could message the bot, but only your id gets a
  reply — still, treat the token like a password.
