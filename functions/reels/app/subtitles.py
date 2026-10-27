"""Sottotitoli dinamici in formato ASS (libass via ffmpeg).

Una riga = 1..N parole; per ogni parola un evento in cui quella parola è
evidenziata (colore + "pop"). Precisione: ASS lavora in centisecondi (10 ms),
sotto la durata di un frame a 60 fps (16,7 ms): invisibile.
"""
from __future__ import annotations

import subprocess
from functools import lru_cache

from .schemas import OutWord, SubtitleStyle


@lru_cache(maxsize=1)
def emoji_font_available() -> bool:
    try:
        out = subprocess.run(["fc-list", ":charset=1f525"], capture_output=True, text=True, timeout=5).stdout
        return bool(out.strip())
    except Exception:
        return False


def _ass_color(hex_rgb: str) -> str:
    h = hex_rgb.lstrip("#")
    r, g, b = h[0:2], h[2:4], h[4:6]
    return f"&H00{b}{g}{r}&".upper()


def _t(sec: float) -> str:
    cs = int(round(max(sec, 0) * 100))
    return f"{cs // 360000}:{cs // 6000 % 60:02d}:{cs // 100 % 60:02d}.{cs % 100:02d}"


def _esc(s: str) -> str:
    return s.replace("\\", "").replace("{", "(").replace("}", ")")


def chunk_words(words: list[OutWord], max_words: int, max_chars: int) -> list[list[OutWord]]:
    chunks: list[list[OutWord]] = []
    cur: list[OutWord] = []
    for w in words:
        chars = sum(len(x.text) for x in cur) + len(cur) + len(w.text)
        if cur and (len(cur) >= max_words or chars > max_chars or w.out_start - cur[-1].out_end > 0.6):
            chunks.append(cur); cur = []
        cur.append(w)
        if w.text.rstrip()[-1:] in ".!?,;:…" and len(cur) >= 2:
            chunks.append(cur); cur = []
    if cur:
        chunks.append(cur)
    return chunks


def build_ass(words: list[OutWord], style: SubtitleStyle, width: int, height: int, fonts_ok_emoji: bool | None = None) -> str:
    emoji_ok = emoji_font_available() if fonts_ok_emoji is None else fonts_ok_emoji
    fs = int(round(style.font_size_pct * height))
    outline = max(2, int(round(style.outline_px * height)))
    # centro riga, tenuto dentro le zone sicure della piattaforma
    cy = min(max(style.position_y, style.safe_top + 0.05), 1 - style.safe_bottom - 0.02) * height
    max_chars = max(8, int((width * 0.86) / (fs * 0.62)))
    prim, outc = _ass_color(style.primary_color), _ass_color(style.outline_color)
    hl = [_ass_color(c) for c in style.highlight_colors]

    head = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {width}
PlayResY: {height}
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{style.font},{fs},{prim},{prim},{outc},&H80000000&,-1,0,0,0,100,100,0,0,1,{outline},{max(1, outline // 3)},5,40,40,40,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    lines: list[str] = []
    for chunk in chunk_words(words, style.max_words_per_line, max_chars):
        for k, w in enumerate(chunk):
            start = w.out_start
            end = chunk[k + 1].out_start if k + 1 < len(chunk) else w.out_end + 0.12
            if end <= start:
                end = start + 0.05
            parts = []
            for j, x in enumerate(chunk):
                txt = _esc(x.text.upper() if style.uppercase else x.text)
                if emoji_ok and style.emoji and x.emoji and j == k:
                    txt += " " + x.emoji
                own = _ass_color(x.color) if x.color else None     # parola-chiave: resta colorata
                if j == k:
                    col = own or (hl[0] if style.preset != "clean" else prim)
                    sc = int(style.pop_scale * 100)
                    parts.append(f"{{\\c{col}\\fscx{sc}\\fscy{sc}\\t(0,90,\\fscx100\\fscy100)}}{txt}{{\\c{prim}}}")
                elif own:
                    parts.append(f"{{\\c{own}}}{txt}{{\\c{prim}}}")
                else:
                    parts.append(txt)
            lines.append(f"Dialogue: 0,{_t(start)},{_t(end)},Default,,0,0,0,,{{\\an5\\pos({width // 2},{int(cy)})}}{' '.join(parts)}")
    return head + "\n".join(lines) + "\n"
