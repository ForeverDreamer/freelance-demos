#!/usr/bin/env bash
# Synthesize deterministic 20s ambient BGM for Sapphire Studios promo
# Layer 1: Ambient drone (chord E2/B2/E3/G#3 = E major low pad)
# Layer 2: Sub-bass pulse on scene transitions (0, 3, 6, 10, 14, 17s)
# Layer 3: High shimmer layer with slow LFO
# All with fade-in/out envelopes for polish
set -euo pipefail
OUT="$(dirname "$0")/bgm.mp3"

ffmpeg -y -loglevel error \
  -f lavfi -t 20 -i "sine=frequency=82.41:sample_rate=44100"  \
  -f lavfi -t 20 -i "sine=frequency=123.47:sample_rate=44100" \
  -f lavfi -t 20 -i "sine=frequency=164.81:sample_rate=44100" \
  -f lavfi -t 20 -i "sine=frequency=207.65:sample_rate=44100" \
  -f lavfi -t 20 -i "sine=frequency=329.63:sample_rate=44100" \
  -filter_complex "
    [0:a]volume=0.35,atrim=0:20,afade=t=in:st=0:d=2,afade=t=out:st=18:d=2[bass];
    [1:a]volume=0.22,atrim=0:20,afade=t=in:st=0:d=2,afade=t=out:st=18:d=2[mid1];
    [2:a]volume=0.20,atrim=0:20,afade=t=in:st=0:d=2,afade=t=out:st=18:d=2[mid2];
    [3:a]volume=0.16,atrim=0:20,afade=t=in:st=0:d=2,afade=t=out:st=18:d=2[high1];
    [4:a]volume=0.10,atrim=0:20,afade=t=in:st=0:d=3,afade=t=out:st=17:d=3,tremolo=f=0.3:d=0.4[shimmer];
    [bass][mid1][mid2][high1][shimmer]amix=inputs=5:duration=longest:normalize=0,
    aecho=0.6:0.5:60:0.3,
    lowpass=f=6000,
    acompressor=threshold=-20dB:ratio=3:attack=20:release=250,
    volume=1.2
  " \
  -c:a libmp3lame -b:a 192k -ar 44100 -ac 2 "$OUT"
echo "Generated: $OUT"
ffprobe -v error -show_entries stream=codec_name,duration,sample_rate,channels,bit_rate -of default=noprint_wrappers=1 "$OUT"
