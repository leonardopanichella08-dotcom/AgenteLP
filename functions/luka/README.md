# LUKA — funzione di [AgenteLP](../../README.md)

Agente specializzato: assistente ed esecutore per personal brand e Pagine
aziendali su LinkedIn — onboarding + knowledge base, discovery dei
**10 post virali** di nicchia, generazione di **commenti e repost ad alto
impatto**, esecuzione assistita via deep-link.

> Parte del mega-agente **AgenteLP**. Condivide con le altre funzioni solo
> l'ecosistema (identità, design system, model dei task): vedi
> [`docs/architecture.md`](../../docs/architecture.md). Nessuna logica
> condivisa con **ANDREA**.

> **Gira gratis.** Nessuna chiave obbligatoria: senza `ANTHROPIC_API_KEY`
> Luka lavora in *demo mode* (risposte da template) su un dataset di post
> incluso. Aggiungendo la chiave passa alla generazione con Claude.

---

## 1. Avvio locale (30 secondi)

**Requisiti:** Python 3.11+ e Node 18+.

```bash
# dalla cartella luka/
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements.txt      # macOS/Linux: .venv/bin/python
.venv/Scripts/python -m uvicorn app.main:app --reload --port 8000
```

In un secondo terminale:

```bash
cd web
npm install
npm run dev
```

Apri **http://localhost:5173**. Il DB SQLite (`luka.db`) e due profili demo
vengono creati al primo avvio.

Scorciatoia Windows: `./dev.ps1` avvia tutto.

---

## 2. Cosa funziona senza configurare nulla

| Funzione | Comportamento di default |
|---|---|
| Profili collegati | 2 profili demo (personale + Pagina) già analizzati |
| Onboarding / Knowledge Base | sintesi euristica di Mission, Value Prop, ICP, Market Context |
| Upload documenti (PDF/DOCX/TXT) | estrazione testo + indicizzazione lessicale (RAG senza embedding) |
| **Discovery** (`DISCOVERY_PROVIDER=free`) | **Hacker News + Reddit**: contenuti che performano ORA sulla nicchia. 100% gratis, nessuna chiave. Ricade sul dataset locale se offline. |
| Incolla-post manuale | `POST /api/tasks/analyze` o pannello "Oppure incolla un post": Luka lavora su post LinkedIn reali incollati a mano — sempre accurato, sempre gratis |
| Ranking | engagement rate ponderato × recency × reach (half-life adattiva per fonte) |
| Generazione commenti/repost | *demo mode*: template coerenti con post + contesto |
| Dashboard | lista post + risposte + Copia + deep-link "Apri su LinkedIn" |

> **Nota:** la discovery `free` non restituisce *post LinkedIn* ma il **segnale
> di trend** della nicchia (di cosa si parla, con quale engagement) su HN/Reddit,
> così Luka può cavalcarlo. Per i post LinkedIn letterali: `analyze` (incolla) —
> gratis e preciso — oppure `DISCOVERY_PROVIDER=apify` (a pagamento).

## 3. Passare alla modalità reale (opzionale, a consumo)

Copia `.env.example` in `.env` e compila solo ciò che ti serve:

```env
ANTHROPIC_API_KEY=sk-ant-...      # -> generazione + onboarding con Claude (qualità)
ANTHROPIC_MODEL=claude-sonnet-5

DISCOVERY_PROVIDER=apify          # -> post LinkedIn reali (Apify, a pagamento)
APIFY_TOKEN=apify_api_...
```

Il resto dell'app non cambia: stessi endpoint, stessa UI.

---

## 4. Struttura

```
functions/luka/
  app/
    main.py              FastAPI + bootstrap (crea tabelle, seed)
    config.py            settings (.env) — has_llm / has_apify / has_linkedin_oauth
    db.py  models.py      SQLAlchemy 2.0 (SQLite locale / Postgres in prod)
    schemas.py           I/O Pydantic
    deps.py              utente singolo v1 + deep-link builder
    crypto.py            cifratura Fernet dei token a riposo
    linkedin_oauth.py    OIDC: authorize URL, scambio code, userinfo, state firmato
    services.py          estrazione testo PDF/DOCX
    kb_index.py          retrieval chunk per connessione
    seed.py              profili demo
    data/seed_posts.json dataset discovery "sample"
    agent/
      prompt.py          System Prompt di Luka + schema tool + prompt caching
      engine.py          generate_engagement(): Claude oppure demo generator
      onboarding.py      sintesi brand profile: Claude oppure euristica
      discovery.py       DiscoveryProvider: Sample | Apify (actor no-cookies)
      ranking.py         engagement_score()
      retriever.py       chunking + LexicalRetriever (BM25-lite, zero dipendenze)
    routers/
      auth.py            /api/auth/linkedin/* (OAuth OIDC)
      connections.py     CRUD profili + rianalisi onboarding
      knowledge.py       upload / lista / delete documenti
      tasks.py           POST /api/tasks/discovery  (ciclo completo), regenerate
  api/index.py           entry point Vercel (ASGI)
  tests/                 pytest: flusso API, unit agenti, crypto+OAuth
  web/                   React 18 + Vite + Tailwind + TanStack Query
    src/App.tsx          dashboard completa (sidebar, topbar, KB card, filtri, feed)
```

### Endpoint principali

| Metodo | Path | Uso |
|---|---|---|
| `GET` | `/api/meta` | modalità (llm/demo), provider, `linkedin_oauth`, opzioni geo |
| `GET` | `/api/auth/linkedin/status` | se l'OAuth è configurato |
| `GET` | `/api/auth/linkedin/start?account_type=` | redirect verso LinkedIn |
| `GET` | `/api/auth/linkedin/callback` | scambio code→token, upsert connessione cifrata |
| `GET/POST` | `/api/connections` | lista / collega profilo manuale (fa partire l'onboarding) |
| `POST` | `/api/connections/{id}/reanalyze` | rigenera la knowledge base |
| `POST` | `/api/connections/{id}/documents` | upload documento (multipart) |
| `POST` | `/api/tasks/discovery` | discovery + ranking + generazione, in un colpo |
| `POST` | `/api/tasks/analyze` | genera su post LinkedIn **incollati a mano** (gratis, preciso) |
| `GET` | `/api/tasks/{id}` | dettaglio task con post e risposte |
| `POST` | `/api/tasks/posts/{id}/regenerate` | rigenera le risposte di un post |

Swagger completo su `http://127.0.0.1:8000/docs`.

---

## 5. Test

```bash
cd functions/luka
.venv/Scripts/python -m pip install -r requirements-dev.txt
.venv/Scripts/python -m pytest
```

Coverage: flusso API end-to-end (demo mode), unit degli agenti
(ranking, retriever, discovery, demo generator, prompt caching),
cifratura token + macchina a stati OAuth.

---

## 6. Deploy su Vercel (free tier)

**DB:** Postgres gratuito su [Neon](https://neon.tech) (nessuna carta), copia
la connection string.

### Opzione A — progetto unico (frontend statico + API Python)

1. Importa il repo `AgenteLP` su Vercel, **Root Directory = `functions/luka`**.
2. Environment Variables (tutte opzionali tranne `DATABASE_URL` in prod):
   - `DATABASE_URL` = connection string Neon (`postgres://...?sslmode=require`)
   - `APP_ENCRYPTION_KEY` = chiave Fernet (obbligatoria se usi l'OAuth)
   - `ANTHROPIC_API_KEY`, `APIFY_TOKEN`, `LINKEDIN_CLIENT_ID/SECRET` — quando le hai
   - `LINKEDIN_REDIRECT_URI` = `https://<tuo-dominio>/api/auth/linkedin/callback`
   - `FRONTEND_URL` = `https://<tuo-dominio>`
   - `CORS_ORIGINS` = `https://<tuo-dominio>`
3. Deploy. `vercel.json` builda `web/` come statico e serve `api/index.py`
   come funzione Python; `/api/*` viene instradato lì.

### Opzione B — due progetti (più robusta per i job lunghi)

| Progetto | Root Directory | Note |
|---|---|---|
| `agentelp-luka-api` | `functions/luka` | preset *Other*; Vercel rileva `api/index.py` + `requirements.txt` |
| `agentelp-luka-web` | `functions/luka/web` | preset *Vite*; env `VITE_API_BASE = https://…-api.vercel.app` |

> **Job lunghi:** con molte varianti + Claude la generazione può avvicinarsi
> al limite di durata delle Function. Per volumi seri: coda (Upstash QStash)
> + una function per post. Vedi [`docs/architecture.md`](../../docs/architecture.md).

---

## 7. Autenticazione LinkedIn

Il flusso **OAuth OpenID Connect** è implementato (`app/linkedin_oauth.py`,
`app/routers/auth.py`): appena imposti `LINKEDIN_CLIENT_ID` e
`LINKEDIN_CLIENT_SECRET` nel `.env`, in "Collega profilo" compare
**"Continua con LinkedIn"**. Token salvati cifrati (Fernet,
`app/crypto.py` + `LinkedInConnection.access_token_enc`). L'inserimento
manuale resta come fallback.

- Scope self-serve: `openid profile email` (prodotto *Sign In with LinkedIn
  using OpenID Connect*).
- Per pubblicare a nome utente: aggiungi `w_member_social` (*Share on LinkedIn*).
- Per le Company Pages: *Community Management API* (soggetta ad approvazione),
  poi aggiungi gli scope org e la selezione della Pagina nel callback.

### Compliance

L'API ufficiale **non** consente ricerca post per keyword, lettura
dell'engagement altrui, né commenti automatici su scala. Quindi:

- discovery via **segnale di nicchia gratuito** (HN/Reddit), incolla-post
  manuale, o **provider terzi** (Apify) per i post LinkedIn letterali;
- **nessun commento pubblicato via API**: Luka genera → *Copia* → deep-link →
  pubblichi tu. È il flusso conforme.
- via API solo **contenuti originali** sul profilo/Pagina dell'utente.
