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
    return `<div class="intel-user-message">${e(message.question)}</div><article class="intel-answer"><div class="intel-answer-label">${ctx.icon('spark',14)} FIELDOPS · SEASON FACTS</div><h3>${e(message.title)}</h3>${message.paragraphs.map(p=>`<p>${e(p)}</p>`).join('')}<details class="intel-answer-evidence"><summary>View supporting facts</summary><dl>${message.evidence.map(x=>`<div><dt>${e(x.label)}</dt><dd>${e(x.value)}</dd></div>`).join('')}</dl><span>Source: committed timeline and species series</span></details><footer>${e(message.context)}</footer></article>`;
  }
  function updateContext() {
    if (!host || !getContext()) return;
    const ctx=getContext();
    host.querySelector('[data-intel-context]').textContent=`${ctx.dateLabel(ctx.day.date)} · ${blockName(ctx,ctx.block)} · ${pestName(ctx)}`;
  }
  function localVoice() { return window.speechSynthesis?.getVoices().find(v=>v.localService&&/^en/i.test(v.lang)) || window.speechSynthesis?.getVoices().find(v=>v.localService); }
  function status(text) { host.querySelector('[data-intel-status]').textContent=text; }
  function readAloud(message) {
    const voice=localVoice();
    if (!voice || !window.SpeechSynthesisUtterance) { status('An on-device reading voice is not available in this browser.'); return; }
    window.speechSynthesis.cancel();
    const utterance=new SpeechSynthesisUtterance([message.title,...message.paragraphs].join('. '));
    utterance.voice=voice;utterance.rate=1;window.speechSynthesis.speak(utterance);
  }
  function submit(question) {
    const text=String(question||'').trim().slice(0,1000), ctx=getContext?.();
    if (!text || !ctx) return;
    const message=answer(ctx,text);messages.push(message);
    if(messages.length>16)messages.shift();
    log.innerHTML=messages.map(m=>renderMessage(m,ctx)).join('');
    log.scrollTop=log.scrollHeight;
    status(`Answer ready. ${message.title}.`);
    if(host.querySelector('[data-intel-read]').checked)readAloud(message);
  }
  function close() {
    if(!dialog?.open)return;
    if(recognition&&listening)recognition.stop();
    window.speechSynthesis?.cancel();dialog.close();launcher.setAttribute('aria-expanded','false');
    if(returnFocus?.isConnected)returnFocus.focus();else launcher.focus();
  }
  function open(question) {
    if(!dialog)return;
    if(!dialog.open){returnFocus=document.activeElement;dialog.showModal();launcher.setAttribute('aria-expanded','true');}
    updateContext();if(question)submit(question);input.focus();
  }
  function mount(contextGetter) {
    getContext=contextGetter;
    if(host){updateContext();return;}
    const ctx=getContext();if(!ctx)return;
    host=document.createElement('div');host.className='intel-assistant-root';
    host.innerHTML=`<button class="intel-launcher" type="button" aria-haspopup="dialog" aria-expanded="false" aria-controls="intel-dialog">${orb('small')}<span><strong>Ask FieldOps</strong><small>Make sense of your orchard</small></span>${ctx.icon('spark',18)}</button>
      <dialog class="intel-dialog" id="intel-dialog" aria-labelledby="intel-dialog-title"><header class="intel-dialog-head">${orb('tiny')}<div><h2 id="intel-dialog-title">Ask FieldOps</h2><span>Offline season facts</span></div><button class="intel-icon-button" data-intel-close aria-label="Close assistant">${ctx.icon('close',22)}</button></header>
      <div class="intel-context-line"><span class="intel-context-dot"></span><span data-intel-context></span></div><div class="intel-conversation" tabindex="0" aria-label="Conversation"><div class="intel-welcome"><span class="intel-eyebrow">YOUR ORCHARD, EXPLAINED</span><h3>From a number<br>to a next step.</h3><p>Explore the committed demo season. Answers use the selected date and block; no language model is connected.</p><div class="intel-quick-list"><button data-intel-question="What should I focus on today?">Give me the briefing ${ctx.icon('chev',15)}</button><button data-intel-question="Why is this block in this status?">Explain this block ${ctx.icon('chev',15)}</button><button data-intel-question="Which block is next?">Which block is next? ${ctx.icon('chev',15)}</button></div></div></div>
      <form class="intel-composer"><label class="intel-sr-only" for="intel-question">Ask about the selected season snapshot</label><div class="intel-input-row"><textarea id="intel-question" rows="2" maxlength="1000" placeholder="Ask about your orchard…"></textarea><button type="submit" class="intel-submit" aria-label="Send question">${ctx.icon('send',19)}</button></div><div class="intel-composer-tools"><button type="button" class="intel-voice" data-intel-voice hidden>${ctx.icon('mic',15)} On-device voice</button><label class="intel-read-toggle"><input type="checkbox" data-intel-read> Read answers aloud</label></div><p class="intel-privacy-note">Local data. No messages or alerts are sent.</p><p class="intel-status" data-intel-status role="status" aria-live="polite"></p></form></dialog>`;
    document.body.appendChild(host);dialog=host.querySelector('dialog');launcher=host.querySelector('.intel-launcher');input=host.querySelector('textarea');log=host.querySelector('.intel-conversation');
    launcher.addEventListener('click',()=>open());host.querySelector('[data-intel-close]').addEventListener('click',close);
    dialog.addEventListener('cancel',event=>{event.preventDefault();close();});
    dialog.addEventListener('click',event=>{if(event.target===dialog){const r=dialog.getBoundingClientRect();if(event.clientX<r.left||event.clientX>r.right||event.clientY<r.top||event.clientY>r.bottom)close();}});
    dialog.addEventListener('keydown',event=>{
      if(event.key!=='Tab')return;
      const focusable=[...dialog.querySelectorAll('button:not([disabled]):not([hidden]),textarea,input,summary,[tabindex="0"]')].filter(el=>el.getClientRects().length);
      const first=focusable[0],last=focusable.at(-1);
      if(event.shiftKey&&document.activeElement===first){event.preventDefault();last.focus();}
      else if(!event.shiftKey&&document.activeElement===last){event.preventDefault();first.focus();}
    });
    host.querySelector('form').addEventListener('submit',event=>{event.preventDefault();if(input.value.trim()){submit(input.value);input.value='';input.focus();}});
    input.addEventListener('keydown',event=>{if(event.key==='Enter'&&!event.shiftKey&&!event.isComposing){event.preventDefault();host.querySelector('form').requestSubmit();}});
    host.querySelector('[data-intel-read]').addEventListener('change',event=>{if(!event.target.checked)window.speechSynthesis?.cancel();else if(!localVoice()){event.target.checked=false;status('No on-device reading voice is available. Text answers still work.');}});
    document.addEventListener('click',event=>{
      const question=event.target.closest('[data-intel-question]');if(question){open(question.dataset.intelQuestion);return;}
      const nav=event.target.closest('[data-intel-nav]');if(nav)getContext().actions.navigate(nav.dataset.intelNav);
    });
    window.addEventListener('fieldops:change',updateContext);
    const Recognition=window.SpeechRecognition||window.webkitSpeechRecognition;
    if(Recognition){
      const candidate=new Recognition();
      if('processLocally' in candidate){
        recognition=candidate;recognition.processLocally=true;recognition.lang='en-US';recognition.interimResults=false;
        const voiceButton=host.querySelector('[data-intel-voice]');voiceButton.hidden=false;
        voiceButton.addEventListener('click',()=>{if(listening){recognition.stop();return;}try{recognition.start();}catch(error){status('On-device voice could not start. You can type your question.');}});
        recognition.onstart=()=>{listening=true;voiceButton.classList.add('intel-listening');voiceButton.setAttribute('aria-pressed','true');status('Listening on this device. Your words will appear in the question box.');};
        recognition.onresult=event=>{input.value=event.results[0][0].transcript;input.focus();status('Voice input ready. Review it, then send your question.');};
        recognition.onerror=()=>status('On-device voice is unavailable. Type your question instead.');
        recognition.onend=()=>{listening=false;voiceButton.classList.remove('intel-listening');voiceButton.setAttribute('aria-pressed','false');};
      }
    }
    updateContext();
  }
  window.FOIntelligence={render,mount,open};
})();
