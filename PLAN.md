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
  (`date,tmax_f,tmin_f,trap_id,species,count`).
- `fieldops/store.py` — validate / add / query over SQLite, `--load` a season CSV.
- `fieldops/decide.py` — degree-days, biofix, spray window, per-(species, block) status, plus
  `replay()` and a self-test.
- `fieldops/species.json` + `species.py` — crop and pest config.
- `pitch/index.html` — the five-beat deck, single offline file.

## ⚠ Open divergences — resolve before wiring the dashboard

`decide.py` and `TIMELINE_CONTRACT.md` do not currently agree. These are cheap to fix now and
expensive to fix at H+8. One person should pick a side for each and make both files match.

| | Contract | `decide.py` / `species.json` |
|---|---|---|
| Biofix threshold | `min_count` 2, `consecutive` 2 | 3 and 3 |
| Status names | `watching`, `accumulating` | `no_biofix`, `biofix` |
| DD accumulation starts | the day **after** `biofix_date` | on `biofix_date` itself |
| Config keys | `dd_base_f`, `spray_open_dd` … | `degree_days.lower_f`, `spray_open` … |
| Output | one timeline document, `days[]` | flat list of event dicts |

**The timeline emitter does not exist yet.** `decide.py` has `replay()` returning events, but
nothing writes `dashboard/data/timeline.json` or its JS twin — so the dashboard still cannot consume
real output. That is the critical-path gap; see [1d](#1d-timeline-emitter--owner-b).

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
- [x] Scaffold `fieldops/` with modules: `ingest.py`, `vision.py`, `store.py`, `decide.py`,
      `agent.py`, `alert.py`. Each gets a `if __name__ == "__main__":` from the start.
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

Landed as `fieldops/species.json`:

```json
{
  "crop": "apple",
  "species": {
    "codling_moth": {
      "display": "Codling moth",
      "biofix": {"min_count": 3, "consecutive_days": 3},
      "degree_days": {"lower_f": 50, "upper_f": 88, "spray_open": 250, "spray_close": 350}
    }
  }
}
```

Only species carrying a `biofix` block get evaluated, so the other two pests can sit in the config
as display entries for the platform beat without breaking anything.

Base 50 °F, upper 88 °F and 250/350 DD follow the UC IPM codling moth model. Treat them as demo
values — **say so if a judge asks, and don't present them as agronomic advice.** The biofix
threshold still disagrees with the contract; see the divergence table above.

---

## Phase 1 — The replay spine (H+0:45 → H+3)

Three people in parallel. This is the phase that must not slip.

### 1a. Season data — *owner: B*

- [x] `fieldops/season.py` generates one season of daily records: date, per-trap catch, tmin_f,
      tmax_f. Trap IDs and block grouping must match the `blocks` list the timeline will carry.
- [ ] Flight curve is a realistic shape, not noise: near-zero through early spring, a sharp first-flight
      rise in late May, a dip, then a smaller second flight in July. Add per-trap variation so the
      traps don't move in lockstep.
- [ ] Temperatures warm through the season with day-to-day jitter, consistent with the flight timing.
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

- [ ] `python -m fieldops.decide --replay` writes `dashboard/data/timeline.json` **and** its JS twin
      `dashboard/data/timeline.js` (`window.FIELDOPS_TIMELINE = {...};`), so the page runs from
      `file://` with no server and no fetch.
- [ ] Shape must validate against [TIMELINE_CONTRACT.md](dashboard/TIMELINE_CONTRACT.md): `days`
      ascending, one entry per calendar day, no gaps, every block present every day.
- [ ] D's stand-in `dashboard/tools/make_sample_timeline.py` already emits the same shape — diff
      against its output to confirm the real emitter matches before wiring the dashboard over.

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
