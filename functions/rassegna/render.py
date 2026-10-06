"""Genera l'email della Rassegna (HTML + testo semplice) da un file JSON.

Uso:  python3 render.py rassegna.json [cartella_output]
Scrive email.html e email.txt (default: /tmp/rassegna/).

Layout a tabelle con un unico blocco <style> a classi: Gmail (web e app, su
account Gmail) supporta gli stili nell'<head>, e così l'HTML resta leggero
da passare a send_message. Niente variabili CSS: Gmail non le supporta.
Schema del JSON: vedi PROMPT.md.
"""
import html
import json
import os
import re
import sys

# Colonna unica da 600px: testata scura, indice, poi una scheda per articolo.
CATEGORIES = {
    # chiave: (etichetta, classe colore)
    "economia": ("Economia", "eco"),
    "startup": ("Startup & Business", "stu"),
    "tech": ("Tech & AI", "tec"),
    "chora": ("Storie & Cultura", "cho"),
}

CSS = """
body{margin:0;padding:0;background:#ECEFF3}
table{border-collapse:collapse}
td{font-family:-apple-system,Roboto,Helvetica,Arial,sans-serif;color:#141B26}
.wrap{background:#ECEFF3}
.page{width:100%;max-width:600px;background:#FFFFFF;border-radius:10px}
.mast{background:#141B26;padding:30px 24px 28px;border-radius:10px 10px 0 0}
.eyebrow{margin:0 0 14px;font-size:11px;line-height:1;font-weight:700;letter-spacing:2px;text-transform:uppercase;color:#8FA3BC}
.hello{margin:0;font-size:34px;line-height:1.1;font-weight:800;letter-spacing:-0.8px;color:#FFFFFF}
.sub{margin:10px 0 0;font-size:15px;line-height:1.4;color:#8FA3BC}
.intro{margin:16px 0 0;font-family:Charter,Georgia,serif;font-size:17px;line-height:1.55;color:#C9D2DE}
.sec{padding:26px 24px 30px}
.label{margin:0 0 6px;font-size:12px;line-height:1;font-weight:700;letter-spacing:1.2px;text-transform:uppercase;color:#141B26}
.ix-n{padding:10px 0;font-size:13px;line-height:1.4;font-weight:700;width:30px}
.ix-t{padding:10px 0;border-bottom:1px solid #E1E6EC}
.ix-h{font-size:15px;line-height:1.4;font-weight:600;color:#141B26}
.ix-s{font-size:13px;line-height:1.5;color:#5E6A7A}
.ix-m{padding:10px 0 10px 8px;border-bottom:1px solid #E1E6EC;font-size:13px;line-height:1.4;color:#5E6A7A;width:40px}
.story{padding:34px 24px;border-top:1px solid #E1E6EC}
.kick{padding:0 0 10px;font-size:11px;line-height:1;font-weight:700;letter-spacing:1.4px;text-transform:uppercase}
.title{padding:0 0 8px;font-size:24px;line-height:1.22;font-weight:700;letter-spacing:-0.3px;color:#141B26}
.meta{padding:0 0 18px;font-size:13px;line-height:1.4;color:#5E6A7A}
.img{padding:4px 0 18px}
.img img{display:block;width:100%;max-width:552px;height:auto;border:0;border-radius:6px;background:#E1E6EC}
.cap{margin:8px 0 0;font-size:13px;line-height:1.45;color:#5E6A7A}
.dek{padding:0 0 14px;font-family:Charter,Georgia,serif;font-size:19px;line-height:1.55;color:#141B26}
.p{padding:0 0 14px;font-family:Charter,Georgia,serif;font-size:17px;line-height:1.62;color:#2A3340}
.h3{padding:10px 0 8px;font-size:18px;line-height:1.3;font-weight:700;color:#141B26}
.pts{padding:8px 0}
.dot{padding:0 0 10px;font-size:17px;line-height:1.55;font-weight:700;width:22px}
.pt{padding:0 0 10px;font-size:16px;line-height:1.55;color:#2A3340}
.why{border-radius:6px;padding:16px 18px}
.why-l{margin:0 0 6px;font-size:12px;line-height:1;font-weight:700;letter-spacing:1.2px;text-transform:uppercase}
.why-t{margin:0;font-size:16px;line-height:1.55;color:#141B26}
.btn{display:inline-block;margin:0 6px 8px 0;padding:11px 18px;border:1.5px solid;border-radius:6px;font-size:14px;line-height:1;font-weight:600;text-decoration:none}
.foot{padding:22px 24px 26px;border-top:1px solid #E1E6EC;font-size:13px;line-height:1.55;color:#5E6A7A}
.eco{color:#0E7A5A;border-color:#0E7A5A}.eco-bg{background:#E8F4EF}
.stu{color:#2847C9;border-color:#2847C9}.stu-bg{background:#ECEFFC}
.tec{color:#7339C6;border-color:#7339C6}.tec-bg{background:#F2ECFB}
.cho{color:#B4440F;border-color:#B4440F}.cho-bg{background:#FBEFE8}
strong{color:#141B26}
@media (max-width:480px){.hello{font-size:30px}.title{font-size:22px}.story,.sec,.mast,.foot{padding-left:20px;padding-right:20px}}
"""


def esc(s):
    """Escape HTML ma consente **grassetto** e _corsivo_ in stile markdown."""
    s = html.escape(s or "", quote=False)
    s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)
    s = re.sub(r"(?<![\w/])_(.+?)_(?![\w/])", r"<em>\1</em>", s)
    return s


def attr(s):
    return html.escape(s or "", quote=True)


def plain(s):
    return re.sub(r"\*\*(.+?)\*\*", r"\1", s or "")


def cat(s):
    return CATEGORIES.get(s.get("category"), CATEGORIES["tech"])


def tr(cls, inner):
    return f'<tr><td class="{cls}">{inner}</td></tr>'


def image_block(img):
    if not img or not img.get("src"):
        return ""
    cap = f'<p class="cap">{esc(img["caption"])}</p>' if img.get("caption") else ""
    return tr("img", f'<img src="{attr(img["src"])}" alt="{attr(img.get("alt") or img.get("caption"))}" width="552">{cap}')


def story_block(i, s):
    label, c = cat(s)
    meta = [esc(s.get("source"))]
    if s.get("translated"):
        meta.append("tradotto dall'inglese")
    if s.get("read_min"):
        meta.append(f'{int(s["read_min"])} min di lettura')

    rows = [
        tr(f"kick {c}", f"{i:02d}&nbsp; {label}"),
        tr("title", esc(s.get("title"))),
        tr("meta", " &nbsp;·&nbsp; ".join(meta)),
        image_block(s.get("image")),
    ]
    if s.get("dek"):
        rows.append(tr("dek", esc(s["dek"])))
    for para in s.get("body") or []:
        if isinstance(para, dict):  # immagine nel punto esatto del testo
            rows.append(image_block(para))
        elif para.startswith("## "):  # sottotitolo di sezione
            rows.append(tr("h3", esc(para[3:])))
        else:
            rows.append(tr("p", esc(para)))
    for img in s.get("images") or []:
        rows.append(image_block(img))

    if s.get("points"):
        li = "".join(
            f'<tr><td valign="top" class="dot {c}">&#8226;</td><td class="pt">{esc(p)}</td></tr>' for p in s["points"]
        )
        rows.append('<tr><td class="label" style="padding-top:4px">Punti chiave</td></tr>')
        rows.append(tr("pts", f'<table role="presentation" width="100%">{li}</table>'))
    if s.get("why"):
        rows.append(
            tr("", f'<table role="presentation" width="100%" style="margin-top:10px"><tr><td class="why {c}-bg">'
                   f'<p class="why-l {c}">Perché ti interessa</p><p class="why-t">{esc(s["why"])}</p></td></tr></table>')
        )
    links = s.get("links") or ([{"url": s["url"], "label": s.get("url_label")}] if s.get("url") else [])
    if links:
        btns = "".join(
            f'<a class="btn {c}" href="{attr(l["url"])}">{esc(l.get("label") or "Leggi l’originale")} &rarr;</a>'
            for l in links
        )
        rows.append(f'<tr><td style="padding-top:18px">{btns}</td></tr>')
    return tr("story", f'<table role="presentation" width="100%">{"".join(rows)}</table>')


def index_block(stories):
    rows = []
    for i, s in enumerate(stories, 1):
        label, c = cat(s)
        mins = f'{int(s["read_min"])}&#8242;' if s.get("read_min") else ""
        rows.append(
            f'<tr><td valign="top" class="ix-n {c}">{i:02d}</td>'
            f'<td class="ix-t"><span class="ix-h">{esc(s.get("title"))}</span><br>'
            f'<span class="ix-s">{esc(s.get("source"))} · {label}</span></td>'
            f'<td valign="top" align="right" class="ix-m">{mins}</td></tr>'
        )
    return tr("sec", f'<p class="label">In questo numero</p><table role="presentation" width="100%">{"".join(rows)}</table>')


def render_html(d):
    stories = d.get("stories") or []
    total = sum(int(s.get("read_min") or 0) for s in stories)
    sub = f"{len(stories)} letture · {total} minuti" if stories else "Nessuna nuova uscita"
    preheader = d.get("preheader") or " · ".join(s.get("title", "") for s in stories[:3])
    intro = f'<p class="intro">{esc(d["intro"])}</p>' if d.get("intro") else ""
    head = tr(
        "mast",
        f'<p class="eyebrow">{esc(d.get("date_label"))}</p><p class="hello">Buongiorno, Leonardo.</p>'
        f'<p class="sub">{sub}</p>{intro}',
    )
    if stories:
        body = index_block(stories) + "".join(story_block(i, s) for i, s in enumerate(stories, 1))
    else:
        body = tr("sec p", "Nelle ultime 24 ore non è arrivata nessuna nuova uscita dalle tue newsletter. Ci sentiamo domani.")
    note = esc(d.get("excluded_note"))
    foot = tr(
        "foot",
        f'{note}{"<br><br>" if note else ""}Riassunti scritti da Claude a partire dalle newsletter che ricevi. '
        "Per cambiare fonti o formato, chiedilo nella sessione della Rassegna.",
    )
    css = re.sub(r"\s*\n\s*", "", CSS)
    return (
        '<!doctype html><html lang="it"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<meta name="color-scheme" content="light"><meta name="supported-color-schemes" content="light">'
        f"<title>Rassegna mattutina</title><style>{css}</style></head><body>"
        f'<div style="display:none;max-height:0;overflow:hidden">{esc(preheader)}</div>'
        '<table role="presentation" width="100%" class="wrap"><tr><td align="center" style="padding:20px 10px 32px">'
        f'<table role="presentation" width="600" class="page">{head}{body}{foot}</table>'
        "</td></tr></table></body></html>"
    )


def render_text(d):
    out = [f"RASSEGNA MATTUTINA · {d.get('date_label','')}", ""]
    if d.get("intro"):
        out += [plain(d["intro"]), ""]
    stories = d.get("stories") or []
    for i, s in enumerate(stories, 1):
        out.append(f"{i:02d}. {plain(s.get('title'))} ({s.get('source')})")
    for i, s in enumerate(stories, 1):
        label = cat(s)[0]
        out += ["", "─" * 40,
                f"{i:02d} · {label.upper()} · {s.get('source')}" + (" (tradotto)" if s.get("translated") else ""),
                plain(s.get("title")), ""]
        if s.get("dek"):
            out += [plain(s["dek"]), ""]
        for p in s.get("body") or []:
            if isinstance(p, str):
                out += [plain(p[3:].upper() if p.startswith("## ") else p), ""]
        for p in s.get("points") or []:
            out.append(f"• {plain(p)}")
        if s.get("why"):
            out += ["", f"Perché ti interessa: {plain(s['why'])}"]
        for l in s.get("links") or ([{"url": s["url"]}] if s.get("url") else []):
            out.append(l["url"])
    if d.get("excluded_note"):
        out += ["", plain(d["excluded_note"])]
    return "\n".join(out).strip() + "\n"


def main():
    src = sys.argv[1]
    outdir = sys.argv[2] if len(sys.argv) > 2 else "/tmp/rassegna"
    os.makedirs(outdir, exist_ok=True)
    d = json.load(open(src, encoding="utf-8"))
    h = render_html(d)
    open(os.path.join(outdir, "email.html"), "w", encoding="utf-8").write(h)
    open(os.path.join(outdir, "email.txt"), "w", encoding="utf-8").write(render_text(d))
    print(f"OK email.html {len(h)} caratteri, {len(d.get('stories') or [])} articoli")


if __name__ == "__main__":
    main()
