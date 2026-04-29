"""Settings loader: .env → dataclass.

Each spider looks up its CDP port via `settings.cdp_port_for(platform)`.
Public demo scope: 2 platforms ("twitter", "tiktok"). The paid version
adds "fb" and "instagram" plus Redis / MongoDB / PostgreSQL settings.

Override via env vars (TWITTER_CDP_PORT, TIKTOK_CDP_PORT) or .env file.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv


def _int(name: str, default: int) -> int:
    v = os.getenv(name)
    if v is None or v == "":
        return default
    try:
        return int(v)
    except ValueError:
        return default


@dataclass
class Settings:
    log_level: str = "INFO"
    data_dir: Path = field(default_factory=lambda: Path("./data"))

    # Chrome CDP ports per platform (demo scope)
    twitter_cdp_port: int = 9223
    tiktok_cdp_port: int = 9225

    @classmethod
    def from_env(cls) -> "Settings":
        load_dotenv()
        return cls(
            log_level=os.getenv("LOG_LEVEL", "INFO"),
            data_dir=Path(os.getenv("DATA_DIR", "./data")),
            twitter_cdp_port=_int("TWITTER_CDP_PORT", 9223),
            tiktok_cdp_port=_int("TIKTOK_CDP_PORT", 9225),
        )

    def cdp_port_for(self, platform: str) -> int:
        attr = f"{platform.lower()}_cdp_port"
        port = getattr(self, attr, None)
        if port is None:
            raise ValueError(
                f"Unknown platform {platform!r}; demo supports 'twitter' and "
                f"'tiktok'. Other platforms ship in the paid version."
            )
        return int(port)
