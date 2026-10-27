# AgenteLP — regole per chi lavora in questo repo (Claude incluso)

Ogni sessione parte senza memoria: questo file è l'unica cosa che la sessione sa prima di scrivere codice.

## Regola n.0 — questo repo è SOLO per gli agenti del mega-agente AgenteLP
- Qui vivono LUKA, REELS, ANDREA e le future funzioni dell'agente personale di Leonardo.
- **Progetti che non sono un agente di AgenteLP** (giochi, automazioni email, siti, esperimenti…) **non vanno in questo repo**:
  né in `functions/luka/` né in una nuova `functions/<nome>/`. Fermati e di' a Leonardo di avviare la sessione su un repo dedicato
  (o chiedigli se vuoi crearlo tu). Non scrivere codice finché non risponde.

## Regola n.1 — una funzione = una cartella propria
- Ogni agente/funzione vive in **`functions/<nome>/`**, con il suo backend, la sua UI e i suoi test, deployabile da solo.
- **Mai** aggiungere un nuovo agente dentro `functions/luka/` (né file, né router, né pagina, né voce nella sidebar di LUKA).
  LUKA è *solo* l'agente LinkedIn. Se un lavoro non riguarda LinkedIn, non va in LUKA.
- Funzioni attuali: `luka` (LinkedIn), `reels` (video editing). `andrea` oggi è **ancora dentro LUKA** (`functions/luka/app/andrea`,
  `routers/andrea.py`, `pages/AndreaPage.tsx`): è un residuo, la migrazione a `functions/andrea/` è nella checklist di `docs/architecture.md`
  e si fa **solo su ok esplicito di Leonardo**. Non copiare quel precedente.
- Una nuova funzione: segui `docs/architecture.md` §2 e aggiungi la riga alla tabella del `README.md` radice.

## Prima di iniziare un lavoro nuovo
1. Se la richiesta non nomina una funzione esistente, è una **nuova funzione**: crea `functions/<nome>/`.
2. Se è ambiguo (es. "aggiungi questo all'agente"), chiedi *quale* funzione prima di toccare codice.
3. Non modificare le altre funzioni per far funzionare quella nuova.

## Convenzioni
- Italiano per UI, documentazione e messaggi utente. Commit in stile `feat(<funzione>): …`.
- Test accanto alla funzione (`functions/<nome>/tests`), eseguibili da soli.
- Niente segreti nel repo: chiavi via variabili d'ambiente.
- Lavora su un branch `claude/<tema>`; non spingere su `main` senza richiesta.
