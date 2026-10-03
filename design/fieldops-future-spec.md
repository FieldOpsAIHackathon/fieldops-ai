# FieldOps dashboard v3

Approved by Himanshu October 3, 2026; direct implementation, no intermediate walkthrough.

## Picks and visual system

Ion atlas A; Space + Manrope A; workspace rail A; orchard atlas A; flight observatory A;
spatial inspector A; evidence lab A; window planner B; daily briefing B; cinematic chapters A.
Reference: `fieldops-future-picker.html`. The user's notes require a natural irregular full-farm
boundary, visible grass/trees and labeled pest illustrations, plus a fixed bottom-right agent
launcher accessible on every dashboard tab. Use Astra for the farm artwork.

Dark tokens: bg #080f1b, surface #101b2b, surface2 #1a293c, ink #edf6ff,
muted #9daec3, line #263649, primary #70d8ed, primarySoft #153645,
onPrimary #062126, warn #ffce86. Light: bg #edf3f9, surface #ffffff,
surface2 #e2eaf3, ink #10243b, muted #526780, line #cbd8e6, primary #08657b,
primarySoft #d9eff4, onPrimary #ffffff, warn #885000. Surface radius12, controls7.
Display: Space (600–700); body: Manrope (400–700); local woff2 in dashboard/assets/fonts.
Body14px, metadata12px, panel18px, page34px, readings36–64px, all respond to --ts.
Use cyan/amber with labels and solid/dashed series; both modes passed contrast/colorblind checks.

## Product and behavior

A complete working offline HTML/CSS/JS dashboard, no framework install, no external network
needed for render. Six tabs with shared date/block/species state. Default June4,2026,BlockC.
Maintain date/focus deep links plus tab/species and presentation chapter. Keyboard navigation,
working filters, block selection, chart hover details, trap sorting/search, CSV export,
theme toggle, presentation/fullscreen and optional replay. Do not automatically send alerts
when navigating/replaying; an explicit user action is the only notification trigger.
No feed simulation work. Display “Demo season” and avoid invented live/model/health claims.

Overview: title “Your orchard. In perspective.” Four real KPI readings, natural farm map plus
selected-block window card, flight chart and next blocks. Orchard: expanded map with block
inspector and block-comparison cards. Pests: species filters, lead flight chart, weekly heatmap,
species per region and labeled pest reference illustrations. Traps: reference-image inspector
with manifest bounding boxes/counts, image gallery, sortable/searchable daily trap ledger.
Reference images are synthetic, separate from replay trap IDs. Weather: ranked DD progress,
selected-block timing, actual temperature history and degree-day curves. Intelligence: daily
briefing and evidence chain, quick questions. Fixed agent launcher opens accessible drawer
with local data-grounded responses; voice input only if supported, clearly labeled as browser
voice. No fake LLM/network success. Cinematic mode: full-bleed map and three navigable story
chapters (detect,biofix,window); hide workspace chrome, retain exit/keyboard controls.

Source: FIELDOPS_TIMELINE (sample fallback), FIELDOPS_SPECIES. Preserve decision statuses/
thresholds as authored by Python; never recompute biofix. Data through currentdate only.
History.csv is a separate irregular30trap,10species research dataset; do not silently mix.

## Parallel module contract

Root owns index.html, dashboard.css, model.js, app.js and browser validation.
Astra owns farm.js and farm.css only. Analytics agent owns panels.js and panels.css plus
`data/trap-reference.js` (generated manifest JS twin). Intelligence agent owns intelligence.js
and intelligence.css only. Each isolated worktree, no commits/pushes/reset/stash.
All modules are classic scripts with IIFEs, loaded before app.js. No imports/build step.
Shared CSS uses fx-* classes from picker: fx-card,fx-pad,fx-cardhead,fx-grid,fx-equal,
fx-kpis,fx-kpi,fx-number,fx-small,fx-muted,fx-tag,fx-progress,fx-row,fx-button,fx-strip.
Read dashboard/dashboard.css. Module-specific prefix farm-,pan-,intel- to avoid collisions.

Root model.js exposes window.FOModel.context(state), returning ctx:
- timeline, days, blocks, speciesData, day, index (current day index), block (selected id),
  species (id), range (7/30/season), tab, presentation, chapter.
- esc(value), num(value,digits=0), dateLabel(iso,opts?), icon(name,size=20).
- series(blockId,speciesId=ctx.species) => full date-aligned numbers (not truncated).
- count(blockId,index=ctx.index,speciesId=ctx.species) => number.
- total(index=ctx.index,speciesId=ctx.species) => farm count.
- weekly(blockId,speciesId=ctx.species,offset=0) =>7day total ending currentindex-offset.
- status(blockId=ctx.block) => current authoritative block state.
- actions.update(patch), actions.openAgent(question?), actions.navigate(tab).

Astra: window.FOFarm.map(ctx,{large=false}={}) => accessibleSVG/HTML string, root delegates
clicks on [data-block] to update selected block; elements keyboard operable role/button/tabindex.
window.FOFarm.pest(speciesId,size=72) => original SVG pest illustration (reference, not taxonomy
proof). Also window.FOFarm.legend(ctx) => labeled pest strip with counts, zero shown honestly.
Map status uses text/labels plus fills, natural farm enclosing six blocks, actual block names/
varieties/acres/counts fromctx. Schematic rather than geospatial claim. Make art memorable.

Analytics: window.FOPanels.renderPests(ctx), renderTraps(ctx), renderTiming(ctx) => HTML strings.
window.FOPanels.flight(ctx,{compact=false}={}) => reusable flight chart card HTML.
window.FOPanels.bind(container,ctx) => attach panel local interactions after root setsinnerHTML.
Global changes use ctx.actions.update. Scope species controls do not change deterministic
codling model; explain if viewing another species. Root handles all [data-block] clicks.
Charts title and explicitserieslegend, dateaxis positioned correctly, hover values/dates.
Trap refs script exposes window.FIELDOPS_TRAP_REFERENCE from manifest; refs relative ../data/traps/.

Intelligence: window.FOIntelligence.render(ctx) => daily briefing tab HTML.
window.FOIntelligence.mount(getContext) => append fixed launcher/drawer once, bind events;
getContext() returns latest ctx. Root dispatches CustomEvent('fieldops:change',{detail:ctx})
after app renders. Module updates open drawer without losing typed text/focus.
window.FOIntelligence.open(question?) => open and optionally answer quick question.
Drawer accessible dialog, Escape closes, focusreturnslauncher, keyboardfocuscontained.
Local answers use authoritative selecteddate data, explicitly fact-based without claimingLLM.

## Acceptance

Verify all6tabs and3chapters at1440x900 dark/light; check1920x1080 recording;150%text;
390px responsive layout with scrollable tables/nav and no page-wide overflow.
Test date/block/species filters update allnumbers, zero states,first/lastday,replay,deep links,
trap sort/search/image annotations, agent questions/close/focus,CSVdownload,theme/presentation.
Observe console and network: no external requests, no implicit alertPOST. Disable network and
load file:// to verify. Run project scripts/ci_check.py and node syntax for newJS. InspectPNG.

## Running and recording the completed dashboard

Open `dashboard/index.html` directly for an offline demo, or serve the repository:

```sh
python3 -m http.server 8789 --bind 127.0.0.1
```

Open `http://127.0.0.1:8789/dashboard/`. The default snapshot is June 4, 2026,
with Block C selected. Date, block, species, tab and 3D mode are shareable
through the URL. No database setup or package install is required.

- Use the workspace rail for Overview, Pest analytics, Orchard blocks, Trap lab,
  Weather & timing, and Intelligence.
- Select **3D farm** to explore the orchard. Drag to orbit, scroll/pinch to zoom,
  and Shift/right-drag to pan. Choose a block to inspect it. R resets the view;
  T selects overhead; Escape returns to the workspace. Orbit tour rotates slowly
  for recording and stops when you interact with the map.
- Select **Talk to FieldOps** to open the voice panel. **Type instead** reveals
  optional chat and supporting facts. The panel remains open while you explore.
  The independent voice pipeline connects through `dashboard/VOICE_UI.md`;
  the built-in answer fallback reads committed season facts.
- **Export snapshot** downloads the selected date/species as a six-block CSV.
- **Play season** replays the committed 139-day dataset; no feed simulation runs.

Piyush's historical mock observations have their own view under Pest analytics.
`dashboard/tools/build_dashboard_data.py` regenerates the browser data twins from
`data/history.csv` and `data/traps/manifest.json`. Historical samples, synthetic trap
reference imagery, and daily replay observations keep their separate provenance.
The farm is an original SVG illustration with selectable blocks and labeled pests.

Jennifer's optional `projected_open` is used in accumulating-block timing cards,
assistant answers and exports. Display it as an estimate “around” a date, without
a weekday. The committed climate normals supply this estimate; the dashboard
never computes a replacement spray date or changes decision states.

## October 3 refinement: 3D farm and voice-first agent

Explicit user direction: push all current work, replace cinematic chapters with an
interactive navigable 3D farm, make the floating agent voice-first with an optional
chat view. The independent voice session owns AI/audio service and voice.js; this
build owns its minimal UI, state display, cancellation and integration hooks.
Insects should look more imposing and detailed while remaining recognizable.

3D: locally bundled Three.js, no runtime CDN; classic script works from file://.
Natural grassy irregular terrain with tree rows, hedges, paths, pond, barn, six
selectable labeled blocks and 18 trap markers. Drag to orbit, wheel/pinch zoom,
right-drag/shift-drag pan; explicit home/top/angled view, +/- and keyboard controls.
Selecting a block updates dashboard focus and a compact inspector. Minimal overlay
chrome, full-height viewport, optional auto-orbit for recording with clear stop.
Real block statuses/counts from current snapshot; schematic geometry clearly labeled.
WebGL failure gets a working 2D map fallback. Release all renderer resources on exit.

Farm module API: window.FOFarm3D.mount(container,ctx) -> controller with
update(ctx), destroy(), home(), focus(blockId), setView('orbit'|'top'), zoom(delta),
setAutoRotate(boolean), getState(). Selection invokes ctx.actions.update({block:id}).
Mount owns canvas and projected DOM block labels only. Labels must be clickable and
accessible. Preserve camera across update calls. Root app owns toolbar/inspector.
THREE and THREE.OrbitControls are provided locally before farm3d.js.

Voice UI: compact floating orb/mic launcher; on opening, a small clean voice panel
with one primary mic button, status (ready/listening/thinking/speaking/error), latest
utterance/brief reply, explicit Stop, and secondary keyboard/chat toggle. Chat is
hidden initially and accessible when requested. Never claim to hear/understand audio
without input support. Keep mic permission tied to a user gesture and stop mic/audio
on close. Local-browser recognition only if available; otherwise show unavailable
honestly while exposing hooks for the voice session. Preserve local-facts fallback,
block/date context and evidence in optional chat. Speech output uses fieldopsVoice
when installed, else supported local browser voice. No automatic network polling.

## Drone survey extension for the demo film

User clarified the intended collection story: drones survey the farm and collect
imagery for analysis. Add a clearly labeled simulated drone mission to the 3D
farm and a Survey review workspace. The existing code analyzes trap photos; do
not misrepresent that as deployed drone hardware or pest counts from aerial pixels.
Aerial views provide spatial coverage; linked trap observations and the degree-day
model provide the demonstrated pest/timing findings. June 4 / Block C remains the
strongest consistent story: 26 codling moths and 261 DD, one open window.

Start drone survey animates a quadcopter along six block waypoints over 24 seconds.
Order: A, B, D, E, F, C. Show capture count, pause/resume/reset and optional follow
camera. Playback never triggers a phone alert, inference request or real flight.
Capture cards use committed virtual aerial previews rendered from this farm.
The Survey workspace joins these to the selected day's actual trap counts and
states. Selecting a capture focuses its block; inspect its evidence and ask the
agent about its timing. A completed survey offers a next step to review Block C.
