# Qobuz Connector for Claude

An MCP server that gives Claude the same kind of music capabilities Anthropic
shipped for Spotify in April 2026 — search, library, playlists, editorial
recommendations — but pointed at [Qobuz](https://www.qobuz.com), the Hi-Res
lossless streaming service.

## What it does

Once connected, Claude can:

| Area | Tools |
|---|---|
| **Auth** | `qobuz_login`, `qobuz_auth_status` |
| **Search** | `qobuz_search` (tracks / albums / artists / playlists) |
| **Catalogue** | `qobuz_get_track`, `qobuz_get_album`, `qobuz_get_artist`, `qobuz_get_playlist` |
| **Discovery** | `qobuz_get_similar_artists`, `qobuz_featured_albums`, `qobuz_featured_playlists`, `qobuz_list_genres` |
| **Library** | `qobuz_get_favorites`, `qobuz_add_favorites`, `qobuz_remove_favorites`, `qobuz_get_purchases` |
| **Playlists** | `qobuz_get_user_playlists`, `qobuz_create_playlist`, `qobuz_update_playlist`, `qobuz_delete_playlist`, `qobuz_add_tracks_to_playlist`, `qobuz_remove_tracks_from_playlist`, `qobuz_subscribe_playlist`, `qobuz_unsubscribe_playlist` |
| **Streaming** | `qobuz_get_stream_url`, `qobuz_report_stream_start`, `qobuz_report_stream_end` |

That covers the same surface area as the official Claude × Spotify connector
(personalized recommendations, library access, playlist edits, playback
control hand-off) plus the thing Qobuz uniquely offers: signed Hi-Res
(24-bit/192 kHz FLAC) streaming URLs.

## How it maps to the Spotify connector

| Spotify connector capability | Qobuz equivalent |
|---|---|
| Recommendations from listening history | `qobuz_get_favorites` + `qobuz_get_similar_artists` |
| Vibe / mood playlists (Premium) | `qobuz_search` + `qobuz_featured_playlists` |
| Preview / save / play | `qobuz_get_stream_url` + `qobuz_add_favorites` |
| Spotify Connect device switching | _Not applicable — Qobuz has no Connect API; URLs are handed to a local player._ |
| Open in Spotify app | Track / album / playlist objects expose canonical Qobuz URLs in `slug` / `url` fields. |

## Setup

### 1. Get partner credentials

The Qobuz API is partner-gated. Email **api@qobuz.com** to request an
`app_id` and `app_secret`. Without these the connector cannot start.

### 2. Install

```bash
cd qobuz-connector
python -m venv .venv && source .venv/bin/activate
pip install -e .
```

### 3. Configure

Copy `.env.example` to `.env` (or export the variables in your shell):

```bash
export QOBUZ_APP_ID=...
export QOBUZ_APP_SECRET=...
# Either:
export QOBUZ_USERNAME=you@example.com
export QOBUZ_PASSWORD_MD5=$(printf '%s' 'your-password' | md5sum | cut -d' ' -f1)
# Or, if you already have one:
export QOBUZ_USER_AUTH_TOKEN=...
```

The first successful login is cached at
`~/.cache/qobuz-connector/token.json` (mode 600), so subsequent runs don't
need credentials.

### 4. Wire it into Claude

**Claude Desktop / Claude Code (`mcpServers` block):**

```json
{
  "mcpServers": {
    "qobuz": {
      "command": "python",
      "args": ["-m", "qobuz_connector"],
      "env": {
        "QOBUZ_APP_ID": "...",
        "QOBUZ_APP_SECRET": "...",
        "QOBUZ_USERNAME": "you@example.com",
        "QOBUZ_PASSWORD_MD5": "..."
      }
    }
  }
}
```

Restart the client. Claude will see the `qobuz_*` tools and can be asked
things like "find me a hi-res FLAC of Kind of Blue and add it to my
favorites" or "build a 20-track focus playlist from my favorite jazz
artists."

## Streaming format reference

`qobuz_get_stream_url` accepts a `format_id`:

| ID | Quality | Notes |
|---|---|---|
| 5  | MP3 320 kbps | Free / promo |
| 6  | FLAC 16/44.1 (CD) | Studio plan |
| 7  | FLAC 24/96 | Studio plan |
| 27 | FLAC 24/192 (Hi-Res) | Sublime / Studio plan |

Returned URLs are short-lived and signed — fetch the URL right before
playback, don't cache them.

## Notes & limitations

- Qobuz has no public Connect-style multi-device control API; this
  connector resolves a URL and leaves playback to the local client (much
  like Spotify Web API before Connect existed).
- `password` is hashed locally with MD5 before being sent — Qobuz's auth
  endpoint expects an MD5 digest, not the raw password.
- Telemetry endpoints (`qobuz_report_stream_*`) exist so listening history
  feeds back into Qobuz's recommendation engine; call them when you actually
  start/stop playback for accurate personalization.
- Per the Qobuz API ToU, `app_id` / `app_secret` are partner-private. Don't
  embed them in client-distributed code.

## Layout

```
qobuz-connector/
├── pyproject.toml
├── requirements.txt
├── README.md
├── .env.example
└── src/qobuz_connector/
    ├── __init__.py
    ├── __main__.py        # python -m qobuz_connector
    ├── config.py          # env loading + token cache path
    ├── client.py          # async Qobuz HTTP client (incl. stream-URL signing)
    └── server.py          # FastMCP server + tool definitions
```
