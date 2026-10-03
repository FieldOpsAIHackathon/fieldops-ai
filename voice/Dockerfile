# Reuse the GB10-compatible NVIDIA torch build already proven by vision.
ARG BASE_IMAGE=local/fieldops-natural-base:latest
FROM ${BASE_IMAGE}
WORKDIR /app
COPY voice /app/voice
COPY dashboard /app/dashboard
COPY data/traps /app/data/traps
ENV HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 HF_HUB_DISABLE_TELEMETRY=1 \
    DO_NOT_TRACK=1 TOKENIZERS_PARALLELISM=false PYTHONUNBUFFERED=1 \
    FIELDOPS_VOICE_MODELS=/models
CMD ["python3", "-m", "voice.server", "--host", "127.0.0.1", "--port", "8790"]
