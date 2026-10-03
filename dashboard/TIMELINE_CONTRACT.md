# Replay timeline contract (decide -> dashboard)

The dashboard never computes anything. It plays back one JSON document that `decide` writes.
That keeps the replay deterministic and independent of live inference, which is the one rule in
AGENTS.md that matters.

- **Producer (B):** `python -m fieldops.decide --replay` writes `dashboard/data/timeline.json`
  and its JS twin `dashboard/data/timeline.js`.
- **Stand-in until decide exists (D):** `python dashboard/tools/make_sample_timeline.py` writes
  `dashboard/data/sample_timeline.json` and `dashboard/data/sample_timeline.js` in the same shape.
- **JS twin:** identical content wrapped as `window.FIELDOPS_TIMELINE = {...};` so the page works
  from `file://` with no server and no fetch. The dashboard loads `data/timeline.js` if present,
  else `data/sample_timeline.js`.

## Shape

```json
{
  "farm": {
    "name": "Nashoba Ridge Orchard",
    "location": "Bolton, MA",
    "crop": "apple",
    "pest": "codling_moth",
    "pest_name": "Codling moth",
    "season": 2026
  },
  "thresholds": {
    "biofix_min_count": 2,
    "biofix_consecutive_checks": 2,
    "dd_base_f": 50,
    "dd_upper_f": 88,
    "spray_open_dd": 250,
    "spray_close_dd": 350
  },
  "blocks": [
    {
      "id": "block-c",
      "name": "Block C",
      "variety": "Honeycrisp",
      "acres": 4.2,
      "traps": ["block-c-01", "block-c-02", "block-c-03"],
      "col": 2,
      "row": 0
    }
  ],
  "days": [
    {
      "date": "2026-05-12",
      "tmin_f": 48,
      "tmax_f": 71,
      "dd_today": 9.5,
      "counts": { "block-c": 7 },
      "traps": { "block-c-01": 3, "block-c-02": 4, "block-c-03": 0 },
      "blocks": {
        "block-c": {
          "status": "accumulating",
          "biofix_date": "2026-05-12",
          "dd_since_biofix": 0
        }
      },
      "events": [
        {
          "block_id": "block-c",
          "type": "biofix",
          "title": "Biofix set on Block C",
          "message": "Sustained codling moth catch on Block C: 7 moths today after 4 yesterday. Degree-day clock starts now."
        }
      ]
    }
  ]
}
```

## Field rules

- `days` is sorted ascending, one entry per calendar day, no gaps, covering the whole season.
- `date` is `YYYY-MM-DD`. Temperatures are Fahrenheit.
- `counts[block_id]` is that day's catch summed over the block's traps. Integer, non-negative.
  Every block in `blocks` has an entry every day.
- `traps` is optional per-trap detail. Trap IDs match the count contract in AGENTS.md
  (`block-c-04` style).
- `blocks[block_id]` is the block's state at the end of that day:
  - `status` is one of `watching` (before biofix), `accumulating` (biofix set, below spray
    threshold), `spray_window` (open), `window_closed` (past close threshold).
  - `biofix_date` is `null` until set, then the `YYYY-MM-DD` it was set.
  - `dd_since_biofix` is a float, 0 until the day after biofix.
- `events` lists what changed that day (empty list most days). `type` is one of `biofix`,
  `spray_window_open`, `spray_window_close`. `title` is short enough for a toast; `message` is
  one or two grower-facing sentences. Order within a day is the order they fired.
- `blocks[].col` / `row` are grid positions for the map (0-based). Six blocks in a 3 x 2 grid is
  plenty.

## Decision rules (so the sample and decide agree)

- **Degree-days (per day):** average method with a horizontal cutoff.
  `avg = (min(tmax_f, dd_upper_f) + max(tmin_f, dd_base_f)) / 2`,
  `dd_today = max(0, avg - dd_base_f)`.
- **Biofix (per block):** the first day that ends a run of `biofix_consecutive_checks` consecutive
  days with `counts[block] >= biofix_min_count`. `biofix_date` is the first day of that run.
  Status becomes `accumulating` and a `biofix` event fires on the day the run completes.
- **Accumulation:** `dd_since_biofix` sums `dd_today` for every day after `biofix_date`.
- **Spray window:** opens on the first day `dd_since_biofix >= spray_open_dd` (status
  `spray_window`, event `spray_window_open`), closes on the first day it reaches `spray_close_dd`
  (status `window_closed`, event `spray_window_close`).
- Base 50 F, upper 88 F, biofix at first sustained catch, and first treatment around 250 DD after
  biofix follow the UC IPM codling moth model. Treat the exact numbers as demo values; verify before
  presenting them as agronomic advice.
