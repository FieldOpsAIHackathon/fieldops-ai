/* Local speech output. Synthesis runs ahead; Web Audio schedules gapless PCM. */
(function (global) {
  'use strict';
  class FieldOpsVoice extends EventTarget {
    constructor(options = {}) {
      super();
      this.endpoint = (options.endpoint || 'http://127.0.0.1:8790').replace(/\/$/, '');
      let preferences = {};
      try { preferences = JSON.parse(global.localStorage?.getItem('fieldops.voice') || '{}') || {}; } catch (_) {}
      this.voice = options.voice || (['orchard','heart','bella','fenrir'].includes(preferences.voice) ? preferences.voice : 'orchard');
      this.speed = options.speed || (preferences.speed >= .85 && preferences.speed <= 1.15 ? Number(preferences.speed) : 1);
      this.format = global.document?.createElement('audio').canPlayType('audio/ogg; codecs=opus') ? 'opus' : 'pcm';
      this.epoch = 0;
      this.sources = new Set();
      this.context = null;
      this.state = 'idle';
    }
    savePreferences() {
      try { global.localStorage?.setItem('fieldops.voice', JSON.stringify({voice:this.voice, speed:this.speed})); } catch (_) {}
    }
    update(state, details = {}) {
      this.state = state;
      this.dispatchEvent(new CustomEvent('state', {detail: {state, ...details}}));
    }
    async health() {
      const response = await fetch(this.endpoint + '/health', {signal: AbortSignal.timeout(4000)});
      if (!response.ok) throw new Error('The local voice service is unavailable.');
      return response.json();
    }
    stop() {
      this.epoch++;
      this.controller?.abort();
      for (const source of this.sources) {
        source.onended = null;
        try { source.stop(); } catch (_) { /* already ended */ }
        source.disconnect();
      }
      this.sources.clear();
      this.update('idle');
    }
    async speak(text, options = {}) {
      this.stop();
      const epoch = this.epoch;
      const current = () => epoch === this.epoch;
      if (!text?.trim()) return;
      const Audio = global.AudioContext || global.webkitAudioContext;
      if (!Audio) {
        const message = 'This browser does not support audio playback.';
        this.update('error', {message});
        throw new Error(message);
      }
      this.context ||= new Audio({latencyHint: 'interactive'});
      this.controller = new AbortController();
      const controller = this.controller;
      const started = performance.now();
      let firstAudio = true, nextTime = 0, receivedDone = false, rate = 24000;
      const finishIfDone = () => { if (current() && receivedDone && this.sources.size === 0) this.update('idle'); };
      let idleTimer;
      const resetTimeout = () => {
        clearTimeout(idleTimer);
        idleTimer = setTimeout(() => controller.abort(new Error('Local voice timed out.')), 30000);
      };
      this.update('preparing');
      try {
        // Called synchronously from the user's gesture, before awaiting network.
        await this.context.resume();
        if (!current()) return;
        resetTimeout();
        const response = await fetch(this.endpoint + '/stream', {
          method: 'POST', headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({input: text, voice: options.voice || this.voice, speed: options.speed || this.speed, response_format: this.format}),
          signal: controller.signal
        });
        if (!response.ok) {
          const error = await response.json().catch(() => ({}));
          throw new Error(error.error || 'The local voice service is unavailable.');
        }
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let pending = '';
        const consume = async (line) => {
          if (!line.trim() || !current()) return;
          const event = JSON.parse(line);
          if (event.type === 'error') throw new Error(event.error);
          if (event.type === 'start') { rate = event.sample_rate; return; }
          if (event.type === 'done') {
            receivedDone = true;
            this.dispatchEvent(new CustomEvent('metrics', {detail: event}));
            finishIfDone();
            return;
          }
          if (event.type !== 'audio') return;
          const raw = atob(event.audio || event.pcm);
          let buffer;
          if (event.encoding === 'opus') {
            const bytes = Uint8Array.from(raw, character => character.charCodeAt(0));
            buffer = await this.context.decodeAudioData(bytes.buffer);
            if (!current()) return;
          } else {
            buffer = this.context.createBuffer(1, raw.length / 2, rate);
            const samples = buffer.getChannelData(0);
            for (let i = 0; i < samples.length; i++) {
              const value = raw.charCodeAt(2 * i) | raw.charCodeAt(2 * i + 1) << 8;
              samples[i] = (value >= 32768 ? value - 65536 : value) / 32768;
            }
          }
          const source = this.context.createBufferSource();
          source.buffer = buffer;
          source.connect(this.context.destination);
          this.sources.add(source);
          source.onended = () => { this.sources.delete(source); source.disconnect(); finishIfDone(); };
          nextTime = Math.max(nextTime, this.context.currentTime + .035);
          source.start(nextTime);
          nextTime += buffer.duration;
          if (firstAudio) {
            firstAudio = false;
            this.update('speaking', {firstAudioMs: Math.round(performance.now() - started), cached: event.cached});
          }
        };
        while (current()) {
          const {value, done} = await reader.read();
          if (!current()) { await reader.cancel(); return; }
          resetTimeout();
          pending += decoder.decode(value, {stream: !done});
          const lines = pending.split('\n');
          pending = lines.pop();
          for (const line of lines) await consume(line);
          if (done) { await consume(pending); break; }
        }
        if (!receivedDone) throw new Error('The audio connection ended early. Please try again.');
        clearTimeout(idleTimer);
        finishIfDone();
      } catch (error) {
        if (!current()) return;
        const message = controller.signal.aborted ? 'Local voice timed out. Please try again.' : error.name === 'TypeError' ? 'Cannot reach the GB10 voice service. Text answers are still available.' : error.message;
        this.stop();
        this.update('error', {message});
        throw new Error(message);
      } finally { clearTimeout(idleTimer); }
    }
  }
  global.FieldOpsVoice = FieldOpsVoice;
  global.fieldopsVoice = new FieldOpsVoice();
  // The dashboard can speak facts or an agent reply without coupling to its UI.
  global.addEventListener('fieldops:speak', event => {
    global.fieldopsVoice.speak(event.detail.text, event.detail).catch(() => {});
  });
  global.addEventListener('fieldops:stop-speaking', () => global.fieldopsVoice.stop());
  global.addEventListener('pagehide', () => global.fieldopsVoice.stop());
  global.addEventListener('storage', event => {
    if (event.key !== 'fieldops.voice') return;
    try {
      const prefs = JSON.parse(event.newValue);
      if (['orchard','heart','bella','fenrir'].includes(prefs?.voice)) global.fieldopsVoice.voice = prefs.voice;
      if (typeof prefs?.speed === 'number' && prefs.speed >= .85 && prefs.speed <= 1.15) global.fieldopsVoice.speed = prefs.speed;
    } catch (_) {}
  });
})(window);
