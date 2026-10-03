# FieldOps: Hackathon Plan

Pitch story and build components for the Dell x NVIDIA AI Hackathon, October 3, 2026.

## The story: a 3-minute pitch in five beats

**1. The problem (30 sec).** "Meet a Massachusetts apple grower. He has 20 traps and checks them once a week. Last season the moths started flying on a Monday. He found out Friday, and by then the larvae were in his fruit." One slide: a trap photo full of moths, with the caption "Found 4 days too late."

**2. Why it's hard today (20 sec).** Counting by hand is slow and inconsistent. Cloud trap cameras exist, but orchards have no signal and growers don't want a subscription per trap.

**3. Live demo (90 sec), the heart of the pitch.**

- Point a webcam at a printed sticky-trap card. The model draws boxes and live counts per species. Swap in a second card with more moths and the count jumps.
- Then the money shot: **replay a whole season in 30 seconds.** A dashboard plays back weeks of trap counts and temperatures. The flight curve rises, FieldOps calls the biofix, the degree-day clock starts, and a phone buzzes on stage: "Biofix reached on block C. Spray window opens Thursday."

**4. Why local (20 sec).** "Everything you just saw ran on this box. No internet. The farm owns its data." Then unplug the network cable live; it keeps working.

**5. The platform (20 sec).** "Same box, new species list: cranberry bogs, blueberries, sweet corn, vineyards." Show the species config switching on screen.

The season replay is what wins. A single live count is a nice trick; the replay shows the decision, which is the actual value.

## Components to build, by priority

### Must have (the demo breaks without these)

1. **Image ingest.** A webcam or folder watcher that grabs a frame every few seconds and simulates many traps (trap ID, timestamp). Keep it simple; there's no real camera network today.
2. **Detection and counting.** Two options:
    - Fastest: a local vision-language model on the GB10, prompted to count and name insects and return JSON. Zero training.
    - Better accuracy if someone already knows YOLO: a small detector trained on a public sticky-trap insect dataset. Riskier on a deadline.

    Start with the VLM and swap later only if time allows.
3. **Count store.** A SQLite table of trap, time, species and count. Nothing fancier.
4. **Season replay data.** A synthetic but realistic CSV of daily counts and temperatures for one season, shaped like a real flight curve. Pre-build it so the replay never depends on live inference.
5. **Decision logic.**
    - Biofix rule: first sustained catch, meaning counts above a threshold on consecutive checks.
    - Degree-day accumulation from daily highs and lows.
    - A threshold that marks the spray window.

    Write this as plain code, not an LLM, so it's deterministic and right on stage.
6. **Agent layer.** A local LLM that reads the decision output and writes the grower-facing alert in plain language. It can also answer questions like "Why do you want me to spray Thursday?" If the hackathon expects OpenClaw or NemoClaw, this is where it plugs in, with tools such as `get_counts`, `get_degree_days` and `send_alert`.
7. **Alert.** A phone notification (Telegram bot or SMS) that buzzes on stage.

### Should have

8. **Dashboard.** Trap map, flight curve, degree-day clock, alert log, and the replay button. A single page is enough.
9. **Species config.** A small file with each crop's pest list and thresholds, so you can show the platform switch.

### Skip today

- Real field hardware, solar power or LoRa radios: describe them on a slide.
- Model fine-tuning, unless it's already working.
- User accounts and multi-farm support.

## Team split (for 3 to 4 people)

- **Person A, vision:** ingest plus the counting model, outputting JSON counts.
- **Person B, brains:** count store, replay data, biofix and degree-day logic.
- **Person C, agent and alert:** local LLM alert writer, Q&A, phone notification.
- **Person D, or whoever finishes first:** dashboard, pitch slides, printed trap cards.

**Integration contract:** agree right now on one JSON shape for counts: trap ID, timestamp, species, count. Then everyone builds in parallel.

**Checkpoint:** aim to have the season replay working end to end, with alert, before polishing anything. If live counting turns out flaky, the replay alone still tells the whole story.
