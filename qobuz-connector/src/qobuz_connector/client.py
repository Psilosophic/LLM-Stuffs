from __future__ import annotations

import hashlib
import json
import time
from typing import Any

import httpx

from .config import Config


class QobuzError(RuntimeError):
    """Raised when the Qobuz API returns an error or unexpected response."""


class QobuzClient:
    """Minimal async client for the Qobuz `api.json/0.2` REST surface.

    Auth model: every request carries `X-App-Id`. Authenticated requests also
    carry `X-User-Auth-Token`, obtained via `user/login`. Streaming-URL requests
    are HMAC-signed with the partner `app_secret`.
    """

    def __init__(self, config: Config, http: httpx.AsyncClient | None = None) -> None:
        self._config = config
        self._http = http or httpx.AsyncClient(
            base_url=config.base_url,
            timeout=config.request_timeout,
            headers={"User-Agent": config.user_agent},
        )
        self._token: str | None = config.user_auth_token
        self._user: dict[str, Any] | None = None
        self._load_cached_token()

    async def aclose(self) -> None:
        await self._http.aclose()

    # ---------- token persistence ----------

    def _load_cached_token(self) -> None:
        if self._token:
            return
        path = self._config.token_cache_path
        if not path.exists():
            return
        try:
            data = json.loads(path.read_text())
            self._token = data.get("user_auth_token")
            self._user = data.get("user")
        except (OSError, json.JSONDecodeError):
            return

    def _save_cached_token(self) -> None:
        path = self._config.token_cache_path
        payload = {"user_auth_token": self._token, "user": self._user}
        path.write_text(json.dumps(payload))
        try:
            path.chmod(0o600)
        except OSError:
            pass

    # ---------- transport ----------

    def _headers(self, *, authed: bool) -> dict[str, str]:
        headers = {"X-App-Id": self._config.app_id}
        if authed:
            if not self._token:
                raise QobuzError(
                    "Not authenticated. Call qobuz_login first or set "
                    "QOBUZ_USER_AUTH_TOKEN."
                )
            headers["X-User-Auth-Token"] = self._token
        return headers

    async def _request(
        self,
        method: str,
        endpoint: str,
        *,
        params: dict[str, Any] | None = None,
        data: dict[str, Any] | None = None,
        authed: bool = True,
    ) -> dict[str, Any]:
        params = {k: v for k, v in (params or {}).items() if v is not None}
        data = {k: v for k, v in (data or {}).items() if v is not None}
        resp = await self._http.request(
            method,
            endpoint,
            params=params or None,
            data=data or None,
            headers=self._headers(authed=authed),
        )
        if resp.status_code == 401:
            self._token = None
            raise QobuzError("Qobuz returned 401 — token expired, please re-login.")
        try:
            payload = resp.json()
        except ValueError as exc:
            raise QobuzError(f"Non-JSON response from Qobuz: {resp.text[:200]}") from exc
        if resp.status_code >= 400 or (
            isinstance(payload, dict) and payload.get("status") == "error"
        ):
            msg = payload.get("message") if isinstance(payload, dict) else resp.text
            raise QobuzError(f"Qobuz error ({resp.status_code}): {msg}")
        return payload

    # ---------- auth ----------

    async def login(self, username: str, password_md5: str) -> dict[str, Any]:
        payload = await self._request(
            "POST",
            "user/login",
            data={"username": username, "password": password_md5},
            authed=False,
        )
        token = payload.get("user_auth_token")
        if not token:
            raise QobuzError("Login succeeded but no user_auth_token returned.")
        self._token = token
        self._user = payload.get("user")
        self._save_cached_token()
        return {"user": self._user, "logged_in": True}

    async def login_from_config(self) -> dict[str, Any]:
        if self._token:
            return {"user": self._user, "logged_in": True, "from": "cache"}
        if not (self._config.username and self._config.password_md5):
            raise QobuzError(
                "No cached token and QOBUZ_USERNAME / QOBUZ_PASSWORD_MD5 are not set."
            )
        return await self.login(self._config.username, self._config.password_md5)

    @property
    def is_authenticated(self) -> bool:
        return bool(self._token)

    # ---------- search & catalogue ----------

    async def search(
        self, query: str, type_: str = "tracks", limit: int = 10, offset: int = 0
    ) -> dict[str, Any]:
        type_map = {
            "track": "tracks",
            "tracks": "tracks",
            "album": "albums",
            "albums": "albums",
            "artist": "artists",
            "artists": "artists",
            "playlist": "playlists",
            "playlists": "playlists",
        }
        normalized = type_map.get(type_.lower())
        if not normalized:
            raise QobuzError(
                f"Unknown search type {type_!r}. Use one of: track, album, artist, playlist."
            )
        endpoint = f"{normalized.rstrip('s')}/search"
        return await self._request(
            "GET", endpoint, params={"query": query, "limit": limit, "offset": offset}
        )

    async def get_track(self, track_id: int | str) -> dict[str, Any]:
        return await self._request("GET", "track/get", params={"track_id": track_id})

    async def get_album(self, album_id: str, *, extra: str | None = None) -> dict[str, Any]:
        return await self._request(
            "GET", "album/get", params={"album_id": album_id, "extra": extra}
        )

    async def get_artist(
        self,
        artist_id: int | str,
        *,
        extra: str | None = "albums",
        limit: int = 25,
        offset: int = 0,
    ) -> dict[str, Any]:
        return await self._request(
            "GET",
            "artist/get",
            params={
                "artist_id": artist_id,
                "extra": extra,
                "limit": limit,
                "offset": offset,
            },
        )

    async def get_similar_artists(
        self, artist_id: int | str, limit: int = 25, offset: int = 0
    ) -> dict[str, Any]:
        return await self._request(
            "GET",
            "artist/getSimilarArtists",
            params={"artist_id": artist_id, "limit": limit, "offset": offset},
        )

    async def get_playlist(
        self, playlist_id: int | str, *, limit: int = 50, offset: int = 0
    ) -> dict[str, Any]:
        return await self._request(
            "GET",
            "playlist/get",
            params={
                "playlist_id": playlist_id,
                "extra": "tracks",
                "limit": limit,
                "offset": offset,
            },
        )

    async def featured_albums(
        self,
        type_: str = "new-releases",
        genre_id: int | None = None,
        limit: int = 25,
        offset: int = 0,
    ) -> dict[str, Any]:
        return await self._request(
            "GET",
            "album/getFeatured",
            params={"type": type_, "genre_id": genre_id, "limit": limit, "offset": offset},
        )

    async def featured_playlists(
        self, type_: str = "editor-picks", limit: int = 25, offset: int = 0
    ) -> dict[str, Any]:
        return await self._request(
            "GET",
            "playlist/getFeatured",
            params={"type": type_, "limit": limit, "offset": offset},
        )

    async def list_genres(
        self, parent_id: int | None = None, limit: int = 50, offset: int = 0
    ) -> dict[str, Any]:
        return await self._request(
            "GET",
            "genre/list",
            params={"parent_id": parent_id, "limit": limit, "offset": offset},
        )

    # ---------- user library ----------

    async def get_favorites(
        self, type_: str = "tracks", limit: int = 50, offset: int = 0
    ) -> dict[str, Any]:
        return await self._request(
            "GET",
            "favorite/getUserFavorites",
            params={"type": type_, "limit": limit, "offset": offset},
        )

    async def add_favorite(
        self,
        *,
        track_ids: list[str] | None = None,
        album_ids: list[str] | None = None,
        artist_ids: list[str] | None = None,
    ) -> dict[str, Any]:
        if not (track_ids or album_ids or artist_ids):
            raise QobuzError("Provide at least one of track_ids, album_ids, artist_ids.")
        return await self._request(
            "POST",
            "favorite/create",
            data={
                "track_ids": ",".join(track_ids) if track_ids else None,
                "album_ids": ",".join(album_ids) if album_ids else None,
                "artist_ids": ",".join(artist_ids) if artist_ids else None,
            },
        )

    async def remove_favorite(
        self,
        *,
        track_ids: list[str] | None = None,
        album_ids: list[str] | None = None,
        artist_ids: list[str] | None = None,
    ) -> dict[str, Any]:
        if not (track_ids or album_ids or artist_ids):
            raise QobuzError("Provide at least one of track_ids, album_ids, artist_ids.")
        return await self._request(
            "POST",
            "favorite/delete",
            data={
                "track_ids": ",".join(track_ids) if track_ids else None,
                "album_ids": ",".join(album_ids) if album_ids else None,
                "artist_ids": ",".join(artist_ids) if artist_ids else None,
            },
        )

    async def purchases(self, limit: int = 50, offset: int = 0) -> dict[str, Any]:
        return await self._request(
            "GET",
            "purchase/getUserPurchases",
            params={"limit": limit, "offset": offset},
        )

    # ---------- user playlists ----------

    async def user_playlists(
        self, limit: int = 50, offset: int = 0
    ) -> dict[str, Any]:
        return await self._request(
            "GET",
            "playlist/getUserPlaylists",
            params={"limit": limit, "offset": offset},
        )

    async def create_playlist(
        self,
        name: str,
        *,
        description: str | None = None,
        is_public: bool = False,
        is_collaborative: bool = False,
        track_ids: list[str] | None = None,
    ) -> dict[str, Any]:
        return await self._request(
            "POST",
            "playlist/create",
            data={
                "name": name,
                "description": description,
                "is_public": int(is_public),
                "is_collaborative": int(is_collaborative),
                "track_ids": ",".join(track_ids) if track_ids else None,
            },
        )

    async def update_playlist(
        self,
        playlist_id: str,
        *,
        name: str | None = None,
        description: str | None = None,
        is_public: bool | None = None,
        is_collaborative: bool | None = None,
    ) -> dict[str, Any]:
        return await self._request(
            "POST",
            "playlist/update",
            data={
                "playlist_id": playlist_id,
                "name": name,
                "description": description,
                "is_public": None if is_public is None else int(is_public),
                "is_collaborative": (
                    None if is_collaborative is None else int(is_collaborative)
                ),
            },
        )

    async def delete_playlist(self, playlist_id: str) -> dict[str, Any]:
        return await self._request(
            "POST", "playlist/delete", data={"playlist_id": playlist_id}
        )

    async def add_tracks_to_playlist(
        self, playlist_id: str, track_ids: list[str]
    ) -> dict[str, Any]:
        if not track_ids:
            raise QobuzError("track_ids must contain at least one id.")
        return await self._request(
            "POST",
            "playlist/addTracks",
            data={"playlist_id": playlist_id, "track_ids": ",".join(track_ids)},
        )

    async def remove_tracks_from_playlist(
        self, playlist_id: str, playlist_track_ids: list[str]
    ) -> dict[str, Any]:
        if not playlist_track_ids:
            raise QobuzError("playlist_track_ids must contain at least one id.")
        return await self._request(
            "POST",
            "playlist/deleteTracks",
            data={
                "playlist_id": playlist_id,
                "playlist_track_ids": ",".join(playlist_track_ids),
            },
        )

    async def subscribe_playlist(self, playlist_id: str) -> dict[str, Any]:
        return await self._request(
            "POST", "playlist/subscribe", data={"playlist_id": playlist_id}
        )

    async def unsubscribe_playlist(self, playlist_id: str) -> dict[str, Any]:
        return await self._request(
            "POST", "playlist/unsubscribe", data={"playlist_id": playlist_id}
        )

    # ---------- streaming ----------

    async def track_file_url(
        self, track_id: int | str, format_id: int | None = None
    ) -> dict[str, Any]:
        """Get a signed streaming URL.

        Streaming endpoints require a request signature:
          md5("trackgetFileUrl" + sorted_kv_concat + ts + app_secret)
        where sorted_kv_concat lists params in alphabetical order (no separators).
        """
        fmt = format_id if format_id is not None else self._config.default_format_id
        ts = int(time.time())
        sig_input = f"trackgetFileUrlformat_id{fmt}intentstreamtrack_id{track_id}{ts}{self._config.app_secret}"
        request_sig = hashlib.md5(sig_input.encode("utf-8")).hexdigest()
        return await self._request(
            "GET",
            "track/getFileUrl",
            params={
                "track_id": track_id,
                "format_id": fmt,
                "intent": "stream",
                "request_ts": ts,
                "request_sig": request_sig,
            },
        )

    async def report_stream_start(self, track_id: int | str) -> dict[str, Any]:
        return await self._request(
            "POST", "track/reportStreamingStart", data={"track_id": track_id}
        )

    async def report_stream_end(
        self, track_id: int | str, duration_seconds: int
    ) -> dict[str, Any]:
        return await self._request(
            "POST",
            "track/reportStreamingEnd",
            data={"track_id": track_id, "duration": duration_seconds},
        )
