/* FieldOps analytics module. window.FOA = { render(dayIndex, selectedBlock) }.
   Fills #foa-kpi, #foa-species, #foa-heat, #foa-traps, #foa-ddrace, #foa-weather from
   window.FIELDOPS_TIMELINE and window.FIELDOPS_SPECIES. Reads nothing else from the page. */
(function () {
  "use strict";

  var IDS = { kpi: "foa-kpi", species: "foa-species", heat: "foa-heat", traps: "foa-traps", ddrace: "foa-ddrace", weather: "foa-weather" };
  // Six categorical hues for blocks A..F, validated with dataviz/scripts/validate_palette.js on #FFFFFF (light): all checks pass.
  var PAL = ["#2F62D6", "#D97A0F", "#199E70", "#C0392B", "#7B4FB0", "#5A7D0E"];
  var STATUS_WORD = { watching: "Healthy", accumulating: "At risk", spray_window: "Needs spray", window_closed: "Window closed" };
  var STATUS_VAR = { watching: "--healthy", accumulating: "--risk", spray_window: "--spray", window_closed: "--closed" };
  var MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  var HEAT_STEPS = [12, 30, 50, 72, 95];

  var CSS = [
    ".foa-root{font-family:var(--fb,system-ui,sans-serif);color:var(--ink,#1F3229);font-size:14px;line-height:1.35;box-sizing:border-box}",
    ".foa-root *{box-sizing:border-box}",
    ".foa-root .foa-head{display:flex;align-items:baseline;gap:12px;flex-wrap:wrap;margin:0 0 10px}",
    ".foa-root .foa-title{font-family:var(--fd,var(--fb,system-ui));font-size:15px;font-weight:600;margin:0;color:var(--ink)}",
    ".foa-root .foa-sub{font-size:13px;color:var(--muted,#5A6B61)}",
    ".foa-root .foa-num{font-family:var(--fm,ui-monospace,monospace);font-variant-numeric:tabular-nums}",
    ".foa-root .foa-legend{display:flex;gap:16px;flex-wrap:wrap;font-size:13px;color:var(--muted);margin:0 0 8px}",
    ".foa-root .foa-legend span{display:inline-flex;align-items:center;gap:6px}",
    ".foa-root .foa-legend i{display:inline-block;width:14px;height:10px;border-radius:2px}",
    ".foa-root .foa-legend i.foa-key{height:0;border-top:2px solid;border-radius:0;width:16px}",
    ".foa-root .foa-legend .foa-on{color:var(--ink);font-weight:600}",
    ".foa-root .foa-cm{background:var(--accent,#126D58)}",
    ".foa-root .foa-ofm{background:repeating-linear-gradient(135deg,var(--muted,#5A6B61) 0 3px,color-mix(in srgb,var(--muted,#5A6B61) 45%,var(--surface,#fff)) 3px 5px)}",
    /* KPI */
    ".foa-root .foa-tiles{display:grid;grid-template-columns:repeat(6,minmax(0,1fr));gap:10px}",
    "@media (max-width:1100px){.foa-root .foa-tiles{grid-template-columns:repeat(3,minmax(0,1fr))}}",
    "@media (max-width:600px){.foa-root .foa-tiles{grid-template-columns:repeat(2,minmax(0,1fr))}}",
    ".foa-root .foa-tile{background:var(--surface,#fff);border:1px solid var(--line,#D9DFD5);border-radius:12px;padding:12px 14px 10px;min-width:0}",
    ".foa-root .foa-tile .foa-lab{font-size:14px;color:var(--muted);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}",
    ".foa-root .foa-tile .foa-val{font-size:32px;line-height:1.1;margin:6px 0 2px;color:var(--ink);white-space:nowrap}",
    ".foa-root .foa-tile .foa-val small{font-size:15px;color:var(--muted);margin-left:4px;font-family:var(--fb,system-ui)}",
    ".foa-root .foa-tile .foa-note{font-size:12px;color:var(--muted);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}",
    /* species rows */
    ".foa-root .foa-rows{display:flex;flex-direction:column;gap:4px}",
    ".foa-root .foa-row{display:grid;grid-template-columns:170px minmax(0,1fr) 96px;align-items:center;gap:12px;padding:3px 0 3px 10px;border-left:2px solid transparent;min-height:28px}",
    ".foa-root .foa-row.foa-sel{border-left-color:var(--accent);background:color-mix(in srgb,var(--accent) 6%,transparent)}",
    ".foa-root .foa-row .foa-bn{font-weight:600;white-space:nowrap}",
    ".foa-root .foa-row .foa-st{font-size:12px;color:var(--muted);white-space:nowrap;display:inline-flex;align-items:center;gap:5px;margin-left:6px}",
    ".foa-root .foa-dot{display:inline-block;width:8px;height:8px;border-radius:50%}",
    ".foa-root .foa-bar{display:flex;height:18px;width:100%}",
    ".foa-root .foa-seg{height:100%;border-radius:0 3px 3px 0;cursor:default}",
    ".foa-root .foa-seg:first-child{border-radius:3px 0 0 3px;margin-right:2px}",
    ".foa-root .foa-seg:hover{outline:1px solid var(--ink)}",
    ".foa-root .foa-row .foa-nums{text-align:right;white-space:nowrap;font-size:14px}",
    ".foa-root .foa-row .foa-nums span{color:var(--muted)}",
    ".foa-root .foa-foot{font-size:13px;color:var(--muted);margin-top:10px;display:flex;align-items:center;gap:6px}",
    /* heat */
    ".foa-root svg{display:block;overflow:visible;font-family:var(--fb,system-ui)}",
    ".foa-root .foa-cell:hover{stroke:var(--ink);stroke-width:1.5}",
    ".foa-root .foa-ax{font-size:11px;fill:var(--muted)}",
    ".foa-root .foa-ax.foa-row-l{font-size:12px;fill:var(--ink);font-weight:600}",
    ".foa-root .foa-grid{stroke:var(--line,#D9DFD5);stroke-width:1}",
    ".foa-root .foa-hit{fill:transparent;pointer-events:all}",
    ".foa-root .foa-hair{stroke:var(--ink);stroke-width:1;stroke-dasharray:2 3;visibility:hidden;pointer-events:none}",
    ".foa-root .foa-lbl{font-size:12px;fill:var(--ink);font-weight:600}",
    ".foa-root .foa-th{font-size:11px;fill:var(--muted)}",
    /* table */
    ".foa-root table{border-collapse:collapse;width:100%;font-size:13px}",
    ".foa-root th{font-weight:600;color:var(--muted);text-align:left;padding:6px 10px;border-bottom:1px solid var(--line);font-size:12px;white-space:nowrap}",
    ".foa-root td{padding:5px 10px;white-space:nowrap;border-left:2px solid transparent}",
    ".foa-root td:not(:first-child){border-left:0}",
    ".foa-root tr.foa-sel td:first-child{border-left-color:var(--accent)}",
    ".foa-root tbody tr:nth-child(even) td{background:var(--surface2,#E8ECE3)}",
    ".foa-root tbody tr:hover td{background:color-mix(in srgb,var(--accent) 8%,var(--surface,#fff))}",
    ".foa-root th.foa-r,.foa-root td.foa-r{text-align:right}",
    ".foa-root td.foa-r{font-family:var(--fm,ui-monospace,monospace);font-variant-numeric:tabular-nums}",
    ".foa-root td.foa-m{color:var(--muted)}",
    ".foa-root .foa-trend{display:inline-flex;align-items:center;gap:5px}",
    ".foa-root .foa-trend svg{width:12px;height:12px;overflow:visible}",
    /* tooltip */
    "#foa-tip{position:fixed;z-index:9999;pointer-events:none;background:var(--ink,#1F3229);color:var(--bg,#F4F6F1);border-radius:8px;padding:7px 10px;font:12px/1.4 var(--fb,system-ui);box-shadow:0 4px 14px rgba(0,0,0,.18);max-width:260px;visibility:hidden}",
    "#foa-tip .foa-tv{font-family:var(--fm,ui-monospace,monospace);font-size:14px;font-weight:600;margin-bottom:2px}",
    "#foa-tip .foa-tl{display:flex;align-items:center;gap:6px;opacity:.9}",
    "#foa-tip .foa-tl i{display:inline-block;width:12px;border-top:2px solid;flex:none}",
    "#foa-tip .foa-tl b{font-family:var(--fm,ui-monospace,monospace);font-weight:600;margin-left:auto;padding-left:10px}"
  ].join("\n");

  var P = null; // precomputed state
  var tip = null;

  function esc(s) { return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/"/g, "&quot;"); }
  function fmt1(x) { return (Math.round(x * 10) / 10).toFixed(1); }
  function dateParts(iso) { var m = +iso.slice(5, 7), d = +iso.slice(8, 10); return { m: m, d: d, md: m + "/" + d, lab: MONTHS[m - 1] + " " + d }; }
  function heatColor(step) { return "color-mix(in srgb, var(--accent) " + HEAT_STEPS[step] + "%, transparent)"; }

  function precompute() {
    var T = window.FIELDOPS_TIMELINE, S = window.FIELDOPS_SPECIES;
    if (!T || !T.days || !T.days.length) return null;
    var days = T.days, n = days.length;
    var blocks = T.blocks.slice().sort(function (a, b) { return (a.row - b.row) || (a.col - b.col); });
    var sIdx = {};
    if (S && S.dates) S.dates.forEach(function (d, i) { sIdx[d] = i; });
    var sOf = days.map(function (d) { return sIdx[d.date] != null ? sIdx[d.date] : -1; });
    function series(src) { // daily series aligned to timeline days; src is an array indexed by species date
      var out = new Array(n);
      for (var i = 0; i < n; i++) out[i] = src && sOf[i] >= 0 ? (src[sOf[i]] || 0) : 0;
      return out;
    }
    function cum(arr) { var c = new Float64Array(n + 1); for (var i = 0; i < n; i++) c[i + 1] = c[i] + arr[i]; return c; }
    var cm = {}, ofm = {}, slf = {}, tcm = {}, tofm = {}, traps = [];
    blocks.forEach(function (b, bi) {
      var sb = S && S.blocks && S.blocks[b.id];
      var dcm = sb && sb.codling_moth ? series(sb.codling_moth) : days.map(function (d) { return (d.counts && d.counts[b.id]) || 0; });
      cm[b.id] = cum(dcm);
      ofm[b.id] = cum(series(sb && sb.oriental_fruit_moth));
      slf[b.id] = cum(series(sb && sb.spotted_lanternfly));
      b.traps.forEach(function (t) {
        var st = S && S.traps && S.traps[t];
        var dt = st && st.codling_moth ? series(st.codling_moth) : days.map(function (d) { return (d.traps && d.traps[t]) || 0; });
        tcm[t] = cum(dt);
        tofm[t] = cum(series(st && st.oriental_fruit_moth));
        traps.push({ id: t, block: b, bi: bi });
      });
      b.short = String(b.name || b.id).replace(/^block\s*/i, "").toUpperCase();
      b.color = PAL[bi % PAL.length];
    });
    var cdd = cum(days.map(function (d) { return d.dd_today || 0; }));
    var dp = days.map(function (d) { return dateParts(d.date); });
    var monthStarts = [];
    for (var i = 0; i < n; i++) if (dp[i].d === 1) monthStarts.push(i);
    var dd = {}; // dd_since_biofix per block per day
    blocks.forEach(function (b) {
      dd[b.id] = days.map(function (d) { var s = d.blocks && d.blocks[b.id]; return s ? (s.dd_since_biofix || 0) : 0; });
    });
    return { T: T, S: S, days: days, n: n, blocks: blocks, traps: traps, cm: cm, ofm: ofm, slf: slf, tcm: tcm, tofm: tofm, cdd: cdd, dp: dp, monthStarts: monthStarts, dd: dd,
      open: (T.thresholds && T.thresholds.spray_open_dd) || 250, close: (T.thresholds && T.thresholds.spray_close_dd) || 350 };
  }

  function rng(c, lo, hi) { if (hi < lo) return 0; lo = Math.max(0, lo); return c[hi + 1] - c[lo]; }

  /* ---------- tooltip ---------- */
  function ensureTip() {
    if (tip) return tip;
    tip = document.createElement("div");
    tip.id = "foa-tip"; tip.className = "foa-tip";
    document.body.appendChild(tip);
    return tip;
  }
  function showTip(text, x, y) {
    var t = ensureTip();
    while (t.firstChild) t.removeChild(t.firstChild);
    var lines = text.split("|");
    lines.forEach(function (ln, i) {
      var div = document.createElement("div");
      if (i === 0) { div.className = "foa-tv"; div.textContent = ln; }
      else {
        div.className = "foa-tl";
        var m = /^#([0-9a-fA-F]{6});(.*)$/.exec(ln);
        if (m) { var key = document.createElement("i"); key.style.borderColor = "#" + m[1]; div.appendChild(key); ln = m[2]; }
        var parts = ln.split("="), lab = document.createElement("span"); lab.textContent = parts[0]; div.appendChild(lab);
        if (parts.length > 1) { var v = document.createElement("b"); v.textContent = parts.slice(1).join("="); div.appendChild(v); }
      }
      t.appendChild(div);
    });
    t.style.visibility = "visible";
    var w = t.offsetWidth, h = t.offsetHeight, vw = window.innerWidth, vh = window.innerHeight;
    var left = x + 14, top = y + 14;
    if (left + w > vw - 8) left = x - w - 14;
    if (top + h > vh - 8) top = y - h - 14;
    t.style.left = Math.max(4, left) + "px"; t.style.top = Math.max(4, top) + "px";
  }
  function hideTip() { if (tip) tip.style.visibility = "hidden"; }
  function bindHover(el) {
    if (el.__foaBound) return; el.__foaBound = true;
    var hair = null;
    el.addEventListener("mousemove", function (e) {
      var tgt = e.target && e.target.closest ? e.target.closest("[data-tip]") : null;
      if (!tgt) { hideTip(); if (hair) hair.style.visibility = "hidden"; return; }
      showTip(tgt.getAttribute("data-tip"), e.clientX, e.clientY);
      var hx = tgt.getAttribute("data-hx");
      var svg = tgt.ownerSVGElement;
      hair = svg ? svg.querySelector(".foa-hair") : null;
      if (hair && hx != null) { hair.setAttribute("x1", hx); hair.setAttribute("x2", hx); hair.style.visibility = "visible"; }
    });
    el.addEventListener("mouseleave", function () { hideTip(); if (hair) hair.style.visibility = "hidden"; });
  }

  function head(title, sub) { return '<div class="foa-head"><h3 class="foa-title">' + title + '</h3><div class="foa-sub">' + sub + "</div></div>"; }

  /* ---------- panels ---------- */
  function renderKPI(d, sel) {
    var b = P.blocks, day = P.days[d];
    var today = 0, last7 = 0, prior7 = 0, spray = 0, hot = 0;
    b.forEach(function (x) {
      today += rng(P.cm[x.id], d, d);
      last7 += rng(P.cm[x.id], d - 6, d);
      prior7 += rng(P.cm[x.id], d - 13, d - 7);
      var st = day.blocks && day.blocks[x.id];
      if (st && st.status === "spray_window") spray++;
    });
    P.traps.forEach(function (t) { if (rng(P.tcm[t.id], d, d) > 10) hot++; });
    var lo = Math.max(0, d - 6), rate = (P.cdd[d + 1] - P.cdd[lo]) / (d - lo + 1);
    var chg, chgNote, chgWord;
    if (prior7 > 0) {
      var pct = Math.round((last7 - prior7) / prior7 * 100);
      chgWord = pct > 0 ? "up" : pct < 0 ? "down" : "flat";
      chg = (pct > 0 ? "+" : "") + pct + "%";
      chgNote = chgWord + " from " + prior7 + " to " + last7 + " moths";
    } else { chg = "—"; chgWord = ""; chgNote = "no catch in the prior 7 days"; }
    var pending = null;
    b.forEach(function (x) {
      var st = day.blocks && day.blocks[x.id];
      if (st && st.status === "accumulating") {
        var rem = P.open - (st.dd_since_biofix || 0);
        if (pending === null || rem < pending.rem) pending = { rem: rem, b: x };
      }
    });
    var daysVal, daysNote;
    if (!pending) { daysVal = '<span style="font-size:20px">none pending</span>'; daysNote = "no block is accumulating"; }
    else if (rate <= 0) { daysVal = "—"; daysNote = pending.b.name + " needs " + fmt1(pending.rem) + " DD, no heat"; }
    else { var dn = Math.max(1, Math.ceil(pending.rem / rate)); daysVal = dn + "<small>d</small>"; daysNote = pending.b.name + ", " + fmt1(pending.rem) + " DD to go (estimate)"; }
    function tile(lab, val, note) { return '<div class="foa-tile"><div class="foa-lab">' + lab + '</div><div class="foa-val foa-num">' + val + '</div><div class="foa-note">' + note + "</div></div>"; }
    return head("Season at a glance", P.dp[d].lab + ", all 18 traps, codling moth") + '<div class="foa-tiles">' +
      tile("Moths today", today, "codling moth, all traps") +
      tile("7-day change", chg + (chgWord ? "<small>" + chgWord + "</small>" : ""), chgNote) +
      tile("Blocks needing spray", spray, spray ? "spray window open" : "no open windows") +
      tile("Traps above 10 today", hot, "of " + P.traps.length + " traps") +
      tile("DD rate", fmt1(rate) + "<small>/day</small>", "trailing 7-day mean") +
      tile("Days to next window", daysVal, daysNote) + "</div>";
  }

  function renderSpecies(d, sel) {
    var rows = P.blocks.map(function (x) {
      var st = P.days[d].blocks && P.days[d].blocks[x.id];
      return { b: x, cm: rng(P.cm[x.id], d - 6, d), ofm: rng(P.ofm[x.id], d - 6, d), status: st ? st.status : "watching" };
    });
    var max = 1; rows.forEach(function (r) { max = Math.max(max, r.cm + r.ofm); });
    var slfTotal = 0; P.blocks.forEach(function (x) { slfTotal += rng(P.slf[x.id], 0, d); });
    var h = head("Species by region", "trailing 7-day trap totals per block, " + P.dp[Math.max(0, d - 6)].lab + " to " + P.dp[d].lab);
    h += '<div class="foa-legend"><span><i class="foa-cm"></i>Codling moth</span><span><i class="foa-ofm"></i>Oriental fruit moth (lookalike)</span></div><div class="foa-rows">';
    rows.forEach(function (r) {
      var wc = r.cm / max * 100, wo = r.ofm / max * 100;
      h += '<div class="foa-row' + (r.b.id === sel ? " foa-sel" : "") + '"><div><span class="foa-bn">' + esc(r.b.name) + '</span><span class="foa-st"><i class="foa-dot" style="background:var(' + STATUS_VAR[r.status] + ')"></i>' + STATUS_WORD[r.status] + "</span></div>" +
        '<div class="foa-bar">' +
        '<div class="foa-seg foa-cm" style="width:' + wc.toFixed(2) + '%" data-tip="' + r.cm + (r.cm === 1 ? ' codling moth|' : ' codling moths|') + esc(r.b.name) + ', last 7 days"></div>' +
        '<div class="foa-seg foa-ofm" style="width:' + wo.toFixed(2) + '%" data-tip="' + r.ofm + (r.ofm === 1 ? ' oriental fruit moth|' : ' oriental fruit moths|') + esc(r.b.name) + ', last 7 days"></div></div>' +
        '<div class="foa-nums foa-num">' + r.cm + ' <span>· ' + r.ofm + "</span></div></div>";
    });
    h += '</div><div class="foa-foot"><i class="foa-dot" style="background:var(--line)"></i>Spotted lanternfly: ' + (slfTotal ? slfTotal + " detected this season" : "none detected this season") + "</div>";
    return h;
  }

  function renderHeat(d, sel, W) {
    var weeks = Math.floor(d / 7) + 1, rows = P.blocks.length;
    var left = 34, top = 6, bottom = 22, cellH = 26, gap = 1;
    var innerW = Math.max(60, W - left - 4), cellW = Math.min(64, innerW / weeks);
    var H = top + rows * cellH + bottom;
    var cells = [], max = 1, c, w, r;
    for (r = 0; r < rows; r++) { cells.push([]); for (w = 0; w < weeks; w++) { c = rng(P.cm[P.blocks[r].id], w * 7, Math.min(d, w * 7 + 6)); cells[r].push(c); if (c > max) max = c; } }
    var s = '<svg width="' + W + '" height="' + H + '" viewBox="0 0 ' + W + " " + H + '" role="img" aria-label="Codling catch heatmap">';
    for (r = 0; r < rows; r++) {
      var b = P.blocks[r], y = top + r * cellH;
      s += '<text class="foa-ax foa-row-l" x="' + (left - 8) + '" y="' + (y + cellH / 2 + 4) + '" text-anchor="end"' + (b.id === sel ? ' style="fill:var(--accent)"' : "") + ">" + b.short + "</text>";
      for (w = 0; w < weeks; w++) {
        var v = cells[r][w], step = v === 0 ? 0 : Math.min(4, Math.floor(v / max * 5));
        var ws = P.dp[w * 7].lab, we = P.dp[Math.min(d, w * 7 + 6)].lab;
        s += '<rect class="foa-cell" x="' + (left + w * cellW + gap).toFixed(1) + '" y="' + (y + gap) + '" width="' + (cellW - 2 * gap).toFixed(1) + '" height="' + (cellH - 2 * gap) + '" rx="2" fill="' + heatColor(step) + '" data-tip="' + v + (v === 1 ? ' moth|' : ' moths|') + esc(b.name) + ', week of ' + ws + '"><title>' + esc(b.name) + ", week of " + ws + " to " + we + ": " + v + (v === 1 ? " codling moth</title>" : " codling moths</title>") + "</rect>";
      }
    }
    for (w = 0; w < weeks; w += 2) s += '<text class="foa-ax" x="' + (left + w * cellW + cellW / 2).toFixed(1) + '" y="' + (top + rows * cellH + 15) + '" text-anchor="middle">' + P.dp[w * 7].md + "</text>";
    var tx = left + (weeks - 1) * cellW;
    s += '<rect x="' + tx.toFixed(1) + '" y="' + top + '" width="' + cellW.toFixed(1) + '" height="' + (rows * cellH) + '" rx="3" fill="none" stroke="var(--ink)" stroke-width="2"/>';
    s += "</svg>";
    var leg = '<div class="foa-legend" style="margin-top:8px;margin-bottom:0"><span>0</span>';
    for (var i = 0; i < 5; i++) leg += '<span><i style="background:' + heatColor(i) + ';width:22px;margin-right:-10px"></i></span>';
    leg += "<span>" + max + " moths a week</span><span style=\"margin-left:auto\"><i style=\"width:12px;height:12px;border:2px solid var(--ink);background:none\"></i>this week</span></div>";
    return head("Catch heatmap", "codling moths per block per week, Apr 15 to " + P.dp[d].lab) + s + leg;
  }

  var ARROW = {
    Rising: '<svg viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M2 10L10 2M5 2h5v5"/></svg>',
    Falling: '<svg viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M2 2l8 8M10 5v5H5"/></svg>',
    Steady: '<svg viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M2 6h8M7 3l3 3-3 3"/></svg>'
  };
  function renderTraps(d, sel) {
    var rows = P.traps.map(function (t) {
      var l7 = rng(P.tcm[t.id], d - 6, d), p7 = rng(P.tcm[t.id], d - 13, d - 7), tr;
      if (p7 === 0) tr = l7 > 0 ? "Rising" : "Steady";
      else { var ch = (l7 - p7) / p7; tr = ch > 0.2 ? "Rising" : ch < -0.2 ? "Falling" : "Steady"; }
      return { t: t, today: rng(P.tcm[t.id], d, d), l7: l7, p7: p7, o7: rng(P.tofm[t.id], d - 6, d), tr: tr, sel: t.block.id === sel ? 0 : 1 };
    });
    rows.sort(function (a, b) { return (a.sel - b.sel) || (b.l7 - a.l7) || (a.t.id < b.t.id ? -1 : 1); });
    var h = head("Trap table", "per-trap counts, 7-day totals and trend vs the prior 7 days" + (sel ? ", selected block first" : ""));
    h += '<table><thead><tr><th>Trap</th><th>Block</th><th class="foa-r">Today</th><th class="foa-r">7-day</th><th class="foa-r">OFM 7-day</th><th>Trend</th></tr></thead><tbody>';
    rows.forEach(function (r) {
      h += '<tr class="' + (r.sel === 0 ? "foa-sel" : "") + '"><td class="foa-num">' + esc(r.t.id) + '</td><td>' + esc(r.t.block.name) + '</td><td class="foa-r">' + r.today + '</td><td class="foa-r">' + r.l7 + '</td><td class="foa-r foa-m">' + r.o7 + '</td><td><span class="foa-trend" title="' + r.p7 + ' then ' + r.l7 + '">' + ARROW[r.tr] + r.tr + "</span></td></tr>";
    });
    return h + "</tbody></table>";
  }

  function xTicks(d, x0, x1, plotW) {
    // returns [{x, label}] for Apr 15 and each month start up to d
    var out = [], sc = plotW / Math.max(1, d);
    out.push({ x: x0, label: P.dp[0].lab });
    P.monthStarts.forEach(function (i) { if (i <= d) { var x = x0 + i * sc; if (x - out[out.length - 1].x > 44) out.push({ x: x, label: MONTHS[P.dp[i].m - 1] }); } });
    return out;
  }

  function renderRace(d, sel, W) {
    var H = 250, left = 44, right = 66, top = 10, bottom = 26, plotW = Math.max(50, W - left - right), plotH = H - top - bottom;
    var maxDD = P.close + 50;
    P.blocks.forEach(function (b) { if (P.dd[b.id][d] > maxDD) maxDD = P.dd[b.id][d]; });
    var step = [50, 100, 200, 250, 500, 1000].filter(function (st) { return maxDD / st <= 6; })[0] || 1000;
    var yMax = Math.ceil(maxDD / step) * step;
    var sc = plotW / Math.max(1, d), sy = function (v) { return top + plotH - v / yMax * plotH; };
    var s = '<svg width="' + W + '" height="' + H + '" viewBox="0 0 ' + W + " " + H + '" role="img" aria-label="Degree-day race">';
    for (var g = 0; g <= yMax; g += step) s += '<line class="foa-grid" x1="' + left + '" x2="' + (left + plotW) + '" y1="' + sy(g).toFixed(1) + '" y2="' + sy(g).toFixed(1) + '"/><text class="foa-ax" x="' + (left - 6) + '" y="' + (sy(g) + 4).toFixed(1) + '" text-anchor="end">' + g + "</text>";
    s += '<rect x="' + left + '" y="' + sy(P.close).toFixed(1) + '" width="' + plotW + '" height="' + (sy(P.open) - sy(P.close)).toFixed(1) + '" fill="color-mix(in srgb, var(--spray) 7%, transparent)"/>';
    var merged = sy(P.open) - sy(P.close) < 26;
    [[P.open, merged ? P.open + " to " + P.close + " DD · spray window" : P.open + " DD · spray window opens"], [P.close, merged ? "" : P.close + " DD · window closes"]].forEach(function (t) {
      s += '<line x1="' + left + '" x2="' + (left + plotW) + '" y1="' + sy(t[0]).toFixed(1) + '" y2="' + sy(t[0]).toFixed(1) + '" stroke="var(--muted)" stroke-width="1" stroke-dasharray="4 3"/>';
      if (t[1]) s += '<text class="foa-th" x="' + (left + 4) + '" y="' + (sy(merged ? P.close : t[0]) - 4).toFixed(1) + '">' + t[1] + "</text>";
    });
    xTicks(d, left, left + plotW, plotW).forEach(function (t) { s += '<text class="foa-ax" x="' + t.x.toFixed(1) + '" y="' + (H - 8) + '" text-anchor="' + (t.x === left ? "start" : "middle") + '">' + t.label + "</text>"; });
    var ends = [];
    P.blocks.forEach(function (b) {
      var arr = P.dd[b.id], pts = [];
      for (var i = 0; i <= d; i++) pts.push((left + i * sc).toFixed(1) + "," + sy(arr[i]).toFixed(1));
      var isSel = b.id === sel;
      s += '<polyline fill="none" stroke="' + b.color + '" stroke-width="' + (isSel ? 4 : 2) + '" stroke-linejoin="round" stroke-linecap="round" points="' + pts.join(" ") + '"' + (sel && !isSel ? ' opacity="0.8"' : "") + "/>";
      ends.push({ y: sy(arr[d]), b: b });
    });
    ends.sort(function (a, b) { return a.y - b.y; });
    var groups = [];
    ends.forEach(function (e) { var g = groups[groups.length - 1]; if (g && e.y - g.y < 4) { g.names.push(e.b); g.sel = g.sel || e.b.id === sel; } else groups.push({ y: e.y, names: [e.b], sel: e.b.id === sel }); });
    var prevBottom = -Infinity, order = P.blocks;
    groups.forEach(function (g) { var y = Math.max(g.y, prevBottom + 13); y = Math.min(y, top + plotH); g.ly = y; prevBottom = y; });
    groups.forEach(function (g) {
      var names = g.names.slice().sort(function (a, b) { return order.indexOf(a) - order.indexOf(b); }), lab;
      var consecutive = names.length > 2 && order.indexOf(names[names.length - 1]) - order.indexOf(names[0]) === names.length - 1;
      lab = consecutive ? names[0].short + " to " + names[names.length - 1].short : names.length > 3 ? names[0].short + ", " + names[1].short + " +" + (names.length - 2) : names.map(function (b) { return b.short; }).join(", ");
      s += '<text class="foa-lbl" x="' + (left + plotW + 6) + '" y="' + (g.ly + 4).toFixed(1) + '"' + (g.sel ? ' style="fill:var(--accent)"' : "") + ">" + lab + "</text>";
    });
    // hit columns + crosshair
    for (var i = 0; i <= d; i++) {
      var x = left + i * sc, t = P.dp[i].lab;
      P.blocks.forEach(function (b) { t += "|" + b.color + ";" + esc(b.name) + "=" + fmt1(P.dd[b.id][i]) + " DD"; });
      s += '<rect class="foa-hit" x="' + (x - sc / 2).toFixed(1) + '" y="' + top + '" width="' + Math.max(1, sc).toFixed(1) + '" height="' + plotH + '" data-tip="' + t + '" data-hx="' + x.toFixed(1) + '"/>';
    }
    s += '<line class="foa-hair" x1="0" x2="0" y1="' + top + '" y2="' + (top + plotH) + '"/></svg>';
    var leg = '<div class="foa-legend">';
    P.blocks.forEach(function (b) { leg += '<span class="' + (b.id === sel ? "foa-on" : "") + '"><i class="foa-key" style="border-color:' + b.color + '"></i>' + esc(b.name) + "</span>"; });
    leg += "</div>";
    return head("Degree-day race", "cumulative degree-days since each block's biofix, Apr 15 to " + P.dp[d].lab) + leg + s;
  }

  function renderWeather(d, sel, W) {
    var H = 190, left = 40, right = 12, top = 24, bottom = 26, plotW = Math.max(50, W - left - right), plotH = H - top - bottom;
    var yMin = 30, yMax = 100, sc = plotW / Math.max(1, d), sy = function (v) { return top + plotH - (v - yMin) / (yMax - yMin) * plotH; };
    var day = P.days[d];
    var s = '<svg width="' + W + '" height="' + H + '" viewBox="0 0 ' + W + " " + H + '" role="img" aria-label="Daily temperature band">';
    for (var g = 40; g <= 100; g += 20) s += '<line class="foa-grid" x1="' + left + '" x2="' + (left + plotW) + '" y1="' + sy(g).toFixed(1) + '" y2="' + sy(g).toFixed(1) + '"/><text class="foa-ax" x="' + (left - 6) + '" y="' + (sy(g) + 4).toFixed(1) + '" text-anchor="end">' + g + " F</text>";
    var hi = [], lo = [], mean = [];
    for (var i = 0; i <= d; i++) {
      var x = (left + i * sc).toFixed(1), dy = P.days[i];
      hi.push(x + "," + sy(dy.tmax_f).toFixed(1)); lo.push(x + "," + sy(dy.tmin_f).toFixed(1)); mean.push(x + "," + sy((dy.tmax_f + dy.tmin_f) / 2).toFixed(1));
    }
    s += '<polygon fill="color-mix(in srgb, var(--accent) 18%, transparent)" points="' + hi.join(" ") + " " + lo.reverse().join(" ") + '"/>';
    s += '<polyline fill="none" stroke="var(--accent)" stroke-width="2" stroke-linejoin="round" points="' + mean.join(" ") + '"/>';
    xTicks(d, left, left + plotW, plotW).forEach(function (t) { s += '<text class="foa-ax" x="' + t.x.toFixed(1) + '" y="' + (H - 8) + '" text-anchor="' + (t.x === left ? "start" : "middle") + '">' + t.label + "</text>"; });
    var tx = left + d * sc;
    s += '<line x1="' + tx.toFixed(1) + '" x2="' + tx.toFixed(1) + '" y1="' + (top - 4) + '" y2="' + (top + plotH) + '" stroke="var(--ink)" stroke-width="2"/>';
    s += '<text class="foa-lbl" x="' + (tx - 8).toFixed(1) + '" y="' + (top - 8) + '" text-anchor="end">Today: ' + Math.round(day.tmin_f) + " to " + Math.round(day.tmax_f) + " F, " + fmt1(day.dd_today || 0) + " DD</text>";
    for (i = 0; i <= d; i++) {
      var xi = left + i * sc, dd = P.days[i];
      s += '<rect class="foa-hit" x="' + (xi - sc / 2).toFixed(1) + '" y="' + top + '" width="' + Math.max(1, sc).toFixed(1) + '" height="' + plotH + '" data-tip="' + P.dp[i].lab + "|High=" + Math.round(dd.tmax_f) + " F|Low=" + Math.round(dd.tmin_f) + " F|Degree-days=" + fmt1(dd.dd_today || 0) + '" data-hx="' + xi.toFixed(1) + '"/>';
    }
    s += '<line class="foa-hair" x1="0" x2="0" y1="' + top + '" y2="' + (top + plotH) + '"/></svg>';
    var leg = '<div class="foa-legend"><span><i style="background:color-mix(in srgb, var(--accent) 18%, transparent)"></i>Daily low to high</span><span><i class="foa-key" style="border-color:var(--accent)"></i>Daily mean</span><span><i class="foa-key" style="border-color:var(--ink)"></i>Today</span></div>';
    return head("Weather strip", "daily low to high, base 50 F, Apr 15 to " + P.dp[d].lab) + leg + s;
  }

  /* ---------- entry ---------- */
  function render(dayIndex, selectedBlock) {
    if (!P) { P = precompute(); if (!P) return; }
    if (!document.getElementById("foa-style")) { var st = document.createElement("style"); st.id = "foa-style"; st.textContent = CSS; document.head.appendChild(st); }
    var d = Math.max(0, Math.min(P.n - 1, Math.floor(+dayIndex || 0)));
    var sel = selectedBlock || null;
    var els = {}, widths = {}, k;
    for (k in IDS) { els[k] = document.getElementById(IDS[k]); if (els[k]) { if (!els[k].classList.contains("foa-root")) els[k].classList.add("foa-root"); widths[k] = els[k].clientWidth || 1392; } }
    for (k in IDS) widths[k] = Math.max(320, (widths[k] || 1392) - 2);
    if (els.kpi) els.kpi.innerHTML = renderKPI(d, sel);
    if (els.species) { els.species.innerHTML = renderSpecies(d, sel); bindHover(els.species); }
    if (els.heat) { els.heat.innerHTML = renderHeat(d, sel, widths.heat); bindHover(els.heat); }
    if (els.traps) els.traps.innerHTML = renderTraps(d, sel);
    if (els.ddrace) { els.ddrace.innerHTML = renderRace(d, sel, widths.ddrace); bindHover(els.ddrace); }
    if (els.weather) { els.weather.innerHTML = renderWeather(d, sel, widths.weather); bindHover(els.weather); }
  }

  window.FOA = { render: render };
})();
