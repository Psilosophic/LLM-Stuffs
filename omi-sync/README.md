# Omi → Obsidian sync

Turns every conversation your [Omi](https://www.omi.me/) wearable captures into a
clean Markdown note inside a local Obsidian vault. Built to run unattended on the
machine that holds the vault — for this setup, a Windows 11 PC.

It **polls** Omi's developer API on a schedule rather than receiving webhooks.
On a home desktop that's the robust choice: no public tunnel to keep alive, no
inbound port to expose, and it survives reboots via Task Scheduler.

Each note gets:

- YAML frontmatter (`title`, `date`, `omi_id`, `category`, `source`, `location`)
- nested tags (`#omi`, `#omi/<category>`) for Dataview/graph queries
- a **Summary** section from Omi's structured overview
- **Action items** as checkboxes with due dates
- the full **transcript** inside a foldable `> [!quote]-` callout
- an entry prepended to a rolling `_Omi Index.md` digest

Re-running never duplicates: synced conversation IDs are tracked in
`.omi_sync_state.json`.

## Setup (Windows 11)

1. **Install Python 3.10+** (python.org) and tick *"Add to PATH"*.
2. **Get an Omi developer API key** — Omi app → Settings → Developer. It starts
   with `omi_dev_`. (Note: that's the REST key. The `omi_mcp_` key is a
   different thing, used only for the MCP path below.)
3. From this folder:
   ```bat
   pip install -r requirements.txt
   copy config.example.json config.json
   ```
4. Edit `config.json`: set `vault_path` to your vault's folder (use double
   backslashes, e.g. `C:\\Users\\You\\Documents\\SecondBrain`). Either put the
   key in `config.json` **or** set the `OMI_API_KEY` env var (preferred — keeps
   it out of every file). Both `config.json` and the state file are gitignored.
5. **Test it** without writing anything:
   ```bat
   python omi_to_obsidian.py --dry-run
   ```
   Then for real:
   ```bat
   python omi_to_obsidian.py
   ```
   Notes land in `<vault>\Omi\`.

## Run it constantly (Task Scheduler)

This is what makes it "always recording → always updating the vault":

1. Open **Task Scheduler** → *Create Task*.
2. **Triggers** → New → *On a schedule* → *Daily*, repeat **every 15 minutes**
   for *Indefinitely*. (Omi only surfaces a conversation once it's finished
   processing, so polling every 10–15 min is plenty.)
3. **Actions** → New → *Start a program* → Program: `run.bat` (or `python` with
   argument `omi_to_obsidian.py` and "Start in" set to this folder).
4. **Settings** → tick *"Run task as soon as possible after a scheduled start is
   missed"* so it catches up after the PC sleeps.

## Config reference

| Key                  | Default        | Meaning                                            |
| -------------------- | -------------- | -------------------------------------------------- |
| `api_key`            | —              | Omi `omi_dev_` key (prefer the `OMI_API_KEY` env var) |
| `vault_path`         | —              | Absolute path to the Obsidian vault root           |
| `subfolder`          | `Omi`          | Notes are written under `<vault>/<subfolder>`      |
| `index_file`         | `_Omi Index.md`| Rolling digest filename; `""` disables it          |
| `lookback_days`      | `7`            | How far back each run scans (dedup handles overlap)|
| `include_transcript` | `true`         | Embed the full transcript in each note             |
| `max_pages`          | `40`           | Pagination safety cap per run                      |

CLI flags (`--api-key`, `--vault`, `--subfolder`, `--lookback-days`,
`--no-transcript`, `--dry-run`) override config + env.

## Making it *your* memory

The sync fills the vault. How a Claude reads it back is a separate choice,
because **a purely-local vault is invisible to any cloud Claude session**:

- **Local brain (vault stays private):** run Claude Code *on this Windows PC*
  pointed at the vault folder. Add a `CLAUDE.md` at the vault root that says to
  treat `Omi/_Omi Index.md` and the `Omi/` notes as long-term memory. Nothing
  leaves the machine.
- **Cloud-readable brain:** also push the vault (or just the `Omi/` folder and
  index) to a private GitHub repo via Obsidian's *Git* plugin. Then a cloud
  session can read it as context. Heads-up: this puts transcripts — including
  other people's words — into a hosted repo, so use a **private** one.

You can also skip files entirely and add **Omi's MCP server**
(`https://api.omi.me/v1/mcp/sse`, auth with an `omi_mcp_` key) to a Claude
client to query conversations live. The file sync and the MCP are complementary:
files give durable, greppable memory; MCP gives live lookup.

## Privacy

Constant recording captures everyone around you, and these notes are
audio-derived text about real people. Keep the vault local or in a private repo,
and mind local consent laws for recording conversations.
