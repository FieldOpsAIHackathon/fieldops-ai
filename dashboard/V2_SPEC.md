# Dashboard v2 spec (from Himanshu's picks, 16:00)

The v1 page is a replay viewer. v2 is an **orchard analytics dashboard** that still plays the
replay. Picks from the design picker, plus his note, decide everything below.

## Picks

| Decision | Pick | Meaning for the build |
|---|---|---|
| Colors | Orchard commons | bg #F4F6F1, surface #FFFFFF, surface2 #E8ECE3, ink #1F3229, muted #5A6B61, line #D9DFD5, primary/accent #126D58, lane #FFFFFF, tree #6F8F7A, grid #E1E6DD. Rounded (radius 16/12, pills). |
| Typeface | Plex | IBM Plex Sans for everything, Plex Mono for readings. Embed both woff2 as base64 `@font-face` (files in `~/Documents/GitHub/hackathon/design/fieldops-picker-src/fonts/`). No web fonts. |
| Page layout | Spine | 280px instrument spine on the left, map stage on the right, signal band under the map, curve strip under that, 84px dock at the bottom. Analytics panels extend the page below the fold (the page scrolls; the replay region stays the first 900px). |
| Orchard map | Commons plan | Rounded joins, broad white lanes, circle-pair trees, stem-and-head pins with a count bubble, 5px accent boundary on the selected block. Base on `design/fieldops-picker-src/parts/map.js`. |
| Flight curve | Lead line | One chart, selected block 4px accent, others 2px muted 35%, biofix marker, spray band. Base on `parts/charts.js` `lead`. |
| Degree-day clock | Arc (recommended) | Semicircle 0 to 350 with the 250 to 350 band. Base on `parts/charts.js` `arc`. |
| Spray window moment | Boundary ignition | Block outline swells 4 to 10 to 4px over 900ms once; the signal band turns spray color with a 36px heading; the clock highlights the 250 tick. No toasts. |
| Replay controls | Bottom bar | Play season, scrub with month ticks, Next event, 0.5x 1x 2x, sound toggle. Keyboard: space, arrows. |
| Phone | Map first | At 390px: date, overview map, selected block caption, clock, curve, log, sticky dock. |

## His note, turned into requirements

1. **Full farm with borders and subregions.** One farm boundary polygon encloses the six blocks
   as subregions, with lanes between them and a couple of non-block features for place (a
   packing barn footprint and a pond or hedgerow). Blocks keep the brief's polygon recipe; the
   outer boundary follows their convex outline with a margin. The map is still "Schematic orchard".
2. **Health colors.** Status maps to health: `watching` = healthy green `#2E7D4F`,
   `accumulating` = at risk amber `#A87C00`, `spray_window` = needs spray red `#B0173A`,
   `window_closed` = window closed gray-green `#6F8A7A`. Fill opacities 10 / 18 / 26 / 12 percent.
   Legend says Healthy, At risk, Needs spray, Window closed. Never color alone: each block carries
   its status word.
3. **Farm score.** A 0 to 100 farm health score in the spine's top panel, acre-weighted mean of
   block scores: healthy 100; at risk `100 - 60 * min(1, dd_since_biofix / spray_open_dd)`;
   needs spray 15; window closed 55. Show the number large, "Farm health", the count of blocks at
   each state beneath, and a 7-day sparkline of the score. Label it a demo heuristic in the
   species key footnote.
4. **Which bugs in which regions.** `dashboard/data/species.js` (already written, loaded after
   `timeline.js`) carries per-block and per-trap daily counts for `codling_moth` (primary),
   `oriental_fruit_moth` (lookalike) and `spotted_lanternfly` (invasive, all zeros this season).
   Analytics panels below the fold, all driven by the current replay day:
   - **Species by region**: six small horizontal stacked bars (one per block) of 7-day totals,
     codling vs oriental fruit moth, with the invasive shown as "none detected" text.
   - **Catch heatmap**: blocks (rows) by week (columns, Apr 15 to today) of codling catch,
     sequential single-hue ramp of the accent, week labels, today's column outlined.
   - **Trap table**: 18 rows: trap id, block, today's codling count, 7-day total, oriental fruit
     moth 7-day, trend arrow from the last two weeks, sorted by 7-day total; the selected block's
     traps grouped first.
   - **Degree-day race**: cumulative DD since biofix per block as six lines on one chart, with the
     250 and 350 thresholds as rules; blocks without biofix flat at 0.
   - **Weather strip**: daily high and low band for the season with today marked and the day's DD.
   - **KPI strip** at the top of the analytics section: moths today (all traps), 7-day change in
     percent vs the prior 7 days, blocks needing spray, traps above 10 today, DD rate (trailing 7
     days), days to the next block's window (from the trailing rate, labelled estimate).
5. **Agent panel.** In the spine under the clock: "Ask FieldOps". A transcript, a text field, a
   mic button, and quick questions ("Why is Block C red?", "Which block is next?", "What did the
   traps catch today?"). Answers come first from a local deterministic responder that reads the
   timeline for the current day (block status, DD, counts, biofix date, next block by DD rate) so
   it works with no server; if `fieldops/api.py` exposes an ask or chat endpoint on localhost it is
   tried first with a 4 second timeout and the local answer is the fallback. The mic button uses
   the browser's SpeechRecognition when present and shows "Voice needs the box's Whisper" when not.
   It must look like a place a voice agent lives: a small pulsing dot when "listening", the
   transcript in Plex, nothing modal.
6. **Phone buzz.** When a `spray_window_open` event fires during replay, POST to the tool server's
   alert endpoint if it exists (read `fieldops/api.py` for the route, port and body), fire and
   forget, never block the replay, never show a "sent" claim without a 2xx.

## Keep from v1 (do not regress)

Data loading order `sample_timeline.js`, `timeline.js`, `species.js` with a "no timeline" state;
works from `file://` and from `python3 -m http.server`; zero external hosts; replay plays 139 days
in about 30 s; events dedupe per run; scrubbing fires the destination day's events; `?date=`,
`?focus=`, `?fire=1` deep links; `navigator.onLine` badge "Running locally on ProMaxGB10" /
"Offline, still running"; crop selector reduced to the species key (Codling moth replay, Oriental
fruit moth lookalike, Spotted lanternfly invasive).

## Files

- `dashboard/index.html`: page, CSS, replay engine, map, curve, clock, dock, alert, agent panel.
  Embeds the two fonts.
- `dashboard/analytics.js`: `window.FOA = { render(dayIndex, selectedBlock) }` that fills the
  analytics containers (`#foa-kpi`, `#foa-species`, `#foa-heat`, `#foa-traps`, `#foa-ddrace`,
  `#foa-weather`) from `window.FIELDOPS_TIMELINE` and `window.FIELDOPS_SPECIES`. Pure DOM writes
  into those ids, reads nothing else from the page, exposes nothing else. Loaded by index.html
  after the data files; index.html calls `FOA.render` on every replay tick that changes the day
  (throttle to at most 10 renders per second) and on block selection.
- `dashboard/data/species.js`: already generated by `dashboard/tools/make_species.py`.
- `pitch/DEMO.md`: update the dashboard beats after the build.
