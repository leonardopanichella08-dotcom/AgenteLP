# Rassegna mattutina

Ogni mattina alle **6:50 (ora italiana)** una Routine di Claude Code legge su Gmail
le newsletter arrivate nelle ultime 24 ore, traduce quelle in inglese, le riassume
(150-250 parole ciascuna) e le invia su **WhatsApp** tramite CallMeBot,
un messaggio per newsletter più un indice iniziale.

Le istruzioni complete della Routine (fonti, filtri, formato, invio, fallback)
sono in [`PROMPT.md`](PROMPT.md): il testo è lo stesso salvato nella Routine.

## Fonti

Cosa Sposta, Foundr (EN, senza mail di vendita), Chapeau Project, Il Punto,
Starting Finance (senza promo), Ragionamenti Finanziari (note Substack),
Morning Tech, Technicismi, Ruben Hassid (EN), The Daily Signal (EN, raggruppato),
Blackbox e Verba Manent (Chora Media).

## Configurazione richiesta

Nelle impostazioni dell'ambiente cloud:

- variabili `CALLMEBOT_PHONE` (es. `+39...`) e `CALLMEBOT_APIKEY`;
- `api.callmebot.com` tra gli **Allowed domains** del Network access.

Se mancano, la Routine invia la rassegna per email (fallback).
