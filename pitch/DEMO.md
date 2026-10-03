# FieldOps demo runbook

Three minutes, five beats. Two browser tabs open before you walk up:

1. `pitch/index.html` (the deck), opened from disk.
2. `dashboard/index.html` (the orchard dashboard), served from the repo root so live mode works:

```bash
cd fieldops-ai && python3 -m http.server 8787        # then open http://localhost:8787/dashboard/index.html
python3 dashboard/tools/simulate_feed.py --pace 1    # second terminal: readings start arriving
```

Both work with the network off (localhost is not the network). The dashboard also opens straight
from `file://` for the replay alone. Test the unplug once before the pitch, not during it.

## Before you start

- Dashboard tab: load it fresh so the replay starts on April 15. Click **Block C** on the orchard
  plan once so the curve, the degree-day clock and the analytics follow the lead block.
- The spine shows **Farm health** (a demo heuristic, say so if asked), the clock, **Ask FieldOps**
  and the alert log. Below the fold is **Season analytics**: species by region, the weekly catch
  heatmap, the trap table, the degree-day race and the weather strip, all following the current day.
- If a real `dashboard/data/timeline.js` exists it overrides the sample automatically. Make sure
  the one on the demo machine is the one you rehearsed with.
- Check the badge top right reads "Running locally on ProMaxGB10". When the cable comes out it
  flips to "Offline, still running" on its own.
- Optional: tick **Alert sound** so the spray banner chimes. Muted by default.
- To buzz the phone, start the tool server in a terminal first: `python -m fieldops.api`. Set up
  Telegram once beforehand with `python -m fieldops.telegram_setup`, which checks the bot token, finds
  your chat, saves both to `~/.config/fieldops.env` (outside the repo, owner-only) and sends a test
  message. It texts twice per replay: biofix, then Block C's spray window. If the server
  is not running the banners still show, so the demo never depends on it. Do not also run
  `python -m fieldops.agent --replay`.

## The beats

**1. Problem (30 s), deck slides 1 to 2.** The grower, 20 traps, found out Friday. Slide 2 is
the 50-moth trap photo with "Found 4 days too late."

**2. Why it is hard (20 s), slide 3.** Hand counting, no signal, no subscription per trap.

**3. Live demo (90 s), slide 4 is the cue card, then switch to the dashboard tab.**

- If the live count is running, show it first: point the webcam at the sparse card, then the
  dense card. The count jumps. Fifteen seconds, no more.
- Data arriving: with the simulator running, press **Live**. Readings land in the feed strip under
  the map, each with its trap photo, and the day advances as they come in. "Every trap reports to
  the box; nothing leaves the farm." Ten seconds, then press **Play season**, which turns Live off.
- The replay. Say "a whole season in thirty seconds". Let it run.
  - Mid May: Block C turns amber, "At risk". "Biofix. First sustained catch. The clock starts."
  - Early June: Block C's outline flares, the block turns red, "Needs spray", and the signal band
    reads "Spray window open on Block C." That is the line. Read it off the screen. Thursday,
    June 4 on the committed season data.
  - The other blocks follow over the next days; the band and the log update for each.
- If a judge asks "why Thursday": press **Why is Block C red?** in the Ask panel, or click the
  clock. Both give the accumulated degree-days against 250 and the biofix date. The curve shows the
  catch that set the biofix. Scroll to the analytics for which traps and which species.
- Keyboard if the mouse misbehaves: **space** plays and pauses, **left/right arrows** step one
  day, **Next event** jumps to the next alert.
- Deep link if you need to land on the money shot directly:
  `dashboard/index.html?date=2026-06-04&focus=block-c&fire=1` opens on June 4 with the banner up.

**4. Why local (20 s), slide 6.** Pull the cable. Point at the badge flipping to "Offline, still
running". Press play again if you want to prove it.

**5. Platform (20 s), slide 7.** Click the crop chips on the slide. On the dashboard, the species
key under the curve lists the lookalike and the invasive, and the analytics track them per block.
Same box, new species list.

Close on slides 8 and 9: what we cut, what is next, the team.

## If something breaks

- Replay stalls or the page is blank: reload the tab. The sample data is baked into the page
  folder, so a reload always works offline.
- Banners already shown do not repeat after a rewind. To show them again, scrub back to April 15
  and press play, or use the deep link above.
- Live count fails: skip it. Say live counting is in progress and go straight to the replay. The
  replay is the pitch.
- Live toggle shows "Live mode needs the page served": the tab was opened from disk. Open it from
  the localhost address instead, and check the simulator terminal is still printing days.
- Deck navigation: arrow keys or space. Print to PDF from the browser if you need a fallback copy.
