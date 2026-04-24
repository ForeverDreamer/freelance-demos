#!/usr/bin/env bash
# Assemble a PNG frame sequence into mp4.
# Usage: ffmpeg_export.sh <frame-dir> <output-mp4> <fps>
set -euo pipefail

FRAME_DIR="${1:?frame directory required}"
OUT="${2:?output mp4 path required}"
FPS="${3:-30}"

ffmpeg -y \
  -framerate "$FPS" \
  -i "$FRAME_DIR/frame_%04d.png" \
  -c:v libx264 \
  -pix_fmt yuv420p \
  -crf 18 \
  "$OUT"
