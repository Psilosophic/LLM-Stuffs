# Brain — operating instructions for Claude Code

> Obsidian is the IDE. The LLM is the programmer. The wiki is the codebase.

This vault is a living knowledge base. Your job is to turn raw material in `raw\`
into a clean, interconnected wiki in `wiki\`. Treat the wiki like source code:
small, well-named, heavily cross-referenced units, with one canonical index.

## Folder layout
```
Brain\
├── raw\      <- I drop sources here (exports, PDFs, articles, transcripts). Never edit; treat as read-only input.
├── wiki\     <- You write compiled, structured notes here. This is the product.
│   └── index.md   <- The single canonical map of the wiki. Always keep current.
├── log.md    <- Append-only processing log. One line per processing run.
└── CLAUDE.md <- This file.
```

## Core rules
1. **Atomic notes.** One idea, person, project, or source per file. If a note
   covers two distinct things, split it.
2. **Wikilink everything.** Connect notes with `[[Note Name]]`. A note with no
   links is a bug — find its neighbors. Prefer linking over duplicating.
3. **Frontmatter on every note:**
   ```yaml
   ---
   title: <human title>
   type: topic | project | person | source | idea
   tags: [domain/subdomain, ...]
   created: YYYY-MM-DD
   source: <where this came from, e.g. raw\chatgpt\conv_123.json>
   ---
   ```
4. **Stable, descriptive filenames.** `Title Case With Spaces.md`. Don't rename
   existing notes without updating inbound `[[links]]`.
5. **The index is canonical.** After any run, update `wiki\index.md` so it maps
   every note by `type` and by `tag`. The index is how both I and you navigate.
6. **Log every run.** Append one line to `log.md`:
   `YYYY-MM-DD HH:MM — processed N sources from raw\..., created/updated M notes`.
7. **Never invent facts.** Only write what the source supports. Mark genuine
   inference as `> [!note] inference`.
8. **Dedupe.** Before creating a note, search the wiki for an existing one to
   extend instead.

## Processing a conversation export (Stage 1)
- For ChatGPT/Claude exports, fan out sub-agents (one per batch of conversations)
  to keep it fast.
- From each conversation extract: durable topics, decisions, projects, people,
  and any reusable artifacts (prompts, snippets, frameworks).
- Skip transient chatter. Capture the signal, link it, drop the noise.
- Route extracted units into atomic `wiki\` notes; cite the source conversation.

## Compiling a source (Stage 2)
- Read the source in `raw\`, summarize it into one `type: source` note, then
  extract its distinct ideas into linked `type: topic`/`type: idea` notes.
- Update `index.md` and `log.md`.

## Voice
When asked to draft in my voice (e.g. via `/create`), study existing wiki notes
and past drafts first; match my phrasing, structure, and level of directness.
