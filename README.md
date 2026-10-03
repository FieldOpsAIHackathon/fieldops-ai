# FieldOps

**Counts the moths. Starts the clock. Tells the grower when to spray.** Entirely offline, on one box.

Built for the Dell x NVIDIA AI Hackathon, October 3 2026.

**[Watch the two-minute demo](pitch/video/fieldops-demo.mp4)** · [Backup cut](pitch/video/fieldops-demo-backup.mp4) · [Transcript](pitch/video/transcript.txt)

---

## The problem

A Massachusetts apple grower has 20 sticky traps and checks them once a week. Last season the
codling moths started flying on a Monday. He found out Friday — and by then the larvae were in
his fruit.

Counting traps by hand is slow and inconsistent. Cloud trap cameras exist, but orchards have no
signal, and nobody wants a subscription per trap.

## What FieldOps does

- **Counts insects on a sticky trap** from a photo, by species. Send the Telegram bot a picture of
  a trap card and a YOLO26 detector on the box counts codling moths, oriental fruit moths and
  spotted lanternflies, ignoring gnats and debris.
- **Tracks the flight curve** across the season and detects **biofix** — the first sustained catch,
  the moment the pest clock starts.
- **Accumulates degree-days** from daily high/low temperatures once biofix is set.
- **Calls the spray window** when accumulated degree-days cross the species threshold.
- **Buzzes the grower's phone** in plain language: *"Biofix reached on block C. Spray window opens
  Thursday."* — and answers follow-ups like *"why Thursday?"*

The counting is the party trick. The decision is the product.

## How it works

```
 trap photo ──▶ vision ──▶ { trap_id, timestamp, species, count } ──▶ store (SQLite)
              (YOLO26, GPU)                                                 │
                                                                            ▼
 daily temps ──────────────────────────────────────────────────────▶    decide
                                                       biofix · degree-days · threshold
                                                                            │
                                                                            ▼
                                                           agent (local LLM) ──▶ phone alert
                                                           phrases it, answers questions
```

The store is the single source of truth `decide` reads, and it holds both halves of the
decision: trap counts and the daily temperatures the degree-day clock runs on. It is rebuilt from
the committed `data/season.csv`, so a reload is deterministic and the replay comes out identical
every time. Live counts from the vision layer can append to the same store (opt-in, so a demo
photo never moves the spray dates). With no store present,
`decide` falls back to reading the CSV directly.

Two deliberate splits:

- **The decision is plain Python, not a model.** Biofix and degree-day math are deterministic and
  auditable. An LLM that hallucinates a spray date costs someone a harvest.
- **The LLM only phrases and explains.** It reads the decision, writes the grower-facing message,
  and answers questions about it. It never computes the answer.

## Why local

Everything runs on the box in the barn — a GB10 — with no internet. No cloud API, no hosted model
endpoint, no telemetry. Orchards have no signal, and the farm's spray records are the farm's
business. You can unplug the network cable and FieldOps keeps working.

## Status

**Under construction during the hackathon.**

Working end to end: season data, the decision engine, the replay dashboard, and the alert.
`fieldops/season.py` generates a season, `fieldops/decide.py` finds biofix, accumulates
degree-days and calls the spray window, and `--replay` writes the timeline the dashboard plays.
`fieldops/agent.py` turns an event into a sentence for the grower and `fieldops/alert.py` sends it
to a phone, and `fieldops/api.py` serves both the dashboard trigger and the OpenClaw tools. Also
here: a synthetic trap-image generator with ground-truth counts
(`fieldops/synth_traps.py`), the deck (`pitch/index.html`) and the presenter runbook
(`pitch/DEMO.md`).

**Vision has landed.** `fieldops/vision.py` counts pests in a trap photo with a YOLO26 detector
trained on synthetic cards (`models/fieldops-yolo26s-v2.pt`). The OpenClaw agent on Telegram sends
photos to it through `POST /count` on the tools API. How it was trained, how accurate it is, and
the overfitting we caught and fixed are in [fieldops/yolo/README.md](fieldops/yolo/README.md).

**Models on the GB10:** the agent's LLM is Qwen3.6-35B-A3B (NVFP4) on the local vLLM server at
`127.0.0.1:8000`, and counting is YOLO26s in a GPU container. Both run offline.

**On the GB10 everything starts at boot:** `bash deploy/install.sh` installs `fieldops.target`
(OpenClaw sandbox + Telegram, vision service, tools API) as systemd user services. See
[deploy/README.md](deploy/README.md). See [PLAN.md](PLAN.md) for the order of work and open decisions.

```bash
python -m fieldops.check_models                  # do the local LLM and VLM load? run this first
python -m fieldops.telegram_setup                # one-time: connect the phone alert to your Telegram bot
python -m fieldops.season                        # regenerate data/season.csv
python -m fieldops.weather --normals             # refetch the average temperatures behind the spray-date estimate (needs network)
python -m fieldops.store --load data/season.csv  # build the store: counts + temperatures
python -m fieldops.decide                        # self-test, then print each block's milestones
python -m fieldops.decide --replay               # ...and write the dashboard timeline
python -m fieldops.agent --status                # what the agent's tools return right now
python -m fieldops.api                           # tool server: dashboard buzz + OpenClaw tools + /count

# vision (GPU container; details in fieldops/yolo/README.md)
bash fieldops/yolo/run.sh serve                  # YOLO counting service on 127.0.0.1:8767
curl --data-binary @data/traps/trap_05_codling050.jpg "localhost:8765/count?trap_id=block-c-04"
bash fieldops/yolo/run.sh eval                   # score the 6 reference cards
bash fieldops/yolo/run.sh phone-test --n 200     # accuracy on phone-style photos (overfitting check)
open dashboard/index.html                        # the replay, straight from disk, no server
open pitch/index.html                            # the deck; arrow keys to advance

python -m fieldops.decide --csv                  # bypass the store and read the CSV directly

# ground-truth trap counts as test data. Use a scratch --db: these traps sit in block C on a
# real season date, so loading them into the demo store spikes its flight curve.
python -m fieldops.store --db data/test.db --load-traps data/traps/manifest.json

# two seasons of multi-species history in its own store, for exercising queries and the
# vision path. 4,665 readings, 30 traps, 10 species, irregular check times.
python -m fieldops.history
```

## Repo map

| Path | What's in it |
|---|---|
| [PLAN.md](PLAN.md) | Implementation plan — phases, tasks, interfaces, risks, definition of done. |
| [ORCHESTRATION.md](ORCHESTRATION.md) | How the pieces run together: processes, ports, data flow, start order, failure modes. |
| [AGENTS.md](AGENTS.md) | Build conventions for coding agents and teammates. Read before writing code. |
| [FieldOps_Hackathon_Plan.md](FieldOps_Hackathon_Plan.md) | The pitch: story beats, demo script, scope calls. |
| [dashboard/TIMELINE_CONTRACT.md](dashboard/TIMELINE_CONTRACT.md) | The `decide → dashboard` timeline shape and the decision rules. Frozen. |
| [fieldops/synth_traps.py](fieldops/synth_traps.py) | Generates synthetic trap photos with ground-truth counts into [data/traps/](data/traps/). |
| [fieldops/vision.py](fieldops/vision.py) | The vision lane: YOLO counting service and CLI, contract records out. |
| [fieldops/yolo/](fieldops/yolo/README.md) | Dataset generator, training, counting, phone-photo stress test, GPU container. |
| [models/](models/README.md) | Trained detector weights and their model card. |
| [openclaw/](openclaw/) | The OpenClaw skill (tools + photo routing) and the sandbox network policy. |
| [deploy/](deploy/README.md) | systemd units for the GB10, plus the CI deploy unit. |

## Stack

Python on a Dell/NVIDIA GB10. A YOLO26 detector for counting, Qwen3.6 on vLLM for the agent
layer, NemoClaw + OpenClaw + OpenShell for the sandboxed Telegram agent, SQLite for counts and
weather, and a single-page dashboard. No cloud services anywhere in the path.

## License

MIT — see [LICENSE](LICENSE).
