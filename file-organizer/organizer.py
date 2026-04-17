"""File organizer entry point.

Runs a watchdog observer against a directory and applies YAML/JSON rules
(currently: move action) to incoming files. Errors in rule application
are logged and do NOT halt the observer.
"""
from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path

from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

from actions import move as move_action
from config import Config, load_config, match_rule

logger = logging.getLogger("file-organizer")


class OrganizerHandler(FileSystemEventHandler):
    def __init__(self, config: Config) -> None:
        self.config = config

    def on_created(self, event: FileSystemEvent) -> None:
        if event.is_directory:
            return
        self._process(event.src_path)

    def on_moved(self, event: FileSystemEvent) -> None:
        if event.is_directory:
            return
        # React to files moved INTO the watched folder
        self._process(event.dest_path)

    def _process(self, src_path: str) -> None:
        """Match the file against rules and apply the action.

        Any exception is caught and logged; the observer keeps running.
        """
        try:
            rule = match_rule(self.config, src_path)
            if rule is None:
                logger.info("[SKIP] %s (no rule matched)", src_path)
                return
            if rule.action is None or rule.action.type != "move":
                logger.warning(
                    "[UNSUPPORTED] rule=%s action=%s",
                    rule.name,
                    rule.action.type if rule.action else None,
                )
                return
            destination = move_action(src_path, rule.action.target)
            logger.info(
                "[MATCH] rule=%s action=move src=%s dest=%s",
                rule.name,
                src_path,
                destination,
            )
        except Exception as exc:  # noqa: BLE001 - observer must not halt
            logger.error("[ERROR] src=%s err=%s", src_path, exc)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Watch a folder, apply YAML rules, route files within 2s of detection."
    )
    parser.add_argument("--config", required=True, help="Path to rules YAML or JSON file")
    parser.add_argument("--watch", required=True, help="Directory to watch")
    parser.add_argument("--log-level", default="INFO", help="Logging level (default: INFO)")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=args.log_level,
        format="%(asctime)s %(levelname)s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    config_path = Path(args.config)
    watch_path = Path(args.watch)

    if not config_path.exists():
        logger.error("Config file not found: %s", config_path)
        return 1
    if not watch_path.exists() or not watch_path.is_dir():
        logger.error("Watch directory not found or not a directory: %s", watch_path)
        return 1

    config = load_config(config_path)
    logger.info("Loaded %d rules from %s", len(config.rules), config_path)
    logger.info("Watching %s", watch_path.resolve())

    handler = OrganizerHandler(config)
    observer = Observer()
    observer.schedule(handler, str(watch_path), recursive=False)
    observer.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Stopping observer")
        observer.stop()
    observer.join()
    return 0


if __name__ == "__main__":
    sys.exit(main())
