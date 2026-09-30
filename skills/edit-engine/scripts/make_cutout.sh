#!/bin/bash
# Cut the speaker out of a talking-head video (transparent background). macOS 14+ only.
#
#   make_cutout.sh <in.mp4> <out.webm> [width=1080] [webm|mov] [startSec] [durSec]
#
# webm  VP9 with alpha. Chrome, and therefore HyperFrames, composites it with real
#       transparency. Every frame is a keyframe (-g 1): the renderer seeks per frame,
#       and a longer GOP lets the cut-out drift a frame against the raw footage
#       underneath, which shows as a double edge.
# mov   ProRes 4444 with alpha, for ffmpeg/NLE use (ffmpeg's overlay cannot read VP9 alpha).
#
# Masking: Vision person segmentation (accurate, good hair edges) united with the
# subject-lift mask (keeps held objects such as a microphone), lightly smoothed over
# time against flicker. Cost: roughly 3 minutes per minute of 1080p footage on Apple
# Silicon. Make the cut-out once per final cut; re-running it for every graphics
# change wastes the time.
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [ $# -lt 2 ]; then sed -n '2,4p' "$0" | sed 's/^# \{0,1\}//'; exit 2; fi
BIN="${EDIT_ENGINE_BIN:-$HOME/.cache/edit-engine}/cutout_video"
if [ ! -x "$BIN" ] || [ "$DIR/cutout_video.swift" -nt "$BIN" ]; then
  mkdir -p "$(dirname "$BIN")"
  swiftc -O -suppress-warnings "$DIR/cutout_video.swift" -o "$BIN"
fi

IN="$1"; OUT="$2"; OUTW="${3:-1080}"; FMT="${4:-webm}"; START="${5:-0}"; DUR="${6:-0}"
# The helper emits frames at the SOURCE size (orientation applied), so tell ffmpeg that size.
SW=$(ffprobe -v error -select_streams v:0 -show_entries stream=width -of csv=p=0 "$IN")
SH=$(ffprobe -v error -select_streams v:0 -show_entries stream=height -of csv=p=0 "$IN")
ROT=$(ffprobe -v error -select_streams v:0 -show_entries stream_side_data=rotation -of csv=p=0 "$IN" | head -1 || true)
if [ "${ROT#-}" = "90" ] || [ "${ROT#-}" = "270" ]; then T="$SW"; SW="$SH"; SH="$T"; fi
FPS=$(ffprobe -v error -select_streams v:0 -show_entries stream=r_frame_rate -of csv=p=0 "$IN")

if [ "$FMT" = "mov" ]; then
  CODEC=(-c:v prores_ks -profile:v 4444 -pix_fmt yuva444p10le)
else
  CODEC=(-c:v libvpx-vp9 -pix_fmt yuva420p -b:v 6M -deadline good -cpu-used 5 -row-mt 1 -tile-columns 2 -g 1)
fi

"$BIN" "$IN" "$START" "$DUR" | ffmpeg -y -v error \
  -f rawvideo -pix_fmt bgra -s "${SW}x${SH}" -r "$FPS" -i - \
  -vf "scale=${OUTW}:-2:flags=lanczos" "${CODEC[@]}" "$OUT"
echo "cut-out -> $OUT"
