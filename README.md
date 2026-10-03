# FieldOps

**Counts the moths. Starts the clock. Tells the grower when to spray.** Entirely offline, on one box.

Built for the Dell x NVIDIA AI Hackathon, October 3 2026.

---

## The problem

A Massachusetts apple grower has 20 sticky traps and checks them once a week. Last season the
codling moths started flying on a Monday. He found out Friday — and by then the larvae were in
his fruit.

Counting traps by hand is slow and inconsistent. Cloud trap cameras exist, but orchards have no
signal, and nobody wants a subscription per trap.

## What FieldOps does

- **Counts insects on a sticky trap** from a camera frame, by species.
- **Tracks the flight curve** across the season and detects **biofix** — the first sustained catch,
  the moment the pest clock starts.
- **Accumulates degree-days** from daily high/low temperatures once biofix is set.
- **Calls the spray window** when accumulated degree-days cross the species threshold.
- **Buzzes the grower's phone** in plain language: *"Biofix reached on block C. Spray window opens
  Thursday."* — and answers follow-ups like *"why Thursday?"*

The counting is the party trick. The decision is the product.

## How it works

```
 camera frame ──▶ vision ──▶ { trap_id, timestamp, species, count } ──▶ store (SQLite)
                   (VLM)                                                    │
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
every time. Live counts from the vision layer append to the same store. With no store present,
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

Still to come: the live vision layer (`ingest.py`, `vision.py`). No local model has been confirmed
to load on the GB10 yet — run `python -m fieldops.check_models` first; until then the agent runs on
its template fallback. See [PLAN.md](PLAN.md) for the order of work and the open decisions.

```bash
python -m fieldops.check_models                  # do the local LLM and VLM load? run this first
python -m fieldops.season                        # regenerate data/season.csv
python -m fieldops.store --load data/season.csv  # build the store: counts + temperatures
python -m fieldops.decide                        # self-test, then print each block's milestones
python -m fieldops.decide --replay               # ...and write the dashboard timeline
python -m fieldops.agent --status                # what the agent's tools return right now
python -m fieldops.api                           # tool server: dashboard buzz + OpenClaw tools
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
| [AGENTS.md](AGENTS.md) | Build conventions for coding agents and teammates. Read before writing code. |
| [FieldOps_Hackathon_Plan.md](FieldOps_Hackathon_Plan.md) | The pitch: story beats, demo script, scope calls. |
| [dashboard/TIMELINE_CONTRACT.md](dashboard/TIMELINE_CONTRACT.md) | The `decide → dashboard` timeline shape and the decision rules. Frozen. |
| [fieldops/synth_traps.py](fieldops/synth_traps.py) | Generates synthetic trap photos with ground-truth counts into [data/traps/](data/traps/). |

## Stack

Python on a Dell/NVIDIA GB10. A local vision-language model for counting, a local LLM for the
agent layer, SQLite for counts and weather, and a single-page dashboard. No cloud services anywhere in the path.

## License

MIT — see [LICENSE](LICENSE).
