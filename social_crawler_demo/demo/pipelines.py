"""Single-file JsonLines pipeline for public demo.

Paid version adds: clean / dedup / mongo / postgres / google_sheets.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from itemadapter import ItemAdapter
from scrapy.crawler import Crawler


class JsonLinesPipeline:
    def __init__(self, data_dir: str):
        self.data_dir = Path(data_dir)
        self._files: dict[tuple[str, str], object] = {}

    @classmethod
    def from_crawler(cls, crawler: Crawler) -> "JsonLinesPipeline":
        return cls(data_dir=crawler.settings.get("DATA_DIR", "./data"))

    def open_spider(self, spider):
        self.data_dir.mkdir(parents=True, exist_ok=True)

    def close_spider(self, spider):
        for f in self._files.values():
            try:
                f.close()
            except Exception:
                pass
        self._files.clear()

    def _file_for(self, platform: str):
        date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        key = (platform, date)
        if key not in self._files:
            shard_dir = self.data_dir / platform
            shard_dir.mkdir(parents=True, exist_ok=True)
            self._files[key] = (shard_dir / f"{date}.jsonl").open("a", encoding="utf-8")
        return self._files[key]

    def process_item(self, item, spider):
        adapter = ItemAdapter(item)
        platform = adapter.get("platform") or "unknown"
        f = self._file_for(platform)
        f.write(json.dumps(adapter.asdict(), ensure_ascii=False, default=str) + "\n")
        f.flush()
        return item
