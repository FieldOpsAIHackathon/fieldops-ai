# FieldOps orchestration

How the pieces run together: processes, ports, data flow, start order, and what survives when
something dies.

This is the systems view. For the other three: [AGENTS.md](AGENTS.md) is how to build,
[PLAN.md](PLAN.md) is what is left, [pitch/DEMO.md](pitch/DEMO.md) is what the presenter clicks,
and [deploy/README.md](deploy/README.md) is CI and installation.

## Two lanes, and only one of them is load-bearing

Everything splits into a **replay lane** and a **live lane**, and keeping them apart is the single
most important property of the system.

- **Replay lane** — deterministic, file-based, no model, no GPU, no network. `season.csv` through
  the store to `decide` to a committed timeline the dashboard plays. This is the pitch. It is
  byte-identical on any machine and cannot be broken by a flaky model.
- **Live lane** — a camera or phone photo through YOLO to a count. This is the supporting trick.
  It writes to the store **only** with `--to-store`, so a stray demo photo can never move a spray
  date in the replay.

If the live lane dies on stage, the pitch still lands. The reverse is not true. Never wire the
replay to depend on live inference.

## Processes

| Process | Command | Listens | Required |
|---|---|---|---|
| **Tools API** | `python -m fieldops.api` | `127.0.0.1:8765`, `172.18.0.1:8765` | for the phone buzz and OpenClaw |
| **Vision service** | `bash fieldops/yolo/run.sh serve` | `127.0.0.1:8767` | live lane only (GPU container) |
| **OpenClaw sandbox** | `fieldops-sandbox.service` | sandbox bridge | agent Q&A demo only |
| **Static server** | `python3 -m http.server 8787` | `127.0.0.1:8787` | for dashboard live mode |
| **Feed simulator** | `python3 dashboard/tools/simulate_feed.py --pace 1` | writes `dashboard/data/live.json` | live-mode visuals |
| **Dashboard** | browser tab | — | yes |
| **Deck** | browser tab on `pitch/index.html` | — | yes |

On the GB10 the first three run as systemd user units under `fieldops.target`, ordered after the
NemoClaw gateway (`bash deploy/install.sh`; see [deploy/README.md](deploy/README.md)).

## Data flow

```
 data/season.csv ──load──▶ data/fieldops.db ──▶ decide ──▶ dashboard/data/timeline.{json,js}
   (committed seed)          counts + temps      │                      │
                                  ▲              │                      ▼
                                  │              │              dashboard (browser)
 phone / camera photo             │              │               replay · curve · DD clock
        │                         │              │                      │
        ▼                         │              │        banner fires  │
   vision :8767 ──contract──┬─────┘              │                      ▼
   (YOLO, GPU)              │  only --to-store   │           POST /trigger ──▶ api :8765
                            │                    │                                 │
                            └── data/vision/counts.jsonl                           ▼
                                                                          agent.write_alert
 OpenClaw sandbox ──/status /counts /degree_days /alert /count──▶ api :8765        │
   (NemoClaw)                                                                      ▼
                                                                    alert.send ──▶ Telegram ──▶ phone
```

Two frozen boundaries carry everything: the **count contract** in [AGENTS.md](AGENTS.md) and the
**replay timeline** in [dashboard/TIMELINE_CONTRACT.md](dashboard/TIMELINE_CONTRACT.md).

## Start order

```bash
# 1. state — rebuild the store from the committed seed, so the replay is exactly the rehearsed one
python -m fieldops.store --load data/season.csv
python -m fieldops.decide --replay          # regenerates timeline.{json,js}; should produce no git diff

# 2. services
python -m fieldops.api                      # tools + /trigger  (needs ~/.config/fieldops.env for Telegram)
bash fieldops/yolo/run.sh serve             # live lane only

# 3. the page
python3 -m http.server 8787                 # from the repo root
python3 dashboard/tools/simulate_feed.py --pace 1

# 4. browser: http://localhost:8787/dashboard/index.html  and  pitch/index.html
```

Step 1 matters most. Rebuilding the store before every rehearsal and before the record is what
keeps a stray live reading out of the numbers. If `--replay` produces a git diff, something changed
the decision — stop and find out what before going on stage.

Do **not** also run `python -m fieldops.agent --replay` while the API is up; both send alerts and
the phone buzzes twice.

## Trust boundaries

- The API binds loopback and the OpenShell docker bridge only — **never the venue network.**
- `/trigger` is deliberately outside the sandbox policy: only the dashboard, same machine, can fire
  a replay alert. OpenClaw *can* reach `POST /alert` (its skill says only when the user asks), so
  the agent can text the phone, but it cannot replay a decision event.
- The dashboard opened from disk sends `Origin: null`; the API accepts that and `file://` and
  nothing else.
- The agent phrases, it never computes. Numbers come from `decide`, and `agent.write_alert`
  falls back to the event's template if the model emits a digit absent from the facts.

## What survives what

| If this dies | What happens |
|---|---|
| Local LLM | Alerts fall back to templated text. Numbers unaffected. Demo fine. |
| Vision service | Live counting stops. Replay untouched. Demo fine. |
| Tools API | Banners still fire on screen; the phone stays quiet. Demo fine. |
| Telegram / internet | `alert.send` prints and returns False. Nothing raises. Demo fine. |
| Static server | Dashboard still opens from `file://` for the replay alone. Live mode lost. |
| **The committed timeline** | **The pitch is gone.** It is the only true single point of failure. |

Everything degrades to the replay. Guard the timeline accordingly.

## The offline beat

Localhost is not the network, so unplugging the cable changes nothing except Telegram. The honest
claim is that **inference and the decision are local** — a push notification inherently needs a
network. So order the demo: **buzz the phone first, pull the cable second.** The badge flips to
"Offline, still running" on its own.
