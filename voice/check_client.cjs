/* Run: node voice/check_client.cjs — no browser or model required. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const window = new EventTarget();
const nodes = [];
class AudioContext {
  currentTime = 0;
  destination = {};
  resume() { return Promise.resolve(); }
  createBuffer(channels, length, rate) { return {duration:length/rate, getChannelData:()=>new Float32Array(length)}; }
  createBufferSource() {
    const node = {connect(){}, disconnect(){}, start(time){this.time=time;}, stop(){this.stopped=true;}};
    nodes.push(node); return node;
  }
}
window.AudioContext = AudioContext;
let impl;
vm.runInNewContext(fs.readFileSync('dashboard/voice.js','utf8'), {window, EventTarget, CustomEvent, AbortController, AbortSignal, TextDecoder, setTimeout, clearTimeout, performance, atob, fetch:(...args)=>impl(...args)});
const audioFrame = {type:'audio', text:'hello', pcm:Buffer.alloc(4800).toString('base64'), cached:false};
const response = () => new Response([JSON.stringify({type:'start',sample_rate:24000}),JSON.stringify(audioFrame),JSON.stringify(audioFrame),JSON.stringify({type:'done',synthesis_ms:5,audio_seconds:.2})].join('\n')+'\n');
(async () => {
  const p = new window.FieldOpsVoice();
  impl = async () => response();
  await p.speak('First. Second.');
  assert.equal(p.state, 'speaking');
  assert.equal(nodes.length, 2);
  assert.equal(nodes[0].time, .035);
  assert.ok(Math.abs(nodes[1].time-.135)<1e-9, 'sentences must be scheduled contiguously');
  nodes[0].onended();
  assert.equal(p.state, 'speaking', 'completion waits for actual final audio');
  nodes[1].onended();
  assert.equal(p.state, 'idle');
  await p.speak('Another reply.'); p.stop();
  assert.equal(p.state, 'idle'); assert.ok(nodes.slice(-2).every(n=>n.stopped));
  let deliver;
  impl = () => new Promise(resolve => {deliver=resolve;});
  const stale = p.speak('An old reply.');
  await new Promise(resolve => setTimeout(resolve,0));
  p.stop();
  impl = async () => response();
  const newer = p.speak('The new reply.');
  await newer; const nodeCount = nodes.length;
  deliver(response()); await stale;
  assert.equal(nodes.length,nodeCount,'cancelled network response must never schedule sound');
  assert.equal(p.state,'speaking','stale reply must not overwrite current state');
  p.stop();
  let finishDecode;
  AudioContext.prototype.decodeAudioData = () => new Promise(resolve => { finishDecode = resolve; });
  impl = async () => new Response(JSON.stringify({type:'audio', encoding:'opus', audio:audioFrame.pcm})+'\n'+JSON.stringify({type:'done'})+'\n');
  const decoding = p.speak('A decoding reply.');
  await new Promise(resolve => setTimeout(resolve,0));
  p.stop(); impl = async () => response();
  await p.speak('A replacement reply.');
  const afterReplacement = nodes.length;
  finishDecode({duration:.1}); await decoding;
  assert.equal(nodes.length,afterReplacement,'stale decoder completion must not schedule audio');
  assert.equal(p.state,'speaking'); p.stop();
  impl = async () => new Response(JSON.stringify({error:'busy'}), {status:429});
  await assert.rejects(()=>p.speak('Hello'), /busy/);
  assert.equal(p.state,'error');
  impl = async () => new Response(JSON.stringify(audioFrame)+'\n');
  await assert.rejects(()=>p.speak('Hello'), /ended early/);
  assert.equal(p.sources.size,0,'truncated audio must stop queued buffers');
  console.log('PASS contiguous scheduling, actual playback completion, immediate stop, stale response/decoder suppression, busy error, truncated stream cleanup');
})();
