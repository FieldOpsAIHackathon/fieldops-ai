# FieldOps natural voice

A separate local speech service for the dashboard. The GB10 runs Kokoro-82M on
CUDA; the browser streams Opus (PCM when Opus is unsupported) and schedules each
sentence while later sentences are generated. The replay, calculations and
phone alerts never depend on this service.

## Use it

On the demo Mac, with the SSH tunnel running:

- Dashboard: http://127.0.0.1:8790/index.html
- Voice studio: http://127.0.0.1:8790/voice.html

The running preview includes the verified assistant controls below. The service/client
branch keeps shared `index.html` and `intelligence.*` untouched so the concurrent
voice-first UI work can integrate this API without a UI merge conflict.

In the preview, open **Ask FieldOps**, ask about a block, then select **Listen to answer**.
**Read answers aloud** speaks subsequent answers automatically. **Stop voice**,
closing the assistant, or changing date/block/species cancels playback. Voice
studio compares four voices and saves voice/pace preferences for that origin.

`Orchard` is a 70% Heart / 30% Bella blend. `Heart` preserves Coach's voice identity
for comparison; `Bella` and `Fenrir` offer alternatives. All four are model-supplied
voices, with no custom voice cloning. Naturalness is subjective: listen to the
comparison before choosing a recording voice.

## Setup on GB10

The existing `local/fieldops-yolo:latest` image supplies NVIDIA PyTorch that works
on the GB10's ARM64/SM121 hardware. New voice images do not replace the vision,
LLM, OpenShell, API, or deployment services.

```bash
# In the FieldOps checkout; internet needed only for build and model download.
bash voice/run.sh build
bash voice/run.sh download
bash voice/run.sh start
bash voice/run.sh status
```

`FIELDOPS_VOICE_MODELS` selects a model directory (default
`~/.local/share/fieldops-voice/models`); `FIELDOPS_VOICE_PORT` defaults to `8790`.
The deployed demo uses `/home/dell/fieldops-natural-voice/models`, with source in
`/home/dell/fieldops-natural-voice`. The container is `fieldops-natural-voice`,
with restart policy `unless-stopped` and a read-only model mount.

From the Mac:

```bash
ssh -N -L 127.0.0.1:8790:127.0.0.1:8790 dell@promaxgb10-887f.local
```

The API binds only to loopback. Runtime has Hugging Face and Transformers offline
mode enabled; every model/voice is loaded by local path. There is no browser
speech-service or cloud fallback. A missing voice service produces a visible
error while the dashboard and text answers keep working. Microphone input is the
existing browser-local dictation feature; this change is speech output.

To deploy a source update, rebuild the image, then recreate only this container:

```bash
bash voice/run.sh build
docker stop fieldops-natural-voice
docker rm fieldops-natural-voice
bash voice/run.sh start
```

Why the base image adds a library: the venue's NVIDIA vLLM-derived image contains
a 14 KB cuFFT placeholder. Kokoro needs FFT synthesis; the base image installs
`nvidia-cufft==12.2.0.57` and loads it ahead of the stub. NVIDIA's existing torch,
numpy and transformers versions are constrained during installation.

## Dashboard/API contract

Load `<script src="voice.js"></script>` before the assistant UI module.
`dashboard/voice.js` exports `window.fieldopsVoice`:

```js
await fieldopsVoice.health();
fieldopsVoice.voice = 'orchard';
fieldopsVoice.speed = 1.0;              // 0.85–1.15
fieldopsVoice.savePreferences();
await fieldopsVoice.speak('Block C has reached 261 DD since biofix.');
fieldopsVoice.stop();
```

Call `speak` from a user gesture (or after that user enabled read-aloud) so the
browser permits audio playback. The returned promise covers generation, not the
end of playback. Listen to the `state` event for `idle`, `preparing`, `speaking`,
or `error`; `speaking` carries browser `firstAudioMs`. `metrics` reports server
processing time (including encoding/writes/cache) and audio duration.

- `GET /health`: readiness, engine/device, voice list. Ready only after warmup.
- `POST /stream`: `{input, voice, speed, response_format: "opus"|"pcm"}`;
  newline-delimited `start`, `audio`, `done` events (or `error`). Opus audio is
  base64 `audio`; PCM is base64 `pcm`, mono signed 16-bit little endian, 24 kHz.
- `POST /v1/audio/speech`: same text/voice/speed fields, `response_format:"wav"`
  only; returns a complete 24 kHz WAV. No external API is contacted.

Text is bounded to 2,400 characters. A single inference lock prevents concurrent
GPU generation; a busy caller gets 429, not an unbounded queue. Up to 32 MB / 128
sentence results are cached in memory. Stop aborts fetch and all scheduled audio;
stale responses are ignored. Server inference stops at the next sentence boundary
once it observes a disconnected socket. Date/DD/temperature/Markdown cleanup
changes pronunciation, never the numbers or deterministic decisions.

Browser origins are explicitly allowed: file/null, voice port, and loopback
8000/8080/8789/8793 through the launch script. Add `--origin` when using another
local preview origin. The HTTP service serves dashboard assets and synthetic trap
references only, never the repository's credentials, database or model weights.

## Measured on October 3, 2026

Real GB10 synthesis, container networking disabled, CUDA tensor allocation about
0.60 GB:

| Case | Generation | Audio duration |
|---|---:|---:|
| Cold load | 6.265 s | — |
| First warmup | 1.890 s | 2.325 s |
| Warm two-sentence update | 95 ms | 5.7 s |
| Warm four-sentence update | 337 ms | 10.9 s |

These are individual samples, not p95 measurements or a measured comparison with
the phone. Warmup happens before readiness. Over the busy venue Wi-Fi/SSH tunnel,
four Opus previews took 265–897 ms to receive first audio; the browser's initial
full briefing was about 1 second. A 9.9-second Orchard sample compressed to 41 KB,
versus 474 KB PCM. Synthesis speed and click-to-play latency are different metrics.

Qwen3-TTS 1.7B CustomVoice was also tested on the GB10 with networking disabled,
BF16 and SDPA. It used 4.21 GB of CUDA tensors and generated 5.2 seconds of audio
in 8.628 seconds, then 10 seconds in 16.895 seconds (after a 42.915-second load).
That non-streaming reference implementation is slower than real time on this
machine. It remains an optional benchmark, not the live dashboard engine; these
results do not measure an optimized Qwen streaming implementation.

Coach's `KokoroSpeech.kt` informed the separate generation/playback queues,
immediate cancellation and voice comparison. The server avoids its cold graph
load on the first utterance. No Coach files were modified.

## Verification

```bash
python3 -m voice.check             # stdlib protocol checks; codec check skips without soundfile
node voice/check_client.cjs        # scheduling, stop, late replies, errors, truncated audio
python3 scripts/ci_check.py        # existing FieldOps replay/API/assets checks
```

Inside the voice image, run `python3 -m voice.check` to include the Opus round-trip.
`voice/benchmark_models.py` writes actual audio and timings. Its Qwen mode is an
isolated optional evaluation; the dashboard's selected engine is Kokoro. To
reproduce Qwen, build `voice/Dockerfile.qwen`, download with
`python3 -m voice.download --qwen`, then mount models and samples and run
`python3 voice/benchmark_models.py --engine qwen` in that image. The CPU TorchAudio
wheel avoids a CUDA 13.0/13.2 wheel mismatch; model inference still uses CUDA.

Sources: [Kokoro](https://github.com/hexgrad/kokoro),
[voice definitions](https://huggingface.co/hexgrad/Kokoro-82M/blob/main/VOICES.md),
[Qwen3-TTS](https://github.com/QwenLM/Qwen3-TTS),
[SoundFile](https://python-soundfile.readthedocs.io/en/latest/).
