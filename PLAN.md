# FieldOps — Implementation Plan

What we are building today, in what order, and how we know it works.

Scope and priorities come from [FieldOps_Hackathon_Plan.md](FieldOps_Hackathon_Plan.md).
Coding conventions come from [AGENTS.md](AGENTS.md). The two frozen interfaces are the counts
contract in [AGENTS.md](AGENTS.md) and the replay timeline in
[dashboard/TIMELINE_CONTRACT.md](dashboard/TIMELINE_CONTRACT.md). **Where this document and those
contracts disagree, the contracts win** — this one is the task list, not the interface spec.

Phases are written as hours from kickoff (**H+0**), not wall-clock, so they survive a late start.

## Already landed

- `fieldops/synth_traps.py` — synthetic sticky-trap JPEGs with ground-truth counts and boxes, for
  `codling_moth`, `oriental_fruit_moth` and `spotted_lanternfly`. Six images plus
  `data/traps/manifest.json` committed.
- `dashboard/TIMELINE_CONTRACT.md` — the `decide → dashboard` timeline shape and decision rules.
- `dashboard/tools/make_sample_timeline.py` + `dashboard/data/sample_timeline.{json,js}` — the
  stand-in timeline, so the dashboard is unblocked.
- `fieldops/season.py` + `data/season.csv` — season generator and committed output
  (`date,tmin_f,tmax_f,trap_id,species,count`): six blocks of three traps, Apr 15 to Aug 31, two flight
  peaks, and a one-day blip on Apr 28 that must not set biofix.
- `fieldops/store.py` — the single source of truth `decide` reads: `counts` and `temps` tables,
  the contract validator, and `--load` to rebuild both from the committed season CSV. Reloading is
  idempotent and the store path yields a byte-identical timeline to the CSV path. `decide --csv`
  bypasses it; an empty store falls back to the CSV automatically.
- `fieldops/decide.py` — degree-days, biofix, spray window and the contract-shaped timeline.
  `python -m fieldops.decide --replay` writes `dashboard/data/timeline.{json,js}`; a self-test
  runs first.
- `fieldops/species.json` + `species.py` — crop, blocks and pest thresholds, using the contract's
  key names.
- `dashboard/index.html` — the replay dashboard. It loads `timeline.js` after the sample, so the
  real timeline wins. Opened from `file://` in a browser against the real timeline: replay, banners
  and alert log work, and the banners call the phone trigger below.
- `fieldops/agent.py` (owner C) — the tools over `decide` (`get_counts`, `get_degree_days`,
  `get_status`, `send_alert`), `write_alert` (local LLM phrasing, template fallback, and a check that
  rejects any number the model was not given), `answer` for "why Thursday?", and a paced `--replay`.
  `find_event` / `deliver_event` serve the dashboard trigger.
- `fieldops/alert.py` (owner C) — Telegram sender with several chat IDs; credentials in the
  environment or `~/.config/fieldops.env`, outside the repo. Logs every alert to `data/alerts.jsonl`.
  Never raises.
- `fieldops/api.py` (owner C) — the one tool server (`python -m fieldops.api`, port 8765): GET
  `/status`, `/counts`, `/degree_days`, POST `/alert` for the OpenClaw sandbox, and POST `/trigger`
  for the dashboard, which sends `{date, block_id, type}` for the first biofix and the first spray
  window of a replay. The text comes from `decide` and the agent, never from the request.
  Browsers are refused on `/alert`; `/trigger` accepts only a page opened from disk.
- `openclaw/` — the sandbox policy and the tool skill the OpenClaw agent reads.
- `fieldops/check_models.py` — smoke test that the local LLM and VLM load and answer. Run it
  first on the GB10.
- `pitch/DEMO.md` — the presenter runbook.
- `pitch/index.html` — the five-beat deck, single offline file.

## Open gaps and decisions

`decide.py` and `TIMELINE_CONTRACT.md` now agree: same thresholds, status names, accumulation
rule and output shape, and the real timeline matches `sample_timeline.json` field for field.
What is still open:

**Not started.** `ingest.py` and `vision.py` do not exist — the live counting path is still
entirely unbuilt. It is also still cut-able.

**Unverified.** Nobody has run `python -m fieldops.check_models` on the GB10, so no local model has
been confirmed to load. Everything in `agent.py` currently runs on its template fallback. Do this
first: it gates the agent wording and the whole vision phase.

**The dashboard-to-phone trigger is built** (`POST /trigger` on `fieldops.api`). Start
`python -m fieldops.api` before the demo; if it is not running, the banners still show and the
phone just does not buzz. It texts twice per replay run, for the first block to reach each
milestone (biofix, then spray window), not once per block. Tested in a browser with the Telegram
step stubbed out, because there is no bot token on this machine yet. Do not also run
`python -m fieldops.agent --replay` during the same demo: it sends the same two alerts on its own
clock, so the phone would buzz twice.

**No spray date in the biofix alert.** `decide.evaluate` still returns `projected_open`, an estimate
from the last week's warmth. In spring it runs weeks late (on May 12 it said Jun 20; the window
opened Jun 4), so the alert text leaves it out and `answer` / OpenClaw should call it an estimate.
The pitch line "opens Thursday" is true once the window opens, not at biofix. Showing a real date
at biofix needs a forecast, which we do not have offline.

**The agent's number check is built.** `agent.write_alert` falls back to a template whenever the
LLM errors, is too long, or uses a number that is not in the facts it was given, so a hallucinated
degree-day count or date cannot reach the phone. Verified with a stubbed model.

**"Why Thursday?" is built but unverified.** `python -m fieldops.agent --ask "..."` and the OpenClaw
tools answer from `decide`'s numbers as of the replay's current day. Nobody has run them against a
real model.

**Decisions needed from the team:** which local runtimes for the VLM and LLM; Telegram or SMS;
whether the organizers require OpenClaw or NemoClaw (`agent.py` is the plug-in point).

**The phone alert needs the network; the unplug beat says we don't.** `alert.send` posts to
`api.telegram.org`. Once the cable is out it degrades to a console print, so the buzz and the
unplug cannot both be live at the same moment. Order the demo so the phone buzzes *before* the
unplug; what the unplug then proves is that inference and the decision are local, which is the
honest claim anyway.

**Check before relying on it:** open `dashboard/index.html` against the real `timeline.js` and
confirm it behaves like the sample.

---

## The critical path

> **Season replay → biofix → degree-day clock → phone alert.**

That chain is the demo. Phases 0–2 build it and nothing else. Everything after is upside.
If we are behind at any point, we cut from the back, never from the spine.

A single live insect count is a nice trick. The replay shows the *decision*, which is the value.

---

## Phase 0 — Skeleton and contract (H+0 → H+0:45)

Everyone in the room, one conversation, then we split and don't block each other again.

- [ ] Agree both contracts out loud: the counts shape in [AGENTS.md](AGENTS.md) and the replay
      timeline in [dashboard/TIMELINE_CONTRACT.md](dashboard/TIMELINE_CONTRACT.md). Freeze them.
      They do not change after this meeting.
- [ ] Scaffold the remaining `fieldops/` modules: `ingest.py` and `vision.py` (`agent.py`, `alert.py` and `api.py` have landed)
      (`store.py` and `decide.py` have landed). Each gets a `if __name__ == "__main__":` from the start.
- [x] `fieldops/species.json` with apple / codling moth filled in.
- [x] Create the SQLite schema and commit it.
- [ ] Confirm the local VLM and the local LLM both load on the GB10 and return *something*. **Do this
      first** — if a runtime is broken, we need to know at H+0:30, not H+5.

**Done when:** every module imports, `species.json` parses, the DB file is created, and both models
have returned one response each.

### The contract

```python
@dataclass
class Count:
    trap_id: str      # "block-c-04"
    timestamp: str    # ISO 8601, UTC, "2026-05-12T14:03:00Z"
    species: str      # snake_case key from species.json
    count: int        # >= 0
```

### The schema

```sql
CREATE TABLE counts (
    trap_id   TEXT    NOT NULL,
    timestamp TEXT    NOT NULL,   -- ISO 8601 UTC
    species   TEXT    NOT NULL,
    count     INTEGER NOT NULL CHECK (count >= 0),
    PRIMARY KEY (trap_id, timestamp, species)
);

CREATE TABLE temps (
    date  TEXT NOT NULL PRIMARY KEY,  -- YYYY-MM-DD
    tmin_f REAL NOT NULL,
    tmax_f REAL NOT NULL
);
```

Primary key on `counts` makes re-ingest idempotent — we will re-run the replay many times today.
Trap-to-block mapping lives in config, not in the DB; `decide` sums a block's traps when it builds
the timeline.

### Config shape

Landed as `fieldops/species.json`, with the contract's key names. Besides `species` it holds the
`farm` and the six `blocks` (id, name, variety, acres, grid position) that the timeline carries:

```json
{
  "crop": "apple",
  "species": {
    "codling_moth": {
      "display_name": "Codling moth",
      "dd_base_f": 50, "dd_upper_f": 88,
      "biofix_min_count": 2, "biofix_consecutive_checks": 2,
      "spray_open_dd": 250, "spray_close_dd": 350
    }
  }
}
```

`decide` evaluates the first species that carries all six thresholds, so the other two pests can sit
in the config as display entries for the platform beat without breaking anything.

Base 50 °F, upper 88 °F and 250/350 DD follow the UC IPM codling moth model. Treat them as demo
values — **say so if a judge asks, and don't present them as agronomic advice.**

---

## Phase 1 — The replay spine (H+0:45 → H+3)

Three people in parallel. This is the phase that must not slip.

### 1a. Season data — *owner: B*

- [x] `fieldops/season.py` generates one season of daily records: date, per-trap catch, tmin_f,
      tmax_f. Trap IDs and block grouping must match the `blocks` list the timeline will carry.
- [x] Flight curve is a realistic shape, not noise: near-zero through early spring, a sharp first-flight
      rise in late May, a dip, then a smaller second flight in July. Add per-trap variation so the
      traps don't move in lockstep.
- [x] Temperatures warm through the season with day-to-day jitter, consistent with the flight timing.
- [x] **Ran once, `data/season.csv` committed.** The demo reads the committed file. Generating data
      live on stage is a failure mode.

**Done when:** `data/season.csv` exists in git and plotting it by eye shows a curve that looks like
a real trap record.

### 1b. Store — *owner: B*

- [x] `store.validate()`, `store.add(records)`, `store.query(trap_id=, species=, since=, until=)`.
- [x] `python -m fieldops.store --load data/season.csv` ingests the season into SQLite.

**Done when:** the season loads, re-loading it twice changes no row counts, and queries come back.

### 1c. Decide — *owner: B* (the one piece that must be exactly right)

Plain Python. No LLM anywhere in this module. The rules below are **copied from
[TIMELINE_CONTRACT.md](dashboard/TIMELINE_CONTRACT.md) §Decision rules** — if they drift, that file
is right and this one is stale.

- [x] **Degree-days (per day), average method with horizontal cutoff:**
      `avg = (min(tmax_f, dd_upper_f) + max(tmin_f, dd_base_f)) / 2`, then
      `dd_today = max(0, avg - dd_base_f)`. The cutoff matters — plain `(tmax+tmin)/2` overestimates
      on hot days and will shift the spray date.
- [x] **Biofix, per block.** The first day that completes a run of `biofix_consecutive_checks`
      consecutive days with `counts[block] >= biofix_min_count`. `biofix_date` is the **first day of
      that run**; the `biofix` event fires on the day the run **completes**. Those are different
      dates — don't collapse them.
- [x] **Accumulation.** `dd_since_biofix` sums `dd_today` for every day *after* `biofix_date`.
- [x] **Spray window.** Opens the first day `dd_since_biofix >= spray_open_dd`, closes the first day
      it reaches `spray_close_dd`.
- [x] **Status machine, per block per day:** `watching` → `accumulating` → `spray_window` →
      `window_closed`. Every block carries a status every day.
- [x] A handful of asserts (`selftest()`): no biofix on an all-zero season; biofix on a known spike, with the run's
      first day as `biofix_date`; `dd_today == 0` when the mean sits below base; the cutoff clamping
      a 95 °F day to 88; a hand-computed two-day DD total.

**Done when:** `python -m fieldops.decide --season data/season.csv` prints each block's biofix date,
running DD total and spray window — and the dates are defensible when someone asks why.

### 1d. Timeline emitter — *owner: B*

The dashboard never computes anything; it plays back one JSON document that `decide` writes. Pacing
is the dashboard's job, not a stream's.

- [x] `python -m fieldops.decide --replay` writes `dashboard/data/timeline.json` **and** its JS twin
      `dashboard/data/timeline.js` (`window.FIELDOPS_TIMELINE = {...};`), so the page runs from
      `file://` with no server and no fetch.
- [x] Shape must validate against [TIMELINE_CONTRACT.md](dashboard/TIMELINE_CONTRACT.md): `days`
      ascending, one entry per calendar day, no gaps, every block present every day.
- [x] D's stand-in `dashboard/tools/make_sample_timeline.py` already emits the same shape — diffed
      against it: same fields and types, same 139 days, same thresholds.

**Done when:** the dashboard, pointed at the real `timeline.js` instead of the sample, behaves
identically.

---

## Phase 2 — Agent and alert (H+2 → H+4, overlaps Phase 1)

Owner: C. Can be built against a hardcoded decision object before `decide` is finished — agree the
output shape with B at H+0:45 and start immediately.

- [ ] `agent.write_alert(decision) -> str`. Local LLM turns the decision into one or two sentences a
      grower would actually read. Target: *"Biofix reached on block C. Spray window opens Thursday."*
      Not a paragraph. Not an essay about integrated pest management.
- [ ] `agent.answer(question, context) -> str` for *"why do you want me to spray Thursday?"* — it
      explains the degree-day reasoning using numbers from `decide`, and never recomputes them itself.
- [ ] Tools exposed to the agent: `get_counts`, `get_degree_days`, `send_alert`. If the hackathon
      expects OpenClaw or NemoClaw, this is the plug-in point.
- [ ] `alert.send(text)` — Telegram bot is the fastest path; SMS if Telegram is blocked on the venue
      network. Test it on the actual demo phone, on the actual venue wifi, well before the pitch.

**Done when:** running the replay buzzes a real phone at the right moment with a sentence we'd be
happy to read aloud.

> ### ✅ CHECKPOINT — H+4
>
> **Replay runs end to end and the phone buzzes.** The pitch is now viable with nothing else built.
> Nobody starts Phase 3 until this is true. If we are late, stop here and rehearse.

---

## Phase 3 — Live vision (H+4 → H+6)

Owner: A. Independently valuable, cut-able without killing the demo.

- [ ] `ingest.py`: grab a webcam frame every few seconds, or watch a folder. Tag with trap ID and
      timestamp. Simulate several traps from one camera — there is no trap network today.
- [ ] `vision.py`: prompt the local VLM to count and name insects in the frame and return JSON.
      Zero training. Only consider a trained YOLO detector if someone already knows YOLO *and*
      everything above is done.
- [ ] **Validate the model's output before it reaches the store.** A VLM will return prose, a wrong
      key, a float, or a species we've never heard of. Parse defensively, drop bad records, log them,
      never crash the preview.
- [ ] **Score against ground truth.** `data/traps/manifest.json` carries exact counts for the six
      committed images — run the VLM over them and record how close it gets. This is free accuracy
      evidence for the pitch, and it tells us early whether live counting is demo-worthy at all.
- [ ] Live preview: boxes drawn on the frame, running count per species.
- [ ] Print trap cards from `data/traps/` — a sparse one and a dense one (the `codling000` and
      `codling050` images), so the on-stage swap makes the count jump visibly. More can be generated
      with `python -m fieldops.synth_traps --counts ...`.

**Done when:** pointing the webcam at a printed card shows boxes and a count, swapping cards moves
the number in the right direction, and we know the error rate against the manifest.

---

## Phase 4 — Dashboard (H+6 → H+8)

Owner: D. One page, no router, no build step, runs from `file://`. **Unblocked from H+0** — build
against `dashboard/data/sample_timeline.js` and swap to the real `timeline.js` when B's emitter
lands. Do not wait for `decide`.

- [ ] Flight curve over the season, biofix marked.
- [ ] Degree-day clock — accumulated total and distance to `spray_open_dd`.
- [ ] Alert log, fed from the timeline's per-day `events`.
- [ ] Block status colouring: `watching` / `accumulating` / `spray_window` / `window_closed`.
- [ ] **Replay button.** This is the one control that matters on stage. The dashboard owns the
      pacing — it walks `days` itself; the timeline is a static document.
- [ ] Trap map from `blocks[].col/row`, if there's time. It's decoration.

**Done when:** one click replays the season visually and the curve, the clock and the alert log all
move together — and pointing the page at the real timeline instead of the sample changes nothing
but the numbers.

---

## Phase 5 — Platform proof and rehearsal (H+8 → end)

- [ ] Add a second crop to the config and show the switch changing the pest list live. `synth_traps`
      already renders `oriental_fruit_moth` and `spotted_lanternfly`, so there are real images to
      back the switch — use one of those rather than inventing a crop with no pictures. This is the
      whole "it's a platform" beat; it costs about ten minutes and it's the cheapest point in the pitch.
- [ ] **Unplug the network cable and run the entire demo again.** If anything breaks, that thing was
      reaching the internet and has to be fixed or cut.
- [x] Slides (`pitch/index.html`): the problem, the too-late trap photo, the hardware we're *not* building today
      (solar, LoRa, enclosures), the platform slide.
- [ ] **Rehearse the full three minutes at least twice, out loud, with the phone in the room.**
      Hit the five beats: problem (30s), why it's hard (20s), live demo (90s), why local (20s),
      platform (20s).

---

## Risks and fallbacks

| Risk | Fallback |
|---|---|
| VLM miscounts badly or returns junk | Phase 3 is cut-able. The replay is the pitch; say live counting is in progress. |
| Model runtime won't load on the GB10 | Found at H+0:30 by design. Swap to a smaller local model immediately. |
| Venue wifi blocks Telegram | Switch to SMS. Test both before the checkpoint, not during the pitch. |
| Webcam focus/lighting makes cards unreadable on stage | Pre-record a 15-second screen capture of live counting; play it if the live path fails. |
| Degree-day numbers questioned by a judge | Cite UC IPM for base 50 °F / upper 88 °F / 250 DD, and call them demo values. |
| `decide` output drifts from the timeline contract | Diff its JSON against `make_sample_timeline.py` output before wiring the dashboard. |
| Phase 1 slips past H+4 | Drop Phase 3 entirely; the dashboard still runs on the sample timeline. Replay plus a phone buzz tells the whole story. |

## Definition of done

The demo is done — not the code — when all of these hold with the network cable unplugged:

1. One command replays a full season in about 30 seconds.
2. Biofix is detected and announced at a defensible date.
3. The degree-day clock accumulates visibly and crosses the threshold.
4. A real phone buzzes with a sentence a grower would act on.
5. Someone can ask *"why Thursday?"* and get an answer grounded in the actual numbers.
6. Switching the species config visibly changes the pest list.
7. The whole thing has been rehearsed end to end, twice.

## Explicitly not building today

Field hardware, solar, LoRa radios, model fine-tuning, user accounts, multi-farm support. These go
on a slide, not in the repo. Also out: auth, Docker, CI, a test framework beyond the asserts in
`decide`, and any abstraction layer over SQLite.
