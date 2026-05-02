"""CLI entry point.

Subcommands (incremental implementation per case.md §5.2):
- pilot:   Module 3 — small-batch sync extraction for prompt iteration
- run:     Module 4 — full 10K Batch API run (TODO)
- qa:      Module 5 — sampled QA helper (TODO)
- fetch:   Module 1 — fetcher-only smoke test (no LLM call)
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

from dotenv import load_dotenv
from rich.console import Console
from rich.table import Table

console = Console()


def _cmd_pilot(args: argparse.Namespace) -> int:
    from .pipeline import run_pilot

    input_path = Path(args.input)
    output_path = Path(args.output)
    if not input_path.exists():
        console.print(f"[red]Input not found: {input_path}[/red]")
        return 1

    stats = asyncio.run(
        run_pilot(input_path=input_path, output_path=output_path, concurrency=args.concurrency)
    )

    table = Table(title="Pilot run stats", show_header=False)
    table.add_row("Attempted", str(stats.total_firms_attempted))
    table.add_row("Succeeded", str(stats.total_firms_succeeded))
    table.add_row("Fetch failed", str(stats.total_firms_fetch_failed))
    table.add_row("LLM failed", str(stats.total_firms_llm_failed))
    table.add_row("Success rate", f"{stats.success_rate:.1%}")
    table.add_row("Input tokens", f"{stats.total_input_tokens:,}")
    table.add_row("Output tokens", f"{stats.total_output_tokens:,}")
    table.add_row("Elapsed", f"{stats.elapsed_seconds:.1f}s")
    console.print(table)
    console.print(f"[green]Output: {output_path}[/green]")
    return 0


def _cmd_fetch(args: argparse.Namespace) -> int:
    """Fetcher-only smoke test (no LLM call). Records per-firm fetch time + failure mode."""
    import csv as _csv

    from .fetcher import fetch_batch

    input_path = Path(args.input)
    if not input_path.exists():
        console.print(f"[red]Input not found: {input_path}[/red]")
        return 1

    with input_path.open() as f:
        reader = _csv.DictReader(f)
        urls = [row["website"].strip() for row in reader]

    results = asyncio.run(fetch_batch(urls, concurrency=args.concurrency))

    table = Table(title=f"Fetch results ({len(results)} URLs)")
    table.add_column("URL")
    table.add_column("Status")
    table.add_column("Elapsed (ms)")
    table.add_column("Error")
    for r in results:
        table.add_row(
            r.url,
            str(r.status_code) if r.status_code else "—",
            str(r.elapsed_ms),
            (r.error or "")[:60],
        )
    console.print(table)

    succeeded = sum(1 for r in results if r.html is not None)
    failure_rate = 1 - succeeded / len(results)
    console.print(
        f"\n[bold]Success rate: {succeeded}/{len(results)} ({succeeded / len(results):.1%})[/bold]"
    )
    if failure_rate > 0.20:
        console.print(
            "[yellow]⚠️  Failure rate > 20%. Per case.md §8 risk #2, escalate to Playwright + residential proxy.[/yellow]"
        )
    return 0


def _cmd_run(args: argparse.Namespace) -> int:
    console.print("[yellow]TODO Module 4: full 10K Batch API run not yet implemented[/yellow]")
    return 2


def _cmd_qa(args: argparse.Namespace) -> int:
    console.print("[yellow]TODO Module 5: sampled QA helper not yet implemented[/yellow]")
    return 2


def main(argv: list[str] | None = None) -> int:
    load_dotenv()

    parser = argparse.ArgumentParser(prog="mna-extract")
    sub = parser.add_subparsers(dest="command", required=True)

    p_pilot = sub.add_parser("pilot", help="Module 3 small-batch extraction")
    p_pilot.add_argument("--input", required=True, help="Input CSV (firm_name, website)")
    p_pilot.add_argument("--output", required=True, help="Output CSV path")
    p_pilot.add_argument("--concurrency", type=int, default=5)
    p_pilot.set_defaults(func=_cmd_pilot)

    p_fetch = sub.add_parser("fetch", help="Module 1 fetcher-only smoke test")
    p_fetch.add_argument("--input", required=True)
    p_fetch.add_argument("--concurrency", type=int, default=10)
    p_fetch.set_defaults(func=_cmd_fetch)

    p_run = sub.add_parser("run", help="Module 4 full 10K Batch API run (TODO)")
    p_run.set_defaults(func=_cmd_run)

    p_qa = sub.add_parser("qa", help="Module 5 sampled QA helper (TODO)")
    p_qa.set_defaults(func=_cmd_qa)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
