# Reels Trattamenti

Tool per smistare foto e video per trattamento.

1. **Carica** – trascini file o un'intera cartella (anche video pesanti: vanno
   diretti su Vercel Blob, con caricamento a pezzi e ripresa automatica).
2. **Classifica** – chi entra scorre i media come reels (swipe verticale, video
   in autoplay, tocca per l'audio) e per ognuno sceglie il trattamento:
   EPILAZIONE / VISO / CORPO (solo le voci ✅) oppure *Da scartare*.
   Scelto il trattamento passa da solo al successivo. Filtro in alto per
   ricontrollare: tutti, già classificati, o un singolo trattamento.
3. **Cartelle** – una cartella per trattamento con anteprime: si può cambiare
   trattamento, scaricare il singolo file, eliminare, rivedere come reels, o
   scaricare lo **ZIP della cartella** / **ZIP di tutto** (una sottocartella per
   trattamento, gli scartati esclusi).

L'elenco dei trattamenti è in [`src/treatments.js`](src/treatments.js).

## Deploy su Vercel

1. Nuovo progetto Vercel da questo repo, **Root Directory** `functions/reels`
   (il resto è già in `vercel.json`).
2. Progetto → **Storage** → **Create** → **Blob**, accesso **Public**, e
   collegalo al progetto: Vercel aggiunge da solo `BLOB_READ_WRITE_TOKEN`.
3. (Consigliato) **Settings → Environment Variables**: `APP_PASSWORD` = una
   password da dare a chi carica e classifica. Senza, il sito è aperto a chi
   ha il link.
4. Redeploy.

## Come sono salvati i dati

Niente database: tutto nel Blob store.

- `media/<id>/<nome file>` – il file caricato
- `tags/<id>/<trattamento>` – file vuoto che indica il trattamento scelto

## Sviluppo locale

```bash
npm install
npx vercel link && npx vercel env pull   # prende BLOB_READ_WRITE_TOKEN
npm run build && npx vercel dev
```
