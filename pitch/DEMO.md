# FieldOps final presentation

Open [the final HTML deck](2026-10-03-fieldops.html). The existing `pitch/index.html`
entry point opens the same deck. Serve the repository for the most reliable video playback:

```bash
python3 -m http.server 8789
# http://127.0.0.1:8789/pitch/
```

The HTML embeds its static imagery and fonts. Keep `pitch/video/fieldops-demo.mp4`
beside it at the existing relative path. This is the sole published MP4; the shared
video URL remains unchanged. Video playback, the deck, and the committed dashboard
replay do not need the GB10 or internet once the files are local.

## Three-minute presenter path

1. **Slide 1, 12 seconds:** explain the grower's problem: manual trap checks leave
   gaps while pest activity and treatment windows change.
2. **Slide 2, 15 seconds:** state the value: which block needs attention, and when.
   The committed June 4 replay has Block C at 26 codling moths and 261 degree-days.
3. **Slide 3, 117 seconds:** play the embedded film. Let its narration carry the demo.
   The video is a recorded demonstration, with concept drone footage labeled.
4. **Slide 4, 18 seconds:** explain the local GB10 architecture. Code computes the
   timing. The agent explains facts. Telegram delivery uses a network connection.
5. **Slide 5, 18 seconds:** close on the intended grower value and next step: a field
   pilot to validate counts on real traps and measure time saved.

Slide 6 is an evidence appendix for questions. Arrow/Page keys navigate, F toggles
fullscreen, and the deck's notes control reveals the speaker notes. Use the native
video controls on slide 3; navigation does not steal keys while video has focus.

## Evidence to keep straight

- **Replay:** June 4, 2026; Block C; 26 codling moths across three traps (10, 10, 6);
  261 degree-days after the May 8 biofix. The model confirms sustained catch on May 9.
  The configured window is 250–350 DD. May 8 itself is excluded from accumulation.
- **Reference image:** the trap lab shows 12 codling and 3 oriental fruit moths with
  manifest annotations. It is a synthetic reference, separate from replay counts.
- **Telegram photo test:** 25 codling and 6 oriental fruit moths, 31 total. Its block
  context is the May 25 replay (149.5 DD rounded to 150), not the June 4 snapshot.
- **3D drone:** a simulated survey and virtual aerial previews. Physical drone
  integration and aerial insect detection are future work.
- **Dashboard voice:** selected local season facts spoken by GB10 Kokoro. The film
  uses the authentic recorded reply. Browser-local dictation depends on browser
  support; the dashboard is not a verified speech-to-speech LLM conversation.
- **Detector:** working local inference on demo trap photos. No field-validated
  accuracy, yield improvement, pesticide reduction, or ROI is claimed.

## Optional live follow-up

Open `../dashboard/?date=2026-06-04&focus=block-c` from the repo server. Use
**Reset demo view** if another block or day was selected. The 3D survey now preserves
that selection and camera; **Review captures** opens the completed survey gallery.

For spoken output, first verify `http://127.0.0.1:8790/health` and the GB10 connection.
Choose **Type instead**, enter a question, then **Hear answer**. If the voice service
is unavailable, play the recorded response in the film. Do not imply the recording
is a live connection. Normal dashboard browsing does not send phone notifications.

The core inference can run locally; Telegram cannot deliver messages without a
network. A stale replay state or old observation is not current farm evidence.
Always retain the visible snapshot date when explaining a result.
