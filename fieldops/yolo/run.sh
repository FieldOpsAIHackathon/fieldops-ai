#!/usr/bin/env bash
# Run the YOLO scripts in the GPU container (NVIDIA's GB10 PyTorch + ultralytics).
#   bash fieldops/yolo/run.sh train
#   bash fieldops/yolo/run.sh count <images...> [--trap-id block-c-04]
#   bash fieldops/yolo/run.sh eval
#   bash fieldops/yolo/run.sh serve          # vision service on 127.0.0.1:8767 (fieldops/vision.py)
#   bash fieldops/yolo/run.sh vision <images...>
# Build the image once: docker build -t local/fieldops-yolo fieldops/yolo/
set -euo pipefail
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
DATA="${YOLO_DATA:-$HOME/hackathon-stack/yolo-data}"
RUNS="${YOLO_RUNS:-$HOME/hackathon-stack/yolo-runs}"
mkdir -p "$RUNS/.home" "$RUNS/.ultralytics"

cmd="${1:?train | count | eval | serve | vision}"; shift
net=()
case "$cmd" in
  train) args=(python3 -m fieldops.yolo.train "$@") ;;
  count) args=(python3 -m fieldops.yolo.count "$@") ;;
  eval)  args=(python3 -m fieldops.yolo.count --eval data/traps/manifest.json "$@") ;;
  serve) args=(python3 -m fieldops.vision --serve "$@"); net=(--network host) ;;
  vision) args=(python3 -m fieldops.vision "$@") ;;
  *) echo "unknown command: $cmd" >&2; exit 1 ;;
esac

exec docker run --rm --gpus all --ipc=host "${net[@]}" --user "$(id -u):$(id -g)" \
  -e HOME=/runs/.home -e YOLO_CONFIG_DIR=/runs/.ultralytics \
  -v "$REPO:/work" -v "$DATA:/data" -v "$RUNS:/runs" -w /work \
  local/fieldops-yolo:latest "${args[@]}"
