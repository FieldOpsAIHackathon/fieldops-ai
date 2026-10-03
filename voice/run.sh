#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
VOICE_MODEL_DIR="${FIELDOPS_VOICE_MODELS:-$HOME/.local/share/fieldops-voice/models}"
VOICE_PORT="${FIELDOPS_VOICE_PORT:-8790}"
case "${1:-help}" in
  build)
    docker build -f voice/Dockerfile.base -t local/fieldops-natural-base:latest .
    docker build -f voice/Dockerfile -t local/fieldops-natural-voice:latest .
    ;;
  download)
    mkdir -p "$VOICE_MODEL_DIR"
    docker run --rm -v "$VOICE_MODEL_DIR:/models" -v "$PWD:/app:ro" -w /app \
      local/fieldops-natural-base:latest python3 -m voice.download
    ;;
  start)
    if docker container inspect fieldops-natural-voice >/dev/null 2>&1; then
      docker start fieldops-natural-voice
      exit 0
    fi
    # A separate loopback-only service; never stop the team's API or LLM.
    docker run -d --name fieldops-natural-voice --restart unless-stopped --gpus all \
      --network host --shm-size 1g -v "$VOICE_MODEL_DIR:/models:ro" \
      local/fieldops-natural-voice:latest python3 -m voice.server --port "$VOICE_PORT" \
      --origin http://localhost:8080 --origin http://127.0.0.1:8080 \
      --origin http://localhost:8000 --origin http://127.0.0.1:8000 \
      --origin http://localhost:8789 --origin http://127.0.0.1:8789 \
      --origin http://localhost:8793 --origin http://127.0.0.1:8793
    ;;
  status)
    curl -fsS "http://127.0.0.1:$VOICE_PORT/health"
    ;;
  stop)
    docker stop fieldops-natural-voice
    ;;
  *) echo 'Usage: bash voice/run.sh build|download|start|status|stop'; exit 2;;
esac
