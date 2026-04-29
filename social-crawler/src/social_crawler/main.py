"""click CLI entrypoint. One subcommand per spider.

Public demo scope: 2 spiders (Twitter user timeline + TikTok user profile).
The paid version expands this to 6 spiders × 4 platforms; see README.

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


if __name__ == "__main__":
    cli()
