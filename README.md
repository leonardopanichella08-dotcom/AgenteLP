# AgenteLP

Mega-agente personale di Leonardo Panichella. Un guscio (orchestratore +
ecosistema condiviso) che espone più **funzioni**, ciascuna delle quali è un
agente specializzato con la propria architettura.

## Funzioni

| Funzione | Stato | Cosa fa | Cartella |
|---|---|---|---|
| **LUKA** | attiva (v0.1) | Analisi profili LinkedIn, discovery post virali di nicchia, generazione di commenti/repost ad alto impatto, esecuzione assistita via deep-link | [`functions/luka/`](functions/luka/) |
| **ANDREA** | pianificata | Ex "Architetto Gestionale": parsing Excel, simulazioni what-if, metriche e spiegazioni AI. Verrà migrata qui con tutta la sua memoria e i processi locali. | `functions/andrea/` (da creare) |

Le funzioni **non condividono logica di dominio** tra loro: condividono solo
l'ecosistema (identità utente, design system, contratto di registrazione
agente). Vedi [`docs/architecture.md`](docs/architecture.md).

## Struttura

```
AgenteLP/
  functions/
    luka/            # agente LUKA — FastAPI + React, deployabile in autonomia
    andrea/          # (futuro) agente ANDREA
  docs/
    architecture.md  # contratto dell'ecosistema condiviso
```

## Sviluppo

Ogni funzione è autonoma e si avvia dalla sua cartella. Per LUKA:

```bash
cd functions/luka
./dev.ps1                 # Windows: crea venv, installa, avvia API :8000 + web :5173
```

Dettagli, test e deploy: [`functions/luka/README.md`](functions/luka/README.md).

## Deploy (gratis)

Ogni funzione è un progetto Vercel separato con **Root Directory** puntato
alla sua cartella (`functions/luka`). Database: Postgres free su Neon.
L'app gira comunque in *demo mode* senza alcuna chiave esterna.
