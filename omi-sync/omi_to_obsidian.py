#!/usr/bin/env python3
"""
omi_to_obsidian.py
==================

Polls the Omi developer API for completed conversations and writes each one as a
Markdown note into a local Obsidian vault. Designed to run unattended on the
machine that hosts the vault (e.g. via Windows Task Scheduler).

It is idempotent: a small state file records which Omi conversation IDs have
already been written, so re-running never duplicates notes.

Config resolution order (later overrides earlier):
  1. config.json sitting next to this script
  2. environment variables (OMI_API_KEY, OBSIDIAN_VAULT_PATH, ...)
  3. command-line flags (--api-key, --vault, ...)

The API key should normally come from the OMI_API_KEY env var so it never lands
in a committed file. See README.md for setup.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import sys
from pathlib import Path

try:
    import requests
except ImportError:  # pragma: no cover - guard for a friendlier message
    sys.exit("Missing dependency: run  pip install -r requirements.txt")

API_BASE = "https://api.omi.me/v1/dev"
PAGE_SIZE = 25
SCRIPT_DIR = Path(__file__).resolve().parent


# --------------------------------------------------------------------------- #
# Config
# --------------------------------------------------------------------------- #
def load_config() -> dict:
    """Merge config.json, environment variables and CLI flags into one dict."""
    cfg: dict = {
        "api_key": "",
        "vault_path": "",
        "subfolder": "Omi",          # notes are written under <vault>/<subfolder>
        "index_file": "_Omi Index.md",  # rolling digest, "" disables it
        "lookback_days": 7,           # how far back to scan on each run
        "include_transcript": True,
        "max_pages": 40,              # safety cap on pagination per run
    }

    cfg_file = SCRIPT_DIR / "config.json"
    if cfg_file.exists():
        cfg.update({k: v for k, v in json.loads(cfg_file.read_text()).items() if v != ""})

    env_map = {
        "OMI_API_KEY": "api_key",
        "OBSIDIAN_VAULT_PATH": "vault_path",
        "OMI_SUBFOLDER": "subfolder",
    }
    for env, key in env_map.items():
        if os.environ.get(env):
            cfg[key] = os.environ[env]

    p = argparse.ArgumentParser(description="Sync Omi conversations into an Obsidian vault.")
    p.add_argument("--api-key")
    p.add_argument("--vault", dest="vault_path")
    p.add_argument("--subfolder")
    p.add_argument("--lookback-days", type=int)
    p.add_argument("--no-transcript", action="store_true")
    p.add_argument("--dry-run", action="store_true", help="Fetch and report, but write nothing.")
    args = p.parse_args()
    for key in ("api_key", "vault_path", "subfolder", "lookback_days"):
        if getattr(args, key) is not None:
            cfg[key] = getattr(args, key)
    if args.no_transcript:
        cfg["include_transcript"] = False
    cfg["dry_run"] = args.dry_run

    if not cfg["api_key"]:
        sys.exit("No Omi API key. Set OMI_API_KEY env var, config.json, or --api-key.")
    if not cfg["vault_path"]:
        sys.exit("No vault path. Set OBSIDIAN_VAULT_PATH env var, config.json, or --vault.")
    return cfg


# --------------------------------------------------------------------------- #
# State
# --------------------------------------------------------------------------- #
def state_path() -> Path:
    return SCRIPT_DIR / ".omi_sync_state.json"


def load_state() -> dict:
    p = state_path()
    if p.exists():
        return json.loads(p.read_text())
    return {"synced_ids": [], "last_run": None}


def save_state(state: dict) -> None:
    state_path().write_text(json.dumps(state, indent=2))


# --------------------------------------------------------------------------- #
# Omi API
# --------------------------------------------------------------------------- #
def fetch_conversations(cfg: dict) -> list[dict]:
    """Return conversations within the lookback window, newest first."""
    headers = {"Authorization": f"Bearer {cfg['api_key']}"}
    start_date = (
        dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=cfg["lookback_days"])
    ).isoformat()

    out: list[dict] = []
    for page in range(cfg["max_pages"]):
        params = {
            "limit": PAGE_SIZE,
            "offset": page * PAGE_SIZE,
            "start_date": start_date,
            "include_transcript": str(cfg["include_transcript"]).lower(),
        }
        resp = requests.get(
            f"{API_BASE}/user/conversations", headers=headers, params=params, timeout=30
        )
        resp.raise_for_status()
        body = resp.json()
        # The API may return a bare list or {"conversations": [...]}; handle both.
        batch = body.get("conversations", body) if isinstance(body, dict) else body
        if not batch:
            break
        out.extend(batch)
        if len(batch) < PAGE_SIZE:
            break
    return out


# --------------------------------------------------------------------------- #
# Markdown rendering
# --------------------------------------------------------------------------- #
def sanitize_filename(name: str) -> str:
    name = re.sub(r'[<>:"/\\|?*\n\r]', " ", name).strip()
    name = re.sub(r"\s+", " ", name)
    return name[:80] or "Untitled"


def fmt_local(ts: str | None) -> str:
    if not ts:
        return ""
    try:
        return dt.datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone().strftime(
            "%Y-%m-%d %H:%M"
        )
    except ValueError:
        return ts


def render_note(conv: dict) -> tuple[str, str]:
    """Return (filename, markdown_body) for one conversation."""
    structured = conv.get("structured") or {}
    title = structured.get("title") or "Untitled conversation"
    emoji = structured.get("emoji") or ""
    overview = structured.get("overview") or ""
    category = structured.get("category") or "uncategorized"
    action_items = structured.get("action_items") or []
    events = structured.get("events") or []
    conv_id = conv.get("id", "")
    started = conv.get("started_at") or conv.get("created_at") or ""
    date_only = (started or "")[:10] or dt.date.today().isoformat()

    short_id = conv_id.replace("conv_", "")[:8]
    filename = f"{date_only} {sanitize_filename(title)} ({short_id}).md"

    # --- YAML frontmatter ---
    fm = [
        "---",
        f'title: "{title.replace(chr(34), chr(39))}"',
        f"date: {date_only}",
        f"started_at: {started}",
        f"finished_at: {conv.get('finished_at', '')}",
        f"omi_id: {conv_id}",
        f"category: {category}",
        f"source: {conv.get('source', 'omi')}",
        "tags:",
        "  - omi",
        f"  - omi/{category}",
    ]
    geo = conv.get("geolocation") or {}
    if geo.get("address"):
        fm.append(f'location: "{geo["address"]}"')
    fm.append("---")

    # --- body ---
    body = [f"# {emoji} {title}".strip(), ""]
    if overview:
        body += ["## Summary", "", overview, ""]

    if action_items:
        body += ["## Action items", ""]
        for item in action_items:
            desc = item.get("description", "").strip()
            checked = "x" if item.get("completed") else " "
            due = item.get("due_at")
            suffix = f"  *(due {fmt_local(due)})*" if due else ""
            body.append(f"- [{checked}] {desc}{suffix}")
        body.append("")

    if events:
        body += ["## Events", ""]
        for ev in events:
            body.append(f"- {ev.get('title', 'Event')} — {fmt_local(ev.get('start'))}")
        body.append("")

    segments = conv.get("transcript_segments") or []
    if segments:
        body += ["> [!quote]- Transcript", ">"]
        for seg in segments:
            speaker = seg.get("speaker_name") or f"Speaker {seg.get('speaker_id', 0)}"
            text = (seg.get("text") or "").strip()
            if text:
                body.append(f"> **{speaker}:** {text}")
        body.append("")

    body += ["---", f"*Imported from Omi · {fmt_local(started)} · `{conv_id}`*"]
    return filename, "\n".join(fm) + "\n\n" + "\n".join(body) + "\n"


def update_index(cfg: dict, vault_subdir: Path, new_notes: list[tuple[str, dict]]) -> None:
    """Prepend the freshly-written notes to a rolling digest the LLM can read."""
    if not cfg["index_file"]:
        return
    index = vault_subdir / cfg["index_file"]
    header = "# Omi Index\n\nMost-recent conversations captured from Omi. Newest first.\n"
    lines: list[str] = []
    for filename, conv in new_notes:
        structured = conv.get("structured") or {}
        title = structured.get("title") or "Untitled"
        when = fmt_local(conv.get("started_at") or conv.get("created_at"))
        link = filename[:-3]  # strip .md for wikilink
        lines.append(f"- {when} — [[{link}|{title}]]")

    existing = ""
    if index.exists():
        existing = index.read_text()
        existing = existing.split("Newest first.\n", 1)[-1] if "Newest first.\n" in existing else ""
    index.write_text(header + "\n".join(lines) + "\n" + existing)


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #
def main() -> None:
    cfg = load_config()
    state = load_state()
    synced = set(state["synced_ids"])

    vault_subdir = Path(cfg["vault_path"]) / cfg["subfolder"]
    if not Path(cfg["vault_path"]).exists():
        sys.exit(f"Vault path does not exist: {cfg['vault_path']}")
    vault_subdir.mkdir(parents=True, exist_ok=True)

    conversations = fetch_conversations(cfg)
    fresh = [c for c in conversations if c.get("id") and c["id"] not in synced]
    fresh.sort(key=lambda c: c.get("started_at") or c.get("created_at") or "", reverse=True)

    print(f"Fetched {len(conversations)} conversation(s); {len(fresh)} new.")

    written: list[tuple[str, dict]] = []
    for conv in fresh:
        filename, markdown = render_note(conv)
        dest = vault_subdir / filename
        if cfg["dry_run"]:
            print(f"  [dry-run] would write {dest}")
        else:
            dest.write_text(markdown, encoding="utf-8")
            print(f"  wrote {dest.name}")
        written.append((filename, conv))
        synced.add(conv["id"])

    if written and not cfg["dry_run"]:
        update_index(cfg, vault_subdir, written)

    if not cfg["dry_run"]:
        state["synced_ids"] = sorted(synced)
        state["last_run"] = dt.datetime.now(dt.timezone.utc).isoformat()
        save_state(state)

    print("Done.")


if __name__ == "__main__":
    main()
