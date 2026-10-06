# Rassegna mattutina

Ogni mattina alle **6:50 (ora italiana)** una Routine di Claude Code legge su Gmail
le newsletter arrivate nelle ultime 24 ore, traduce quelle in inglese, le riassume
(lunghezza variabile, con le immagini degli articoli) e le invia in un'unica **email**
impaginata come una newsletter.

Le istruzioni complete della Routine (fonti, filtri, formato, invio)
sono in [`PROMPT.md`](PROMPT.md); la Routine legge questo file a ogni esecuzione.

## Fonti

Cosa Sposta, Foundr (EN, senza mail di vendita), Chapeau Project, Il Punto,
Starting Finance (senza promo), Ragionamenti Finanziari (note Substack),
Morning Tech, Technicismi, Ruben Hassid (EN), The Daily Signal (EN, raggruppato),
Blackbox e Verba Manent (Chora Media).

## File

- `PROMPT.md`: istruzioni della Routine.
- `extract_images.py`: estrae le immagini editoriali da una mail e segnala quelle sponsorizzate.
- `render.py`: trasforma il JSON del giorno nell'email HTML (grafica fissa) e nella versione testo.
