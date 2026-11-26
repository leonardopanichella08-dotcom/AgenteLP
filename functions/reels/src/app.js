import { upload } from '@vercel/blob/client';
import { downloadZip } from 'client-zip';
import { CATEGORIES, DISCARD, TREATMENTS } from './treatments.js';

// ---------- utilità ----------
const $ = (sel) => document.querySelector(sel);
const el = (tag, props = {}, ...children) => {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(props)) {
    if (k === 'class') node.className = v;
    else if (k === 'text') node.textContent = v;
    else if (k.startsWith('on')) node.addEventListener(k.slice(2), v);
    else if (v !== undefined && v !== null && v !== false) node.setAttribute(k, v === true ? '' : v);
  }
  for (const c of children) if (c) node.append(c);
  return node;
};
const store = {
  get(k) { try { return localStorage.getItem(k); } catch { return null; } },
  set(k, v) { try { localStorage.setItem(k, v); } catch { /* ignora */ } },
};
const fmtSize = (b) => (b > 1e9 ? `${(b / 1e9).toFixed(2)} GB` : b > 1e6 ? `${(b / 1e6).toFixed(1)} MB` : `${Math.ceil(b / 1e3)} KB`);
let toastTimer;
function toast(msg, ms = 3000) {
  const t = $('#toast');
  t.textContent = msg;
  t.hidden = false;
  clearTimeout(toastTimer);
  if (ms) toastTimer = setTimeout(() => (t.hidden = true), ms);
}

// ---------- API ----------
async function api(path, body) {
  const res = await fetch(path, {
    method: body ? 'POST' : 'GET',
    headers: body ? { 'content-type': 'application/json' } : {},
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) throw new Error((await res.json().catch(() => ({}))).error || `Errore ${res.status}`);
  return res.json();
}

// ---------- stato ----------
let items = [];
const byId = new Map();
const treatmentLabel = (id) => (id === DISCARD.id ? DISCARD.label : TREATMENTS.get(id)?.label || '');
const treatmentFull = (id) => {
  const t = TREATMENTS.get(id);
  return !t ? '' : t.category ? `${t.category} · ${t.label}` : t.label;
};

// Aggiorna la lista mantenendo gli stessi oggetti (il feed aperto continua a puntarli).
async function loadItems() {
  const data = await api('/api/items');
  const fresh = new Set();
  const next = [];
  for (const it of data.items) {
    fresh.add(it.id);
    const cur = byId.get(it.id);
    if (cur) { if (!cur.saving) cur.treatment = it.treatment; next.push(cur); }
    else { byId.set(it.id, it); next.push(it); }
  }
  for (const id of [...byId.keys()]) if (!fresh.has(id)) byId.delete(id);
  items = next;
  updateBadge();
}
function updateBadge() {
  const todo = items.filter((i) => !i.treatment).length;
  $('#todo-badge').textContent = todo ? String(todo) : '';
  if (currentTab === 'tag') buildFilterOptions();
  renderProgress();
}

// Avanzamento visibile a tutti, su ogni scheda.
function renderProgress() {
  const total = items.length;
  const done = items.filter((i) => i.treatment).length;
  const discarded = items.filter((i) => i.treatment === DISCARD.id).length;
  const vids = items.filter((i) => i.kind === 'video');
  const pics = items.filter((i) => i.kind !== 'video');
  const pct = total ? Math.round((done / total) * 100) : 0;
  $('#progress-text').textContent = total
    ? `Smistati ${done} su ${total} (${pct}%)`
    : 'Nessun file caricato';
  const det = [];
  if (vids.length) det.push(`video ${vids.filter((i) => i.treatment).length}/${vids.length}`);
  if (pics.length) det.push(`foto ${pics.filter((i) => i.treatment).length}/${pics.length}`);
  if (discarded) det.push(`${discarded} scartati`);
  $('#progress-detail').textContent = det.join(' · ');
  $('#progress-fill').style.width = `${pct}%`;
}

// Ricarica ogni 30 s per vedere il lavoro degli altri.
setInterval(() => {
  if (document.visibilityState === 'visible') loadItems().catch(() => {});
}, 30_000);

// ---------- tabs ----------
let currentTab = null;
function showTab(name) {
  currentTab = name;
  for (const b of document.querySelectorAll('.tabs button')) b.classList.toggle('active', b.dataset.tab === name);
  for (const v of document.querySelectorAll('.view')) v.classList.toggle('active', v.id === `view-${name}`);
  if (name !== 'tag') pauseAll();
  if (name === 'tag') buildFeed();
  if (name === 'folders') renderFolders();
  if (name === 'upload') renderUploadSummary();
  store.set('reels-tab', name);
}
for (const b of document.querySelectorAll('.tabs button')) {
  b.addEventListener('click', async () => {
    if (b.dataset.tab !== 'upload') await loadItems().catch((e) => toast(e.message));
    showTab(b.dataset.tab);
  });
}

// ---------- CARICA ----------
const queue = [];
let running = 0;
const CONCURRENCY = 3;

function isMedia(file) {
  return /^(image|video)\//.test(file.type) || /\.(heic|heif|mov|mp4|m4v|jpe?g|png|webp|gif|avi|mkv|3gp)$/i.test(file.name);
}
function safeName(name) {
  const base = name.split(/[\\/]/).pop();
  return base.replace(/[^\w.\- ()À-ÿ]/g, '_').replace(/\s+/g, ' ').slice(-150) || 'file';
}
function newId() {
  const rnd = Array.from(crypto.getRandomValues(new Uint8Array(8)), (b) => (b % 36).toString(36)).join('');
  return `${Date.now().toString(36)}-${rnd}`;
}

function enqueue(fileList) {
  const files = [...fileList].filter(isMedia);
  const skipped = fileList.length - files.length;
  if (skipped) toast(`${skipped} file ignorati (non sono foto o video)`);
  for (const file of files) {
    const bar = el('i');
    const state = el('span', { class: 'state', text: 'in coda' });
    const li = el('li', {}, el('span', { class: 'name', text: `${file.name} · ${fmtSize(file.size)}` }), state, el('div', { class: 'bar' }, bar));
    $('#queue').prepend(li);
    queue.push({ file, bar, state });
  }
  pump();
}

function pump() {
  while (running < CONCURRENCY && queue.length) {
    const job = queue.shift();
    running++;
    uploadOne(job).finally(() => { running--; pump(); renderUploadSummary(); });
  }
  renderUploadSummary();
}

async function uploadOne({ file, bar, state }) {
  state.textContent = 'caricamento…';
  const pathname = `media/${newId()}/${safeName(file.name)}`;
  for (let attempt = 1; attempt <= 3; attempt++) {
    try {
      await upload(pathname, file, {
        access: 'public',
        handleUploadUrl: '/api/upload',
        contentType: file.type || undefined,
        multipart: file.size > 30 * 1024 * 1024,
        onUploadProgress: ({ percentage }) => {
          bar.style.width = `${percentage}%`;
          state.textContent = `${Math.round(percentage)}%`;
        },
      });
      bar.style.width = '100%';
      state.textContent = 'caricato ✓';
      state.className = 'state ok';
      uploadedCount++;
      return;
    } catch (err) {
      if (attempt === 3) {
        state.textContent = `errore: ${err.message}`;
        state.className = 'state err';
        failedCount++;
      } else {
        state.textContent = `riprovo (${attempt + 1}/3)…`;
      }
    }
  }
}
let uploadedCount = 0;
let failedCount = 0;
function renderUploadSummary() {
  const pending = queue.length + running;
  const parts = [];
  if (pending) parts.push(`${pending} in caricamento`);
  if (uploadedCount) parts.push(`${uploadedCount} caricati in questa sessione`);
  if (failedCount) parts.push(`${failedCount} non riusciti`);
  $('#upload-summary').textContent = parts.join(' · ');
}

const drop = $('#drop');
$('#file-input').addEventListener('change', (e) => { enqueue(e.target.files); e.target.value = ''; });
$('#folder-input').addEventListener('change', (e) => { enqueue(e.target.files); e.target.value = ''; });
$('#pick-files').addEventListener('click', () => $('#file-input').click());
$('#pick-folder').addEventListener('click', () => $('#folder-input').click());
drop.addEventListener('dragover', (e) => { e.preventDefault(); drop.classList.add('over'); });
drop.addEventListener('dragleave', () => drop.classList.remove('over'));
drop.addEventListener('drop', async (e) => {
  e.preventDefault();
  drop.classList.remove('over');
  const entries = [...e.dataTransfer.items].map((i) => i.webkitGetAsEntry?.()).filter(Boolean);
  if (!entries.length) return enqueue(e.dataTransfer.files);
  const files = [];
  const walk = async (entry) => {
    if (entry.isFile) files.push(await new Promise((res, rej) => entry.file(res, rej)));
    else if (entry.isDirectory) {
      const reader = entry.createReader();
      for (;;) {
        const batch = await new Promise((res, rej) => reader.readEntries(res, rej));
        if (!batch.length) break;
        for (const child of batch) await walk(child);
      }
    }
  };
  for (const entry of entries) await walk(entry);
  enqueue(files);
});
window.addEventListener('beforeunload', (e) => {
  if (queue.length + running) { e.preventDefault(); e.returnValue = ''; }
});

// ---------- CLASSIFICA (reels) ----------
const feed = $('#feed');
let feedItems = [];
let activeIndex = -1;
let soundOn = false;
let filter = 'todo';
let pendingStartId = null;
let activeCat = CATEGORIES[0].id;

function buildFilterOptions() {
  const sel = $('#filter');
  const count = (fn) => items.filter(fn).length;
  sel.replaceChildren(
    el('option', { value: 'todo', text: `Da classificare (${count((i) => !i.treatment)})` }),
    el('option', { value: 'all', text: `Tutti (${items.length})` }),
    el('option', { value: 'done', text: `Già classificati (${count((i) => i.treatment)})` }),
  );
  for (const c of CATEGORIES) {
    const g = el('optgroup', { label: c.label });
    for (const [id, label] of c.items) {
      const n = count((i) => i.treatment === id);
      if (n) g.append(el('option', { value: `t:${id}`, text: `${label} (${n})` }));
    }
    if (g.children.length) sel.append(g);
  }
  const nd = count((i) => i.treatment === DISCARD.id);
  if (nd) sel.append(el('option', { value: `t:${DISCARD.id}`, text: `${DISCARD.label} (${nd})` }));
  if (![...sel.options].some((o) => o.value === filter)) filter = 'todo';
  sel.value = filter;
}
$('#filter').addEventListener('change', (e) => { filter = e.target.value; buildFeed(); });

function matches(it) {
  if (filter === 'todo') return !it.treatment;
  if (filter === 'done') return !!it.treatment;
  if (filter.startsWith('t:')) return it.treatment === filter.slice(2);
  return true;
}

let observer;
function buildFeed() {
  buildFilterOptions();
  pauseAll();
  feedItems = items.filter(matches);
  observer?.disconnect();
  feed.replaceChildren();
  activeIndex = -1;
  const empty = $('#feed-empty');
  if (!feedItems.length) {
    empty.hidden = false;
    empty.textContent = items.length
      ? (filter === 'todo' ? 'Tutto classificato 🎉  Puoi ricontrollare scegliendo un altro filtro in alto, o scaricare da "Cartelle".' : 'Nessun elemento con questo filtro.')
      : 'Nessun file ancora. Caricali dalla scheda "Carica".';
    renderPicker();
    $('#feed-pos').textContent = '';
    return;
  }
  empty.hidden = true;
  observer = new IntersectionObserver((entries) => {
    for (const e of entries) if (e.isIntersecting) setActive(Number(e.target.dataset.index));
  }, { root: feed, threshold: 0.6 });
  feedItems.forEach((it, i) => {
    const slide = el('div', { class: 'slide', 'data-index': i });
    observer.observe(slide);
    feed.append(slide);
  });
  let start = 0;
  if (pendingStartId) {
    start = Math.max(0, feedItems.findIndex((i) => i.id === pendingStartId));
    pendingStartId = null;
  }
  feed.scrollTop = 0;
  if (start) feed.scrollTop = feed.children[start].offsetTop;
  setActive(start);
}

function mountSlide(i) {
  const slide = feed.children[i];
  if (!slide || slide.dataset.mounted) return;
  slide.dataset.mounted = '1';
  const it = feedItems[i];
  let media;
  if (it.kind === 'video') {
    media = el('video', { src: it.url, loop: true, playsinline: true, preload: 'auto', muted: !soundOn });
    media.muted = !soundOn;
    media.addEventListener('click', () => {
      if (media.paused) { media.play().catch(() => {}); return; }
      soundOn = !soundOn;
      for (const v of feed.querySelectorAll('video')) v.muted = !soundOn;
      updateSoundButtons();
    });
  } else {
    media = el('img', { src: it.url, alt: it.name, decoding: 'async' });
  }
  const meta = el('div', { class: 'meta' });
  slide.append(media, meta);
  if (it.kind === 'video') {
    slide.append(el('button', { class: 'sound', onclick: (e) => { e.stopPropagation(); media.click(); } }));
  }
  renderSlideMeta(i);
  updateSoundButtons();
}
function unmountSlide(i) {
  const slide = feed.children[i];
  if (!slide || !slide.dataset.mounted) return;
  const v = slide.querySelector('video');
  if (v) { v.pause(); v.removeAttribute('src'); v.load(); }
  slide.replaceChildren();
  delete slide.dataset.mounted;
}
function renderSlideMeta(i) {
  const slide = feed.children[i];
  const meta = slide?.querySelector('.meta');
  if (!meta) return;
  const it = feedItems[i];
  meta.replaceChildren();
  if (it.treatment) {
    meta.append(el('span', { class: `tagpill${it.treatment === DISCARD.id ? ' discard' : ''}`, text: `✓ ${treatmentFull(it.treatment)}` }));
  }
  meta.append(el('span', { class: 'fname', text: it.name }));
}
function updateSoundButtons() {
  for (const b of feed.querySelectorAll('.sound')) b.textContent = soundOn ? '🔊 audio' : '🔇 tocca per audio';
}
function pauseAll() {
  for (const v of feed.querySelectorAll('video')) v.pause();
}

function setActive(i) {
  if (i === activeIndex || i < 0 || i >= feedItems.length) return;
  activeIndex = i;
  for (let k = 0; k < feedItems.length; k++) {
    if (Math.abs(k - i) <= 2) mountSlide(k);
    else unmountSlide(k);
  }
  feed.querySelectorAll('video').forEach((v) => {
    const own = Number(v.closest('.slide').dataset.index) === i;
    if (own) { v.currentTime = 0; v.play().catch(() => {}); } else v.pause();
  });
  $('#feed-pos').textContent = `${i + 1} / ${feedItems.length}`;
  const t = feedItems[i].treatment && TREATMENTS.get(feedItems[i].treatment);
  if (t && t.category) activeCat = CATEGORIES.find((c) => c.label === t.category).id;
  renderPicker();
}

function renderPicker() {
  const it = feedItems[activeIndex];
  $('#current-label').textContent = it
    ? (it.treatment ? `Attuale: ${treatmentFull(it.treatment)}` : 'Non ancora classificato')
    : '';
  $('#cat-tabs').replaceChildren(...CATEGORIES.map((c) => el('button', {
    class: c.id === activeCat ? 'active' : '',
    text: c.label,
    onclick: () => { activeCat = c.id; renderPicker(); },
  })));
  const cat = CATEGORIES.find((c) => c.id === activeCat);
  $('#chips').replaceChildren(...cat.items.map(([id, label]) => el('button', {
    class: `chip${it?.treatment === id ? ' selected' : ''}`,
    text: label,
    disabled: !it,
    onclick: () => choose(id),
  })));
  const d = $('#discard-btn');
  d.classList.toggle('selected', it?.treatment === DISCARD.id);
  d.disabled = !it;
  $('#skip-btn').disabled = !it;
}
$('#discard-btn').addEventListener('click', () => choose(DISCARD.id));
$('#skip-btn').addEventListener('click', () => goTo(activeIndex + 1));

function goTo(i) {
  const slide = feed.children[i];
  if (slide) feed.scrollTo({ top: slide.offsetTop, behavior: 'smooth' });
  else toast('Fine della lista');
}

async function choose(treatment) {
  const i = activeIndex;
  const it = feedItems[i];
  if (!it) return;
  const prev = it.treatment;
  const next = prev === treatment ? null : treatment; // ritoccare lo stesso = togli
  it.treatment = next;
  renderSlideMeta(i);
  renderPicker();
  updateBadge();
  if (next) setTimeout(() => goTo(i + 1), 250);
  it.saving = true;
  try {
    await api('/api/tag', { id: it.id, treatment: next });
    it.saving = false;
    renderProgress();
  } catch (err) {
    it.saving = false;
    it.treatment = prev;
    renderSlideMeta(i);
    if (activeIndex === i) renderPicker();
    updateBadge();
    toast(`Non salvato: ${err.message}`);
  }
}

document.addEventListener('keydown', (e) => {
  if (currentTab !== 'tag' || e.target.closest('input, select, textarea')) return;
  if (e.key === 'ArrowDown' || e.key === 'j') { e.preventDefault(); goTo(activeIndex + 1); }
  if (e.key === 'ArrowUp' || e.key === 'k') { e.preventDefault(); goTo(activeIndex - 1); }
});

// ---------- CARTELLE ----------
function folderGroups() {
  const groups = [];
  for (const c of CATEGORIES) {
    for (const [id] of c.items) groups.push({ id, cat: c.label, t: TREATMENTS.get(id) });
  }
  groups.push({ id: DISCARD.id, cat: 'ALTRO', t: TREATMENTS.get(DISCARD.id) });
  return groups;
}

function renderFolders() {
  const root = $('#folders');
  root.replaceChildren();
  const done = items.filter((i) => i.treatment).length;
  $('#folders-summary').textContent = `${items.length} file · ${done} classificati · ${items.length - done} da classificare`;

  const todo = items.filter((i) => !i.treatment);
  if (todo.length) {
    root.append(el('div', { class: 'cat-title', text: 'DA CLASSIFICARE' }));
    root.append(folderBlock('Da classificare', null, todo));
  }
  let lastCat = null;
  for (const g of folderGroups()) {
    if (g.cat !== lastCat) { root.append(el('div', { class: 'cat-title', text: g.cat })); lastCat = g.cat; }
    root.append(folderBlock(g.t.label, g.id, items.filter((i) => i.treatment === g.id)));
  }
}

function folderBlock(title, treatmentId, list) {
  const size = list.reduce((s, i) => s + i.size, 0);
  const grid = el('div', { class: 'grid' });
  const summary = el('summary', {},
    el('span', { class: 'title', text: title }),
    el('span', { class: 'count', text: list.length ? `${list.length} file · ${fmtSize(size)}` : 'vuota' }),
  );
  if (list.length && treatmentId) {
    summary.append(
      el('button', { class: 'btn ghost small', text: 'Rivedi', onclick: (e) => { e.preventDefault(); openInFeed(`t:${treatmentId}`); } }),
      el('button', { class: 'btn small', text: 'Scarica ZIP', onclick: (e) => { e.preventDefault(); downloadFolder(treatmentId); } }),
    );
  }
  const details = el('details', { class: `folder${list.length ? '' : ' empty-folder'}` }, summary, grid);
  details.addEventListener('toggle', () => {
    if (details.open && !grid.children.length) grid.append(...list.map(card));
  });
  return details;
}

function card(it) {
  const thumb = it.kind === 'video'
    ? el('video', { class: 'thumb', src: `${it.url}#t=0.5`, preload: 'metadata', muted: true, playsinline: true })
    : el('img', { class: 'thumb', src: it.url, loading: 'lazy', alt: it.name });
  thumb.addEventListener('click', () => openInFeed(it.treatment ? `t:${it.treatment}` : 'todo', it.id));

  const sel = el('select', {}, el('option', { value: '', text: '— da classificare —' }));
  for (const c of CATEGORIES) {
    const g = el('optgroup', { label: c.label });
    for (const [id, label] of c.items) g.append(el('option', { value: id, text: label }));
    sel.append(g);
  }
  sel.append(el('option', { value: DISCARD.id, text: DISCARD.label }));
  sel.value = it.treatment || '';
  sel.addEventListener('change', async () => {
    const prev = it.treatment;
    it.treatment = sel.value || null;
    try {
      await api('/api/tag', { id: it.id, treatment: it.treatment });
      toast(it.treatment ? `Spostato in: ${treatmentLabel(it.treatment)}` : 'Tolto dalla cartella');
      updateBadge();
      renderFolders();
    } catch (err) {
      it.treatment = prev;
      sel.value = prev || '';
      toast(`Non salvato: ${err.message}`);
    }
  });

  const del = el('button', { class: 'del', text: 'Elimina', onclick: async () => {
    if (!confirm(`Eliminare definitivamente "${it.name}"?`)) return;
    try {
      await api('/api/delete', { id: it.id });
      items = items.filter((x) => x !== it);
      byId.delete(it.id);
      updateBadge();
      renderFolders();
    } catch (err) { toast(err.message); }
  } });

  return el('div', { class: 'card' }, thumb, el('div', { class: 'info' },
    el('span', { class: 'n', text: it.name, title: it.name }),
    sel,
    el('div', { class: 'acts' }, el('a', { href: it.downloadUrl, text: 'Scarica' }), del),
  ));
}

function openInFeed(f, startId) {
  filter = f;
  pendingStartId = startId || null;
  showTab('tag');
}

// ---------- download ZIP ----------
async function pickTarget(filename) {
  if (window.showSaveFilePicker) {
    try {
      const handle = await window.showSaveFilePicker({ suggestedName: filename, types: [{ description: 'Archivio ZIP', accept: { 'application/zip': ['.zip'] } }] });
      return { handle };
    } catch (err) {
      if (err.name === 'AbortError') return null;
    }
  }
  return { fallback: true };
}

async function buildZip(list, filename) {
  if (!list.length) return toast('Cartella vuota');
  const target = await pickTarget(filename); // da chiamare subito, durante il clic
  if (!target) return;
  let n = 0;
  const used = new Set();
  async function* entries() {
    for (const it of list) {
      const folder = TREATMENTS.get(it.treatment).folder;
      let name = `${folder}/${it.name}`;
      for (let k = 2; used.has(name.toLowerCase()); k++) name = `${folder}/${it.name.replace(/(\.[^.]*)?$/, ` (${k})$1`)}`;
      used.add(name.toLowerCase());
      n++;
      toast(`Preparo lo ZIP… ${n}/${list.length}`, 0);
      const res = await fetch(it.url);
      if (!res.ok) throw new Error(`Download fallito: ${it.name}`);
      yield { name, input: res, lastModified: new Date(it.uploadedAt) };
    }
  }
  try {
    const zip = downloadZip(entries());
    if (target.handle) {
      const writable = await target.handle.createWritable();
      await zip.body.pipeTo(writable);
    } else {
      const blob = await zip.blob();
      const a = el('a', { href: URL.createObjectURL(blob), download: filename });
      document.body.append(a);
      a.click();
      a.remove();
      setTimeout(() => URL.revokeObjectURL(a.href), 60_000);
    }
    toast(`ZIP pronto: ${list.length} file`);
  } catch (err) {
    toast(`Errore ZIP: ${err.message}`, 6000);
  }
}

function downloadFolder(treatmentId) {
  const t = TREATMENTS.get(treatmentId);
  buildZip(items.filter((i) => i.treatment === treatmentId), `${t.folder}.zip`);
}
$('#zip-all').addEventListener('click', () => {
  const list = items.filter((i) => i.treatment && i.treatment !== DISCARD.id);
  buildZip(list, 'Trattamenti.zip');
});

// ---------- avvio ----------
(async () => {
  try {
    await loadItems();
  } catch (err) {
    toast(err.message, 6000);
  }
  const saved = store.get('reels-tab');
  showTab(['upload', 'tag', 'folders'].includes(saved) ? saved : items.length ? 'tag' : 'upload');
})();
