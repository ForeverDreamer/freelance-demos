"""Round-trip tests for the dataclass items.

We don't run a live spider in unit tests (it would require a Chrome instance
and platform login). Instead we verify that:

- `dataclasses.asdict()` produces JSON-serializable dicts
- `clean()` validates required fields and normalizes timestamps
- `_detect_item_kind()` correctly distinguishes post-kind from user-kind
"""
from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime, timezone

import pytest

from social_crawler.items import (
    InstagramPostItem,
    InstagramUserItem,
    TikTokUserItem,
    TikTokVideoItem,
    TwitterPostItem,
    TwitterUserItem,
)
from social_crawler.pipelines import DropItem, _detect_item_kind, clean


def test_tiktok_video_item_round_trip():
    item = TikTokVideoItem(
        post_id="1234567890",
        url="https://www.tiktok.com/@user/video/1234567890",
        author_handle="user",
        content_text="hello #world",
        hashtags=["world"],
    )
    d = asdict(item)
    assert d["platform"] == "tiktok"
    assert d["post_id"] == "1234567890"
    assert d["hashtags"] == ["world"]
    # Must be JSON-serializable
    json.dumps(d)


def test_clean_post_kind_normalizes_iso_time():
    item_dict = asdict(
        TwitterPostItem(
            post_id="100",
            url="https://x.com/u/status/100",
            author_handle="u",
            created_at="2026-04-29T12:00:00Z",
        )
    )
    cleaned = clean(item_dict, spider_name="twitter_user")
    assert cleaned["created_at"] == "2026-04-29T12:00:00+00:00"
    assert cleaned["scraped_at"]  # filled if missing


def test_clean_user_kind_passes_with_username():
    item_dict = asdict(InstagramUserItem(username="apple"))
    cleaned = clean(item_dict)
    # Required check passes because username is set
    assert cleaned["username"] == "apple"


def test_clean_post_kind_drops_when_url_missing():
    item_dict = asdict(TikTokVideoItem(post_id="1", url=""))
    with pytest.raises(DropItem):
        clean(item_dict)


def test_clean_user_kind_drops_when_no_identifier():
    item_dict = asdict(TwitterUserItem(handle=""))
    with pytest.raises(DropItem):
        clean(item_dict)


def test_detect_item_kind_post():
    item = asdict(TikTokVideoItem(post_id="1", url="https://x"))
    assert _detect_item_kind(item) == "post"


def test_detect_item_kind_user_via_username():
    item = asdict(InstagramUserItem(username="apple"))
    assert _detect_item_kind(item) == "user"


def test_detect_item_kind_user_via_unique_id():
    item = asdict(TikTokUserItem(unique_id="natgeo"))
    assert _detect_item_kind(item) == "user"
