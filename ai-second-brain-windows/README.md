# AI Second Brain — Windows

A Windows-native rebuild of [charlie947/ai-second-brain](https://github.com/charlie947/ai-second-brain):
a local, AI-powered "second brain" you build with Claude Code and Obsidian.

The methodology is untouched — three stages, the Karpathy `raw/` → `wiki/`
living-wiki pattern, the `/today` `/ideas` `/create` commands. Only the
Mac-specific plumbing is replaced:

| Mac version | This Windows port |
| --- | --- |
| iMessage Channels | **Telegram bot** (stdlib, locked to your user id) |
| `bash` setup scripts | **PowerShell** (`scaffold.ps1`) |
| `~/Desktop` hard-coded | `[Environment]::GetFolderPath('Desktop')` (**OneDrive-safe**) |
| Full Disk Access / Messages automation | not needed |

## What's in here
```
ai-second-brain-windows\
├── SKILL.md                     # the Claude Code skill (the full workflow)
├── scaffold.ps1                 # one-command vault scaffolder (OneDrive-safe)
├── brain-template\
│   ├── CLAUDE.md                # Karpathy wiki schema — the brain of the vault
│   ├── log.md                   # seed processing log
│   └── wiki\index.md            # seed canonical index
├── commands\
│   ├── today.md  ideas.md  create.md   # slash commands
└── telegram\
    ├── telegram_brain_bot.py    # text-your-brain relay (pure stdlib)
    └── README.md                # Telegram + Task Scheduler always-on setup
```

## Quick start
1. **Scaffold the vault:**
   ```powershell
   powershell -ExecutionPolicy Bypass -File .\scaffold.ps1
   ```
2. **Start your exports** (ChatGPT + Claude → Export Data; they take 1–3 days).
3. **Open** `<Desktop>\Brain` in Obsidian (*Open folder as vault*).
4. **Compile:** `cd "<Desktop>\Brain"; claude` → *"Compile the sources in raw\ per CLAUDE.md."*
5. **Phone access:** follow `telegram\README.md` (~3 min).

## Install as a Claude Code skill
Copy the whole `ai-second-brain-windows\` folder into your skills directory:
```powershell
Copy-Item -Recurse -Force .\ai-second-brain-windows "$env:USERPROFILE\.claude\skills\ai-second-brain-windows"
```
Then in any Claude Code session: invoke the **ai-second-brain-windows** skill.

## Prerequisites
- [Claude Code](https://claude.com/claude-code) on PATH
- [Obsidian](https://obsidian.md) (free)
- Python 3.10+ (only for the Telegram bot; stdlib only — no pip installs)
- For Stage 3 commands: Gmail / Google Calendar / Granola / NotebookLM connectors
  in Claude Code

## Privacy
Everything stays local except Claude Code's normal Anthropic API calls. The bot
answers only your Telegram id. Your vault contains real people's words — keep it
local or in a **private** repo, and mind local recording-consent laws.

---
*Ported from charlie947/ai-second-brain (MIT). Methodology credits in that repo:
Andrej Karpathy, Alex Freedman, Greg Isenberg.*
