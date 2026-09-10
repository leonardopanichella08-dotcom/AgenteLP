"""Generazione dei deliverable A.I.R.S.:
- Piano Economico-Finanziario .xlsx con FORMULE VIVE (Google Fogli)
- Report / Analisi Narrativa in PDF (reportlab)
"""

from __future__ import annotations

import io
import re
from typing import Any

# ══════════════════════════════ XLSX ══════════════════════════════

# chiave assunzione -> (etichetta, default)
_ASSUMPTIONS: list[tuple[str, str, float]] = [
    ("prezzo_fee_mese_eur", "Prezzo / Platform fee al mese (EUR)", 8000.0),
    ("arpu_mese_eur", "ARPU netto per cliente al mese (EUR)", 1.2),
    ("cac_canale_a_eur", "CAC canale A / intermediario (EUR)", 110000.0),
    ("cac_canale_b_eur", "CAC canale B / diretto (EUR)", 200000.0),
    ("mix_canale_a", "Mix canale A (0-1)", 0.7),
    ("churn_annuo", "Churn annuo (0-1)", 0.1),
    ("anni_contratto", "Anni di contratto (LTV)", 5.0),
    ("clienti_anno1", "Clienti acquisiti Anno 1", 2.0),
    ("crescita_clienti_mensile_pct", "Crescita clienti mensile (%)", 8.0),
    ("stipendio_medio_annuo_eur", "Stipendio medio annuo per persona (EUR)", 55000.0),
    ("team_size", "Dimensione team", 3.0),
    ("infra_mese_eur", "Costi infrastruttura al mese (EUR)", 3000.0),
]


def build_xlsx(startup_name: str, assumptions: dict[str, Any]) -> bytes:
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill

    wb = Workbook()
    yellow = PatternFill("solid", fgColor="FFF2CC")
    bold = Font(bold=True)

    # ── 01_ASSUNZIONI ───────────────────────────────────────────
    a = wb.active
    a.title = "01_ASSUNZIONI"
    a["A1"] = f"ASSUNZIONI — {startup_name}"
    a["A1"].font = Font(bold=True, size=13)
    a["A3"], a["B3"] = "Parametro", "Valore"
    a["A3"].font = a["B3"].font = bold
    ref: dict[str, str] = {}
    row = 4
    for key, label, default in _ASSUMPTIONS:
        val = assumptions.get(key)
        try:
            val = float(val)
        except (TypeError, ValueError):
            val = default
        a[f"A{row}"] = label
        a[f"B{row}"] = round(val, 4)
        a[f"B{row}"].fill = yellow
        ref[key] = f"'01_ASSUNZIONI'!B{row}"
        row += 1
    a.column_dimensions["A"].width = 44
    a.column_dimensions["B"].width = 16

    # ── 02_REVENUE_MODEL (36 mesi) ──────────────────────────────
    r = wb.create_sheet("02_REVENUE_MODEL")
    r["A1"] = "REVENUE MODEL — 36 mesi"
    r["A1"].font = bold
    headers = ["Mese", "Clienti attivi", "MRR (EUR)", "ARR (EUR)"]
    for c, h in enumerate(headers, 1):
        r.cell(3, c, h).font = bold
    for m in range(1, 37):
        rr = 3 + m
        r.cell(rr, 1, m)
        if m == 1:
            r.cell(rr, 2, f"={ref['clienti_anno1']}/12")
        else:
            r.cell(rr, 2, f"=B{rr - 1}*(1+{ref['crescita_clienti_mensile_pct']}/100)"
                          f"*(1-{ref['churn_annuo']}/12)")
        r.cell(rr, 3, f"=B{rr}*({ref['prezzo_fee_mese_eur']}+{ref['arpu_mese_eur']})")
        r.cell(rr, 4, f"=C{rr}*12")
    for col in "ABCD":
        r.column_dimensions[col].width = 16

    # ── 03_COSTI_OPERATIVI (36 mesi) ────────────────────────────
    co = wb.create_sheet("03_COSTI_OPERATIVI")
    co["A1"] = "COSTI OPERATIVI — 36 mesi"
    co["A1"].font = bold
    for c, h in enumerate(["Mese", "Personale", "Infrastruttura", "Totale OPEX"], 1):
        co.cell(3, c, h).font = bold
    for m in range(1, 37):
        rr = 3 + m
        co.cell(rr, 1, m)
        co.cell(rr, 2, f"={ref['team_size']}*{ref['stipendio_medio_annuo_eur']}/12")
        co.cell(rr, 3, f"={ref['infra_mese_eur']}")
        co.cell(rr, 4, f"=B{rr}+C{rr}")
    for col in "ABCD":
        co.column_dimensions[col].width = 16

    # ── 04_UNIT_ECONOMICS ──────────────────────────────────────
    u = wb.create_sheet("04_UNIT_ECONOMICS")
    u["A1"] = "UNIT ECONOMICS"
    u["A1"].font = bold
    rows = [
        ("CAC ponderato (EUR)",
         f"={ref['mix_canale_a']}*{ref['cac_canale_a_eur']}"
         f"+(1-{ref['mix_canale_a']})*{ref['cac_canale_b_eur']}"),
        ("ARPU annuo per cliente (EUR)",
         f"=({ref['prezzo_fee_mese_eur']}+{ref['arpu_mese_eur']})*12"),
        ("LTV per cliente (EUR)",
         f"=B4*{ref['anni_contratto']}*(1-{ref['churn_annuo']})"),
        ("LTV / CAC", "=B5/B3"),
        ("Payback period (mesi)", "=B3/(B4/12)"),
    ]
    for i, (label, formula) in enumerate(rows, start=3):
        u.cell(i, 1, label)
        u.cell(i, 2, formula)
    u.column_dimensions["A"].width = 34
    u.column_dimensions["B"].width = 20

    # ── 05_CASHFLOW_36MESI ─────────────────────────────────────
    cf = wb.create_sheet("05_CASHFLOW_36MESI")
    cf["A1"] = "CASHFLOW — 36 mesi"
    cf["A1"].font = bold
    for c, h in enumerate(["Mese", "Ricavi", "OPEX", "Cashflow netto", "Cassa cumulata"], 1):
        cf.cell(3, c, h).font = bold
    for m in range(1, 37):
        rr = 3 + m
        cf.cell(rr, 1, m)
        cf.cell(rr, 2, f"='02_REVENUE_MODEL'!C{rr}")
        cf.cell(rr, 3, f"='03_COSTI_OPERATIVI'!D{rr}")
        cf.cell(rr, 4, f"=B{rr}-C{rr}")
        cf.cell(rr, 5, f"=D{rr}" if m == 1 else f"=E{rr - 1}+D{rr}")
    for col in "ABCDE":
        cf.column_dimensions[col].width = 16

    # ── 06_BREAKEVEN ───────────────────────────────────────────
    be = wb.create_sheet("06_BREAKEVEN")
    be["A1"] = "BREAK-EVEN"
    be["A1"].font = bold
    be["A3"] = "OPEX mensile (EUR)"
    be["B3"] = "='03_COSTI_OPERATIVI'!D4"
    be["A4"] = "Margine per cliente/mese (EUR)"
    be["B4"] = f"={ref['prezzo_fee_mese_eur']}+{ref['arpu_mese_eur']}"
    be["A5"] = "Clienti al break-even"
    be["B5"] = "=B3/B4"
    be["A6"] = "Mese di break-even (cassa cumulata >= 0)"
    be["B6"] = "=SUMPRODUCT(--('05_CASHFLOW_36MESI'!E4:E39<0))+1"
    be["A7"] = "Runway se non si raggiunge il break-even (mesi con cassa < 0)"
    be["B7"] = "=SUMPRODUCT(--('05_CASHFLOW_36MESI'!E4:E39<0))"
    be.column_dimensions["A"].width = 40
    be.column_dimensions["B"].width = 18

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


# ══════════════════════════════ PDF ══════════════════════════════


def build_pdf(title: str, markdown: str) -> bytes:
    from reportlab.lib.enums import TA_LEFT
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import (
        ListFlowable, ListItem, Paragraph, SimpleDocTemplate, Spacer,
    )

    styles = getSampleStyleSheet()
    body = ParagraphStyle("body", parent=styles["Normal"], fontSize=9.5, leading=14, alignment=TA_LEFT)
    h1 = ParagraphStyle("h1", parent=styles["Heading1"], fontSize=16, spaceBefore=6, spaceAfter=8)
    h2 = ParagraphStyle("h2", parent=styles["Heading2"], fontSize=12.5, spaceBefore=10, spaceAfter=4)
    h3 = ParagraphStyle("h3", parent=styles["Heading3"], fontSize=10.5, spaceBefore=8, spaceAfter=3)

    def esc(s: str) -> str:
        return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                .replace("**", "").replace("`", ""))

    story: list = [Paragraph(esc(title), h1), Spacer(1, 4 * mm)]
    bullets: list = []

    def flush_bullets() -> None:
        if bullets:
            story.append(ListFlowable(
                [ListItem(Paragraph(b, body), leftIndent=10) for b in bullets],
                bulletType="bullet", start="•",
            ))
            bullets.clear()

    for raw in markdown.splitlines():
        line = raw.rstrip()
        if not line:
            flush_bullets()
            story.append(Spacer(1, 2.5 * mm))
            continue
        if line.startswith("### "):
            flush_bullets(); story.append(Paragraph(esc(line[4:]), h3))
        elif line.startswith("## "):
            flush_bullets(); story.append(Paragraph(esc(line[3:]), h2))
        elif line.startswith("# "):
            flush_bullets(); story.append(Paragraph(esc(line[2:]), h2))
        elif re.match(r"^\s*[-*]\s+", line):
            bullets.append(esc(re.sub(r"^\s*[-*]\s+", "", line)))
        elif line.startswith("|"):
            cells = [c.strip() for c in line.strip("|").split("|")]
            if set("".join(cells)) <= set("-: "):
                continue
            bullets.append(esc(" · ".join(c for c in cells if c)))
        else:
            flush_bullets(); story.append(Paragraph(esc(line), body))
    flush_bullets()

    buf = io.BytesIO()
    SimpleDocTemplate(
        buf, pagesize=A4, topMargin=18 * mm, bottomMargin=18 * mm,
        leftMargin=18 * mm, rightMargin=18 * mm, title=title,
    ).build(story)
    return buf.getvalue()
