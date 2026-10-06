"""Elenca le immagini editoriali di una newsletter, scartando pixel, icone e pubblicità.

Uso:  python3 extract_images.py <file>
<file> può essere il JSON salvato da Gmail get_message (FULL_CONTENT, con htmlBody)
oppure un file .html. Stampa una riga JSON per immagine candidata, con il testo
che la circonda, così si può decidere se è un'immagine di contenuto o uno sponsor.
"""
import html as htmllib
import json
import re
import sys
from html.parser import HTMLParser

SKIP_SRC = re.compile(
    r"(pixel|tracking|open\.php|/o/|spacer|1x1|blank\.gif|/icon|icons?/|logo|avatar|"
    r"badge|emoji|header|divider|banner|signature|-sig|_sig|passa-a-plus|promo|/ads?/|twemoji|social|facebook|twitter|instagram|linkedin|youtube_|"
    r"app-?store|google-?play|footer|unsubscribe|substack-post-media.*w_(32|40|48|64|80)\b|"
    r"/profile|static\.licdn|/aero-v1/|data:image)",
    re.I,
)
AD_HINT = re.compile(
    r"(sponsor|in collaborazione|offerto da|pubblicit|advert|promo|affiliate|"
    r"utm_medium=affiliate|irclickid|codice sconto|coupon|cashback|partner)",
    re.I,
)


class P(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.items, self.text, self.link = [], [], None

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "a":
            self.link = a.get("href")
        if tag != "img":
            return
        src = a.get("src") or ""
        w = re.sub(r"\D", "", a.get("width") or "") or "0"
        h = re.sub(r"\D", "", a.get("height") or "") or "0"
        if not src.startswith("http") or SKIP_SRC.search(src):
            return
        if (0 < int(w) < 120) or (0 < int(h) < 80):
            return
        self.items.append({
            "src": htmllib.unescape(src),
            "alt": a.get("alt") or "",
            "link": self.link,
            "pos": len(" ".join(self.text)),
        })

    def handle_endtag(self, tag):
        if tag == "a":
            self.link = None

    def handle_data(self, d):
        d = d.strip()
        if d:
            self.text.append(d)


def main(path):
    raw = open(path, encoding="utf-8").read()
    try:
        data = json.loads(raw)
        if isinstance(data, list):
            data = data[0]
        doc = data.get("htmlBody") or data.get("html_body") or ""
    except json.JSONDecodeError:
        doc = raw
    p = P()
    p.feed(doc)
    full = " ".join(p.text)
    seen = set()
    for it in p.items:
        key = re.sub(r"[?#].*", "", it["src"])
        if key in seen:
            continue
        seen.add(key)
        before = full[max(0, it["pos"] - 200): it["pos"]]
        after = full[it["pos"]: it["pos"] + 200]
        ctx = before + " ⟦IMG⟧ " + after
        it["likely_ad"] = bool(AD_HINT.search(ctx) or AD_HINT.search(it["link"] or ""))
        it["context"] = re.sub(r"\s+", " ", ctx)
        del it["pos"]
        print(json.dumps(it, ensure_ascii=False))


if __name__ == "__main__":
    main(sys.argv[1])
