"""Genera l'email della Rassegna (HTML + testo semplice) da un file JSON.

Uso:  python3 render.py rassegna.json [cartella_output] [--no-images]
Scrive email.html e email.txt (default: /tmp/rassegna/).

Stile: newsletter "lifestyle" (cielo azzurro sfumato, titoli grandi e leggeri con
una parola in grassetto, immagini a tutta larghezza, schede bianche arrotondate su
fasce colorate, pulsanti a pillola). Layout a tabelle con un blocco <style> a classi:
Gmail (web e app, su account Gmail) lo supporta. Niente variabili CSS né margini
negativi, che Gmail scarta. Schema del JSON: vedi PROMPT.md.
"""
import html
import json
import os
import re
import sys
from html.parser import HTMLParser

# Colonna da 600px. Testata a cielo con copertina del giorno, poi indice su fondo
# chiaro, poi una fascia colorata per articolo con immagine e scheda bianca.
CATEGORIES = {
    # chiave: (etichetta, classe)
    "economia": ("Economia", "eco"),
    "startup": ("Startup & Business", "stu"),
    "tech": ("Tech & AI", "tec"),
    "chora": ("Storie & Cultura", "cho"),
}

CSS = """
body{margin:0;padding:0;background:#DDE7F1}
table{border-collapse:collapse}

.wrap{background:#DDE7F1;font-family:Helvetica,Arial,sans-serif;color:#16202C}
.page{font-family:Helvetica,Arial,sans-serif;width:100%;max-width:600px;background:#FFFFFF;border-radius:18px;overflow:hidden}
.sky{background:#7FA7D0;text-align:center}
.brand{padding:26px 28px 0;font-size:12px;line-height:1;font-weight:600;letter-spacing:3.5px;text-transform:uppercase;color:#FFFFFF}
.date{padding:8px 28px 0;font-size:12px;line-height:1;letter-spacing:1.5px;text-transform:uppercase;color:#E7F0F8}
.hl{padding:30px 30px 0;font-size:36px;line-height:1.08;font-weight:300;letter-spacing:-1.2px;color:#FFFFFF}
.hl strong{font-weight:700;color:#FFFFFF}
.lede{padding:16px 44px 0;font-size:16px;line-height:1.5;color:#F2F7FC}
.stat{padding:22px 28px 26px}
.pill{display:inline-block;padding:9px 18px;border-radius:999px;background:#FFFFFF;font-size:12px;line-height:1;font-weight:600;letter-spacing:1.2px;text-transform:uppercase;color:#34618F;text-decoration:none}
.hero img{display:block;width:100%;max-width:600px;height:auto;border:0}
.hcap{padding:10px 28px 0;font-size:12px;line-height:1.4;color:#6B7A8A;text-align:center}
.ix{padding:40px 28px 34px;text-align:center}
.h2{margin:0;font-size:30px;line-height:1.12;font-weight:300;letter-spacing:-0.8px;color:#16202C}
.h2 strong{font-weight:700}
.ixl{padding:22px 0 0}
.ixr{padding:15px 0;border-bottom:1px solid #E4E9EF;text-align:left}
.ixn{padding:15px 14px 15px 0;border-bottom:1px solid #E4E9EF;font-size:12px;line-height:1.5;font-weight:700;letter-spacing:1px;width:26px;vertical-align:top}
.ixh{font-size:16px;line-height:1.35;font-weight:600;color:#16202C}
.ixs{font-size:12px;line-height:1.6;letter-spacing:0.6px;text-transform:uppercase;color:#7A8796}
.ixm{padding:15px 0 15px 10px;border-bottom:1px solid #E4E9EF;font-size:13px;line-height:1.5;color:#7A8796;width:36px;text-align:right;vertical-align:top}
.band{padding:44px 16px 40px}
.head{padding:0 18px 22px;text-align:center}
.kick{margin:0 0 12px;font-size:11px;line-height:1;font-weight:700;letter-spacing:2.6px;text-transform:uppercase}
.title{margin:0;font-size:31px;line-height:1.12;font-weight:300;letter-spacing:-0.8px;color:#16202C}
.title strong{font-weight:700}
.src{margin:12px 0 0;font-size:12px;line-height:1.4;letter-spacing:1px;text-transform:uppercase;color:#6B7A8A}
.cover img{display:block;width:100%;max-width:568px;height:auto;border:0;border-radius:16px}
.card{background:#FFFFFF;border-radius:16px;padding:28px 24px 26px}
.dek{padding:0 0 18px;font-size:19px;line-height:1.5;font-weight:400;color:#16202C}
.h3{padding:12px 0 10px;font-size:13px;line-height:1.3;font-weight:700;letter-spacing:1.6px;text-transform:uppercase}
.rule{border-top:1px solid #DCE3EA;padding:0 0 6px}
.p{padding:0 0 15px;font-family:Charter,Georgia,serif;font-size:17px;line-height:1.65;color:#2B3542}
.p strong{font-family:Helvetica,Arial,sans-serif;font-weight:700;color:#16202C}
.img{padding:6px 0 20px}
.img img{display:block;width:100%;max-width:520px;height:auto;border:0;border-radius:12px}
.cap{margin:8px 0 0;font-size:13px;line-height:1.45;color:#6B7A8A}
.pth{padding:14px 0 4px;font-size:13px;line-height:1.3;font-weight:700;letter-spacing:1.6px;text-transform:uppercase}
.pt{padding:12px 0;border-bottom:1px solid #E4E9EF;font-size:16px;line-height:1.5;color:#2B3542}
.pt strong{color:#16202C}
.why{padding:22px 0 0}
.whyb{border-radius:14px;padding:20px 20px}
.whyl{margin:0 0 8px;font-size:11px;line-height:1;font-weight:700;letter-spacing:2.2px;text-transform:uppercase}
.whyt{margin:0;font-size:16px;line-height:1.55;color:#16202C}
.cta{padding:28px 0 0;text-align:center}
.btn{display:inline-block;margin:0 4px 10px;padding:14px 26px;border-radius:999px;font-size:12px;line-height:1;font-weight:700;letter-spacing:1.6px;text-transform:uppercase;color:#FFFFFF;text-decoration:none}
.foot{background:#16202C;padding:34px 30px 38px;text-align:center}
.fh{margin:0 0 10px;font-size:22px;line-height:1.2;font-weight:300;color:#FFFFFF}
.fh strong{font-weight:700}
.ft{margin:0;font-size:13px;line-height:1.6;color:#A9B6C4}
.eco-bg{background:#E3ECE5}.eco{color:#2E5E47}.eco-btn{background:#2E5E47}.eco-why{background:#F1F6F2}
.stu-bg{background:#E1EAF4}.stu{color:#2F5E8E}.stu-btn{background:#2F5E8E}.stu-why{background:#EFF4FA}
.tec-bg{background:#EAE6E1}.tec{color:#4B5A73}.tec-btn{background:#4B5A73}.tec-why{background:#F5F2EE}
.cho-bg{background:#EFE3DA}.cho{color:#9A5636}.cho-btn{background:#9A5636}.cho-why{background:#F8F0EA}
@media (max-width:480px){.hl{font-size:34px;padding-left:22px;padding-right:22px}.lede{padding-left:24px;padding-right:24px}.title{font-size:27px}.h2{font-size:26px}.band{padding-left:10px;padding-right:10px}.card{padding:24px 18px 22px}.ix{padding-left:20px;padding-right:20px}}
"""


class _Inliner(HTMLParser):
    """Copia le regole CSS a classi dentro l'attributo style di ogni elemento.

    Il connettore Gmail elimina <style> e gli attributi class: solo lo style
    inline sopravvive. Supporta selettori `.a` e `.a tag` (discendente).
    """

    def __init__(self, rules):
        super().__init__(convert_charrefs=False)
        self.rules, self.out, self.stack = rules, [], []

    def _style(self, tag, classes):
        decl = []
        for sel, body in self.rules:
            parts = sel.split()
            if len(parts) == 1 and parts[0] == tag:
                decl.insert(0, body)
            elif len(parts) == 1 and parts[0][1:] in classes:
                decl.append(body)
            elif len(parts) == 2 and parts[1] == tag and any(parts[0][1:] in c for c in self.stack):
                decl.append(body)
        css = ";".join(decl)
        css = re.sub(r"(^|;)background:", r"\1background-color:", css)
        return css

    def handle_starttag(self, tag, attrs, closed=False):
        a = dict(attrs)
        classes = (a.pop("class", None) or "").split()
        css = self._style(tag, classes)
        if css:
            a["style"] = css + (";" + a["style"] if a.get("style") else "")
            m = re.findall(r"background-color:(#[0-9A-Fa-f]{6})", css)
            if m and tag in ("td", "table"):
                a["bgcolor"] = m[-1]
        at = "".join(f' {k}="{html.escape(v, quote=True)}"' if v is not None else f" {k}" for k, v in a.items())
        self.out.append(f"<{tag}{at}{' /' if closed else ''}>")
        if not closed and tag not in ("img", "br", "meta", "hr"):
            self.stack.append(set(classes))

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs, closed=True)

    def handle_endtag(self, tag):
        if self.stack:
            self.stack.pop()
        self.out.append(f"</{tag}>")

    def handle_data(self, d):
        self.out.append(d)

    def handle_entityref(self, n):
        self.out.append(f"&{n};")

    def handle_charref(self, n):
        self.out.append(f"&#{n};")

    def handle_decl(self, d):
        self.out.append(f"<!{d}>")


def inline_css(doc):
    css = re.sub(r"@media[^{]*\{(?:[^{}]*\{[^}]*\})*[^}]*\}", "", CSS)
    rules = [(sel.strip(), body.strip()) for sel, body in re.findall(r"([^{}]+)\{([^}]*)\}", css)]
    rules = [(s, b) for s, b in rules if s.startswith(".") or s == "td"]
    p = _Inliner(rules)
    p.feed(re.sub(r"<style>.*?</style>", "", doc, flags=re.S))
    return "".join(p.out)


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


def tr(cls, inner, extra=""):
    return f'<tr><td class="{cls}"{extra}>{inner}</td></tr>'


def table(rows, cls=""):
    c = f' class="{cls}"' if cls else ""
    return f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0"{c}>{"".join(rows)}</table>'


def img_tag(img, width):
    return f'<img src="{attr(img["src"])}" alt="{attr(img.get("alt") or img.get("caption"))}" width="{width}">'


NO_IMAGES = False  # True quando si invia col connettore Gmail, che toglie le immagini


def image_block(img):
    if NO_IMAGES or not img or not img.get("src"):
        return ""
    cap = f'<p class="cap">{esc(img["caption"])}</p>' if img.get("caption") else ""
    return tr("img", img_tag(img, 520) + cap)


def story_block(i, s):
    label, c = cat(s)
    meta = [esc(s.get("source"))]
    if s.get("translated"):
        meta.append("tradotto dall'inglese")
    if s.get("read_min"):
        meta.append(f'{int(s["read_min"])} min')

    head = tr(
        "head",
        f'<p class="kick {c}">{i:02d} &nbsp;·&nbsp; {label}</p>'
        f'<p class="title">{esc(s.get("title"))}</p>'
        f'<p class="src">{" &nbsp;·&nbsp; ".join(meta)}</p>',
    )
    rows = [head]
    if not NO_IMAGES and s.get("image") and s["image"].get("src"):
        cap = f'<p class="cap" style="text-align:center">{esc(s["image"]["caption"])}</p>' if s["image"].get("caption") else ""
        rows.append(tr("cover", img_tag(s["image"], 568) + cap, ' style="padding:0 0 14px"'))

    card = []
    if s.get("dek"):
        card.append(tr("dek", esc(s["dek"])))
    for para in s.get("body") or []:
        if isinstance(para, dict):  # immagine nel punto esatto del testo
            card.append(image_block(para))
        elif para.startswith("## "):  # sottotitolo di sezione
            card.append(tr("rule", ""))
            card.append(tr(f"h3 {c}", esc(para[3:])))
        else:
            card.append(tr("p", esc(para)))
    for img in s.get("images") or []:
        card.append(image_block(img))
    if s.get("points"):
        card.append(tr(f"pth {c}", "Punti chiave"))
        card += [tr("pt", esc(p)) for p in s["points"]]
    if s.get("why"):
        card.append(tr("why", table([tr(f"whyb {c}-why",
            f'<p class="whyl {c}">Perché ti interessa</p><p class="whyt">{esc(s["why"])}</p>')])))
    links = s.get("links") or ([{"url": s["url"], "label": s.get("url_label")}] if s.get("url") else [])
    if links:
        btns = "".join(
            f'<a class="btn {c}-btn" href="{attr(l["url"])}">{esc(l.get("label") or "Leggi l’originale")} &rarr;</a>'
            for l in links
        )
        card.append(tr("cta", btns))
    rows.append(tr("card", table(card)))
    return tr(f"band {c}-bg", table(rows))


def index_block(stories):
    rows = []
    for i, s in enumerate(stories, 1):
        label, c = cat(s)
        mins = f'{int(s["read_min"])}&#8242;' if s.get("read_min") else ""
        rows.append(
            f'<tr><td class="ixn {c}">{i:02d}</td>'
            f'<td class="ixr"><span class="ixh">{esc(plain(s.get("title")))}</span><br>'
            f'<span class="ixs">{esc(s.get("source"))} · {label}</span></td>'
            f'<td class="ixm">{mins}</td></tr>'
        )
    return tr("ix", f'<p class="h2">Oggi nella <strong>rassegna</strong></p>'
                    f'{table([tr("ixl", table(rows))])}')


def render_html(d):
    stories = d.get("stories") or []
    total = sum(int(s.get("read_min") or 0) for s in stories)
    stat = f"{len(stories)} letture &nbsp;·&nbsp; {total} minuti" if stories else "Nessuna nuova uscita"
    preheader = d.get("preheader") or d.get("intro") or " · ".join(plain(s.get("title", "")) for s in stories[:3])
    headline = d.get("headline") or "Le idee che contano, **stamattina**."

    sky = [
        tr("brand", "La Rassegna"),
        tr("date", esc(d.get("date_label"))),
        tr("hl", esc(headline)),
    ]
    if d.get("intro"):
        sky.append(tr("lede", esc(d["intro"])))
    sky.append(tr("stat", f'<span class="pill">{stat}</span>'))
    hero = None if NO_IMAGES else d.get("hero")
    if hero and hero.get("src"):
        sky.append(tr("hero", img_tag(hero, 600)))
    top = tr("sky", table(sky))
    if hero and hero.get("caption"):
        top += tr("hcap", esc(hero["caption"]))

    if stories:
        body = index_block(stories) + "".join(story_block(i, s) for i, s in enumerate(stories, 1))
    else:
        body = tr("ix", '<p class="h2">Oggi è tutto <strong>tranquillo</strong>.</p>'
                        '<p class="whyt" style="padding-top:14px">Nelle ultime 24 ore non è arrivata nessuna '
                        "nuova uscita dalle tue newsletter. Ci sentiamo domani.</p>")
    note = esc(d.get("excluded_note"))
    foot = tr(
        "foot",
        '<p class="fh">Buona <strong>giornata</strong>, Leonardo.</p>'
        f'<p class="ft">{note}{"<br><br>" if note else ""}Riassunti scritti da Claude a partire dalle newsletter '
        "che ricevi. Per cambiare fonti o formato, chiedilo nella sessione della Rassegna.</p>",
    )
    css = re.sub(r"\s*\n\s*", "", CSS)
    return (
        '<!doctype html><html lang="it"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<meta name="color-scheme" content="light"><meta name="supported-color-schemes" content="light">'
        f"<title>La Rassegna</title><style>{css}</style></head><body>"
        f'<div style="display:none;max-height:0;overflow:hidden">{esc(plain(preheader))}</div>'
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" class="wrap"><tr><td align="center" style="padding:24px 10px 36px">'
        f'<table role="presentation" width="600" cellpadding="0" cellspacing="0" class="page">{top}{body}{foot}</table>'
        "</td></tr></table></body></html>"
    )


def render_text(d):
    out = [f"LA RASSEGNA · {d.get('date_label','')}", ""]
    if d.get("headline"):
        out += [plain(d["headline"]), ""]
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
    global NO_IMAGES
    args = [a for a in sys.argv[1:] if a != "--no-images"]
    NO_IMAGES = "--no-images" in sys.argv
    src = args[0]
    outdir = args[1] if len(args) > 1 else "/tmp/rassegna"
    os.makedirs(outdir, exist_ok=True)
    d = json.load(open(src, encoding="utf-8"))
    h = inline_css(render_html(d))
    open(os.path.join(outdir, "email.html"), "w", encoding="utf-8").write(h)
    open(os.path.join(outdir, "email.txt"), "w", encoding="utf-8").write(render_text(d))
    print(f"OK email.html {len(h)} caratteri, {len(d.get('stories') or [])} articoli")


if __name__ == "__main__":
    main()
