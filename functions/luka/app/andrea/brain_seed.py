"""Seed del CORE SIMULATOR BRAIN — leggi universali di partenza.

Estratte dai progetti Kinetic API (2026) e Linkup (2026). Non cancellare:
si aggiungono, non si rimuovono.
"""

SEED_LAWS: list[dict] = [
    {"code": "P-1", "module": "Pricing & Unit Economics",
     "title": "La struttura dei costi comanda il pricing minimo",
     "body": "Se il CAC supera 10.000 EUR, il pricing per utente singolo e' sbagliato. "
             "ARPU_minimo = CAC / (anni_LTV x utenti_per_contratto x (1-churn)^anni_LTV). "
             "Se LTV/CAC < 3 il modello di pricing e' rotto, non il mercato. Correzione: "
             "Platform Fee fissa + PMPM scalabile + Outcomes Bonus.",
     "source": "[FONTE: Kinetic API, 2026]"},
    {"code": "P-2", "module": "Pricing & Unit Economics",
     "title": "Il pricing deve parlare la lingua del buyer",
     "body": "Enterprise/assicurazioni: fee mensile fissa (budget planning). PMI/welfare: fee "
             "per dipendente/mese. Consumer: micro-fee o freemium. Se il buyer deve fare un "
             "calcolo per capire quanto spendera', il pricing e' sbagliato.",
     "source": "[FONTE: Kinetic API, 2026]"},
    {"code": "P-3", "module": "Pricing & Unit Economics",
     "title": "L'outcomes-based pricing abbatte il ciclo di vendita del 60%",
     "body": "Nei B2B dove il prodotto promette un risparmio misurabile, 'paghi solo se "
             "funziona' porta il ciclo da 18 a 6 mesi. Fee base 20-30% del valore (copre "
             "OPEX) + fee di performance 70-80% su risultati documentati.",
     "source": "[FONTE: Noom enterprise 2017 -> Kinetic API, 2026]"},
    {"code": "GTM-1", "module": "Go-to-market",
     "title": "In ogni marketplace B2B a due lati, un lato puo' operare senza l'altro",
     "body": "Identifica quale lato genera valore parziale in modalita' single-side: quello e' "
             "il punto d'ingresso. Domanda: 'se domani un lato sparisse, il prodotto "
             "funzionerebbe al 40%?' Se si', e' il lato di lancio.",
     "source": "[FONTE: Kinetic API, 2026]"},
    {"code": "GTM-2", "module": "Go-to-market",
     "title": "Il canale critico non e' il cliente finale ma l'intermediario",
     "body": "Con decision-making frammentato, il broker/intermediario che gia' serve il "
             "cliente in modo continuativo ha CAC 5-10x inferiore al canale diretto. Prende "
             "8-15% del valore: conviene se abbatte il CAC di oltre il 30%.",
     "source": "[FONTE: Hinge Health, Kinetic API, 2026]"},
    {"code": "GTM-3", "module": "Go-to-market",
     "title": "Il first-mover advantage esiste solo se produce un asset non replicabile in 24 mesi",
     "body": "Essere primi non e' difendibile. Serve un asset che sia (1) longitudinale, (2) "
             "richieda accordi umani complessi, (3) cresca di valore con la scala. Se manca "
             "anche una condizione, un competitor finanziato replica in 18 mesi.",
     "source": "[FONTE: Kinetic API, A16Z, 2026]"},
    {"code": "REG-1", "module": "Compliance",
     "title": "La compliance by design e' un vantaggio competitivo, non un costo",
     "body": "GDPR/FDA/IVASS/FCA sono barriere all'ingresso se progetti il prodotto per "
             "soddisfarle prima dei competitor: il secondo entrante si ferma 6-18 mesi in "
             "review. Assumi il DPO/legal nel team fondatore, non come consulente esterno.",
     "source": "[FONTE: Kinetic API, 2026]"},
    {"code": "REG-2", "module": "Compliance",
     "title": "Il regime regolatorio che tratti determina il ciclo di vendita",
     "body": "Dati di categoria speciale (Art.9 GDPR) -> DPIA obbligatoria -> 3-6 mesi -> "
             "possibile blocco. Ridisegnare per restare in Art.6 (edge/on-device: il server "
             "riceve solo score aggregati) accorcia il ciclo di 3-6 mesi.",
     "source": "[FONTE: Kinetic API, 2026]"},
    {"code": "REG-3", "module": "Compliance",
     "title": "L'ispettorato regolatorio segue il denaro, poi il danno",
     "body": "I regolatori ispezionano i settori in crescita e ad alto rischio per gli "
             "individui. 'Settore in crescita + dati sensibili' = lista nera. Verifica il "
             "piano ispettivo del regolatore di settore per i 12 mesi successivi.",
     "source": "[FONTE: Garante Privacy IT, 2026]"},
    {"code": "COMP-1", "module": "Competizione & Moat",
     "title": "Il buyer del PoC e' il tuo competitor piu' pericoloso",
     "body": "In una vendita enterprise dove il buyer potrebbe costruire internamente, il PoC "
             "e' trasferimento di know-how. Mitiga: clausola di non-replica (24 mesi, penale "
             "200% fee annua) + moat cross-cliente + acquisire piu' clienti durante il PoC.",
     "source": "[FONTE: Kinetic API, 2026]"},
    {"code": "COMP-2", "module": "Competizione & Moat",
     "title": "Il database cross-entita' e' l'unico moat sostenibile per un middleware B2B",
     "body": "Un middleware tecnico e' replicabile. Un database aggregato da piu' entita' "
             "concorrenti no: ogni entita' ha solo i propri dati. Esempi: Plaid, Vitality, "
             "Kinetic API.",
     "source": "[FONTE: Plaid, Discovery Vitality, 2026]"},
    {"code": "COMP-3", "module": "Competizione & Moat",
     "title": "In mercati multi-livello il layer dati piu' prezioso e' quello vendibile al livello sovrastante",
     "body": "Assicuratore -> riassicuratore: il riassicuratore ha valore atteso "
             "sull'informazione 100-1000x superiore. In produttore->distributore->rivenditore "
             "vale lo stesso: guarda sempre un livello sopra a chi servi direttamente.",
     "source": "[FONTE: Swiss Re / Munich Re, 2026]"},
    {"code": "PRD-1", "module": "Design del prodotto",
     "title": "Non costruire il sensore: aggrega i dati che esistono gia'",
     "body": "Prima di costruire raccolta dati proprietaria, verifica se i dati esistono in "
             "formati standard accessibili (HealthKit, Health Connect, Plaid, Stripe). "
             "Costruire il sensore solo se non esistono alternative accessibili.",
     "source": "[FONTE: Discovery Vitality vs Kinetic API V1, 2026]"},
    {"code": "PRD-2", "module": "Design del prodotto",
     "title": "Il gaming degli incentivi segue la curva di risposta razionale",
     "body": "Tasso di gaming = f(valore incentivo / costo del gaming). Se (valore x prob. "
             "successo) < (costo gaming + rischio penalita'), il gaming non avviene. Accettare "
             "1-3% di frode residua e' superiore a un anti-frode che costa piu' delle frodi.",
     "source": "[FONTE: Kinetic API, 2026]"},
    {"code": "PRD-3", "module": "Design del prodotto",
     "title": "Il prodotto invisibile vince nel B2B2C",
     "body": "Nel B2B2C, il prodotto che l'utente finale NON vede come separato ha adozione "
             "3-10x superiore a quello che richiede un'app o un account nuovo. Ideale: sembra "
             "una feature dell'app che l'utente gia' usa.",
     "source": "[FONTE: Discovery Vitality, Plaid, 2026]"},
    {"code": "EXIT-1", "module": "Fundraising & Exit",
     "title": "La valutazione di exit cresce geometricamente con la rarita' del dataset",
     "body": "Dataset disponibile: 4-6x ARR. Raro ma replicabile: 6-10x. Unico strutturalmente "
             "non replicabile: 15-50x. L'obiettivo non e' massimizzare ARR ma la rarita' "
             "dell'asset dati.",
     "source": "[FONTE: Kinetic API vs Hinge vs Alan, 2026]"},
    {"code": "EXIT-2", "module": "Fundraising & Exit",
     "title": "Il Series A europeo nel healthtech e' sempre anche un pre-M&A",
     "body": "Gli LP strategici (Allianz X, AXA VP, Munich Re Ventures) usano il round come "
             "opzione di acquisto. Scegli i co-investitori per la rete di distribuzione e il "
             "valore come acquirenti, non solo per il capitale.",
     "source": "[FONTE: Nelson Advisors, Alan, 2026]"},
    {"code": "CS-1", "module": "Marketplace locale",
     "title": "Il cold start nei marketplace locali e' un problema di sequenza, non di budget",
     "body": "Il lato offerta (B2B) si costruisce prima, a mano, dal founder. Il lato B2C si "
             "introduce solo con >=100 attivita' nell'area. Marketplace vuoto (<50 attivita') "
             "= disinstallazione >80% al primo uso. Con 5 visite/giorno e 20% conversione: "
             "40 attivita' in 40 giorni, zero budget.",
     "source": "[FONTE: Linkup, Pescara 2026]"},
    {"code": "CS-2", "module": "Marketplace locale",
     "title": "La fee percentuale sul GMV e' incollettabile nei marketplace offline",
     "body": "Senza tracking fisico obbligatorio, la % sul transato e' matematicamente "
             "incollettabile. Usa fee flat per azione (1-3 EUR/prenotazione): revenue piu' "
             "basso ma 100% verificabile. Su Linkup: 9% GMV 'stimato' ~40k EUR -> 5.250 EUR "
             "reali, ma certi.",
     "source": "[FONTE: Linkup, 2026]"},
    {"code": "LM-1", "module": "Marketplace locale",
     "title": "Il moat locale e' il grafo sociale, non il catalogo di attivita'",
     "body": "Il numero di attivita' e' replicabile da Google in 3 mesi. Il grafo delle "
             "relazioni sociali locali (chi e' amico di chi, dove vanno insieme) no. Feature "
             "P0: amici vicini + activity feed. L'AI di raccomandazione viene dopo.",
     "source": "[FONTE: Linkup, 2026]"},
    {"code": "PR-1", "module": "Pricing & Unit Economics",
     "title": "Soglia prezzo minimo B2B SaaS per PMI italiane",
     "body": "Sotto 29 EUR/mese il prodotto e' percepito come accessorio e non entra nel "
             "workflow (churn >10%/mese). Sopra 199 EUR/mese cambia il decisore e il ciclo si "
             "allunga. ARPU sano per marketplace locali: 40-80 EUR/mese.",
     "source": "[FONTE: Linkup, 2026]"},
    {"code": "EXP-1", "module": "Go-to-market",
     "title": "L'espansione geografica accumula i ricavi, non li moltiplica",
     "body": "Da 1 a N citta' NON significa ricavi x N. Ogni citta' e' un cold start "
             "indipendente: 6-9 mesi per la massa critica, 1.500-2.500 EUR/mese di City "
             "Manager, CAC 20-40% piu' basso della prima citta'. Hub & Spoke > replicazione "
             "parallela.",
     "source": "[FONTE: Linkup, 2026]"},
    {"code": "RS-1", "module": "Resilienza",
     "title": "Il team minimo e' sempre piu' profittevole in Anno 1",
     "body": "Con revenue <200k EUR/anno, EBITDA positivo o negativo dipende dalla dimensione "
             "del team, non dal prodotto. Non assumere per un ruolo finche' il founder non e' "
             "fisicamente saturo (60+ h/settimana). Eccezione: il CTO tecnico e' co-founder, "
             "non dipendente.",
     "source": "[FONTE: Linkup, 2026]"},
]
