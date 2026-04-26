"""Orchestrator: extract -> normalize -> rebuild for every .docx in input/. Per-file logging with three statuses (OK / PARTIAL / FAILED). Errors do not halt the batch. Log lines stream to stdout live; FAILED lines additionally dump traceback to stderr so root cause is visible during live demos."""

import argparse
import datetime as dt
import sys
import traceback
from pathlib import Path
from typing import List

from dotenv import load_dotenv

from extract import extract
from normalize import NormalizationFailed, normalize
from rebuild import rebuild
from schema import StandardizedDocument


def _ts() -> str:
    return dt.datetime.now().isoformat(timespec="seconds")


def _emit(line: str, log_lines: List[str]) -> None:
    log_lines.append(line)
    print(line, flush=True)


def _emit_traceback() -> None:
    print(traceback.format_exc(), file=sys.stderr, flush=True)


def _classify(normalized: StandardizedDocument) -> str:
    """PARTIAL when any of the four optional list sections is empty."""
    optional = [
        normalized.definitions,
        normalized.responsibilities,
        normalized.records,
        normalized.references,
    ]
    return "PARTIAL" if any(len(o) == 0 for o in optional) else "OK"


def process_file(
    path: Path,
    output_dir: Path,
    master_path: Path,
    log_lines: List[str],
) -> str:
    try:
        extracted = extract(path)
    except Exception as e:
        _emit(
            f"{_ts()} | {path.name} | FAILED | extract: {type(e).__name__}: {e}",
            log_lines,
        )
        _emit_traceback()
        return "FAILED"

    try:
        normalized = normalize(extracted)
    except (NormalizationFailed, Exception) as e:
        _emit(
            f"{_ts()} | {path.name} | FAILED | normalize: {type(e).__name__}: {e}",
            log_lines,
        )
        _emit_traceback()
        return "FAILED"

    try:
        doc = rebuild(normalized, master_path)
        out_path = output_dir / f"{path.stem}_standardized.docx"
        doc.save(str(out_path))
    except Exception as e:
        _emit(
            f"{_ts()} | {path.name} | FAILED | rebuild: {type(e).__name__}: {e}",
            log_lines,
        )
        _emit_traceback()
        return "FAILED"

    status = _classify(normalized)
    _emit(f"{_ts()} | {path.name} | {status} | wrote {out_path.name}", log_lines)
    return status


def main() -> int:
    load_dotenv()
    p = argparse.ArgumentParser()
    p.add_argument("--input", required=True, type=Path)
    p.add_argument("--output", required=True, type=Path)
    p.add_argument("--master", required=True, type=Path)
    p.add_argument("--log", required=True, type=Path)
    args = p.parse_args()

    args.output.mkdir(parents=True, exist_ok=True)
    args.log.parent.mkdir(parents=True, exist_ok=True)

    log_lines: List[str] = []
    counts = {"OK": 0, "PARTIAL": 0, "FAILED": 0}

    for docx_path in sorted(args.input.glob("*.docx")):
        status = process_file(docx_path, args.output, args.master, log_lines)
        counts[status] += 1

    summary = (
        f"Processed {sum(counts.values())} files. "
        f"OK: {counts['OK']}, PARTIAL: {counts['PARTIAL']}, FAILED: {counts['FAILED']}"
    )
    _emit(f"{_ts()} | summary | {summary}", log_lines)
    args.log.write_text("\n".join(log_lines) + "\n", encoding="utf-8")
    return 0 if counts["FAILED"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
