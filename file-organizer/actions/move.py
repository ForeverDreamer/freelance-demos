"""Move action: relocate a file into the rule's target directory."""
from __future__ import annotations

import shutil
from pathlib import Path
from typing import Union


def move(source_path: Union[str, Path], target_dir: Union[str, Path]) -> Path:
    """Move source_path into target_dir.

    Creates target_dir (and parents) if missing. If a file with the same
    name already exists in target_dir, appends a numeric suffix so nothing
    is overwritten. Returns the final destination path.
    """
    source = Path(source_path)
    target = Path(target_dir)
    target.mkdir(parents=True, exist_ok=True)

    destination = target / source.name
    counter = 1
    while destination.exists():
        destination = target / f"{source.stem}-{counter}{source.suffix}"
        counter += 1

    shutil.move(str(source), str(destination))
    return destination
