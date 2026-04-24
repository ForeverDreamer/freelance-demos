"""End-to-end pipeline: prompt -> Blender procedural render -> ffmpeg -> mp4.

Reads a one-line prompt, parses it into a scene config, shells out to Blender
in background mode to render a frame sequence, then shells out to ffmpeg to
assemble the sequence into an mp4.

Kept intentionally minimal. The production pipeline uses a long-lived Blender
process addressed as a TCP service (see ../ARCHITECTURE.md). This demo uses
--background mode so a reviewer can run it with only `blender` and `ffmpeg`
on PATH.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
BLENDER_SCRIPT = HERE / "blender_render.py"
FFMPEG_SCRIPT = HERE / "ffmpeg_export.sh"

COLOR_MAP = {
    "red": (0.8, 0.1, 0.1),
    "green": (0.1, 0.7, 0.2),
    "blue": (0.1, 0.3, 0.9),
    "yellow": (0.9, 0.8, 0.1),
    "purple": (0.5, 0.1, 0.7),
    "white": (0.95, 0.95, 0.95),
    "black": (0.05, 0.05, 0.05),
}


def parse_prompt(text: str) -> dict:
    """Parse one line of the form: <color> <shape> ... <N> seconds.

    Very permissive. Unknown words are ignored. Defaults fill in the gaps.
    """
    text = text.strip().lower()

    color = next((c for c in COLOR_MAP if c in text), "blue")
    shape = next((s for s in ("cube", "sphere", "cone", "torus") if s in text), "cube")
    bg = "white"
    for candidate in ("on white", "on black"):
        if candidate in text:
            bg = candidate.split()[-1]
            break

    duration_match = re.search(r"(\d+(?:\.\d+)?)\s*second", text)
    duration = float(duration_match.group(1)) if duration_match else 3.0

    return {
        "shape": shape,
        "color_rgb": list(COLOR_MAP[color]),
        "background_rgb": list(COLOR_MAP[bg]),
        "duration_seconds": duration,
        "fps": 30,
    }


def require_cmd(name: str) -> str:
    path = shutil.which(name)
    if not path:
        sys.exit(f"error: `{name}` not on PATH. Install it and retry.")
    return path


def render_frames(config: dict, frame_dir: Path) -> None:
    blender = require_cmd("blender")
    config_path = frame_dir / "config.json"
    config_path.write_text(json.dumps(config))

    cmd = [
        blender,
        "--background",
        "--python", str(BLENDER_SCRIPT),
        "--",
        "--config", str(config_path),
        "--out-dir", str(frame_dir),
    ]
    print(f"[pipeline] rendering {int(config['duration_seconds'] * config['fps'])} frames via Blender")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(result.stdout)
        print(result.stderr, file=sys.stderr)
        sys.exit(f"blender exited with code {result.returncode}")


def export_mp4(frame_dir: Path, out_path: Path, fps: int) -> None:
    require_cmd("ffmpeg")
    print(f"[pipeline] assembling mp4 via ffmpeg -> {out_path}")
    subprocess.run(
        ["bash", str(FFMPEG_SCRIPT), str(frame_dir), str(out_path), str(fps)],
        check=True,
    )


def main() -> None:
    ap = argparse.ArgumentParser(description="prompt -> Blender -> ffmpeg -> mp4")
    ap.add_argument("--prompt", type=Path, required=True, help="path to a one-line prompt file")
    ap.add_argument("--out", type=Path, required=True, help="output mp4 path")
    ap.add_argument("--keep-frames", action="store_true", help="keep intermediate PNG frames")
    args = ap.parse_args()

    config = parse_prompt(args.prompt.read_text())
    print(f"[pipeline] parsed config: {json.dumps(config, indent=2)}")

    with tempfile.TemporaryDirectory(prefix="vcp_") as tmp:
        frame_dir = Path(tmp)
        render_frames(config, frame_dir)
        export_mp4(frame_dir, args.out, config["fps"])

        if args.keep_frames:
            keep_dir = args.out.with_suffix("")
            keep_dir.mkdir(exist_ok=True)
            for png in frame_dir.glob("*.png"):
                shutil.copy(png, keep_dir)
            print(f"[pipeline] frames copied to {keep_dir}")

    print(f"[pipeline] done: {args.out}")


if __name__ == "__main__":
    main()
