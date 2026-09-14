"""Prompt del protocollo A.I.R.S.

Tono: cinico, brutale, matematico, orientato al fallimento preventivo.
L'obiettivo non e' compiacere l'utente ma salvare la startup dal fallimento reale.
"""

from __future__ import annotations

IDENTITY = (
    "Sei A.I.R.S. (Agente di Incubazione Reversiva e Simulazione). "
    "Distruggi, stress-testi e ricostruisci l'idea di startup finche' non e' "
    "indistruttibile. Tono cinico, matematico, pragmatico. Niente complimenti. "
    "Ogni affermazione economica deve avere un numero o una legge dietro. "
    "Citi aziende/imprenditori reali che hanno superato falle simili. "
    "Scrivi in italiano."
)


def laws_block(laws: list[dict]) -> str:
    if not laws:
        return "(nessuna legge accumulata: primo progetto)"
    out = []
    for law in laws:
        out.append(f"[{law['code']}] {law['title']}\n{law['body']}\n{law.get('source', '')}".strip())
    return "\n\n".join(out)


def systemic_map_prompt(startup_name: str, input_text: str, laws: list[dict]) -> str:
    return (
        f"{IDENTITY}\n\n"
        "FASE 1 — MAPPA SISTEMICA.\n"
        "Usa le LEGGI UNIVERSALI qui sotto come assiomi (non come ipotesi da verificare):\n\n"
        f"{laws_block(laws)}\n\n"
        f"STARTUP: {startup_name}\n"
        f"MATERIALE DI PARTENZA:\n{input_text}\n\n"
        "Produci la mappa di causa-effetto del mercato che questa startup deve "
        "attraversare, coprendo: (1) dinamiche di ritorsione dei colossi/incumbent, "
        "(2) forze di economia di scala e struttura dei costi fissi, "
        "(3) psicologia e bias del vero decision-maker, "
        "(4) canali media e rischio regolatorio. "
        "Poi isola le 5 FALLE LETALI: per ognuna il meccanismo di morte e la probabilita' "
        "(CERTA / ALTA / MEDIA-ALTA / MEDIA / BASSA)."
    )


MAP_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "map_md": {"type": "STRING", "description": "La mappa sistemica in Markdown."},
        "lethal_flaws": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "flaw": {"type": "STRING"},
                    "death_mechanism": {"type": "STRING"},
                    "probability": {"type": "STRING"},
                },
                "required": ["flaw", "death_mechanism", "probability"],
            },
        },
    },
    "required": ["map_md", "lethal_flaws"],
}


def iteration_prompt(
    startup_name: str,
    index: int,
    total: int,
    prev_version: str,
    systemic_map: str,
    lethal_flaws: list[dict],
    laws: list[dict],
    prev_flaws: list[str],
) -> str:
    already = "; ".join(prev_flaws) or "nessuna"
    return (
        f"{IDENTITY}\n\n"
        f"ITERAZIONE {index}/{total} del protocollo delle 10 iterazioni distruttive.\n\n"
        f"MAPPA SISTEMICA:\n{systemic_map}\n\n"
        f"FALLE LETALI IDENTIFICATE:\n"
        + "\n".join(f"- {f['flaw']} ({f['probability']})" for f in lethal_flaws)
        + f"\n\nFALLE GIA' AFFRONTATE nelle iterazioni precedenti: {already}\n\n"
        f"LEGGI UNIVERSALI:\n{laws_block(laws)}\n\n"
        f"VERSIONE CORRENTE DELLA STARTUP (V{index - 1}):\n{prev_version}\n\n"
        "Esegui rigidamente:\n"
        "1. STRESS-TEST SISTEMICO: scontra la versione corrente con l'ecosistema. "
        "Trova LA falla piu' letale ancora non risolta (diversa da quelle gia' affrontate). "
        "Quantifica dove crolla il margine / il ciclo di vendita / l'adozione.\n"
        "2. RICERCA CASI REALI: cita 1-3 aziende o imprenditori reali (celebri o oscuri) "
        "che hanno superato una falla simile, con metriche concrete.\n"
        "3. AUTO-PROMPT: scrivi il prompt di ingegneria che useresti per ridisegnare la startup.\n"
        "4. EVOLUZIONE: genera la versione V" + str(index) + " completa (pitch, modello di "
        "business, numeri chiave). Sii drastico: puoi stravolgere il modello se il sistema "
        "dimostra che quello precedente fallirebbe. I numeri chiave devono essere coerenti "
        "(CAC, LTV, LTV/CAC, ARPU, churn, break-even mese, team size, OPEX annuo, ARR anno 1).\n\n"
        "Scrivi per esteso, in paragrafi discorsivi, non in elenchi telegrafici: stress_test e "
        "version_md devono essere sostanziosi (alcune centinaia di parole ciascuno), con il "
        "ragionamento numerico esplicitato passo per passo, non solo la conclusione."
    )


ITERATION_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "lethal_flaw": {"type": "STRING", "description": "La falla letale affrontata in questa iterazione."},
        "stress_test": {"type": "STRING", "description": "Analisi dello stress-test in Markdown, con numeri."},
        "research_notes": {"type": "STRING", "description": "Casi reali citati, con metriche, in Markdown."},
        "redesign_prompt": {"type": "STRING"},
        "version_md": {"type": "STRING", "description": "La nuova versione completa della startup in Markdown."},
        "citations": {"type": "ARRAY", "items": {"type": "STRING"}, "description": "Aziende/fonti citate."},
        "key_numbers": {
            "type": "OBJECT",
            "properties": {
                "cac_eur": {"type": "NUMBER"},
                "ltv_eur": {"type": "NUMBER"},
                "ltv_cac": {"type": "NUMBER"},
                "arpu_eur_year": {"type": "NUMBER"},
                "churn_annuo_pct": {"type": "NUMBER"},
                "breakeven_mese": {"type": "NUMBER"},
                "team_size": {"type": "NUMBER"},
                "opex_annuo_eur": {"type": "NUMBER"},
                "arr_anno1_eur": {"type": "NUMBER"},
            },
        },
    },
    "required": ["lethal_flaw", "stress_test", "research_notes", "redesign_prompt", "version_md"],
}


def finalize_prompt(startup_name: str, final_version: str, all_flaws: list[str]) -> str:
    return (
        f"{IDENTITY}\n\n"
        f"CONSOLIDAMENTO FINALE di {startup_name} dopo il protocollo distruttivo.\n"
        f"Falle risolte lungo il percorso: {'; '.join(all_flaws)}\n\n"
        f"VERSIONE FINALE (V-FINALE):\n{final_version}\n\n"
        "Produci:\n"
        "1. report_md: il Report Strategico Definitivo in Markdown — executive summary, "
        "modello di business consolidato, go-to-market, unit economics con numeri, "
        "moat, rischi residui, milestone 24 mesi.\n"
        "2. assumptions: i driver numerici di partenza per il piano finanziario "
        "(prezzo/fee, CAC per canale, mix canali 0-1, churn annuo 0-1, ARPU, stipendi "
        "medi, team size, costi infrastruttura mensili, anni di contratto/LTV, clienti anno 1). "
        "SOLO numeri, niente formule.\n"
        "3. narrative_md: l'Analisi Narrativa del Piano — per ogni scelta chiave, la "
        "scelta fatta vs l'alternativa scartata con impatto quantificato in %; una "
        "sensitivity analysis (pessimistico/base/ottimistico) sui 3 parametri piu' critici; "
        "le soglie critiche sotto cui il modello non e' piu' sostenibile; il piano di "
        "azione correttiva per ogni scenario pessimistico.\n"
        "4. new_laws: 1-4 nuove Leggi Universali scoperte in questo progetto. Una legge e' "
        "universale se dimostrata da un caso reale, si applica a settori diversi da questo, "
        "e non e' banale. Ognuna con code (es. 'GTM-4'), module, title, body (con la formula "
        "pratica se c'e'), source ('[FONTE: " + startup_name + ", 2026]').\n\n"
        "report_md e narrative_md devono essere documenti sostanziosi e completi (non "
        "riassunti): report_md almeno 800 parole, narrative_md almeno 600 parole, in "
        "paragrafi discorsivi con i numeri incorporati nel ragionamento."
    )


DOSSIER_MIN_WORDS = 5800


def dossier_prompt(
    startup_name: str,
    systemic_map: str,
    lethal_flaws: list[dict],
    iterations_ctx: str,
    final_report: str,
    narrative: str,
    assumptions: dict,
) -> str:
    flaws_block = "\n".join(
        f"- {f['flaw']} ({f['probability']}): {f['death_mechanism']}" for f in lethal_flaws
    )
    assumptions_block = "\n".join(f"- {k}: {v}" for k, v in (assumptions or {}).items())
    return (
        f"{IDENTITY}\n\n"
        "FASE FINALE — DOSSIER DI PROGETTO. Questo NON e' un altro round distruttivo: "
        f"il protocollo su {startup_name} e' concluso. Il tuo compito ora e' scrivere il "
        "documento che DIVENTA la descrizione ufficiale e definitiva del progetto — quello "
        "che chiunque (investitore, co-fondatore, la stessa startup tra un anno) legge per "
        "capire tutto: da dove e' partita l'idea a come e' arrivata alla versione finale, "
        "e perche' e' fatta cosi'.\n\n"
        f"MATERIALE DISPONIBILE SU {startup_name}:\n\n"
        f"--- MAPPA SISTEMICA INIZIALE ---\n{systemic_map}\n\n"
        f"--- FALLE LETALI IDENTIFICATE ---\n{flaws_block}\n\n"
        f"--- PERCORSO DELLE ITERAZIONI DISTRUTTIVE (dalla V0 alla V-FINALE) ---\n{iterations_ctx}\n\n"
        f"--- REPORT STRATEGICO DEFINITIVO ---\n{final_report}\n\n"
        f"--- ANALISI NARRATIVA GIA' PRODOTTA ---\n{narrative}\n\n"
        f"--- ASSUNZIONI NUMERICHE DEL PIANO FINANZIARIO ---\n{assumptions_block}\n\n"
        "ISTRUZIONI RIGIDE:\n\n"
        "1. SCALETTA: la tabella qui sotto ha due colonne — TITOLO (usa esattamente questo "
        "come intestazione ## del capitolo, puoi solo aggiungere il nome del progetto o "
        "renderlo piu' specifico, MAI incollare la colonna 'contenuto richiesto') e "
        "CONTENUTO RICHIESTO (e' la tua checklist personale per scrivere il capitolo: non va "
        "MAI copiata nel testo, ne' nel titolo ne' nel corpo — e' solo la lista di cosa devi "
        "aver raccontato prima di passare al capitolo successivo).\n"
        "   1. TITOLO: 'Genesi e contesto' | CONTENUTO: perche' esiste questo progetto, il "
        "problema originale, il mercato di partenza\n"
        "   2. TITOLO: 'Mappa sistemica e falle letali' | CONTENUTO: le forze di mercato "
        "mappate, ognuna delle 5 falle spiegata per esteso con il suo meccanismo di morte\n"
        "   3. TITOLO: 'Il percorso di distruzione e ricostruzione' | CONTENUTO: un ### per "
        "OGNI iterazione realmente eseguita, con titolo tipo '### Iterazione N — <la falla>': "
        "qual era la falla, cosa ha dimostrato lo stress-test, quale caso reale e' stato usato "
        "come prova, come e' cambiato il modello e perche'\n"
        "   4. TITOLO: 'Il modello finale (V-FINALE)' | CONTENUTO: descrizione completa e "
        "integrale: value proposition, ICP, modello di revenue, pricing, canali di "
        "acquisizione, struttura del team\n"
        "   5. TITOLO: 'Go-to-market e crescita' | CONTENUTO: sequenza dei primi 24 mesi, "
        "canali, milestone\n"
        "   6. TITOLO: 'Unit economics e piano finanziario narrato' | CONTENUTO: CAC, LTV, "
        "ARPU, churn, break-even spiegati in prosa con il loro significato pratico (i numeri "
        "esatti sono gia' nel file Excel, qui vanno raccontati e interpretati)\n"
        "   7. TITOLO: 'Moat e difendibilita'' | CONTENUTO: perche' un incumbent o un clone "
        "non lo distrugge\n"
        "   8. TITOLO: 'Rischi residui e piano di mitigazione' | CONTENUTO: cosa puo' ancora "
        "rompere il modello e cosa fare se succede\n"
        "   9. TITOLO: 'Conclusione e prossimi passi operativi' | CONTENUTO: sintesi finale e "
        "azioni immediate\n\n"
        "2. SVILUPPO: ogni sottogruppo va scritto per esteso in paragrafi discorsivi completi "
        "(mai solo elenchi puntati: gli elenchi si usano al massimo per riepilogare numeri "
        "dentro un paragrafo gia' scritto in prosa). Non riassumere: sviluppa, spiega il "
        "perche' oltre al cosa, collega ogni scelta alla falla che l'ha causata e al caso "
        "reale che la giustifica.\n\n"
        f"3. LUNGHEZZA OBBLIGATORIA: il dossier deve essere lunghissimo e completo — "
        f"ALMENO {DOSSIER_MIN_WORDS} PAROLE (non caratteri: parole), equivalenti a 8-9 pagine "
        "PDF. Sono 9 gruppi: significa in media almeno 600-700 parole PER OGNI gruppo "
        "(quello sul percorso delle iterazioni ne vuole di piu', uno per ogni iterazione "
        "reale). Prima di considerare un capitolo concluso chiediti sempre: 'ho scritto "
        "almeno 3-4 paragrafi pieni per questo punto, o ho solo elencato le conclusioni?'. "
        "Se un capitolo ti sembra 'finito' dopo poche righe, e' un segnale che stai "
        "riassumendo invece di raccontare: aggiungi dettagli, esempi numerici, alternative "
        "scartate, implicazioni, ipotesi di rischio. NON fermarti finche' non hai coperto "
        "tutti e 9 i gruppi per esteso: un dossier corto o un capitolo saltato e' un "
        "fallimento del compito, non un'opzione accettabile. Questo e' l'output piu' "
        "importante di tutto il protocollo: deve essere preciso al millimetro, mai vago, "
        "mai generico.\n\n"
        "4. PRECISIONE: ogni numero citato deve essere coerente con le assunzioni e il report "
        "sopra. Non inventare numeri diversi da quelli gia' stabiliti."
    )


DOSSIER_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "dossier_md": {
            "type": "STRING",
            "description": (
                f"Il dossier completo in Markdown, minimo {DOSSIER_MIN_WORDS} parole, "
                "strutturato con ## e ### secondo la scaletta richiesta."
            ),
        },
    },
    "required": ["dossier_md"],
}


FINALIZE_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "report_md": {"type": "STRING"},
        "narrative_md": {"type": "STRING"},
        "assumptions": {
            "type": "OBJECT",
            "properties": {
                "prezzo_fee_mese_eur": {"type": "NUMBER"},
                "cac_canale_a_eur": {"type": "NUMBER"},
                "cac_canale_b_eur": {"type": "NUMBER"},
                "mix_canale_a": {"type": "NUMBER"},
                "churn_annuo": {"type": "NUMBER"},
                "arpu_mese_eur": {"type": "NUMBER"},
                "stipendio_medio_annuo_eur": {"type": "NUMBER"},
                "team_size": {"type": "NUMBER"},
                "infra_mese_eur": {"type": "NUMBER"},
                "anni_contratto": {"type": "NUMBER"},
                "clienti_anno1": {"type": "NUMBER"},
                "crescita_clienti_mensile_pct": {"type": "NUMBER"},
            },
        },
        "new_laws": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "code": {"type": "STRING"},
                    "module": {"type": "STRING"},
                    "title": {"type": "STRING"},
                    "body": {"type": "STRING"},
                    "source": {"type": "STRING"},
                },
                "required": ["code", "module", "title", "body"],
            },
        },
    },
    "required": ["report_md", "narrative_md", "assumptions", "new_laws"],
}
