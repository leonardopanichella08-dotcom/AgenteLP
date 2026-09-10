# Ecosistema AgenteLP — contratto condiviso

Questo documento definisce **cosa** condividono le funzioni del mega-agente e
**come** una nuova funzione (es. ANDREA) si innesta. Non è codice ancora
astratto in un package `core/`: è il contratto che il codice di ogni funzione
rispetta, così l'estrazione futura è meccanica e non inventata.

## 1. Cosa è condiviso

| Ambito | Contratto | Dove vive oggi (in LUKA) |
|---|---|---|
| **Identità utente** | un `User` (email) possiede risorse per-funzione; v1 single-tenant con utente demo, sostituibile con auth JWT/OAuth | `functions/luka/app/models.py` (`User`), `deps.py` |
| **Registro agenti** | ogni funzione si dichiara con: `key`, `display_name`, `capabilities[]`, `required_scopes[]`; l'orchestratore instrada i task per `key` | `agent_tasks.agent_key` (stringa `"luka"`); il registro come tabella arriva quando c'è la 2ª funzione |
| **Task model** | `AgentTask { id, agent_key, user_id, type, status, params, result_summary, timestamps }` — stesso schema per ogni funzione | `functions/luka/app/models.py` (`AgentTask`) |
| **Design system** | palette (bianco / grigi / accento `#0A66C2` / antracite), Inter, icone Lucide, bordi 1px, no ombre pesanti, tanto white space | `functions/luka/web/tailwind.config.ts` + `src/index.css` |
| **Shell UI** | sidebar sinistra (Dashboard, Funzioni, Profili, Settings) + workspace centrale; su mobile → bottom nav | `functions/luka/web/src/App.tsx` |
| **Cifratura segreti** | token di terze parti cifrati a riposo con Fernet (`APP_ENCRYPTION_KEY`) | `functions/luka/app/crypto.py` |

## 2. Come si aggiunge una funzione

1. `functions/<nome>/` con la stessa struttura di `luka/` (backend FastAPI +
   `web/` opzionale, oppure solo backend se headless).
2. Il backend espone `GET /api/meta` con almeno
   `{ "function": "<nome>", "capabilities": [...] }`.
3. I task usano il model `AgentTask` con `agent_key = "<nome>"`.
4. Il frontend riusa `tailwind.config.ts` e i token da questo contratto.
5. Deploy: nuovo progetto Vercel, Root Directory `functions/<nome>`.

## 3. Quando estrarre un `core/`

Alla **seconda** funzione (ANDREA). A quel punto si sposta in
`packages/core/` (Python) e `packages/ui/` (React):
- `core/models.py` → `User`, `AgentTask`, base `Base`
- `core/crypto.py`, `core/auth/`
- `ui/tokens`, `ui/shell`

Fino ad allora, duplicare è più economico che astrarre a vuoto.

## 4. Migrazione di ANDREA (ex Architetto Gestionale) — checklist futura

> Da eseguire solo quando Leonardo dà l'ok.

- [ ] Copiare `backend/` (FastAPI + parser Excel + simulate/explain) in `functions/andrea/app/`
- [ ] Copiare `frontend/` in `functions/andrea/web/` e allinearlo al design system
- [ ] Portare la **memoria** del progetto Architetto Gestionale
      (`~/.claude/projects/.../memory/`) sotto la nuova funzione
- [ ] Adattare i task al model `AgentTask` con `agent_key = "andrea"`
- [ ] Nuovo progetto Vercel, Root Directory `functions/andrea`
- [ ] Verificare che LUKA e ANDREA non condividano tabelle di dominio
