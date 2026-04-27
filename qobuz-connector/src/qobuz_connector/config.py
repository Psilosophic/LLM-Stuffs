import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Config:
    app_id: str
    app_secret: str
    username: str | None
    password_md5: str | None
    user_auth_token: str | None
    token_cache_path: Path
    base_url: str = "https://www.qobuz.com/api.json/0.2"
    user_agent: str = "QobuzConnector/0.1 (+https://claude.ai)"
    default_format_id: int = 27  # 27 = Hi-Res 24bit ≤192kHz; 7 = CD 16/44.1; 5 = 320kbps MP3
    request_timeout: float = 20.0


def _require(name: str, value: str | None) -> str:
    if not value:
        raise RuntimeError(
            f"Missing required environment variable: {name}. "
            "Request app credentials from api@qobuz.com and export them before "
            "starting the connector."
        )
    return value


def load_config() -> Config:
    cache_dir = Path(
        os.environ.get("QOBUZ_TOKEN_CACHE_DIR")
        or (Path.home() / ".cache" / "qobuz-connector")
    )
    cache_dir.mkdir(parents=True, exist_ok=True)
    return Config(
        app_id=_require("QOBUZ_APP_ID", os.environ.get("QOBUZ_APP_ID")),
        app_secret=_require("QOBUZ_APP_SECRET", os.environ.get("QOBUZ_APP_SECRET")),
        username=os.environ.get("QOBUZ_USERNAME"),
        password_md5=os.environ.get("QOBUZ_PASSWORD_MD5"),
        user_auth_token=os.environ.get("QOBUZ_USER_AUTH_TOKEN"),
        token_cache_path=cache_dir / "token.json",
        default_format_id=int(os.environ.get("QOBUZ_DEFAULT_FORMAT_ID", "27")),
    )
