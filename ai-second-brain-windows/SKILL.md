---
name: ai-second-brain-windows
description: >-
  Build a local, AI-powered "second brain" on Windows: shred your ChatGPT/Claude
  exports into a tagged, wikilinked Obsidian vault, stand up a Karpathy-style
  raw/ -> wiki/ living knowledge base driven by Claude Code, and give it a phone
  channel via a Telegram bot. A Windows-native port of charlie947/ai-second-brain
  (iMessage -> Telegram, bash -> PowerShell, with the OneDrive-Desktop trap handled).
  Use when the user wants to set up a personal knowledge base / second brain on Windows.
---

# AI Second Brain (Windows)

A Windows-native rebuild of the "AI Second Brain" workflow. The soul is
OS-agnostic — Obsidian + Claude Code + a folder of markdown — so this keeps the
methodology intact and swaps only the Mac-specific plumbing.

> Obsidian is the IDE. The LLM is the programmer. The wiki is the codebase.

There are three stages. Do them in order, but Stage 1's export can bake in the
background while you do Stages 2–3.

---

## Stage 0 — Scaffold the vault (one command)

The Brain folder must be a **single word** (path-handling), and on Windows the
Desktop is frequently redirected into OneDrive — so never hard-code `~\Desktop`.
Run the bundled scaffolder, which resolves the real Desktop and lays down the
`raw\`, `wiki\`, and `CLAUDE.md` skeleton:

```powershell
powershell -ExecutionPolicy Bypass -File .\scaffold.ps1
```

This creates `<Desktop>\Brain\` with `raw\`, `wiki\`, a seeded `wiki\index.md`,
a `log.md`, and the Karpathy `CLAUDE.md`. Then open that folder in Obsidian
(*Open folder as vault*).

---

## Stage 1 — AI Brain (your conversation history)

Goal: turn every conversation you've had with ChatGPT and Claude into a
searchable, tagged, wikilinked Obsidian graph.

1. **Start the exports now** (they take 1–3 days to arrive by email):
   - ChatGPT: Settings → Data Controls → Export Data.
   - Claude: Settings → Privacy → Export Data.
2. When the `.zip` files arrive, unzip them into `<Desktop>\Brain\raw\`.
3. `cd` into the Brain folder and launch Claude Code:
   ```powershell
   cd "$([Environment]::GetFolderPath('Desktop'))\Brain"; claude
   ```
4. Tell Claude Code: **"Process every conversation export in raw\ using CLAUDE.md.
   Fan out sub-agents to shred them into tagged, wikilinked notes in wiki\."**
   It will spawn parallel sub-agents, one per batch, extracting topics, projects,
   and people into atomic notes and updating `wiki\index.md`.

---

## Stage 2 — Karpathy Wiki (the living knowledge base)

Goal: a `raw/` → `wiki/` pipeline where you drop any source and Claude Code
compiles it into the structured wiki.

- Drop sources (PDFs, articles, saved pages, meeting notes) into `raw\`.
- In a Claude Code session inside the Brain folder: **"Compile the new sources in
  raw\ into wiki\ following CLAUDE.md."**
- The rules live in `CLAUDE.md` (shipped in `brain-template\`): atomic notes,
  `[[wikilinks]]`, frontmatter tags, one canonical `index.md`, append to `log.md`.

See `brain-template/CLAUDE.md` for the full schema.

---

## Stage 3 — Living Wiki (connectors + commands + phone)

### MCP connectors (port intact from the Mac version)
Connect these in Claude Code so the slash commands have data to work with:
- **Gmail** — urgent threads + email patterns (`/today`, `/ideas`).
- **Google Calendar** — today's schedule (`/today`).
- **Granola** — meeting transcripts, decisions, action items (`/ideas`).
- **NotebookLM** — paste a notebook URL; it dumps every source into `raw\`.
  Requires a one-time browser login; do it in a separate PowerShell window, not
  inside a Claude Code session.

### Slash commands
Copy `commands\today.md`, `commands\ideas.md`, `commands\create.md` into
`%USERPROFILE%\.claude\commands\` (the scaffolder offers to do this). They give
you `/today`, `/ideas`, `/create` — same behavior as the Mac skill.

### Phone channel — Telegram bot (the iMessage replacement)
iMessage Channels are Apple-only, so this ships a pure-stdlib Telegram relay
(no `pip install` — safe on bleeding-edge Python). It locks to **your** Telegram
user ID, shells out to `claude` against the Brain vault, and replies in-thread.
Full setup + a Task Scheduler "always-on" recipe in `telegram\README.md`.

---

## Windows gotchas this skill handles for you
- **OneDrive Desktop trap:** uses `[Environment]::GetFolderPath('Desktop')`, never `~\Desktop`.
- **Single-word folder name:** `Brain`, not `My Brain`.
- **No pip dependency:** the bot is stdlib-only.
- **Single copyable command lines:** every command is one line, no fragments.

## Privacy
All data stays local except Claude Code's normal calls to Anthropic. The Telegram
bot is locked to your own user ID. Conversation/wiki content includes real people —
keep the vault local or in a private repo, and mind local recording-consent laws.
