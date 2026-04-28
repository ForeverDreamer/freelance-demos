"""Orchestrator: input CSV -> fetch -> extract -> flag -> output CSV.

TODO during 实测:
- Module 3 (pilot mode): in-memory list, single-pass, real-time progress bar
- Module 4 (full 10K run): switch to OpenAI Batch API + chunked checkpointing
"""

from __future__ import annotations

import asyncio
import csv
import time
from dataclasses import dataclass
from pathlib import Path

from rich.console import Console
from rich.progress import Progress

from .excel_writer import write_buyer_database
from .fetcher import HttpxFetcher, fetch_firm_pages
from .flagger import post_process
from .llm_extractor import LLMExtractor
from .schema import ExtractionRunStats, FirmRecord


console = Console()


@dataclass
class FirmInput:
    firm_name: str
    website: str


def load_input(csv_path: Path) -> list[FirmInput]:
    rows: list[FirmInput] = []
    with csv_path.open() as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(
                FirmInput(
                    firm_name=row["firm_name"].strip(),
                    website=row["website"].strip(),
                )
            )
    return rows


async def run_pilot(
    input_path: Path,
    output_path: Path,
    concurrency: int = 5,
) -> ExtractionRunStats:
    """Pilot mode: small batch with sync LLM calls, used for prompt iteration + spot check."""
    inputs = load_input(input_path)
    fetcher = HttpxFetcher()
    extractor = LLMExtractor()
    stats = ExtractionRunStats(total_firms_attempted=len(inputs))

    sem = asyncio.Semaphore(concurrency)
    records: list[FirmRecord] = []
    failures: list[dict] = []

    start = time.monotonic()

    async def _process_one(inp: FirmInput) -> None:
        async with sem:
            pages = await fetch_firm_pages(inp.website, max_subpages=3, fetcher=fetcher)
            if pages.concatenated_html is None:
                stats.total_firms_fetch_failed += 1
                failures.append(
                    {
                        "firm_name": inp.firm_name,
                        "website": inp.website,
                        "stage": "fetch",
                        "error": pages.homepage_error or "homepage unreachable",
                    }
                )
                return

            extraction = extractor.extract(
                firm_name=inp.firm_name,
                website=inp.website,
                html=pages.concatenated_html,
            )
            stats.total_input_tokens += extraction.input_tokens
            stats.total_output_tokens += extraction.output_tokens

            if extraction.record is None:
                stats.total_firms_llm_failed += 1
                failures.append(
                    {
                        "firm_name": inp.firm_name,
                        "website": inp.website,
                        "stage": "llm",
                        "error": extraction.error,
                    }
                )
                return

            # Override LLM-supplied source_urls with pipeline's actual fetched URLs.
            # Pipeline knows the truth; LLM may hallucinate.
            record_dict = extraction.record.model_dump()
            record_dict["source_urls"] = pages.fetched_urls
            authoritative = FirmRecord.model_validate(record_dict)

            processed = post_process(authoritative)
            records.append(processed)
            stats.total_firms_succeeded += 1

    with Progress(console=console) as progress:
        task = progress.add_task("Pilot run", total=len(inputs))

        async def _wrapped(inp: FirmInput) -> None:
            await _process_one(inp)
            progress.update(task, advance=1)

        await asyncio.gather(*[_wrapped(i) for i in inputs])

    stats.elapsed_seconds = time.monotonic() - start

    _write_output_csv(output_path, records)
    # Always write XLSX alongside CSV (client deliverable format).
    if records:
        write_buyer_database(records, output_path.with_suffix(".xlsx"))
    if failures:
        _write_failures_csv(output_path.with_suffix(".failures.csv"), failures)

    return stats


def _write_output_csv(path: Path, records: list[FirmRecord]) -> None:
    if not records:
        path.write_text("")
        return

    fieldnames = list(records[0].model_dump(mode="json").keys())
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in records:
            row = r.model_dump(mode="json")
            for k, v in list(row.items()):
                if isinstance(v, (list, dict)):
                    import json

                    row[k] = json.dumps(v, ensure_ascii=False)
            writer.writerow(row)


def _write_failures_csv(path: Path, failures: list[dict]) -> None:
    if not failures:
        return
    fieldnames = ["firm_name", "website", "stage", "error"]
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(failures)
