"""click CLI entrypoint. One subcommand per spider.

Run:
    uv run python -m social_crawler.main --help
    uv run python -m social_crawler.main tk-user --username natgeo --max 5
"""
from __future__ import annotations

import asyncio
import logging
import sys

import click

from social_crawler.config import Settings


def _configure_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        stream=sys.stderr,
    )


@click.group()
@click.option("--log-level", default=None, help="DEBUG/INFO/WARNING/ERROR (default from .env)")
@click.pass_context
def cli(ctx: click.Context, log_level: str | None) -> None:
    """social_crawler — pure asyncio + Playwright social platform crawler."""
    settings = Settings.from_env()
    if log_level:
        settings.log_level = log_level
    _configure_logging(settings.log_level)
    ctx.obj = settings


# ────────── TikTok ──────────


@cli.command(name="tk-user")
@click.option("--username", required=True, help="TikTok @handle (without @)")
@click.option("--max", "max_videos", default=5, type=int, help="Max video items")
@click.option("--scroll-distance", default=600, type=int)
@click.pass_obj
def tk_user_cmd(settings: Settings, username: str, max_videos: int,
                scroll_distance: int) -> None:
    """Crawl TikTok user profile (header + video grid)."""
    from social_crawler.spiders.tiktok_user import crawl
    asyncio.run(crawl(
        settings=settings,
        username=username,
        max_videos=max_videos,
        scroll_distance=scroll_distance,
    ))


@cli.command(name="tk-video")
@click.option("--username", required=True, help="TikTok @handle whose feed to walk")
@click.option("--max", "max_videos", default=5, type=int)
@click.pass_obj
def tk_video_cmd(settings: Settings, username: str, max_videos: int) -> None:
    """Crawl TikTok video detail metadata across @username's feed.

    Walks the user's profile, clicks the first video card to open the detail
    modal, then advances with arrow-right (Go to next video) `max` times. Per
    video extracts full description, hashtags, mentions, music_title,
    duration_ms, likes, comments, collects (bookmarks/saves).
    """
    from social_crawler.spiders.tiktok_video import crawl
    asyncio.run(crawl(
        settings=settings,
        username=username,
        max_videos=max_videos,
    ))


@cli.command(name="tk-hashtag")
@click.option("--hashtag", required=True,
              help="Hashtag name without leading # (case-insensitive)")
@click.option("--max", "max_videos", default=5, type=int)
@click.option("--scroll-distance", default=800, type=int)
@click.pass_obj
def tk_hashtag_cmd(settings: Settings, hashtag: str, max_videos: int,
                   scroll_distance: int) -> None:
    """Crawl TikTok hashtag page (/tag/<name>) — grid of videos using the tag.

    Click-flow: clean homepage → search popup → fill <hashtag> → Enter →
    /search?q= → click first `search-common-link[href="/tag/<name>"]` →
    SPA navigate /tag/<name> → grid extract. Per-item likes/comments are not
    exposed on the hashtag page; use tk-video for engagement metrics.
    """
    from social_crawler.spiders.tiktok_hashtag import crawl
    asyncio.run(crawl(
        settings=settings,
        hashtag=hashtag,
        max_videos=max_videos,
        scroll_distance=scroll_distance,
    ))


# ────────── Facebook ──────────


@cli.command(name="fb-feed")
@click.option("--page-handle", required=True,
              help="FB Page vanity URL slug (e.g. nasaearth, cocacola)")
@click.option("--max", "max_posts", default=5, type=int)
@click.option("--scroll-distance", default=800, type=int)
@click.pass_obj
def fb_feed_cmd(settings: Settings, page_handle: str, max_posts: int,
                scroll_distance: int) -> None:
    """Crawl Facebook Page feed (header + posts)."""
    from social_crawler.spiders.fb_feed import crawl
    asyncio.run(crawl(
        settings=settings,
        page_handle=page_handle,
        max_posts=max_posts,
        scroll_distance=scroll_distance,
    ))


# ────────── Twitter (X) ──────────


@cli.command(name="tw-user")
@click.option("--handle", required=True, help="X @screen_name (without @)")
@click.option("--max", "max_tweets", default=5, type=int)
@click.option("--scroll-distance", default=800, type=int)
@click.pass_obj
def tw_user_cmd(settings: Settings, handle: str, max_tweets: int,
                scroll_distance: int) -> None:
    """Crawl Twitter (X) user timeline (header + tweets)."""
    from social_crawler.spiders.twitter_user import crawl
    asyncio.run(crawl(
        settings=settings,
        handle=handle,
        max_tweets=max_tweets,
        scroll_distance=scroll_distance,
    ))


# ────────── Instagram ──────────


@cli.command(name="ig-profile")
@click.option("--username", required=True, help="IG @handle (without @)")
@click.option("--max", "max_posts", default=5, type=int)
@click.option("--scroll-distance", default=800, type=int)
@click.pass_obj
def ig_profile_cmd(settings: Settings, username: str, max_posts: int,
                   scroll_distance: int) -> None:
    """Crawl Instagram profile (header + posts/reels grid)."""
    from social_crawler.spiders.instagram_profile import crawl
    asyncio.run(crawl(
        settings=settings,
        username=username,
        max_posts=max_posts,
        scroll_distance=scroll_distance,
    ))


if __name__ == "__main__":
    cli()
