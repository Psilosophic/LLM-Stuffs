"""MCP server entry point for the Qobuz connector.

Run with:  python -m qobuz_connector

The server speaks MCP over stdio, so any MCP-aware client (Claude Desktop,
Claude Code, etc.) can launch it as a subprocess.
"""
from __future__ import annotations

import hashlib
from typing import Any

from mcp.server.fastmcp import FastMCP

from .client import QobuzClient, QobuzError
from .config import load_config


def _md5(value: str) -> str:
    return hashlib.md5(value.encode("utf-8")).hexdigest()


def build_server() -> FastMCP:
    config = load_config()
    client = QobuzClient(config)
    mcp = FastMCP(
        "qobuz-connector",
        instructions=(
            "Tools for searching Qobuz, managing the user's library and "
            "playlists, browsing editorial recommendations, and resolving "
            "lossless / hi-res streaming URLs. Call qobuz_login first if no "
            "user_auth_token is cached."
        ),
    )

    # ---------- auth ----------

    @mcp.tool()
    async def qobuz_login(
        username: str | None = None, password: str | None = None
    ) -> dict[str, Any]:
        """Authenticate a Qobuz user. If username/password aren't supplied, falls
        back to QOBUZ_USERNAME / QOBUZ_PASSWORD_MD5 env vars or the cached token.
        Passwords given inline are MD5-hashed locally before being sent."""
        if username and password:
            return await client.login(username, _md5(password))
        return await client.login_from_config()

    @mcp.tool()
    async def qobuz_auth_status() -> dict[str, Any]:
        """Return whether the connector currently has a valid user_auth_token."""
        return {"authenticated": client.is_authenticated}

    # ---------- search ----------

    @mcp.tool()
    async def qobuz_search(
        query: str, type: str = "track", limit: int = 10, offset: int = 0
    ) -> dict[str, Any]:
        """Search Qobuz. `type` is one of: track, album, artist, playlist."""
        return await client.search(query, type_=type, limit=limit, offset=offset)

    # ---------- catalogue lookups ----------

    @mcp.tool()
    async def qobuz_get_track(track_id: int) -> dict[str, Any]:
        """Fetch full metadata for a single track."""
        return await client.get_track(track_id)

    @mcp.tool()
    async def qobuz_get_album(album_id: str, extra: str | None = None) -> dict[str, Any]:
        """Fetch an album with its tracklist. `extra=track_ids` returns only ids."""
        return await client.get_album(album_id, extra=extra)

    @mcp.tool()
    async def qobuz_get_artist(
        artist_id: int, limit: int = 25, offset: int = 0
    ) -> dict[str, Any]:
        """Fetch an artist plus a page of their albums."""
        return await client.get_artist(artist_id, limit=limit, offset=offset)

    @mcp.tool()
    async def qobuz_get_similar_artists(
        artist_id: int, limit: int = 25, offset: int = 0
    ) -> dict[str, Any]:
        """Recommend artists similar to the given one."""
        return await client.get_similar_artists(artist_id, limit=limit, offset=offset)

    @mcp.tool()
    async def qobuz_get_playlist(
        playlist_id: int, limit: int = 50, offset: int = 0
    ) -> dict[str, Any]:
        """Fetch a playlist with a page of its tracks."""
        return await client.get_playlist(playlist_id, limit=limit, offset=offset)

    # ---------- editorial / discovery ----------

    @mcp.tool()
    async def qobuz_featured_albums(
        type: str = "new-releases",
        genre_id: int | None = None,
        limit: int = 25,
        offset: int = 0,
    ) -> dict[str, Any]:
        """Editorial album feeds. `type` examples: new-releases, press-awards,
        editor-picks, ideal-discography, qobuzissims, recent-releases."""
        return await client.featured_albums(
            type_=type, genre_id=genre_id, limit=limit, offset=offset
        )

    @mcp.tool()
    async def qobuz_featured_playlists(
        type: str = "editor-picks", limit: int = 25, offset: int = 0
    ) -> dict[str, Any]:
        """Editorial playlist feeds. `type` examples: editor-picks, last-created."""
        return await client.featured_playlists(type_=type, limit=limit, offset=offset)

    @mcp.tool()
    async def qobuz_list_genres(
        parent_id: int | None = None, limit: int = 50, offset: int = 0
    ) -> dict[str, Any]:
        """List genres (or subgenres of `parent_id`)."""
        return await client.list_genres(parent_id=parent_id, limit=limit, offset=offset)

    # ---------- favorites / library ----------

    @mcp.tool()
    async def qobuz_get_favorites(
        type: str = "tracks", limit: int = 50, offset: int = 0
    ) -> dict[str, Any]:
        """List the user's favorites. `type`: tracks, albums, or artists."""
        return await client.get_favorites(type_=type, limit=limit, offset=offset)

    @mcp.tool()
    async def qobuz_add_favorites(
        track_ids: list[str] | None = None,
        album_ids: list[str] | None = None,
        artist_ids: list[str] | None = None,
    ) -> dict[str, Any]:
        """Add tracks, albums, and/or artists to the user's library."""
        return await client.add_favorite(
            track_ids=track_ids, album_ids=album_ids, artist_ids=artist_ids
        )

    @mcp.tool()
    async def qobuz_remove_favorites(
        track_ids: list[str] | None = None,
        album_ids: list[str] | None = None,
        artist_ids: list[str] | None = None,
    ) -> dict[str, Any]:
        """Remove tracks, albums, and/or artists from the user's library."""
        return await client.remove_favorite(
            track_ids=track_ids, album_ids=album_ids, artist_ids=artist_ids
        )

    @mcp.tool()
    async def qobuz_get_purchases(limit: int = 50, offset: int = 0) -> dict[str, Any]:
        """List the user's Qobuz Store purchases."""
        return await client.purchases(limit=limit, offset=offset)

    # ---------- user playlists ----------

    @mcp.tool()
    async def qobuz_get_user_playlists(
        limit: int = 50, offset: int = 0
    ) -> dict[str, Any]:
        """List playlists owned by the current user."""
        return await client.user_playlists(limit=limit, offset=offset)

    @mcp.tool()
    async def qobuz_create_playlist(
        name: str,
        description: str | None = None,
        is_public: bool = False,
        is_collaborative: bool = False,
        track_ids: list[str] | None = None,
    ) -> dict[str, Any]:
        """Create a new playlist, optionally seeded with tracks."""
        return await client.create_playlist(
            name,
            description=description,
            is_public=is_public,
            is_collaborative=is_collaborative,
            track_ids=track_ids,
        )

    @mcp.tool()
    async def qobuz_update_playlist(
        playlist_id: str,
        name: str | None = None,
        description: str | None = None,
        is_public: bool | None = None,
        is_collaborative: bool | None = None,
    ) -> dict[str, Any]:
        """Update playlist metadata."""
        return await client.update_playlist(
            playlist_id,
            name=name,
            description=description,
            is_public=is_public,
            is_collaborative=is_collaborative,
        )

    @mcp.tool()
    async def qobuz_delete_playlist(playlist_id: str) -> dict[str, Any]:
        """Delete a playlist owned by the user."""
        return await client.delete_playlist(playlist_id)

    @mcp.tool()
    async def qobuz_add_tracks_to_playlist(
        playlist_id: str, track_ids: list[str]
    ) -> dict[str, Any]:
        """Append tracks to a playlist."""
        return await client.add_tracks_to_playlist(playlist_id, track_ids)

    @mcp.tool()
    async def qobuz_remove_tracks_from_playlist(
        playlist_id: str, playlist_track_ids: list[str]
    ) -> dict[str, Any]:
        """Remove tracks from a playlist by their playlist_track_id (not track_id)."""
        return await client.remove_tracks_from_playlist(playlist_id, playlist_track_ids)

    @mcp.tool()
    async def qobuz_subscribe_playlist(playlist_id: str) -> dict[str, Any]:
        """Subscribe to (follow) a public playlist."""
        return await client.subscribe_playlist(playlist_id)

    @mcp.tool()
    async def qobuz_unsubscribe_playlist(playlist_id: str) -> dict[str, Any]:
        """Unsubscribe from a public playlist."""
        return await client.unsubscribe_playlist(playlist_id)

    # ---------- streaming ----------

    @mcp.tool()
    async def qobuz_get_stream_url(
        track_id: int, format_id: int | None = None
    ) -> dict[str, Any]:
        """Resolve a signed streaming URL for a track.

        format_id reference:
          5  = MP3 320 kbps
          6  = FLAC 16/44.1 (CD)
          7  = FLAC 24/96
          27 = FLAC 24/192 (Hi-Res, requires Sublime/Studio plan)
        Subject to the user's subscription tier."""
        return await client.track_file_url(track_id, format_id=format_id)

    @mcp.tool()
    async def qobuz_report_stream_start(track_id: int) -> dict[str, Any]:
        """Report start-of-stream telemetry (call when playback begins)."""
        return await client.report_stream_start(track_id)

    @mcp.tool()
    async def qobuz_report_stream_end(
        track_id: int, duration_seconds: int
    ) -> dict[str, Any]:
        """Report end-of-stream telemetry, with the played duration in seconds."""
        return await client.report_stream_end(track_id, duration_seconds)

    return mcp


def main() -> None:
    server = build_server()
    try:
        server.run()
    except QobuzError as exc:
        # FastMCP turns tool exceptions into protocol errors automatically; this
        # only catches startup-time failures (e.g., bad config) so the operator
        # gets a readable message instead of a traceback.
        raise SystemExit(f"qobuz-connector failed to start: {exc}") from exc


if __name__ == "__main__":
    main()
