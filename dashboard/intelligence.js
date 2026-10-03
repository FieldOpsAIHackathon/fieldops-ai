(function () {
  'use strict';
  const labels = {watching:'Watching for biofix', accumulating:'Accumulating degree-days', spray_window:'Spray window open', window_closed:'Window closed'};
  let getContext, host, dialog, input, log, launcher, returnFocus, recognition, listening = false;
  const messages = [];
  const modelSpecies = ctx => ctx.timeline.farm.pest || 'codling_moth';
  const pestName = (ctx, id = ctx.species) => ctx.speciesData.display?.[id] || id.replaceAll('_', ' ');
  const blockName = (ctx, id) => ctx.blocks.find(b => b.id === id)?.name || id;
  const stateOf = (ctx, id) => ctx.day.blocks[id] || {status:'watching', biofix_date:null, dd_since_biofix:0};
  const projectedOpen = (ctx, id) => {
    const s=stateOf(ctx,id);
    return s.status==='accumulating' && /^\d{4}-\d{2}-\d{2}$/.test(s.projected_open||'') && s.projected_open>ctx.day.date
      ? `around ${ctx.dateLabel(s.projected_open,{month:'short',day:'numeric'})}` : '';
  };
  const projectionExplanation = (ctx, id) => {
    const estimate=projectedOpen(ctx,id);
    return estimate ? `The season model estimates ${blockName(ctx,id)}'s window will open ${estimate}, using the farm's 2016–2025 climate normals. Actual timing can shift with the weather.` : 'No calendar estimate is recorded for this block.';
  };
  const eventsThrough = ctx => ctx.days.slice(0, ctx.index + 1).flatMap(d => (d.events || []).map(e => ({...e, date:d.date})));
  function facts(ctx) {
    const thresholds = ctx.timeline.thresholds, selected = stateOf(ctx, ctx.block);
    const open = ctx.blocks.filter(b => stateOf(ctx,b.id).status === 'spray_window');
    const next = ctx.blocks.filter(b => stateOf(ctx,b.id).status === 'accumulating').sort((a,b) => stateOf(ctx,b.id).dd_since_biofix - stateOf(ctx,a.id).dd_since_biofix)[0];
    const closed = ctx.blocks.filter(b => stateOf(ctx,b.id).status === 'window_closed');
    const confirmed = ctx.blocks.filter(b => stateOf(ctx,b.id).biofix_date);
    return {thresholds,selected,open,next,closed,confirmed};
  }
  function summary(ctx) {
    const f = facts(ctx), n = ctx.num, pest = pestName(ctx, modelSpecies(ctx));
    if (f.open.length) return `${f.open.map(b=>b.name).join(', ')} ${f.open.length===1?'is':'are'} in the ${pest.toLowerCase()} spray window.`;
    if (f.next) return `${f.next.name} is closest to the next spray window.`;
    if (f.closed.length === ctx.blocks.length) return 'The modeled spray window has closed across the orchard.';
    return `Watching ${n(ctx.blocks.reduce((s,b)=>s+b.traps.length,0))} traps for sustained ${pest.toLowerCase()} flight.`;
  }
  function detail(ctx) {
    const f=facts(ctx), n=ctx.num;
    if (f.open.length) return `The season model places ${f.open.length===1?'this block':'these blocks'} in its ${n(f.thresholds.spray_open_dd)}–${n(f.thresholds.spray_close_dd)} degree-day window. ${f.next?`${f.next.name} follows at ${n(stateOf(ctx,f.next.id).dd_since_biofix,1)} DD.${projectedOpen(ctx,f.next.id)?' Its estimated opening is '+projectedOpen(ctx,f.next.id)+', based on climate normals.':''}`:'No additional blocks are accumulating toward an unopened window.'}`;
    if (f.next) return `${ctx.num(stateOf(ctx,f.next.id).dd_since_biofix,1)} degree-days accumulated since biofix; ${n(Math.max(0,f.thresholds.spray_open_dd-stateOf(ctx,f.next.id).dd_since_biofix),1)} DD remain to the opening threshold. ${projectionExplanation(ctx,f.next.id)}`;
    return f.closed.length===ctx.blocks.length?'Continue reviewing trap activity. The timeline contains one modeled biofix cycle per block; a closed window is not a new-cycle prediction.':`Biofix requires ${n(f.thresholds.biofix_min_count)} or more moths on ${n(f.thresholds.biofix_consecutive_checks)} consecutive checks. The recorded timeline determines when each clock starts.`;
  }
  function orb(size='large') { return `<span class="intel-orb intel-orb-${size}" aria-hidden="true"><i></i><i></i><i></i><span></span></span>`; }
  function evidence(ctx, id=ctx.block) {
    const s=stateOf(ctx,id), n=ctx.num, name=blockName(ctx,id), pest=pestName(ctx,modelSpecies(ctx));
    return [
      {label:'Observation',value:`${n(ctx.count(id,ctx.index,modelSpecies(ctx)))} ${pest.toLowerCase()}`,note:`${name} · ${ctx.blocks.find(b=>b.id===id)?.traps.length||0} traps · ${ctx.dateLabel(ctx.day.date)}`},
      {label:'Biofix',value:s.biofix_date?ctx.dateLabel(s.biofix_date):'Not established',note:s.biofix_date?'Recorded sustained-catch start':'Waiting for sustained catch'},
      {label:'Thermal clock',value:`${n(s.dd_since_biofix,1)} DD`,note:`Window ${n(ctx.timeline.thresholds.spray_open_dd)}–${n(ctx.timeline.thresholds.spray_close_dd)} DD`},
      {label:'Decision',value:labels[s.status]||s.status,note:'Deterministic season model'}
    ];
  }
  function render(ctx) {
    const {esc:e,num:n,dateLabel:d,icon}=ctx, f=facts(ctx), s=f.selected, b=ctx.blocks.find(b=>b.id===ctx.block);
    const recent=eventsThrough(ctx).slice(-4).reverse(), focus=f.open[0]||f.next||b;
    const selectedEvidence=evidence(ctx);
    return `<div class="intel-page">
      <div class="intel-brief-grid">
        <section class="fx-card intel-lead" aria-labelledby="intel-lead-title"><div class="intel-lead-top"><span class="intel-eyebrow">ORCHARD INTELLIGENCE</span><span class="intel-timestamp">${e(d(ctx.day.date))}</span></div><div class="intel-lead-content"><div class="intel-orb-stage">${orb()}<span class="intel-orb-caption">SIGNAL → CONTEXT</span></div><div><h2 id="intel-lead-title">${e(summary(ctx))}</h2><p>${e(detail(ctx))}</p><div class="intel-lead-actions"><button class="fx-button" data-intel-question="What should I focus on today?">${icon('spark',17)} Explore the briefing</button><button class="intel-text-button" data-block="${e(focus.id)}">Focus ${e(focus.name)} ${icon('chev',15)}</button></div></div></div><div class="intel-lead-foot"><span>${icon('check',14)} Evidence through ${e(d(ctx.day.date))}</span><span>Codling moth decision model</span></div></section>
        <section class="fx-card intel-focus"><div class="intel-eyebrow">${f.next?'NEXT TO WATCH':'SEASON SNAPSHOT'}</div><h2>${e(f.next?f.next.name:f.open.length?'Window activity':'Orchard coverage')}</h2><div class="intel-focus-number">${f.next?n(stateOf(ctx,f.next.id).dd_since_biofix,1):n(f.open.length||f.confirmed.length)}<small>${f.next?'DD':f.open.length?'open blocks':'biofixes'}</small></div><p>${e(f.next?`${n(Math.max(0,f.thresholds.spray_open_dd-stateOf(ctx,f.next.id).dd_since_biofix),1)} DD to the opening threshold.`:`${n(f.closed.length)} of ${n(ctx.blocks.length)} modeled windows closed.`)}</p><div class="intel-meter"><i style="width:${f.next?Math.min(100,stateOf(ctx,f.next.id).dd_since_biofix/f.thresholds.spray_open_dd*100):f.confirmed.length/ctx.blocks.length*100}%"></i></div><div class="intel-meter-label"><span>${f.next?'Accumulated heat':'Confirmed biofix'}</span><span>${f.next?n(f.thresholds.spray_open_dd)+' DD':n(ctx.blocks.length)+' blocks'}</span></div><button class="intel-text-button" data-intel-nav="timing">View window planner ${icon('chev',15)}</button></section>
      </div>
      <section class="fx-card intel-evidence-card"><div class="fx-cardhead"><h2>Follow the evidence</h2><span class="intel-chip">${e(b.name)} · ${e(b.variety)}</span></div><div class="intel-evidence-chain">${selectedEvidence.map((item,i)=>`<div class="intel-evidence-step"><div class="intel-step-label"><span>${String(i+1).padStart(2,'0')}</span>${e(item.label)}</div><strong>${e(item.value)}</strong><small>${e(item.note)}</small></div>`).join('')}</div></section>
      <div class="fx-grid fx-equal intel-lower-grid"><section class="fx-card"><div class="fx-cardhead"><h2>Decision journal</h2><span class="fx-small">Recorded events</span></div><div class="intel-journal">${recent.length?recent.map(ev=>`<div class="intel-journal-row"><span class="intel-event-mark ${ev.type==='spray_window_open'?'intel-event-warm':''}">${icon(ev.type==='biofix'?'leaf':ev.type==='spray_window_open'?'bell':'check',16)}</span><div><strong>${e(ev.title)}</strong><p>${e(ev.message)}</p></div><time datetime="${e(ev.date)}">${e(d(ev.date))}</time></div>`).join(''):`<div class="intel-empty">${icon('leaf',28)}<strong>The season is just getting started.</strong><p>No biofix or spray-window events have been recorded by ${e(d(ctx.day.date))}.</p></div>`}</div></section>
        <section class="fx-card intel-questions"><div class="fx-cardhead"><h2>A clearer answer starts here.</h2>${icon('spark',19)}</div><p class="intel-questions-intro">Ask about this date, this block, or the orchard around it.</p>${[['Why is '+b.name+' in this status?','Understand the decision'],['Which block is next?','Compare the orchard'],['How did the weather affect timing?','Follow the thermal clock'],['What species are in the traps?','Explore pest activity']].map(([q,label])=>`<button class="intel-question" data-intel-question="${e(q)}"><span><small>${e(label)}</small>${e(q)}</span>${icon('chev',17)}</button>`).join('')}<div class="intel-facts-note">${icon('note',15)} Answers are assembled from the committed demo season. No language model is connected.</div></section></div>
    </div>`;
  }
  function answer(ctx, question) {
    const q=question.toLowerCase(), f=facts(ctx), n=ctx.num, d=ctx.dateLabel, model=modelSpecies(ctx);
    const mentioned=q.match(/block[\s-]+([a-z])\b/i), id=mentioned&&ctx.blocks.some(b=>b.id==='block-'+mentioned[1])?'block-'+mentioned[1]:ctx.block;
    const b=ctx.blocks.find(b=>b.id===id), s=stateOf(ctx,id), sp=(ctx.speciesData.species||[]).find(key=>q.includes(key.replaceAll('_',' '))||q.includes((ctx.speciesData.display?.[key]||key).toLowerCase()))||ctx.species;
    let title, paragraphs;
    if (/\b(send|notify|alert me|text me)\b/.test(q)) {
      title='No notification sent'; paragraphs=['This drawer reads the demo season and cannot send messages or operate the orchard. You can review the recorded decision here.',summary(ctx)];
    } else if (/\b(drones?|surveys?|aerial|captures?)\b/.test(q)) {
      let mission=null;
      try{mission=window.FieldOps?.getSurveyState?.()||null;}catch{}
      const captured=[...new Set((Array.isArray(mission?.captures)?mission.captures:[]).filter(blockId=>ctx.blocks.some(block=>block.id===blockId)))];
      const states={idle:'Ready to start',ready:'Ready to start',running:'In progress',flying:'In progress',surveying:'In progress',paused:'Paused',complete:'Complete',completed:'Complete',finished:'Complete'};
      title='Survey coverage, linked evidence';
      paragraphs=[
        'Drone survey is a simulated aerial tour of the orchard. Its virtual captures show spatial coverage. Insect counts come from the linked trap observations; the aerial previews do not count insects.',
        mission?`${states[mission.status]||'Survey snapshot'}: ${n(captured.length)} of ${n(ctx.blocks.length)} blocks captured${captured.length?' — '+captured.map(blockId=>blockName(ctx,blockId)).join(', '):''}.`:`The Drone survey tab has ${n(ctx.blocks.length)} virtual aerial previews, one per block. Select Start drone survey in the 3D farm to follow the simulated capture sequence.`,
        `${b.name}'s linked trap records show ${n(ctx.count(id,ctx.index,model))} ${pestName(ctx,model).toLowerCase()} on ${d(ctx.day.date)} across ${n(b.traps.length)} traps. Its recorded thermal clock is ${n(s.dd_since_biofix,1)} DD; the season model says ${labels[s.status].toLowerCase()}.`,
        `The ${n(f.thresholds.spray_open_dd)}–${n(f.thresholds.spray_close_dd)} DD spray window comes from the codling-moth timing model. A virtual capture does not change that decision or send an alert.`
      ];
    } else if (/\b(next|closest|following)\b/.test(q)) {
      title=f.next?`${f.next.name} is closest`:'No unopened window is accumulating';
      paragraphs=[f.next?`${f.next.name} has ${n(stateOf(ctx,f.next.id).dd_since_biofix,1)} DD since biofix. It needs ${n(Math.max(0,f.thresholds.spray_open_dd-stateOf(ctx,f.next.id).dd_since_biofix),1)} more DD to reach the ${n(f.thresholds.spray_open_dd)} DD opening threshold.`:'The selected snapshot has no block in the accumulating state. Blocks may still be waiting for biofix or have already entered or closed their window.',f.open.length?`${f.open.map(x=>x.name).join(', ')} ${f.open.length===1?'currently has':'currently have'} an open window.`:'No block has an open spray window on this date.',f.next?projectionExplanation(ctx,f.next.id):'This comparison uses accumulated heat through the selected date.'];
    } else if (/\b(weather|temperature|heat|warm|cold)\b/.test(q)) {
      title='Heat advances the clock'; paragraphs=[`${d(ctx.day.date)} recorded a low of ${n(ctx.day.tmin_f,1)}°F and a high of ${n(ctx.day.tmax_f,1)}°F. The timeline reports ${n(ctx.day.dd_today,1)} DD for the day.`,`${b.name} has accumulated ${n(s.dd_since_biofix,1)} DD${s.biofix_date?' since its '+d(s.biofix_date)+' biofix':'; its biofix has not been established'}. The configured lower and upper thresholds are ${n(f.thresholds.dd_base_f)}°F and ${n(f.thresholds.dd_upper_f)}°F.`, 'These are recorded demo-season temperatures, not a weather forecast.'];
    } else if (/\b(species|pests|insects|bugs)\b/.test(q)) {
      title='A species-level view'; paragraphs=[(ctx.speciesData.species||[model]).map(key=>`${pestName(ctx,key)}: ${n(ctx.total(ctx.index,key))} across the orchard`).join(' · ')+'.',`${b.name} has ${n(ctx.count(id,ctx.index,sp))} ${pestName(ctx,sp).toLowerCase()} in this snapshot. Counts are daily trap totals.`,`The timing model applies to ${pestName(ctx,model).toLowerCase()} only; selecting another species does not change the biofix or spray-window decision.`];
    } else if (/\b(how many|counts?|catch|catches|caught|traps?|moths?|flight|trend)\b/.test(q) && !/\b(why|biofix|status|window|spray)\b/.test(q)) {
      const week=ctx.weekly(id,sp), previous=ctx.weekly(id,sp,7), available=Math.min(7,ctx.index+1);
      title=`${pestName(ctx,sp)} in ${b.name}`;
      paragraphs=[`${n(ctx.count(id,ctx.index,sp))} recorded on ${d(ctx.day.date)} across ${n(b.traps.length)} traps. The orchard total is ${n(ctx.total(ctx.index,sp))}.`,`${n(week)} recorded over the latest ${available} available ${available===1?'day':'days'}${ctx.index>=13?`, compared with ${n(previous)} over the preceding seven days`:'. A complete preceding seven-day comparison is not yet available'}.`];
    } else if (/\b(biofix|why|status|window|spray|degree|dd|timing|thursday)\b/.test(q)) {
      title=`${b.name}: ${labels[s.status]||s.status}`;
      paragraphs=[s.biofix_date?`The authoritative timeline records biofix on ${d(s.biofix_date)}. ${b.name} has ${n(s.dd_since_biofix,1)} degree-days since that recorded start.`:`${b.name} has no recorded biofix by ${d(ctx.day.date)}. Sustained catch must meet the configured ${n(f.thresholds.biofix_min_count)}-moth threshold for ${n(f.thresholds.biofix_consecutive_checks)} consecutive checks.`,`The ${pestName(ctx,model).toLowerCase()} window is ${n(f.thresholds.spray_open_dd)}–${n(f.thresholds.spray_close_dd)} DD. ${s.status==='spray_window'?'The recorded state is inside that window.':s.status==='window_closed'?'The recorded state has passed the window.':s.status==='accumulating'?`${n(Math.max(0,f.thresholds.spray_open_dd-s.dd_since_biofix),1)} DD remain to its opening threshold.`:'The thermal clock is waiting for a confirmed biofix.'}`,`Today's recorded ${pestName(ctx,model).toLowerCase()} count is ${n(ctx.count(id,ctx.index,model))}. The state comes from the deterministic season model; this assistant does not recompute it.`];
      if(s.status==='accumulating')paragraphs.splice(2,0,projectionExplanation(ctx,id));
    } else if (/\b(today|focus|brief|summary|happening|attention|priorit)\b/.test(q)) {
      title='The orchard, at a glance'; paragraphs=[summary(ctx),detail(ctx),`${n(ctx.total(ctx.index,ctx.species))} ${pestName(ctx).toLowerCase()} recorded across ${n(ctx.blocks.length)} blocks on ${d(ctx.day.date)}.`];
    } else {
      title='I can explain the season facts'; paragraphs=[`I can read trap counts, species totals, recorded biofix, degree-days, temperatures, and block status through ${d(ctx.day.date)}. I cannot answer general questions or make a forecast.`,`Try “Why is ${b.name} in this status?”, “Which block is next?”, or “What species are in the traps?”`];
    }
    return {question,title,paragraphs,date:ctx.day.date,block:b.name,species:pestName(ctx),evidence:evidence(ctx,id),context:`${d(ctx.day.date)} · ${b.name} · Demo season`};
  }
  function renderMessage(message,ctx) {
    const e=ctx.esc;
    if(message.kind==='assistant')return `${message.question?`<div class="intel-user-message">${e(message.question)}</div>`:''}<article class="intel-answer"><div class="intel-answer-label">${ctx.icon('spark',14)} FIELDOPS · ASSISTANT REPLY</div>${message.paragraphs.map(p=>`<p>${e(p)}</p>`).join('')}<footer>${e(message.context)}</footer></article>`;
    return `<div class="intel-user-message">${e(message.question)}</div><article class="intel-answer"><div class="intel-answer-label">${ctx.icon('spark',14)} FIELDOPS · SEASON FACTS</div><h3>${e(message.title)}</h3>${message.paragraphs.map(p=>`<p>${e(p)}</p>`).join('')}<details class="intel-answer-evidence"><summary>View supporting facts</summary><dl>${message.evidence.map(x=>`<div><dt>${e(x.label)}</dt><dd>${e(x.value)}</dd></div>`).join('')}</dl><span>Source: committed timeline and species series</span></details><footer>${e(message.context)}</footer></article>`;
  }
  let voiceAdapter=null, voiceState='idle', voiceMessage='', voiceSession=false, chatVisible=false, turn=0, outputClient=null, outputListener=null;
  const activeStates=new Set(['preparing','listening','thinking','speaking']);
  const voiceLabels={idle:'Ready when you are',preparing:'Getting ready',listening:'Listening',thinking:'Thinking',speaking:'Speaking',error:'Voice paused'};
  function updateContext() {
    if(!host || !getContext?.())return;
    const ctx=getContext();
    host.querySelector('[data-intel-context]').textContent=`${ctx.dateLabel(ctx.day.date)} · ${blockName(ctx,ctx.block)}`;
  }
  function localVoice(){return window.speechSynthesis?.getVoices().find(v=>v.localService&&/^en/i.test(v.lang))||window.speechSynthesis?.getVoices().find(v=>v.localService);}
  function canListen(){return !!voiceAdapter?.start || !!recognition;}
  function renderVoiceState(){
    if(!host)return;
    const active=activeStates.has(voiceState);
    dialog.dataset.voiceState=voiceState;
    host.querySelector('[data-intel-voice-title]').textContent=voiceLabels[voiceState];
    const defaults={preparing:'Opening the microphone.',listening:'Ask about your orchard.',thinking:'Reading your orchard snapshot.',speaking:'Your orchard, explained.',error:'You can continue using the keyboard.'};
    host.querySelector('[data-intel-status]').textContent=voiceMessage||defaults[voiceState]||(canListen()?'Tap the mic to talk about your orchard.':'Type a question, then hear the answer. Microphone input is unavailable in this browser.');
    const mic=host.querySelector('[data-intel-voice]');
    mic.setAttribute('aria-label',active?'Stop voice session':canListen()?'Start voice session':'Voice input unavailable; use Type instead');
    mic.setAttribute('aria-pressed',String(active));
    mic.setAttribute('aria-disabled',String(!canListen()&&!active));
    host.querySelector('[data-intel-stop]').disabled=!active;
    host.querySelector('[data-intel-hear]').disabled=active;
    host.querySelector('[data-intel-connection]').textContent=voiceAdapter?'Voice available':recognition?'On-device voice':window.fieldopsVoice?'Voice replies · keyboard input':'Keyboard available';
  }
  function setVoiceState(state,details={}){
    const normalized={ready:'idle',starting:'preparing',processing:'thinking'}[state]||state;
    if(!Object.hasOwn(voiceLabels,normalized))return;
    voiceState=normalized;voiceMessage=typeof details==='string'?details:details.message||'';
    listening=voiceState==='listening';renderVoiceState();
  }
  function emitVoice(action){
    document.dispatchEvent(new CustomEvent('fieldops:voice-request',{bubbles:true,detail:{action,context:getContext?.()||null}}));
  }
  function connectOutput(){
    const client=window.fieldopsVoice;
    if(client===outputClient)return client;
    if(outputClient?.removeEventListener&&outputListener)outputClient.removeEventListener('state',outputListener);
    outputClient=client||null;
    outputListener=event=>{
      if(!voiceSession||!dialog?.open)return;
      const detail=event.detail||{};
      setVoiceState(detail.state==='preparing'?'thinking':detail.state,detail);
    };
    outputClient?.addEventListener?.('state',outputListener);
    return outputClient;
  }
  function stopVoice({announce=true,emit=true}={}){
    turn++;voiceSession=false;listening=false;
    try{recognition?.abort();}catch{}
    try{voiceAdapter?.stop?.();}catch{}
    try{window.fieldopsVoice?.stop?.();}catch{}
    window.speechSynthesis?.cancel();
    if(emit)emitVoice('stop');
    setVoiceState('idle',announce?'Stopped. Tap the mic whenever you’re ready.':'');
  }
  async function speakText(text){
    const currentTurn=turn,client=connectOutput();
    if(client?.speak){
      setVoiceState('thinking','Preparing your reply.');
      // The promise covers receiving/scheduling audio; playback ends on the client's idle event.
      try{await client.speak(text);}
      catch(error){if(currentTurn===turn&&voiceSession)setVoiceState('error','Audio is unavailable. Your answer is shown below.');}
      return;
    }
    const voice=localVoice();
    if(!voice||!window.SpeechSynthesisUtterance){setVoiceState('idle','Your answer is ready. Audio is unavailable in this browser.');return;}
    window.speechSynthesis.cancel();
    const utterance=new SpeechSynthesisUtterance(text);utterance.voice=voice;utterance.rate=1;
    utterance.onstart=()=>{if(currentTurn===turn)setVoiceState('speaking','');};
    utterance.onend=()=>{if(currentTurn===turn)setVoiceState('idle','Tap the mic for another question.');};
    utterance.onerror=event=>{if(currentTurn===turn&&event.error!=='canceled'&&event.error!=='interrupted')setVoiceState('error','Audio is unavailable. Your answer is shown below.');};
    setVoiceState('speaking','');window.speechSynthesis.speak(utterance);
  }
  function submit(question,{voice=false}={}){
    const text=String(question||'').trim().slice(0,1000),ctx=getContext?.();
    if(!text||!ctx)return;
    const message=answer(ctx,text);messages.push(message);if(messages.length>16)messages.shift();
    log.innerHTML=messages.map(m=>renderMessage(m,ctx)).join('');log.scrollTop=log.scrollHeight;
    host.querySelector('[data-intel-utterance]').textContent=text;
    host.querySelector('[data-intel-utterance]').hidden=false;
    host.querySelector('[data-intel-reply-title]').textContent=message.title;
    host.querySelector('[data-intel-reply]').textContent=message.paragraphs[0];
    host.querySelector('[data-intel-latest]').hidden=false;
    host.querySelector('[data-intel-hear]').hidden=false;
    host.querySelector('[data-intel-show-evidence]').innerHTML='See supporting facts '+ctx.icon('chev',14);
    if(voice){voiceSession=true;speakText([message.title,message.paragraphs[0]].join('. '));}
    else setVoiceState('idle','Answer ready. Open the chat for supporting facts.');
    return message;
  }
  function presentReply(text,{question='',speak=false}={}){
    const reply=String(text||'').trim().slice(0,12000),ctx=getContext?.();
    if(!reply||!ctx||!dialog?.open)return;
    const asked=String(question||'').trim().slice(0,1000);
    const message={kind:'assistant',question:asked,paragraphs:reply.split(/\n\s*\n/),context:`${ctx.dateLabel(ctx.day.date)} · ${blockName(ctx,ctx.block)} · Assistant reply`};
    messages.push(message);if(messages.length>16)messages.shift();
    log.innerHTML=messages.map(m=>renderMessage(m,ctx)).join('');log.scrollTop=log.scrollHeight;
    const utterance=host.querySelector('[data-intel-utterance]');utterance.textContent=asked;utterance.hidden=!asked;
    host.querySelector('[data-intel-reply-title]').textContent='FieldOps';
    host.querySelector('[data-intel-reply]').textContent=message.paragraphs[0];
    host.querySelector('[data-intel-latest]').hidden=false;
    host.querySelector('[data-intel-hear]').hidden=false;
    host.querySelector('[data-intel-show-evidence]').innerHTML='Open chat '+ctx.icon('chev',14);
    if(speak){voiceSession=true;speakText(reply);}
    else setVoiceState('idle','Reply ready.');
    return message;
  }
  function submitVoice(text){
    if(!host||!String(text||'').trim())return;
    if(!dialog.open)open();
    try{recognition?.stop();}catch{}
    listening=false;voiceSession=true;setVoiceState('thinking','Reading your orchard snapshot.');
    return submit(text,{voice:true});
  }
  function setVoiceAdapter(adapter){
    if(activeStates.has(voiceState))stopVoice({announce:false});
    voiceAdapter=adapter&&typeof adapter.start==='function'?adapter:null;
    setVoiceState('idle','');
  }
  async function startVoice(){
    if(activeStates.has(voiceState)){stopVoice();return;}
    if(!canListen()){setVoiceState('error','Voice input is unavailable here. Choose Type instead to ask a question.');return;}
    turn++;const currentTurn=turn;voiceSession=true;setVoiceState('preparing','Opening the microphone.');
    emitVoice('start');
    try{
      if(voiceAdapter?.start){
        await voiceAdapter.start({context:getContext(),onTranscript:text=>{if(currentTurn===turn&&voiceSession)submitVoice(text);},onReply:(text,options)=>{if(currentTurn===turn&&voiceSession)presentReply(text,options);},onState:(state,details)=>{if(currentTurn===turn&&voiceSession)setVoiceState(state,details);}});
      }else recognition.start();
    }catch(error){
      if(currentTurn===turn){voiceSession=false;setVoiceState('error','Could not start voice. Check microphone access, or type your question.');}
    }
  }
  function setChat(visible){
    chatVisible=visible;dialog.classList.toggle('intel-chat-open',visible);
    host.querySelector('[data-intel-chat]').hidden=!visible;
    const toggle=host.querySelector('[data-intel-chat-toggle]');toggle.setAttribute('aria-expanded',String(visible));
    toggle.innerHTML=getContext().icon(visible?'mic':'note',15)+(visible?'Back to voice':'Type instead');
    if(visible){input.focus();log.scrollTop=log.scrollHeight;}else host.querySelector('[data-intel-voice]').focus();
  }
  function close(){
    if(!dialog?.open)return;
    stopVoice({announce:false});dialog.close();launcher.setAttribute('aria-expanded','false');
    if(returnFocus?.isConnected)returnFocus.focus();else launcher.focus();
  }
  function open(question){
    if(!dialog)return;
    if(!dialog.open){returnFocus=document.activeElement;dialog.show();launcher.setAttribute('aria-expanded','true');setChat(false);}
    updateContext();connectOutput();renderVoiceState();
    if(question)submit(question);
    if(chatVisible)input.focus();else host.querySelector('[data-intel-voice]').focus();
  }
  function mount(contextGetter){
    getContext=contextGetter;if(host){updateContext();return;}const ctx=getContext();if(!ctx)return;
    host=document.createElement('div');host.className='intel-assistant-root';
    host.innerHTML=`<button class="intel-launcher intel-launcher-voice" type="button" aria-label="Talk to FieldOps" aria-haspopup="dialog" aria-expanded="false" aria-controls="intel-dialog">${orb('small')}<span>Talk to FieldOps</span>${ctx.icon('mic',18)}</button>
      <dialog class="intel-dialog intel-voice-dialog" id="intel-dialog" aria-modal="false" aria-labelledby="intel-dialog-title"><header class="intel-dialog-head"><div><h2 id="intel-dialog-title">FieldOps</h2><span data-intel-connection>Keyboard available</span></div><button class="intel-icon-button" data-intel-close aria-label="Close assistant">${ctx.icon('close',20)}</button></header>
      <div class="intel-context-line"><span class="intel-context-dot"></span><span data-intel-context></span></div>
      <section class="intel-voice-main" aria-label="Voice assistant"><button type="button" class="intel-voice-primary" data-intel-voice aria-label="Start voice session" aria-pressed="false">${orb()}<span class="intel-mic-symbol">${ctx.icon('mic',23)}</span></button><h3 data-intel-voice-title>Ready when you are</h3><p class="intel-status" data-intel-status role="status" aria-live="polite"></p><div class="intel-voice-actions"><button type="button" class="intel-chat-toggle" data-intel-hear hidden>Hear answer</button><button type="button" class="intel-stop" data-intel-stop disabled><span></span>Stop</button><button type="button" class="intel-chat-toggle" data-intel-chat-toggle aria-expanded="false" aria-controls="intel-chat">${ctx.icon('note',15)}Type instead</button></div>
      <div class="intel-latest" data-intel-latest hidden><p class="intel-latest-question" data-intel-utterance></p><h4 data-intel-reply-title></h4><p data-intel-reply></p><button type="button" class="intel-text-button" data-intel-show-evidence>See supporting facts ${ctx.icon('chev',14)}</button></div></section>
      <section id="intel-chat" class="intel-chat-secondary" data-intel-chat hidden aria-label="Optional chat"><div class="intel-conversation" tabindex="0" aria-label="Conversation"><div class="intel-welcome"><h3>What would you like to know?</h3><p>Answers use the selected date and block from the demo season.</p><div class="intel-quick-list"><button data-intel-question="What should I focus on today?">Give me the briefing ${ctx.icon('chev',15)}</button><button data-intel-question="Which block is next?">Which block is next? ${ctx.icon('chev',15)}</button></div></div></div><form class="intel-composer"><label class="intel-sr-only" for="intel-question">Ask about the selected season snapshot</label><div class="intel-input-row"><textarea id="intel-question" rows="2" maxlength="1000" placeholder="Ask about your orchard…"></textarea><button type="submit" class="intel-submit" aria-label="Send question">${ctx.icon('send',19)}</button></div><p class="intel-privacy-note">Season facts · No messages or alerts are sent.</p></form></section></dialog>`;
    document.body.appendChild(host);dialog=host.querySelector('dialog');launcher=host.querySelector('.intel-launcher');input=host.querySelector('textarea');log=host.querySelector('.intel-conversation');
    launcher.addEventListener('click',()=>open());host.querySelector('[data-intel-close]').addEventListener('click',close);
    host.querySelector('[data-intel-voice]').addEventListener('click',startVoice);host.querySelector('[data-intel-stop]').addEventListener('click',()=>stopVoice());
    host.querySelector('[data-intel-hear]').addEventListener('click',()=>{stopVoice({announce:false});voiceSession=true;speakText([host.querySelector('[data-intel-reply-title]').textContent,host.querySelector('[data-intel-reply]').textContent].join('. '));});
    host.querySelector('[data-intel-chat-toggle]').addEventListener('click',()=>setChat(!chatVisible));host.querySelector('[data-intel-show-evidence]').addEventListener('click',()=>setChat(true));
    dialog.addEventListener('cancel',event=>{event.preventDefault();close();});
    document.addEventListener('keydown',event=>{if(event.key==='Escape'&&dialog.open){event.preventDefault();event.stopPropagation();close();}},true);
    host.querySelector('form').addEventListener('submit',event=>{event.preventDefault();if(input.value.trim()){submit(input.value);input.value='';input.focus();}});
    input.addEventListener('keydown',event=>{if(event.key==='Enter'&&!event.shiftKey&&!event.isComposing){event.preventDefault();host.querySelector('form').requestSubmit();}});
    document.addEventListener('click',event=>{const question=event.target.closest('[data-intel-question]');if(question){open(question.dataset.intelQuestion);return;}const nav=event.target.closest('[data-intel-nav]');if(nav)getContext().actions.navigate(nav.dataset.intelNav);});
    window.addEventListener('fieldops:change',updateContext);
    document.addEventListener('fieldops:voice-transcript',event=>{if(!voiceSession)return;const detail=event.detail||{};if(detail.final===false){host.querySelector('[data-intel-utterance]').textContent=detail.text||'';return;}submitVoice(detail.text||'');});
    document.addEventListener('fieldops:voice-state',event=>{const detail=event.detail||{};if(voiceSession||detail.state==='idle')setVoiceState(detail.state,detail);});
    document.addEventListener('fieldops:voice-reply',event=>{if(!voiceSession||!dialog?.open)return;const detail=event.detail||{};presentReply(detail.text||'',{question:detail.question,speak:detail.speak===true});});
    document.addEventListener('fieldops:voice-adapter',event=>setVoiceAdapter(event.detail?.adapter||event.detail));
    const Recognition=window.SpeechRecognition||window.webkitSpeechRecognition;
    if(Recognition){try{const candidate=new Recognition();if('processLocally' in candidate){recognition=candidate;recognition.processLocally=true;recognition.lang='en-US';recognition.interimResults=false;
      recognition.onstart=()=>{if(voiceSession)setVoiceState('listening','Ask about your orchard.');};
      recognition.onresult=event=>{if(voiceSession)submitVoice(event.results[0][0].transcript);};
      recognition.onerror=event=>{if(voiceSession&&event.error!=='aborted'){voiceSession=false;setVoiceState('error','On-device voice is unavailable. You can type your question.');}};
      recognition.onend=()=>{if(voiceState==='listening'||voiceState==='preparing')setVoiceState('idle','Tap the mic to try again.');};
    }}catch{recognition=null;}}
    updateContext();connectOutput();renderVoiceState();
  }
  window.FOIntelligence={render,mount,open,submitVoice,presentReply,setVoiceState,setVoiceAdapter};
})();
