# Voice-first dashboard integration

The floating FieldOps panel starts in voice mode; chat is available through
**Type instead**. It is nonmodal, so map and date changes remain available while
it is open. The dashboard does not start listening or speaking on page load.

The voice session owns recognition, model/reasoning and `dashboard/voice.js`.
This UI owns the launcher, state display, optional text conversation and cleanup.
Load the voice integration after `app.js` (or register after app initialization).

```js
FOIntelligence.setVoiceAdapter({
  async start({ context, onTranscript, onState, onReply }) {
    // Called only from an explicit mic click. Request microphone access here.
    // Report onState('listening') only after capture actually starts.
    // For the built-in facts fallback: onTranscript(finalText).
    // For your own agent pipeline: onReply(replyText, { question: finalText }).
    // If this pipeline also plays audio, report speaking/idle via onState.
    // To use the dashboard's speech client: onReply(replyText, { speak: true }).
  },
  stop() {
    // Abort microphone capture, recognition and any pending agent turn.
  }
});
```

`context` contains the current authoritative snapshot, block, species, counts and
model states. Read `FieldOps.getContext()` for current context during longer turns.
Registering an adapter enables the mic UI; do not register a placeholder that
cannot capture audio. If no adapter exists, browser recognition is used only when
it supports on-device processing. Otherwise the UI offers text input honestly.

Output uses `window.fieldopsVoice.speak(text)` and `.stop()` when installed.
Its `state` events (`preparing`, `speaking`, `idle`, `error`) drive the UI.
The speak promise may settle before playback finishes; **idle must arrive as an
event when playback finishes**. The fallback uses only a local browser voice.

Additional methods:

- `FOIntelligence.submitVoice(text)`: submit recognized text to the season-facts
  fallback and speak its short answer during the active voice session.
- `FOIntelligence.presentReply(text, { question, speak: false })`: display your
  agent reply during an active session. Plain text is escaped; no model evidence
  is invented. Default is silent if the external pipeline already handles audio.
- `FOIntelligence.setVoiceState(state, { message })`: update visible state.

Document events are also available: `fieldops:voice-adapter` (`detail.adapter`),
`fieldops:voice-transcript` (`detail.text`, `final`), `fieldops:voice-reply`
(`detail.text`, `question`, `speak`), and `fieldops:voice-state` (`detail.state`,
`message`). The UI emits `fieldops:voice-request` with `{ action: 'start'|'stop',
context }`. Prefer the adapter callbacks to keep stale turns scoped correctly.
Stop/close cancels the session; late callbacks are ignored. The first Escape closes
voice; a subsequent Escape leaves the 3D view. No dashboard action sends alerts.
