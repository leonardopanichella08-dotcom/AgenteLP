# REELS — agente di video editing autonomo

Funzione di AgenteLP. Due modalità, quattro formati, un solo contratto JSON.

| Modalità | Input | Output |
|---|---|---|
| **A · Script + clip** | script testuale + più clip (riprese multiple, take sbagliate incluse) | un video montato nella sequenza esatta dello script, con la take migliore per ogni frase |
| **B · Video lungo → Reels** | uno o più video lunghi (podcast, lezioni, vlog) | 3-5 reel autonomi di 15-60 s, ognuno con virality score motivato, caption e hashtag |

Formati: **9:16** 1080×1920 (TikTok, Reels, Shorts, FB Reels) · **4:5** 1080×1350 (feed IG/FB) · **1:1** 1080×1080 (LinkedIn, IG grid) · **16:9** 1920×1080 (YouTube, LinkedIn video). 30 o 60 fps.

```bash
cd functions/reels
pip install -r requirements-dev.txt          # serve anche ffmpeg (con libass) nel PATH
python -m pytest                              # 39 test, ~2 min
uvicorn app.main:app --port 8000              # dashboard su http://localhost:8000
```

Nella dashboard i pulsanti **Demo** creano un progetto con media sintetici (nessuna chiave necessaria).
Per video veri serve un provider ASR (vedi *Configurazione*) oppure una trascrizione accanto al video (`nome.transcript.json`).

---

## 1. Il principio che fa cadere i tagli nel punto giusto

> **L'LLM decide *cosa* tagliare (id di frase). Il segnale audio decide *dove* cade il taglio.**

I timestamp word-level di Whisper/Deepgram sbagliano di ~50-150 ms. Tagliare "dove dice l'ASR" mozza le parole.
Per questo l'agente **non scrive mai un tempo**: sceglie frasi per id, e `app/cutting.py` calcola ogni punto di taglio sull'onda audio.

**Gap analysis** (`analyze_gaps`). Tra due parole consecutive guarda le *run* di attività vocale (energia RMS a 5 ms, soglia
adattiva) comprese tra i **punti medi** delle due parole (robusti a un jitter ASR fino a mezza parola):

- ≥ 2 run → c'è una pausa vera. `off` = fine della prima run, `on` = inizio dell'ultima. Le run intermedie sono voce **non trascritta**
  (eh, respiri: Whisper spesso li omette) e vengono rimosse insieme alla pausa.
- 1 run → parlato continuo: il taglio, se serve, va nella **valle di energia** (confidenza bassa, dichiarata).

Poi: padding naturale (`tail_pad`/`lead_pad`) **limitato dalla prossima attività vocale**, aggancio al **frame** *dentro* il silenzio,
segmenti < 0,2 s fusi, micro-fade audio di 6 ms. Ogni taglio nel JSON dichiara metodo, silenzio, confidenza e di quanto
differirebbe da un taglio sui timestamp ASR (`asr_time` vs `time`).

Policy di jump-cut: `tight` (pausa max 0,25 s) · `natural` (0,45) · `relaxed` (0,80).

**Modalità B**: finestre di *frasi intere* → inizio = inizio frase, fine = fine frase, entrambi su silenzio reale. La durata 15-60 s si
misura sul montato (dopo i jump-cut). **Modalità A**: allineamento semi-globale (Needleman-Wunsch con inizio/fine liberi) script↔clip →
trova *tutte* le take, scarta false partenze/ripetizioni, sceglie per completezza, poche esitazioni e (a parità) la più recente.

## 2. Architettura e stack

```
upload ─▶ probe ─▶ ASR (word-ts + diarizzazione) ─▶ audio envelope ─▶ gap analysis ─▶ ┬─ Mod. A: align script↔take ─┐
                                                                                       └─ Mod. B: frasi → candidati ─┤
        (LLM Claude opzionale: sceglie id di frase, caption, keyword)  ──────────────────────────────────────────────┤
                                                                                                                      ▼
   face tracking + active speaker ─▶ crop path ─▶ planner (timeline, parole, zoom, SFX, b-roll, framing) ─▶ EditPlan JSON
                                                                                                                      ▼
                                                  review nella dashboard (modifiche sicure) ─▶ FFmpeg filter_complex ─▶ MP4
```

| Stadio | Implementazione | Alternative consigliate in produzione |
|---|---|---|
| ASR + word-timestamps | `asr.py`: Deepgram (nova-2, diarize), OpenAI whisper-1, faster-whisper locale, sidecar JSON | WhisperX (+ forced alignment wav2vec2, ±20 ms) e pyannote per la diarizzazione |
| Forced alignment (A) | allineamento testuale su token ASR + gap analysis sull'audio | WhisperX / Montreal Forced Aligner se l'ASR sbaglia molte parole |
| Voce vs silenzio | RMS 5 ms, soglia adattiva (`audio_analysis.py`) | Silero VAD per audio molto rumoroso |
| Volti / active speaker | OpenCV Haar (4.x) + moto della zona-bocca + diarizzazione (`reframe.py`), interfaccia `FaceDetector` | MediaPipe / YuNet per i volti; TalkNet/Light-ASD per l'active speaker vero |
| LLM editoriale | Claude con tool-use forzato (`llm.py`), output validato; fallback euristico offline | — |
| Compositing/render | **FFmpeg** `filter_complex` (un solo encode), sottotitoli ASS/libass | Remotion o Shotstack se servono template grafici ricchi: il JSON è già il contratto |
| B-roll | Pexels (`broll.py`, `PEXELS_API_KEY`) | Shutterstock: stessa interfaccia `BrollProvider` |
| SFX | sintetizzati in numpy (`sfx.py`), nessuna licenza | libreria di SFX reali con le stesse chiavi (`whoosh/pop/ding/click/riser`) |
| API / job | FastAPI + thread pool, stato su filesystem | coda reale (Celery/RQ/Cloud Tasks) + object storage |

**Frame-accuracy del render**: ogni segmento è `trim` sul tempo sorgente (tolleranza di ½ frame in ingresso), bloccato a N frame esatti; l'audio dello stesso segmento a N/fps secondi.
Nessuna deriva A/V concatenando decine di segmenti (verificato: vedi test).

**Reframing** (`reframe.py`). `auto`: aspect uguale → nessuno; target più stretto + volti rilevati ≥ 50% → **smart crop** sul parlante attivo
(diarizzazione → volto tramite correlazione col moto della bocca; senza diarizzazione vince la bocca che si muove; se i volti stanno tutti nella finestra, inquadra il gruppo per evitare jitter);
altrimenti, o per target più largo della sorgente → **sfondo sfocato dinamico** (mai bande nere). Camera: deadband + smoothing, scatto rapido al cambio di parlante.

## 3. System prompt dell'agente

[`app/prompts/system_prompt.md`](app/prompts/system_prompt.md) — è il prompt realmente usato da `llm.py` (e visibile nella dashboard).
Regole portanti: lavora solo su id di frase (mai timestamp), criteri di selezione ordinati (gancio, autonomia, arco, picco, densità, durata),
vincoli duri, punteggi calibrati, checklist finale, "meno reel ma buoni" invece di riempire.

## 4. Universal Edit Plan (JSON)

Schema completo: [`docs/edit_plan.schema.json`](docs/edit_plan.schema.json) (generato da `app/schemas.py`, esposto su `GET /api/schema`).
Esempio reale prodotto dalla pipeline: [`docs/example_plan.json`](docs/example_plan.json).

```jsonc
{
  "schema_version": "1.0", "mode": "long_form_extraction", "cut_policy": "natural",
  "sources":  [{ "id": "podcast", "path": "...", "duration": 42.27, "fps": 30, "width": 960, "height": 540 }],
  "exports":  [{ "format_id": "9:16", "width": 1080, "height": 1920, "fps": 30, "platforms": ["tiktok", "instagram_reels", "youtube_shorts", "facebook_reels"],
                 "reframe": { "strategy": "auto", "blur_sigma": 30, "smooth": 0.85 } }],
  "reels": [{
    "id": "reel1", "title": "...", "rank": 1, "duration": 25.23, "selected": true,
    "virality": { "score": 85, "reasons": ["Si apre con una domanda: curiosità immediata", "..."], "hook_text": "Davvero?" },
    "timeline": [{                                   // segmenti tenuti, già tagliati nel silenzio e sul frame
      "id": "s2", "source_id": "podcast",
      "src_start": 8.8, "src_end": 9.8, "src_start_frame": 264, "src_end_frame": 294,
      "out_start": 0.566667, "out_end": 1.566667, "removed_before": "pause",   // pause | drop | filler | take_change
      "cut_in":  { "asr_time": 8.828, "time": 8.8, "frame": 264, "method": "silence_gap", "silence": [8.195, 8.875], "confidence": 1.0, "reason": "pause" },
      "cut_out": { "asr_time": 9.788, "time": 9.8, "frame": 294, "method": "silence_gap", "silence": [9.8, 10.365], "confidence": 1.0, "reason": "pause" },
      "script_unit": null, "take_id": null }],
    "words":   [{ "text": "segreto", "out_start": 1.2097, "out_end": 1.5547, "src_start": 9.443, "src_end": 9.788, "speaker": "A",
                  "segment_id": "s2", "emphasis": "power", "color": "#FF3B30", "emoji": "🤫" }],
    "framing": [{ "format_id": "9:16", "strategy": "smart_crop", "reason": "volti rilevati nel 100% del tempo: crop sul parlante attivo",
                  "crop_keyframes": { "s2": [{ "t": 0.0, "x": 88.1, "y": 0, "w": 303.8, "h": 540 }] },   // pixel sorgente, t relativo al segmento
                  "active_speaker": { "s2": ["0"] } }],
    "subtitles": { "preset": "hormozi", "font": "Inter", "max_words_per_line": 3, "uppercase": true, "position_y": 0.66,
                   "highlight_colors": ["#FFE600", "#00E676", "#FF3B30"], "safe_top": 0.1, "safe_bottom": 0.22 },
    "zooms":   [{ "out_start": 0.566667, "out_end": 1.566667, "from_scale": 1.12, "to_scale": 1.17, "reason": "punch_in" }],
    "sfx":     [{ "out_time": 1.21, "sfx_id": "pop", "gain_db": -16, "reason": "parola d'impatto (power)", "anchor_word": "segreto" }],
    "broll":   [{ "out_start": 21.2, "out_end": 23.0, "query": "montaggio", "asset_path": "...", "provider": "pexels" }],
    "transitions": [{ "out_time": 0.566667, "type": "cut" }],       // cut | whoosh_cut
    "social":  { "title": "...", "caption": "...", "hashtags": ["#..."] }
  }],
  "script_report": [{ "unit": 0, "text": "...", "status": "matched", "chosen_take": "clip1@3.62", "similarity": 1.0, "alternatives": [] }]
}
```

## 5. API

| | |
|---|---|
| `POST /api/projects` (multipart) | `mode`, `formats` (`9:16,1:1`), `script`, `cut_policy`, `reframe`, `subtitle_preset`, `n_min/n_max`, `min_dur/max_dur`, `fps`, `sfx/emoji/zoom/broll`, `files[]` (video + `.transcript.json` opzionali) |
| `POST /api/demo` | progetto con media sintetici |
| `GET /api/projects/{id}` | stato: stage per stage, progress, errori (`error_kind: asr_unavailable`), output |
| `GET /api/projects/{id}/plan` | l'Edit Plan |
| `POST /api/projects/{id}/edit` | `{reel_id, ops:[…]}`: `nudge`, `remove_segment`, `swap_take`, `set_style`, `set_sfx`, `set_zoom`, `set_social`, `toggle_reel` |
| `POST /api/projects/{id}/render` | `{reels?, formats?, quality: draft\|final}` |
| `GET …/files/{name}` · `…/media/{source}` (Range) · `…/waveform/{source}` | download, anteprima, forma d'onda |
| `GET /api/schema` · `/api/system-prompt` · `/api/formats` · `/api/meta` | |

**Modifiche sicure**: `nudge` sposta un taglio di ±N frame solo se l'intero intervallo spazzato è silenzio (altrimenti 422, salvo `force`).
Dalla dashboard è impossibile mozzare una parola per sbaglio.

## 6. Specifiche UI/UX della dashboard (implementate in `app/static/`)

1. **Selettore di modalità**: due card ("Video lungo → Reels", "Script + clip multiple") con descrizione di cosa fa l'agente.
2. **Upload multi-file**: dropzone + lista ordinabile/rimovibile, numerazione delle clip, accetta `.transcript.json` per saltare l'ASR; campo script visibile solo in modalità A.
3. **Selettore formati**: 4 card multi-selezione con glifo proporzionale all'aspect e chip delle piattaforme; almeno uno sempre attivo.
4. **Elaborazione**: barra complessiva + una per fase (analisi file → trascrizione → analisi audio → tagli → volti → piano), messaggio live; errori azionabili (es. "imposta DEEPGRAM_API_KEY o carica il trascritto").
5. **Revisione dei tagli prima del render** (nessun rendering necessario):
   - player sul video originale che **salta i tratti rimossi** (anteprima istantanea dei tagli), con overlay del **riquadro di crop** per il formato scelto (tab 9:16 / 1:1 / …) e dei **sottotitoli** con parola attiva;
   - **timeline** sull'onda audio: segmenti tenuti, marker di taglio verdi (sicuro) / ambra (parlato continuo), secondi rimossi; clic = riproduci da lì;
   - **tabella dei punti di taglio**: confidenza, scarto rispetto all'ASR, ±1 frame IN/OUT (solo nel silenzio), ▶ riproduci, ✕ rimuovi;
   - **report script↔clip** (A): stato per frase (trovata/debole/mancante) e menu per **cambiare take**;
   - stile sottotitoli, SFX, zoom, posizione, caption/hashtag modificabili; checkbox per includere/escludere ogni reel.
6. **Render** per formato × reel (bozza a metà risoluzione o finale), progress, poi card con player, download MP4, copia caption+hashtag, trascrizione.

## 7. Cosa è stato testato (e cosa no)

`python -m pytest` → 39 test. Media sintetici con **verità-terreno** (audio con parole brevi, dip d'ampiezza, "eh" non trascritti, pause lunghe, timestamp ASR con jitter ±100 ms), più un volto reale (foto *astronaut* di scikit-image).

| Verificato | Come |
|---|---|
| Nessuna parola vera spezzata, in nessuna policy, in entrambe le modalità | confronto con le parole vere (non con i timestamp ASR) |
| **Controprova**: tagliare sui timestamp ASR grezzi *spezza* parole | test dedicato sullo stesso audio |
| Tagli nel silenzio, sul frame, "eh" non trascritti rimossi, nessuna pausa residua > policy | su piano **e** sull'audio renderizzato |
| Render **frame-exact** (anche segmenti da 1 frame, adiacenti, fuori ordine) | video che codifica l'indice di ogni frame in blocchi b/n, riletto dopo il montaggio |
| Durata e A/V sync a 30 e 60 fps; 1080×1920 reale; tutti i 4 formati | ffprobe sull'output |
| Active speaker: mapping parlante→volto dai pixel della bocca; crop che segue chi parla | video con due volti-cartone |
| Rilevatore volti **reale** (Haar) su un volto vero e crop 9:16 che lo segue | foto reale in un video 16:9 |
| Mod. A: testo montato = script **parola per parola**, take pulite, false partenze escluse; swap take | clip con inciampi e ripetizioni |
| Mod. B: 3-5 reel, 15-60 s, inizio/fine frase, non sovrapposti, ordinati per score | podcast sintetico di ~5 min |
| LLM: id invalidi/sovrapposti scartati, tempi decisi dal codice | client Claude simulato |
| Blur-pad senza bande nere, b-roll overlay, SFX mixati, client Pexels | render + HTTP simulato |
| API completa e dashboard in Chromium (demo A/B, nudge, swap take, render, download) | TestClient + Playwright, 0 errori JS |

**Non verificato in questo ambiente** (rete verso HuggingFace/API ASR non raggiungibile, nessun volto-video reale, nessuna GPU):
- ASR reali: i parser Deepgram/OpenAI sono testati su payload nel formato documentato, **non** su chiamate vere; Whisper locale non è stato eseguito.
- Robustezza del rilevatore Haar su video reali (profili, occlusioni, più persone, illuminazione): per produzione sostituire con MediaPipe/YuNet + un vero active-speaker model dietro la stessa interfaccia `FaceDetector`.
- Qualità del giudizio editoriale su contenuti reali (il virality score offline è euristico; con `ANTHROPIC_API_KEY` decide Claude, ma non ho potuto chiamarlo).
- Emoji nei sottotitoli: servono un font emoji nel sistema (qui assente → le emoji vengono omesse automaticamente). I sottotitoli ASS hanno risoluzione di 10 ms (< 1 frame a 60 fps).
- Il pre-echo del codec AAC a una giunzione (~−30 dBc, inudibile) è normale; i test lo tengono in conto.
- `loudnorm` è a singolo passaggio; su silenzio digitale puro cade e il render ritenta senza normalizzare.
- Limiti noti: un taglio tra due eventi vocali distanti < 1 frame (33 ms) cade subito dopo la parola e viene dichiarato con confidenza ridotta; "emphasis zoom" su singola parola non implementato (zoom alternati per segmento sì).

## 8. Configurazione

| Variabile | Effetto |
|---|---|
| `DEEPGRAM_API_KEY` / `OPENAI_API_KEY` | provider ASR (in ordine); altrimenti faster-whisper se installato |
| `ANTHROPIC_API_KEY` (`REELS_LLM_MODEL`) | selezione editoriale e copy con Claude; senza, euristica offline |
| `PEXELS_API_KEY` | b-roll |
| `REELS_DATA_DIR` | dove salvare progetti e output (default `functions/reels/data`) |

**Deploy**: richiede ffmpeg e CPU per il render → non adatto a Vercel serverless (a differenza di LUKA). Usare un container
(Cloud Run / Fly / Render) con volume o object storage; per volumi reali spostare i job su una coda.
