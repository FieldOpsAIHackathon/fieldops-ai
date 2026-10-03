# AGENTS.md — FieldOps (fieldops-ai)

Instructions for coding agents working in this repo. Read this before writing code.

## What this is

FieldOps is a one-day hackathon build (Dell x NVIDIA AI Hackathon, **October 3, 2026**). It counts
insects on sticky traps from camera images, tracks the pest flight curve, and tells an orchard
grower when to spray — all running locally on a GB10 box with no internet.

The full pitch and priorities live in [FieldOps_Hackathon_Plan.md](FieldOps_Hackathon_Plan.md).
That document is the source of truth for scope. This one is the source of truth for *how to build*.

**The repo is currently empty.** Everything below describes the target, not existing code.

## The one rule that matters

The demo is a **season replay**: weeks of trap counts and temperatures play back in 30 seconds, the
flight curve rises, FieldOps calls the biofix, the degree-day clock starts, and a phone buzzes with
a spray-window alert. The live webcam count is a supporting trick.

So: **the replay must work end to end before anything gets polished.** If you are choosing between
making the replay path work and making any other thing better, make the replay work. If live
inference is flaky on stage, the replay alone still tells the whole story — never let the replay
depend on live inference.

## Integration contract

One JSON shape for counts. Everything crosses module boundaries in this form; do not invent variants.

```json
{
  "trap_id": "block-c-04",
  "timestamp": "2026-05-12T14:03:00Z",
  "species": "codling_moth",
  "count": 7
}
```

- `trap_id` — string, stable per trap.
- `timestamp` — ISO 8601, UTC, with `Z`.
- `species` — snake_case key from the species config, not a display name.
- `count` — integer, non-negative.

Producers emit a list of these. Consumers accept a list of these. If you need extra fields
(bounding boxes, confidence), keep them in the vision layer and do not leak them into the contract.

## Architecture

Six pieces, loosely coupled, each runnable on its own:

| Piece | Job |
|---|---|
| **ingest** | Grab webcam frames (or watch a folder) every few seconds; tag with trap ID + timestamp. |
| **vision** | Count and name insects in a frame; return the contract JSON. |
| **store** | SQLite table of `(trap_id, timestamp, species, count)`. Nothing fancier. |
| **season** | Pre-built synthetic CSV of daily counts + temps, shaped like a real flight curve. |
| **decide** | Biofix detection, degree-day accumulation, spray-window threshold. Plain Python. |
| **agent** | Local LLM: writes the grower-facing alert, answers "why Thursday?", calls tools. |
| **alert** | Phone notification (Telegram bot or SMS) that buzzes on stage. |

Suggested layout (Python):

```
fieldops/
  ingest.py       vision.py       store.py
  decide.py       agent.py        alert.py
  species.yaml    # per-crop pest lists and thresholds
data/
  season.csv      # pre-built replay data — committed, never generated at demo time
dashboard/        # single page: trap map, flight curve, DD clock, alert log, replay button
```

## Rules by layer

**vision** — Start with a local vision-language model prompted to return JSON. Zero training, fastest
path. Only swap in a trained YOLO detector if someone already knows YOLO *and* the replay is already
done. Always validate the model's JSON against the contract before it reaches the store; a VLM will
occasionally return prose, a wrong key, or a float count — handle that, don't crash the demo.

**decide** — This is **deterministic plain code, never an LLM.** It must be right on stage.
- Biofix: first sustained catch — counts above threshold on consecutive checks.
- Degree-days: accumulate from daily highs and lows.
- Spray window: a threshold on accumulated degree-days past biofix.
Thresholds come from `species.yaml`, not from literals in the logic.

**agent** — The LLM reads `decide`'s output and *phrases* it. It does not compute anything. Tools:
`get_counts`, `get_degree_days`, `send_alert`. If the hackathon expects OpenClaw or NemoClaw, this is
the plug-in point. Never let the agent be the thing that decides whether to spray.

**season** — Pre-build and commit `data/season.csv`. Generating it live is a failure mode.

## Scope

**Build, in this order:** ingest → vision → store → season data → decide → agent → alert. Then
dashboard, then species config.

**Do not build** (explicitly cut — say it on a slide instead): field hardware, solar, LoRa radios,
model fine-tuning, user accounts, multi-farm support.

**Do not add** without being asked: auth, Docker, CI, test frameworks beyond a couple of asserts on
`decide`, abstraction layers over SQLite, or a second config format. One day, four people.

## Conventions

- Python. Standard library plus whatever the model runtime needs; justify every new dependency.
- Everything runs offline. No cloud APIs, no hosted model endpoints, no telemetry — the pitch
  includes unplugging the network cable live, and anything that phones home kills that moment.
- Keep modules importable and independently runnable (`python -m fieldops.decide`) so four people
  can work in parallel without blocking each other.
- Short functions, obvious names, no premature structure. Hackathon code; readable beats clever.

## Ownership

| Person | Area |
|---|---|
| A | ingest + vision |
| B | store, season data, decide |
| C | agent, alert |
| D | dashboard, slides, printed trap cards |

If you are an agent asked to work on one area, stay in that area's files and respect the contract at
the boundary — someone else is editing the rest right now.
