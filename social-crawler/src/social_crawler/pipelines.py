"""Async pipeline chain: clean → write_jsonl.

Demo scope: JSONL output only, daily-sharded by platform. The paid version
adds:

- Redis dedup with TTL (skip already-scraped post_ids)
- MongoDB upsert (warehouse for cross-day analytics)
- PostgreSQL warehouse rows (analytics-friendly schema)
- Google Sheets export (for non-technical clients)
- Field cleaning extras (zero-width char strip, language detection)

Calling convention:
    spider yields dataclass items
    item_dict = dataclasses.asdict(item)
    result = await run_pipelines(item_dict, ctx)  # → dict | None (None = dropped)
"""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import IO, Optional

from social_crawler.config import Settings

logger = logging.getLogger(__name__)


# Item kind detection. post-kind requires post_id; user-kind requires one
# of the user identifier fields (varies by platform).
USER_IDENTIFIER_FIELDS = (
    "user_id", "sec_uid", "unique_id", "handle", "username", "page_handle",
)
TIME_FIELDS = ("created_at", "scraped_at")


def _to_iso(value) -> Optional[str]:
    """Normalize a time value to ISO 8601 UTC string, or pass through if unparseable."""
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        dt = value if value.tzinfo else value.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).isoformat()
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value, tz=timezone.utc).isoformat()
    if isinstance(value, str):
        try:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
            if not dt.tzinfo:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc).isoformat()
        except ValueError:
            return value
    return str(value)


def _detect_item_kind(item: dict) -> str:
    if "post_id" in item and item.get("post_id"):
        return "post"
    if any(item.get(f) for f in USER_IDENTIFIER_FIELDS):
        return "user"
    return "post"  # conservative default


def _missing_required(item: dict, kind: str) -> list[str]:
    if kind == "post":
        return [f for f in ("platform", "post_id", "url") if not item.get(f)]
    if kind == "user":
        missing = []
        if not item.get("platform"):
            missing.append("platform")
        if not any(item.get(f) for f in USER_IDENTIFIER_FIELDS):
            missing.append("any-of(" + "/".join(USER_IDENTIFIER_FIELDS) + ")")
        return missing
    return []


class DropItem(Exception):
    """Drop signal raised by clean()."""


def clean(item: dict, *, spider_name: str = "") -> dict:
    """Validate required fields and normalize timestamps. Mutates and returns
    the item; raises DropItem if required fields are missing."""
    kind = _detect_item_kind(item)
    missing = _missing_required(item, kind)
    if missing:
        raise DropItem(f"Missing required {missing} for {kind}-kind item")

    if not item.get("scraped_at"):
        item["scraped_at"] = datetime.now(timezone.utc).isoformat()

    if "source_spider" in item and not item.get("source_spider"):
        item["source_spider"] = spider_name

    for f in TIME_FIELDS:
        if f in item and item.get(f):
            item[f] = _to_iso(item[f])

    return item


@dataclass
class PipelineContext:
    """Per-run pipeline state. Use as: `async with PipelineContext(settings) as ctx:`."""

    settings: Settings
    spider_name: str = ""
    _jsonl_files: dict = field(default_factory=dict)

    async def __aenter__(self) -> "PipelineContext":
        self.settings.data_dir.mkdir(parents=True, exist_ok=True)
        return self

    async def __aexit__(self, exc_type, exc, tb):
        for f in self._jsonl_files.values():
            try:
                f.close()
            except Exception as ex:
                logger.warning("jsonl close failed: %s", ex)
        self._jsonl_files.clear()


def _jsonl_file_for(ctx: PipelineContext, platform: str) -> IO:
    date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    key = (platform, date)
    if key not in ctx._jsonl_files:
        shard = ctx.settings.data_dir / platform
        shard.mkdir(parents=True, exist_ok=True)
        ctx._jsonl_files[key] = (shard / f"{date}.jsonl").open("a", encoding="utf-8")
    return ctx._jsonl_files[key]


async def write_jsonl(item: dict, ctx: PipelineContext) -> None:
    platform = item.get("platform") or "unknown"
    f = _jsonl_file_for(ctx, platform)
    f.write(json.dumps(item, ensure_ascii=False, default=str) + "\n")
    f.flush()


async def run_pipelines(item: dict, ctx: PipelineContext) -> Optional[dict]:
    """clean → write_jsonl. Return None if dropped, item if persisted."""
    try:
        item = clean(item, spider_name=ctx.spider_name)
    except DropItem as e:
        logger.warning("clean drop: %s", e)
        return None

    await write_jsonl(item, ctx)
    return item
