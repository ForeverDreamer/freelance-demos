"""Settings loader: .env → dataclass.

Each spider looks up its CDP port via `settings.cdp_port_for(platform)` where
platform is one of {"fb", "twitter", "instagram", "tiktok"}. Override via env
vars (FB_CDP_PORT, etc.) or .env file.

Demo scope: JSONL output only. The paid version's Settings adds Redis
(dedup), MongoDB (warehouse), PostgreSQL (analytics), and pipeline-level
toggle flags.
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

    # Chrome CDP ports per platform
    fb_cdp_port: int = 9222
    twitter_cdp_port: int = 9223
    instagram_cdp_port: int = 9224
    tiktok_cdp_port: int = 9225

    @classmethod
    def from_env(cls) -> "Settings":
        load_dotenv()
        return cls(
            log_level=os.getenv("LOG_LEVEL", "INFO"),
            data_dir=Path(os.getenv("DATA_DIR", "./data")),
            fb_cdp_port=_int("FB_CDP_PORT", 9222),
            twitter_cdp_port=_int("TWITTER_CDP_PORT", 9223),
            instagram_cdp_port=_int("INSTAGRAM_CDP_PORT", 9224),
            tiktok_cdp_port=_int("TIKTOK_CDP_PORT", 9225),
        )

    def cdp_port_for(self, platform: str) -> int:
        attr = f"{platform.lower()}_cdp_port"
        port = getattr(self, attr, None)
        if port is None:
            raise ValueError(f"Unknown platform {platform!r}; no CDP port configured")
        return int(port)
