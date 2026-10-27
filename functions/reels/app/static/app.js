"use strict";
/* REELS dashboard — vanilla JS, nessuna dipendenza. Tutto il testo utente passa da textContent (no innerHTML). */

const $ = (s, el = document) => el.querySelector(s);
function h(tag, attrs = {}, ...kids) {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (v === false || v == null) continue;
    if (k === "class") el.className = v;
    else if (k.startsWith("on")) el.addEventListener(k.slice(2), v);
    else if (k === "style" && typeof v === "object") Object.assign(el.style, v);
    else if (k in el && k !== "list") el[k] = v;
    else el.setAttribute(k, v === true ? "" : v);
  }
  for (const c of kids.flat()) if (c != null && c !== false) el.append(c.nodeType ? c : document.createTextNode(c));
  return el;
}
const fmtT = (s) => { s = Math.max(0, s); const m = Math.floor(s / 60); return `${m}:${(s - m * 60).toFixed(1).padStart(4, "0")}`; };
const ms = (x) => `${x >= 0 ? "+" : "−"}${Math.abs(Math.round(x * 1000))} ms`;

async function api(path, opts = {}) {
  const r = await fetch("/api" + path, opts);
  let body = null;
  try { body = await r.json(); } catch { /* no body */ }
  if (!r.ok) throw new Error((body && (body.detail || body.error)) || `Errore ${r.status}`);
  return body;
}
const post = (p, data) => api(p, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(data) });

let toastT;
function toast(msg, err = false) {
  const t = $("#toast"); t.textContent = msg; t.className = "show" + (err ? " err" : "");
  clearTimeout(toastT); toastT = setTimeout(() => (t.className = ""), err ? 5000 : 2200);
}

const FORMATS = [
  { id: "9:16", w: 9, h: 16, label: "Verticale 9:16", plat: ["TikTok", "Instagram Reels", "YouTube Shorts", "Facebook Reels"] },
  { id: "4:5", w: 4, h: 5, label: "Portrait 4:5", plat: ["Instagram Feed", "Facebook Feed"] },
  { id: "1:1", w: 1, h: 1, label: "Quadrato 1:1", plat: ["LinkedIn Feed", "Instagram Grid", "Facebook"] },
  { id: "16:9", w: 16, h: 9, label: "Orizzontale 16:9", plat: ["LinkedIn Video", "YouTube", "Web"] },
];
const MODES = [
  { id: "long_form_extraction", title: "Video lungo → Reels", desc: "Carica podcast, lezioni o vlog di 10+ minuti. L'agente trova i 3-5 momenti migliori (15-60 s), con gancio, jump-cut, sottotitoli, SFX e zoom." },
  { id: "script_assembly", title: "Script + clip multiple", desc: "Incolla il tuo script e carica le riprese. L'agente allinea il parlato allo script, sceglie la take migliore per ogni frase e monta nella sequenza esatta." },
];

const S = { mode: "long_form_extraction", formats: new Set(["9:16"]), files: [], pid: null, timer: null };
const app = $("#app");
const stopPoll = () => { clearInterval(S.timer); S.timer = null; };

/* ───────────── Nuovo progetto ───────────── */
function viewNew() {
  stopPoll(); S.pid = null; history.replaceState(null, "", "#");
  const script = h("textarea", { placeholder: "Una frase per riga, nell'ordine in cui deve comparire nel video finale.", id: "script" });
  const fileList = h("div", { class: "files" });
  const input = h("input", { type: "file", multiple: true, accept: "video/*,.json", style: { display: "none" }, onchange: (e) => addFiles(e.target.files) });
  const drop = h("div", { class: "drop", tabindex: 0, role: "button", onclick: () => input.click(),
    ondragover: (e) => { e.preventDefault(); drop.classList.add("over"); }, ondragleave: () => drop.classList.remove("over"),
    ondrop: (e) => { e.preventDefault(); drop.classList.remove("over"); addFiles(e.dataTransfer.files); } },
    h("b", {}, "Trascina qui i video"), h("div", { class: "small" }, "oppure clicca · puoi caricarne più di uno · opzionale: ", h("code", {}, "nome.transcript.json"), " accanto al video per saltare l'ASR"));
  const modeBox = h("div", { class: "cards two" });
  const fmtBox = h("div", { class: "cards four" });
  const scriptBox = h("div", {}, h("h2", {}, h("span", { class: "step" }, "3"), "Script"), script);
  const advanced = {
    policy: h("select", {}, ...[["natural", "Naturale (pausa max 0,45 s)"], ["tight", "Serrato (0,25 s) — stile Hormozi"], ["relaxed", "Rilassato (0,8 s)"]].map(([v, l]) => h("option", { value: v }, l))),
    subs: h("select", {}, ...[["hormozi", "Hormozi"], ["mrbeast", "MrBeast"], ["clean", "Pulito"]].map(([v, l]) => h("option", { value: v }, l))),
    reframe: h("select", {}, ...[["auto", "Automatico (crop sul parlante o sfondo sfocato)"], ["smart_crop", "Sempre crop sul parlante"], ["blur_pad", "Sempre sfondo sfocato"]].map(([v, l]) => h("option", { value: v }, l))),
    sfx: h("input", { type: "checkbox", checked: true }), emoji: h("input", { type: "checkbox", checked: true }), zoom: h("input", { type: "checkbox", checked: true }),
    nmax: h("input", { type: "text", value: "5", size: 2 }), dmin: h("input", { type: "text", value: "15", size: 3 }), dmax: h("input", { type: "text", value: "60", size: 3 }),
  };
  const bOnly = h("div", { class: "grid2" },
    h("label", { class: "f" }, "Numero massimo di reel", advanced.nmax), h("label", { class: "f" }, "Durata minima (s)", advanced.dmin), h("label", { class: "f" }, "Durata massima (s)", advanced.dmax));

  function addFiles(list) {
    for (const f of list) if (!S.files.some((x) => x.name === f.name && x.size === f.size)) S.files.push(f);
    paint();
  }
  function paint() {
    modeBox.replaceChildren(...MODES.map((m) => h("button", { class: "card pick" + (S.mode === m.id ? " on" : ""), onclick: () => { S.mode = m.id; paint(); } },
      h("b", {}, m.title), h("span", { class: "muted" }, m.desc))));
    fmtBox.replaceChildren(...FORMATS.map((f) => h("button", { class: "card pick" + (S.formats.has(f.id) ? " on" : ""),
      onclick: () => { S.formats.has(f.id) ? (S.formats.size > 1 && S.formats.delete(f.id)) : S.formats.add(f.id); paint(); } },
      h("b", {}, h("span", { class: "glyph", style: { width: 18 * Math.min(1, f.w / f.h) + 6 + "px", height: 18 * Math.min(1, f.h / f.w) + 6 + "px" } }), f.label),
      h("div", { class: "chips" }, f.plat.map((p) => h("span", { class: "chip" }, p))))));
    fileList.replaceChildren(...S.files.map((f, i) => h("div", { class: "file" },
      h("span", { class: "badge b-acc" }, f.name.endsWith(".json") ? "json" : `#${S.files.filter((x) => !x.name.endsWith(".json")).indexOf(f) + 1}`),
      h("span", { class: "name" }, f.name), h("span", { class: "muted small" }, (f.size / 1048576).toFixed(1) + " MB"),
      h("button", { class: "btn sm", title: "Rimuovi", onclick: () => { S.files.splice(i, 1); paint(); } }, "✕"))));
    scriptBox.style.display = S.mode === "script_assembly" ? "" : "none";
    bOnly.style.display = S.mode === "long_form_extraction" ? "" : "none";
    go.disabled = !S.files.some((f) => !f.name.endsWith(".json"));
  }
  const go = h("button", { class: "btn primary", onclick: submit }, "Avvia analisi");
  async function submit() {
    if (S.mode === "script_assembly" && !script.value.trim()) return toast("Scrivi lo script", true);
    const fd = new FormData();
    fd.set("mode", S.mode); fd.set("formats", [...S.formats].join(",")); fd.set("script", script.value);
    fd.set("cut_policy", advanced.policy.value); fd.set("subtitle_preset", advanced.subs.value); fd.set("reframe", advanced.reframe.value);
    fd.set("sfx", advanced.sfx.checked); fd.set("emoji", advanced.emoji.checked); fd.set("zoom", advanced.zoom.checked);
    if (S.mode === "long_form_extraction") { fd.set("n_max", advanced.nmax.value); fd.set("min_dur", advanced.dmin.value); fd.set("max_dur", advanced.dmax.value); }
    S.files.forEach((f) => fd.append("files", f));
    go.disabled = true; go.textContent = "Caricamento…";
    try { const r = await api("/projects", { method: "POST", body: fd }); S.files = []; openProject(r.id); }
    catch (e) { toast(e.message, true); go.disabled = false; go.textContent = "Avvia analisi"; }
  }
  async function demo(mode) {
    try { const r = await post("/demo", { mode, formats: [...S.formats] }); openProject(r.id); } catch (e) { toast(e.message, true); }
  }
  app.replaceChildren(
    h("h1", {}, "Crea contenuti brevi dai tuoi video"),
    h("div", { class: "muted" }, "Scegli la modalità, carica i file, scegli i formati. I tagli vengono piazzati nel silenzio reale tra le parole e agganciati al frame."),
    h("h2", {}, h("span", { class: "step" }, "1"), "Modalità"), modeBox,
    h("h2", {}, h("span", { class: "step" }, "2"), "Video"), drop, input, fileList, scriptBox,
    h("h2", {}, h("span", { class: "step" }, "4"), "Formati di export (anche più di uno)"), fmtBox,
    h("details", {}, h("summary", {}, "Opzioni avanzate"),
      h("div", { class: "grid2", style: { marginTop: "10px" } },
        h("label", { class: "f" }, "Aggressività dei tagli", advanced.policy), h("label", { class: "f" }, "Stile sottotitoli", advanced.subs),
        h("label", { class: "f" }, "Reframing", advanced.reframe)),
      h("div", { class: "row", style: { margin: "10px 0" } }, h("label", {}, advanced.sfx, "SFX"), h("label", {}, advanced.emoji, "Emoji nei sottotitoli"), h("label", {}, advanced.zoom, "Zoom dinamici")), bOnly),
    h("div", { class: "row", style: { marginTop: "22px" } }, go,
      h("span", { class: "muted" }, "oppure prova subito:"),
      h("button", { class: "btn", id: "demo-b", onclick: () => demo("long_form_extraction") }, "Demo video lungo"),
      h("button", { class: "btn", id: "demo-a", onclick: () => demo("script_assembly") }, "Demo script + clip")));
  paint();
}

/* ───────────── Progetto: elaborazione / revisione ───────────── */
function openProject(pid) {
  S.pid = pid; history.replaceState(null, "", "#" + pid); stopPoll();
  tick(); S.timer = setInterval(tick, 800);
}
async function tick() {
  let st;
  try { st = await api("/projects/" + S.pid); } catch (e) { stopPoll(); return toast(e.message, true); }
  if (st.status === "created" || st.status === "analyzing") return viewProcessing(st);
  if (st.status === "error") { stopPoll(); return viewError(st); }
  if (st.status === "rendering") { if (!$("#render-bar")) return viewReview(st, true); return updateRender(st); }
  if (st.status === "ready" || st.status === "done") {
    if ($("#review-root") && S.reviewFor === st.id) { if (st.status === "done" || $("#render-bar")) { updateRender(st); } if (st.status === "done") stopPoll(); return; }
    return viewReview(st, false);
  }
}
function viewProcessing(st) {
  const order = ["probe", "transcribe", "audio", "cuts", "faces", "plan"];
  const labels = { probe: "Analisi file", transcribe: "Trascrizione", audio: "Analisi audio", cuts: "Scelta dei tagli", faces: "Tracking volti", plan: "Piano di montaggio" };
  const rows = order.map((k) => { const s = st.stages[k] || { progress: 0, state: "pending" };
    return h("div", { class: "stage " + s.state }, h("span", {}, labels[k]), h("div", { class: "bar" }, h("i", { style: { width: Math.round(s.progress * 100) + "%" } })), h("span", { class: "small muted" }, s.state === "done" ? "✓" : Math.round(s.progress * 100) + "%")); });
  app.replaceChildren(h("h1", {}, "Elaborazione in corso"), h("div", { class: "muted" }, st.message || "In coda…"),
    h("div", { class: "card", style: { marginTop: "16px" } }, h("div", { class: "bar", style: { height: "12px", marginBottom: "12px" } }, h("i", { style: { width: Math.round((st.overall || 0) * 100) + "%" } })), ...rows));
}
function viewError(st) {
  app.replaceChildren(h("h1", {}, "Qualcosa non ha funzionato"),
    h("div", { class: "card", style: { marginTop: "12px" } }, h("span", { class: "badge b-bad" }, st.error_kind === "asr_unavailable" ? "ASR non configurato" : "Errore"), h("p", {}, st.error),
      h("div", { class: "row" }, h("button", { class: "btn primary", onclick: viewNew }, "Nuovo progetto"))));
}

/* ───────────── Revisione dei tagli ───────────── */
async function viewReview(st, rendering) {
  S.reviewFor = st.id;
  const plan = await api(`/projects/${st.id}/plan`);
  S.plan = plan;
  const root = h("div", { id: "review-root" });
  const fmts = plan.exports.map((e) => e.format_id);
  const quality = h("select", { id: "quality" }, h("option", { value: "draft" }, "Bozza veloce (metà risoluzione)"), h("option", { value: "final", selected: true }, "Finale (full-res)"));
  const fchecks = fmts.map((f) => h("label", {}, h("input", { type: "checkbox", checked: true, "data-fmt": f }), f));
  const bar = h("div", { id: "render-bar", style: { display: "none" } }, h("div", { class: "bar", style: { margin: "8px 0 4px" } }, h("i", { id: "render-fill", style: { width: "0%" } })), h("div", { class: "small muted", id: "render-msg" }));
  const renderBtn = h("button", { class: "btn primary", id: "render-btn", onclick: async () => {
    try { await post(`/projects/${st.id}/render`, { quality: quality.value, formats: fchecks.map((l) => l.firstChild).filter((c) => c.checked).map((c) => c.dataset.fmt) });
      bar.style.display = ""; renderBtn.disabled = true; openProject(st.id); } catch (e) { toast(e.message, true); } } }, "Renderizza i reel selezionati");
  const outputs = h("div", { id: "outputs" });
  const n = plan.reels.length;
  root.append(...[
    h("div", { class: "row", style: { justifyContent: "space-between" } }, h("div", {}, h("h1", {}, plan.mode === "script_assembly" ? "Montaggio dallo script" : `${n} ${n === 1 ? "reel estratto" : "reel estratti"}`),
      h("div", { class: "muted" }, "Controlla i tagli prima del rendering: anteprima istantanea sul video originale, nessun rendering necessario.")),
      h("button", { class: "btn", onclick: viewNew }, "Nuovo progetto")),
    plan.diagnostics.warning ? h("p", { class: "warn" }, plan.diagnostics.warning) : null,
    plan.mode === "script_assembly" ? scriptReport(st, plan) : null].filter(Boolean));
  plan.reels.forEach((r) => root.append(reelCard(st.id, plan, r)));
  root.append(h("h2", {}, h("span", { class: "step" }, "✓"), "Rendering ed esportazione"),
    h("div", { class: "card" }, h("div", { class: "row" }, ...fchecks, quality, renderBtn), bar), outputs);
  app.replaceChildren(root);
  paintOutputs(st);
  if (rendering || st.status === "rendering") { bar.style.display = ""; renderBtn.disabled = true; updateRender(st); }
}
function updateRender(st) {
  const bar = $("#render-bar"); if (!bar) return;
  bar.style.display = ""; $("#render-fill").style.width = Math.round(st.render.progress * 100) + "%";
  $("#render-msg").textContent = st.render.state === "running" ? `Rendering ${st.render.current || ""} · ${Math.round(st.render.progress * 100)}%` : st.render.state === "done" ? "Rendering completato" : "";
  $("#render-btn").disabled = st.render.state === "running";
  if (st.error && st.render.state === "error") toast(st.error, true);
  paintOutputs(st);
}
function paintOutputs(st) {
  const box = $("#outputs"); if (!box) return;
  box.replaceChildren(...st.outputs.map((o) => h("div", { class: "card out", style: { marginTop: "10px" } },
    h("video", { src: `/api/projects/${st.id}/files/${o.file}`, controls: true, preload: "metadata" }),
    h("div", {}, h("b", {}, `${o.reel_id} · ${o.format_id}`), " ", h("span", { class: "chip" }, o.quality === "draft" ? "bozza" : "finale"), " ", h("span", { class: "muted small" }, `${o.duration.toFixed(1)} s · ${(o.size / 1048576).toFixed(1)} MB`),
      h("div", { style: { margin: "8px 0" } }, h("a", { class: "btn primary sm", href: `/api/projects/${st.id}/files/${o.file}`, download: o.file }, "Scarica MP4"), " ",
        h("button", { class: "btn sm", onclick: () => navigator.clipboard.writeText(o.caption + "\n\n" + o.hashtags.join(" ")).then(() => toast("Caption copiata")) }, "Copia caption + hashtag")),
      h("details", {}, h("summary", {}, "Caption, hashtag e trascrizione"), h("p", { style: { whiteSpace: "pre-wrap" } }, o.caption), h("p", { class: "chips" }, o.hashtags.map((x) => h("span", { class: "chip" }, x))), h("p", { class: "muted small" }, o.transcript))))));
}

/* — report script (modalità A) — */
function scriptReport(st, plan) {
  const cls = { matched: "b-ok", weak: "b-warn", missing: "b-bad" }, lab = { matched: "trovata", weak: "debole", missing: "mancante" };
  return h("div", { class: "card", style: { marginTop: "14px" } }, h("b", {}, "Allineamento script ↔ clip"),
    h("div", { class: "muted small" }, "Per ogni frase l'agente ha scelto la take più completa e pulita. Puoi cambiarla."),
    ...plan.script_report.map((u) => {
      const sel = h("select", { onchange: async (e) => { try { const p = await post(`/projects/${st.id}/edit`, { reel_id: plan.reels[0].id, ops: [{ op: "swap_take", unit: u.unit, take_id: e.target.value }] }); S.plan = p; toast("Take cambiata"); viewReview(await api("/projects/" + st.id), false); } catch (er) { toast(er.message, true); } } },
        u.chosen_take ? h("option", { value: u.chosen_take, selected: true }, `${u.chosen_take} (${Math.round(u.similarity * 100)}%)`) : h("option", {}, "—"),
        ...u.alternatives.map((a) => h("option", { value: a.take_id }, `${a.take_id} (${Math.round(a.similarity * 100)}%)`)));
      return h("div", { class: "unit" }, h("span", { class: "muted" }, u.unit + 1), h("span", {}, u.text), h("span", { class: "badge " + cls[u.status] }, lab[u.status]), sel);
    }));
}

/* — card di un reel — */
const SRC_PEAKS = {};
async function peaks(pid, sid) { return (SRC_PEAKS[pid + sid] ||= (await api(`/projects/${pid}/waveform/${sid}`)).peaks); }

function reelCard(pid, plan, reel) {
  const card = h("div", { class: "card reel", "data-reel": reel.id });
  const srcs = Object.fromEntries(plan.sources.map((s) => [s.id, s]));
  let fmt = plan.exports[0].format_id;
  const send = async (ops) => {
    try { const p = await post(`/projects/${pid}/edit`, { reel_id: reel.id, ops }); S.plan = p; const nr = p.reels.find((x) => x.id === reel.id); pv.stop(); card.replaceWith(reelCard(pid, p, nr)); }
    catch (e) { toast(e.message, true); }
  };
  const v = reel.virality;
  const head = h("div", { class: "reel-head" },
    v ? h("div", {}, h("div", { class: "score", style: { color: v.score >= 80 ? "var(--ok)" : v.score >= 60 ? "var(--warn)" : "var(--muted)" } }, v.score), h("div", { class: "small muted" }, "virality")) : h("div", { class: "score muted" }, "▶"),
    h("div", { style: { flex: 1 } }, h("b", {}, `${reel.id} — ${reel.title}`), h("div", { class: "small muted" }, `${reel.duration.toFixed(1)} s · ${reel.timeline.length} segmenti · ${reel.sfx.length} SFX`),
      v ? h("ul", { style: { margin: "6px 0 0", paddingLeft: "18px" } }, v.reasons.map((r) => h("li", { class: "small" }, r))) : null),
    h("label", { class: "row" }, h("input", { type: "checkbox", checked: reel.selected, onchange: (e) => send([{ op: "toggle_reel", selected: e.target.checked }]) }), "Includi nel render"));
  /* player + overlay */
  const player = h("div", { class: "player" }), cropBox = h("div", { class: "crop", style: { display: "none" } }), subs = h("div", { class: "subs" });
  const vids = {};
  [...new Set(reel.timeline.map((s) => s.source_id))].forEach((sid) => { vids[sid] = h("video", { src: `/api/projects/${pid}/media/${sid}`, preload: "metadata", playsInline: true, controls: false }); player.append(vids[sid]); });
  player.append(cropBox, subs);
  const tabs = h("div", { class: "tabs" }), fnote = h("div", { class: "small muted", style: { marginTop: "6px" } });
  const chunks = chunkWords(reel.words);
  const pv = previewer(reel, srcs, vids, () => fmt, cropBox, subs, chunks, player);
  const paintTabs = () => { tabs.replaceChildren(...plan.exports.map((e) => h("button", { class: "tab" + (fmt === e.format_id ? " on" : ""), onclick: () => { fmt = e.format_id; paintTabs(); } }, e.format_id)));
    const fr = reel.framing.find((f) => f.format_id === fmt); fnote.textContent = fr ? `${{ smart_crop: "Crop sul parlante", blur_pad: "Sfondo sfocato", none: "Nessun reframing" }[fr.strategy]} — ${fr.reason}` : ""; };
  paintTabs();
  const playBtn = h("button", { class: "btn sm", onclick: () => pv.play(0) }, "▶ Anteprima tagli"), stopBtn = h("button", { class: "btn sm", onclick: () => pv.stop() }, "■");
  const left = h("div", {}, player, h("div", { class: "row", style: { marginTop: "8px" } }, playBtn, stopBtn), tabs, fnote);
  /* timeline */
  const cv = h("canvas", { class: "tl" });
  const legend = h("div", { class: "legend" }, h("span", {}, h("i", { style: { background: "var(--accent)" } }), "audio tenuto"), h("span", {}, h("i", { style: { background: "var(--ok)" } }), "taglio sicuro"), h("span", {}, h("i", { style: { background: "var(--warn)" } }), "taglio incerto (parlato continuo)"), h("span", {}, "− = secondi rimossi"));
  const table = segTable(reel, send, pv);
  /* stile */
  const st = reel.subtitles;
  const preset = h("select", { onchange: (e) => send([{ op: "set_style", preset: e.target.value }]) }, ...["hormozi", "mrbeast", "clean", "karaoke"].map((p) => h("option", { value: p, selected: st.preset === p }, p)));
  const style = h("div", { class: "row" }, h("label", { class: "f" }, "Sottotitoli", preset),
    h("label", {}, h("input", { type: "checkbox", checked: st.uppercase, onchange: (e) => send([{ op: "set_style", uppercase: e.target.checked }]) }), "MAIUSCOLO"),
    h("label", {}, h("input", { type: "checkbox", checked: st.emoji, onchange: (e) => send([{ op: "set_style", emoji: e.target.checked }]) }), "Emoji"),
    h("label", {}, h("input", { type: "checkbox", checked: reel.sfx.length > 0, onchange: (e) => send([{ op: "set_sfx", enabled: e.target.checked }]) }), "SFX"),
    h("label", {}, h("input", { type: "checkbox", checked: reel.zooms.length > 0, onchange: (e) => send([{ op: "set_zoom", enabled: e.target.checked }]) }), "Zoom"),
    h("label", { class: "f" }, "Posizione verticale", h("input", { type: "range", min: 0.3, max: 0.85, step: 0.01, value: st.position_y, onchange: (e) => send([{ op: "set_style", position_y: +e.target.value }]) })));
  /* social */
  const title = h("input", { type: "text", value: reel.social.title, onchange: (e) => send([{ op: "set_social", title: e.target.value }]) });
  const caption = h("textarea", { onchange: (e) => send([{ op: "set_social", caption: e.target.value }]) }); caption.value = reel.social.caption;
  const tags = h("input", { type: "text", value: reel.social.hashtags.join(" "), onchange: (e) => send([{ op: "set_social", hashtags: e.target.value.split(/\s+/).filter(Boolean) }]) });
  const right = h("div", {}, cv, legend, table, h("div", { style: { marginTop: "12px" } }, style),
    h("details", {}, h("summary", {}, "Caption e hashtag"), h("label", { class: "f" }, "Titolo", title), h("label", { class: "f" }, "Caption", caption), h("label", { class: "f" }, "Hashtag", tags),
      h("p", { class: "small muted" }, reel.transcript)),
    reel.warnings.length ? h("p", { class: "warn" }, reel.warnings.join(" · ")) : null);
  card.append(head, h("div", { class: "reel-body" }, left, right));
  requestAnimationFrame(() => drawTimeline(cv, pid, reel, pv));
  new ResizeObserver(() => drawTimeline(cv, pid, reel, pv)).observe(cv);
  return card;
}

function chunkWords(words, maxW = 3) {
  const chunks = []; let cur = [];
  words.forEach((w, i) => { cur.push(i); if (cur.length >= maxW || /[.!?,;:…]$/.test(w.text)) { chunks.push(cur); cur = []; } });
  if (cur.length) chunks.push(cur);
  const of = {}; chunks.forEach((c, ci) => c.forEach((i) => (of[i] = ci)));
  return { chunks, of };
}

function previewer(reel, srcs, vids, getFmt, cropBox, subs, ck, player) {
  let idx = 0, playing = false, raf = 0, active = null;
  const segs = reel.timeline;
  const show = (sid) => { Object.entries(vids).forEach(([k, el]) => el.classList.toggle("act", k === sid)); active = vids[sid]; };
  show(segs[0].source_id);
  Object.entries(vids).forEach(([sid, el]) => {                // a riposo: primo frame del reel + riquadro di crop già visibile
    el.addEventListener("loadedmetadata", () => { if (!playing && sid === segs[0].source_id) el.currentTime = segs[0].src_start; });
    el.addEventListener("seeked", () => { if (!playing && el === active) overlay(segs[Math.min(idx, segs.length - 1)], el.currentTime); });
  });
  const loop = () => {
    if (!playing) return;
    const s = segs[idx], t = active.currentTime;
    if (t >= s.src_end - 0.012) {                 // fine segmento → salta al prossimo (o ferma)
      idx++;
      if (idx >= segs.length) return stop();
      const n = segs[idx];
      if (n.source_id !== s.source_id) { active.pause(); show(n.source_id); }
      active.currentTime = n.src_start; active.play();
    }
    overlay(segs[idx], active.currentTime);
    raf = requestAnimationFrame(loop);
  };
  function overlay(s, t) {
    const fr = reel.framing.find((f) => f.format_id === getFmt()), src = srcs[s.source_id];
    if (fr && fr.strategy === "smart_crop" && fr.crop_keyframes[s.id]) {
      const kf = fr.crop_keyframes[s.id], tr = t - s.src_start; let a = kf[0], b = kf[kf.length - 1];
      for (let i = 0; i < kf.length - 1; i++) if (tr >= kf[i].t && tr <= kf[i + 1].t) { a = kf[i]; b = kf[i + 1]; break; }
      const k = b.t > a.t ? Math.min(1, Math.max(0, (tr - a.t) / (b.t - a.t))) : 0, x = a.x + (b.x - a.x) * k, y = a.y + (b.y - a.y) * k;
      Object.assign(cropBox.style, { display: "block", left: (x / src.width) * 100 + "%", top: (y / src.height) * 100 + "%", width: (a.w / src.width) * 100 + "%", height: (a.h / src.height) * 100 + "%" });
    } else cropBox.style.display = "none";
    const ot = s.out_start + (t - s.src_start);
    const wi = reel.words.findIndex((w) => ot >= w.out_start && ot < w.out_end + 0.1);
    if (wi < 0) return (subs.textContent = "");
    subs.replaceChildren(...ck.chunks[ck.of[wi]].map((i) => h("span", { class: i === wi ? "hl" : "" }, reel.words[i].text + " ")));
  }
  function play(i) { idx = i; const s = segs[i]; show(s.source_id); active.currentTime = s.src_start; active.play(); playing = true; cancelAnimationFrame(raf); raf = requestAnimationFrame(loop); }
  function stop() { playing = false; cancelAnimationFrame(raf); Object.values(vids).forEach((v) => v.pause()); }
  return { play, stop, segs };
}

function segTable(reel, send, pv) {
  const conf = (c) => h("span", { class: "badge " + (c.confidence >= 0.7 ? "b-ok" : c.confidence >= 0.4 ? "b-warn" : "b-bad"), title: `metodo: ${c.method}\nsilenzio: ${c.silence ? c.silence.map((x) => x.toFixed(2)).join("–") + " s" : "—"}\nsecondi ASR: ${c.asr_time.toFixed(3)} → taglio: ${c.time.toFixed(3)} (frame ${c.frame})` }, `${Math.round(c.confidence * 100)}%`);
  const why = { pause: "pausa tolta", drop: "ripetizione tolta", filler: "intercalare tolto", take_change: "cambio frase/take" };
  const rows = reel.timeline.map((s, i) => {
    const nb = (edge, f) => h("button", { class: "btn sm", title: `${edge === "in" ? "Inizio" : "Fine"} ${f > 0 ? "+" : ""}${f} frame (solo attraverso il silenzio)`, onclick: () => send([{ op: "nudge", segment_id: s.id, edge, frames: f }]) }, (f > 0 ? "+" : "−") + Math.abs(f));
    return h("tr", {}, h("td", {}, i + 1), h("td", {}, fmtT(s.out_start)), h("td", {}, `${s.source_id} ${s.src_start.toFixed(2)}–${s.src_end.toFixed(2)}`), h("td", {}, (s.out_end - s.out_start).toFixed(2) + " s"),
      h("td", {}, i ? why[s.removed_before] || "—" : "inizio"), h("td", {}, conf(s.cut_in), " ", h("span", { class: "muted", title: "Differenza rispetto al timestamp ASR: un taglio ingenuo cadrebbe qui" }, ms(s.cut_in.asr_time - s.cut_in.time))),
      h("td", {}, conf(s.cut_out), " ", h("span", { class: "muted" }, ms(s.cut_out.asr_time - s.cut_out.time))),
      h("td", {}, h("div", { class: "seg-actions" }, h("button", { class: "btn sm", onclick: () => pv.play(i), title: "Riproduci da qui" }, "▶"), "in:", nb("in", -1), nb("in", 1), "out:", nb("out", -1), nb("out", 1),
        h("button", { class: "btn sm", title: "Rimuovi segmento", onclick: () => send([{ op: "remove_segment", segment_id: s.id }]) }, "✕"))));
  });
  return h("details", { open: true }, h("summary", {}, `Segmenti e punti di taglio (${reel.timeline.length})`),
    h("div", { style: { overflowX: "auto" } }, h("table", {}, h("thead", {}, h("tr", {}, ["#", "out", "sorgente", "durata", "prima del taglio", "taglio IN", "taglio OUT", "azioni"].map((x) => h("th", {}, x)))), h("tbody", {}, rows))));
}

async function drawTimeline(cv, pid, reel, pv) {
  const dpr = window.devicePixelRatio || 1, W = (cv.width = Math.max(300, cv.clientWidth) * dpr), H = (cv.height = 78 * dpr), g = cv.getContext("2d");
  const css = getComputedStyle(document.documentElement), acc = css.getPropertyValue("--accent").trim(), ok = css.getPropertyValue("--ok").trim(), warn = css.getPropertyValue("--warn").trim(), mut = css.getPropertyValue("--muted").trim();
  g.clearRect(0, 0, W, H);
  const dur = reel.duration, X = (t) => (t / dur) * W;
  const data = {}; for (const sid of new Set(reel.timeline.map((s) => s.source_id))) { try { data[sid] = await peaks(pid, sid); } catch { data[sid] = []; } }
  const total = {}; reel.timeline.forEach((s) => (total[s.source_id] = Math.max(total[s.source_id] || 0, s.src_end)));
  reel.timeline.forEach((s) => {
    const pk = data[s.source_id] || []; if (!pk.length) return;
    const srcDur = S.plan.sources.find((x) => x.id === s.source_id).duration;
    const a = Math.floor((s.src_start / srcDur) * pk.length), b = Math.ceil((s.src_end / srcDur) * pk.length);
    g.fillStyle = acc;
    const x0 = X(s.out_start), x1 = X(s.out_end), n = Math.max(1, Math.floor((x1 - x0) / (2 * dpr)));
    for (let i = 0; i < n; i++) { const p = Math.max(...pk.slice(a + Math.floor((i / n) * (b - a)), a + Math.floor(((i + 1) / n) * (b - a)) + 1), 0.02); const hh = p * (H * 0.62); g.fillRect(x0 + i * 2 * dpr, H * 0.45 - hh / 2, 1.4 * dpr, hh); }
  });
  reel.timeline.forEach((s, i) => {
    if (!i) return;
    const c = s.cut_in, x = X(s.out_start); g.fillStyle = c.confidence >= 0.7 ? ok : warn; g.fillRect(x - dpr, 0, 2 * dpr, H * 0.9);
    const prev = reel.timeline[i - 1], removed = s.src_start - prev.src_end;
    if (prev.source_id === s.source_id && removed > 0.05) { g.fillStyle = mut; g.font = `${10 * dpr}px sans-serif`; g.fillText("−" + removed.toFixed(1), x + 3 * dpr, 11 * dpr); }
  });
  g.fillStyle = mut; g.font = `${10 * dpr}px sans-serif`; g.fillText("0:00", 3 * dpr, H - 4 * dpr); g.fillText(fmtT(dur), W - 40 * dpr, H - 4 * dpr);
  cv.onclick = (e) => { const t = ((e.offsetX / cv.clientWidth) * dur); const i = reel.timeline.findIndex((s) => t >= s.out_start && t < s.out_end); pv.play(Math.max(0, i)); };
}

/* ───────────── Nav / dialoghi / bootstrap ───────────── */
$("#nav-new").onclick = viewNew;
async function dialog(title, fn) { $("#dlg-title").textContent = title; $("#dlg-body").textContent = "…"; $("#dlg").showModal(); try { $("#dlg-body").textContent = await fn(); } catch (e) { $("#dlg-body").textContent = e.message; } }
$("#nav-schema").onclick = () => dialog("Universal Edit Plan — JSON Schema", async () => JSON.stringify(await api("/schema"), null, 2));
$("#nav-prompt").onclick = () => dialog("System prompt dell'agente", async () => (await api("/system-prompt")).markdown);
$("#dlg-close").onclick = () => $("#dlg").close();
if (location.hash.length > 5) openProject(location.hash.slice(1)); else viewNew();
