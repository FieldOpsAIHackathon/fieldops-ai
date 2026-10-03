# FieldOps demo runbook

Three minutes, five beats. Two browser tabs open before you walk up, both loaded from disk:

1. `pitch/index.html` (the deck)
2. `dashboard/index.html` (the replay)

Both work with the network off. Open them from `file://`, no server needed. Test the unplug once
before the pitch, not during it.

## Before you start

- Dashboard tab: load it fresh so the replay starts on April 15. Click **Block C** once so the
  curve and the degree-day clock follow the lead block.
- If a real `dashboard/data/timeline.js` exists it overrides the sample automatically. Make sure
  the one on the demo machine is the one you rehearsed with.
- Check the badge top right reads "Running locally on ProMaxGB10". When the cable comes out it
  flips to "Offline, still running" on its own.
- Optional: tick **Alert sound** so the spray banner chimes. Muted by default.
- To buzz the phone, start the tool server in a terminal first: `python -m fieldops.api`. Put the
  Telegram token and chat ID in `~/.config/fieldops.env` (or the environment) beforehand; the file
  stays out of the repo. It texts twice per replay: biofix, then Block C's spray window. If the server
  is not running the banners still show, so the demo never depends on it. Do not also run
  `python -m fieldops.agent --replay`.

## The beats

**1. Problem (30 s), deck slides 1 to 2.** The grower, 20 traps, found out Friday. Slide 2 is
the 50-moth trap photo with "Found 4 days too late."

**2. Why it is hard (20 s), slide 3.** Hand counting, no signal, no subscription per trap.

**3. Live demo (90 s), slide 4 is the cue card, then switch to the dashboard tab.**

- If the live count is running, show it first: point the webcam at the sparse card, then the
  dense card. The count jumps. Fifteen seconds, no more.
- Then the replay. Say "a whole season in thirty seconds" and press **Play season**. Let it run.
  - Mid May: Block C turns amber. "Biofix. First sustained catch. The degree-day clock starts."
  - Early June: Block C turns red and the banner lands: "Spray window open on Block C." That is
    the line. Read it off the screen. Thursday, June 4 on the committed season data.
  - The other blocks follow over the next days and stack their own banners.
- If a judge asks "why Thursday": click the degree-day clock. It shows the accumulated total
  against 250 DD and the biofix date. The curve shows the catch that set the biofix.
- Keyboard if the mouse misbehaves: **space** plays and pauses, **left/right arrows** step one
  day, **Next event** jumps to the next alert.
- Deep link if you need to land on the money shot directly:
  `dashboard/index.html?date=2026-06-04&focus=block-c&fire=1` opens on June 4 with the banner up.

**4. Why local (20 s), slide 6.** Pull the cable. Point at the badge flipping to "Offline, still
running". Press play again if you want to prove it.

**5. Platform (20 s), slide 7.** Click the crop chips on the slide, or use the **Crop and pest
model** selector on the dashboard. Same box, new species list.

Close on slides 8 and 9: what we cut, what is next, the team.

## If something breaks

- Replay stalls or the page is blank: reload the tab. The sample data is baked into the page
  folder, so a reload always works offline.
- Banners already shown do not repeat after a rewind. To show them again, scrub back to April 15
  and press play, or use the deep link above.
- Live count fails: skip it. Say live counting is in progress and go straight to the replay. The
  replay is the pitch.
- Deck navigation: arrow keys or space. Print to PDF from the browser if you need a fallback copy.
