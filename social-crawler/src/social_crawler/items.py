"""Dataclass items, one schema per platform.

The demo writes these directly to JSONL via `dataclasses.asdict()`. The paid
version reuses the same schemas for MongoDB upsert (keyed by `post_id`) and
PostgreSQL warehouse rows.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class SocialPostItem:
    """Common fields shared across platforms."""

    platform: str = ""
    post_id: str = ""
    url: str = ""

    # Author
    author_handle: str = ""
    author_display_name: str = ""
    author_id: str = ""
    author_verified: Optional[bool] = None

    # Content
    content_text: str = ""
    language: str = ""
    media_urls: list[str] = field(default_factory=list)
    media_types: list[str] = field(default_factory=list)

    # Time (clean pipeline normalizes to ISO 8601 UTC)
    created_at: Optional[str] = None
    scraped_at: str = ""

    # Common engagement metrics
    likes_count: Optional[int] = None
    comments_count: Optional[int] = None

    # Source tracking
    source_spider: str = ""
    source_query: str = ""
    raw_snapshot: dict = field(default_factory=dict)


@dataclass
class TikTokVideoItem(SocialPostItem):
    """One TikTok video. post_id is the numeric aweme_id from the URL."""

    platform: str = "tiktok"

    plays_count: Optional[int] = None
    shares_count: Optional[int] = None
    collects_count: Optional[int] = None  # bookmarks/saves

    description: str = ""
    duration_ms: Optional[int] = None
    cover_url: str = ""
    play_url: str = ""

    # Music
    music_id: str = ""
    music_title: str = ""
    music_author: str = ""

    hashtags: list[str] = field(default_factory=list)
    mentions: list[str] = field(default_factory=list)


@dataclass
class TikTokUserItem:
    """TikTok user profile header. JSONL-only by design."""

    platform: str = "tiktok"
    user_id: str = ""
    sec_uid: str = ""
    unique_id: str = ""
    nickname: str = ""
    bio: str = ""
    bio_link: str = ""
    avatar_url: str = ""
    is_verified: bool = False
    is_private: bool = False
    followers_count: Optional[int] = None
    following_count: Optional[int] = None
    hearts_count: Optional[int] = None
    videos_count: Optional[int] = None
    scraped_at: str = ""


@dataclass
class TwitterPostItem(SocialPostItem):
    """Twitter (X) tweet. post_id is the numeric status id."""

    platform: str = "twitter"

    retweets_count: Optional[int] = None
    quotes_count: Optional[int] = None
    views_count: Optional[int] = None
    bookmarks_count: Optional[int] = None

    is_retweet: Optional[bool] = None
    is_quote: Optional[bool] = None
    is_reply: Optional[bool] = None
    in_reply_to_id: Optional[str] = None
    in_reply_to_handle: str = ""

    hashtags: list[str] = field(default_factory=list)
    mentions: list[str] = field(default_factory=list)
    urls: list[str] = field(default_factory=list)


@dataclass
class TwitterUserItem:
    """Twitter (X) user profile header. JSONL-only by design."""

    platform: str = "twitter"
    user_id: str = ""
    handle: str = ""
    display_name: str = ""
    bio: str = ""
    location: str = ""
    website: str = ""
    verified: bool = False
    followers_count: Optional[int] = None
    following_count: Optional[int] = None
    profile_image_url: str = ""
    scraped_at: str = ""


@dataclass
class FacebookPostItem(SocialPostItem):
    """Facebook Page post. post_id is the FB numeric id or pfbid string."""

    platform: str = "fb"

    reactions_total: Optional[int] = None
    reactions_breakdown: dict = field(default_factory=dict)
    shares_count: Optional[int] = None
    page_id: str = ""
    post_type: str = ""  # "post" | "reel" | "video" | "photo"

    media_alts: list[str] = field(default_factory=list)


@dataclass
class FacebookPageItem:
    """Facebook Page profile header. JSONL-only by design."""

    platform: str = "fb"
    page_handle: str = ""
    page_id: str = ""
    page_name: str = ""
    page_url: str = ""
    bio: str = ""
    category: str = ""
    verified: bool = False
    follower_count: Optional[int] = None
    avatar_url: str = ""
    scraped_at: str = ""


@dataclass
class InstagramPostItem(SocialPostItem):
    """Instagram post / reel / IGTV. post_id is the IG shortcode (base64-like)."""

    platform: str = "instagram"

    saves_count: Optional[int] = None
    plays_count: Optional[int] = None  # reel views

    hashtags: list[str] = field(default_factory=list)
    mentions: list[str] = field(default_factory=list)
    cover_url: str = ""
    post_type: str = ""  # "p" | "reel" | "tv"

    # True if alt text is IG-vision auto-generated ("Photo by X. May be an
    # image of...") rather than a user-written caption. Reels generally have
    # real captions; posts vary by account.
    is_alt_text_auto: Optional[bool] = None


@dataclass
class InstagramUserItem:
    """Instagram user profile header. JSONL-only by design."""

    platform: str = "instagram"
    username: str = ""
    user_id: str = ""
    display_name: str = ""
    bio: str = ""
    bio_link: str = ""
    avatar_url: str = ""
    is_verified: bool = False
    is_private: bool = False
    posts_count: Optional[int] = None
    followers_count: Optional[int] = None
    following_count: Optional[int] = None
    scraped_at: str = ""
