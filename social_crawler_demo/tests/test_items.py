"""Smoke tests for demo items."""
from __future__ import annotations

from demo.items import SocialPostItem


def test_item_instantiation():
    item = SocialPostItem()
    item["platform"] = "twitter"
    item["post_id"] = "1"
    item["url"] = "https://x.com/a/status/1"
    item["content_text"] = "hello"
    assert item["platform"] == "twitter"


def test_item_platform_specific_fields():
    item = SocialPostItem()
    item["platform"] = "instagram"
    item["shortcode"] = "C7abc123"
    item["media_type"] = "reel"
    assert item["shortcode"] == "C7abc123"
    assert item["media_type"] == "reel"
