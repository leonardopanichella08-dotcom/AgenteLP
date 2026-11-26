# Reels Trattamenti

Tool per smistare foto e video per trattamento.

1. **Carica** – trascini file o un'intera cartella. I file vanno diretti su
   Cloudflare R2 (10 GB gratis), con 3 tentativi per file e "Riprova i non riusciti".
2. **Classifica** – chi entra scorre i media come reels (swipe verticale, video
   in autoplay, tocca per l'audio) e per ognuno sceglie il trattamento:
   EPILAZIONE / VISO / CORPO (solo le voci ✅) oppure *Da scartare*.
   Scelto il trattamento passa da solo al successivo. Filtro in alto per
   ricontrollare: tutti, già classificati, o un singolo trattamento.
3. **Cartelle** – una cartella per trattamento con anteprime: si può cambiare
   trattamento, scaricare il singolo file, eliminare, rivedere come reels, o
   scaricare lo **ZIP della cartella** / **ZIP di tutto** (una sottocartella per
   trattamento, gli scartati esclusi).

In alto, su ogni scheda, una barra mostra a tutti quanti file sono già
smistati (totale, video, foto, scartati); si aggiorna da sola ogni 30 secondi.

L'elenco dei trattamenti è in [`src/treatments.js`](src/treatments.js).

## Deploy su Vercel

1. Nuovo progetto Vercel da questo repo, **Root Directory** `functions/reels`,
   Framework **Other** (il resto è in `vercel.json`).
2. Su Cloudflare: **R2** → crea un bucket (es. `reels-trattamenti`), poi
   **Manage API tokens → Create API token** con permesso **Admin Read & Write**.
3. Su Vercel, **Settings → Environment Variables**:
   `R2_ACCOUNT_ID`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_BUCKET`.
4. Redeploy. Al primo caricamento il sito imposta da solo il CORS del bucket.

Accesso libero: chiunque abbia il link vede la stessa pagina e può caricare,
classificare, scaricare ed eliminare. Il bucket resta privato: foto e video si
vedono tramite link firmati validi 7 giorni.

## Come sono salvati i dati

Niente database: tutto nel bucket R2.

- `media/<id>/<nome file>` – il file caricato
- `tags/<id>/<trattamento>` – file vuoto che indica il trattamento scelto

## Sviluppo locale

```bash
npm install && npm run build
npx vercel dev   # con le variabili R2_* in .env.local
```
