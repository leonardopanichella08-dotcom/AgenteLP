"""Reframing 16:9 -> 9:16 / 4:5 / 1:1: face tracking, active speaker, percorso di crop.

Active speaker = fusione audio-visiva: la diarizzazione dice *chi* parla,
il movimento della zona-bocca dice *quale volto* è quello. Se la diarizzazione
manca, vince il volto con più movimento della bocca mentre c'è voce.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Callable, Protocol

import numpy as np

Box = tuple[float, float, float, float]  # x, y, w, h in pixel sorgente

SAMPLE_FPS = 10.0
MOUTH_ROI = (0.15, 0.55, 0.85, 1.0)      # frazioni del box del volto (x0,y0,x1,y1)


class FaceDetector(Protocol):
    def detect(self, frame_bgr: np.ndarray) -> list[Box]: ...


class HaarDetector:
    """Rilevatore OpenCV (Haar, frontale). Gira su frame ridotti a 640px."""

    def __init__(self) -> None:
        import cv2
        self.cv2 = cv2
        self.casc = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")

    def detect(self, frame_bgr: np.ndarray) -> list[Box]:
        cv2 = self.cv2
        h, w = frame_bgr.shape[:2]
        sc = 640 / w if w > 640 else 1.0
        small = cv2.resize(frame_bgr, None, fx=sc, fy=sc) if sc != 1.0 else frame_bgr
        g = cv2.equalizeHist(cv2.cvtColor(small, cv2.COLOR_BGR2GRAY))
        r = self.casc.detectMultiScale(g, 1.1, 5, minSize=(max(24, int(small.shape[1] * 0.04)),) * 2)
        return [(x / sc, y / sc, fw / sc, fh / sc) for x, y, fw, fh in r]


@dataclass
class Track:
    id: int
    t: list[float] = field(default_factory=list)
    box: list[Box] = field(default_factory=list)
    mouth: list[float] = field(default_factory=list)     # movimento zona-bocca per campione

    def center_at(self, t: float) -> tuple[float, float] | None:
        if not self.t:
            return None
        i = int(np.argmin(np.abs(np.asarray(self.t) - t)))
        if abs(self.t[i] - t) > 1.0:
            return None
        x, y, w, h = self.box[i]
        return x + w / 2, y + h / 2


@dataclass
class TrackingResult:
    tracks: list[Track]
    sample_times: list[float]
    coverage: float            # frazione di campioni con almeno un volto
    width: int
    height: int


def _iou_center(a: Box, b: Box) -> float:
    ax, ay = a[0] + a[2] / 2, a[1] + a[3] / 2
    bx, by = b[0] + b[2] / 2, b[1] + b[3] / 2
    return math.hypot(ax - bx, ay - by) / max(a[2], b[2], 1)


def track_faces(video_path: str, ranges: list[tuple[float, float]], detector: FaceDetector | None = None,
                progress: Callable[[float], None] | None = None) -> TrackingResult:
    import cv2
    det = detector or HaarDetector()
    cap = cv2.VideoCapture(video_path)
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    W = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)); H = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    step = max(1, int(round(fps / SAMPLE_FPS)))
    tracks: list[Track] = []
    prev_gray: dict[int, np.ndarray] = {}
    times: list[float] = []
    with_face = 0
    total = sum(e - s for s, e in ranges) or 1.0
    done = 0.0
    for rs, re_ in sorted(ranges):
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(rs * fps))
        k0 = int(rs * fps)
        for k in range(k0, int(re_ * fps)):
            if (k - k0) % step:
                if not cap.grab():
                    break
                continue
            ok, frame = cap.read()
            if not ok:
                break
            t = k / fps
            times.append(t)
            boxes = det.detect(frame)
            if boxes:
                with_face += 1
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            used: set[int] = set()
            for b in sorted(boxes, key=lambda b: -b[2] * b[3]):
                # associa al track più vicino (visto di recente), altrimenti ne crea uno
                best, bd = None, 0.9
                for tr in tracks:
                    if tr.id in used or not tr.t or t - tr.t[-1] > 1.5:
                        continue
                    d = _iou_center(tr.box[-1], b)
                    if d < bd:
                        best, bd = tr, d
                if best is None:
                    best = Track(len(tracks)); tracks.append(best)
                used.add(best.id)
                best.t.append(t); best.box.append(b)
                x, y, w, h = [int(v) for v in b]
                x0, x1 = x + int(w * MOUTH_ROI[0]), x + int(w * MOUTH_ROI[2])
                y0, y1 = y + int(h * MOUTH_ROI[1]), y + int(h * MOUTH_ROI[3])
                roi = cv2.resize(gray[max(y0, 0):max(y1, 1), max(x0, 0):max(x1, 1)], (32, 16)) if x1 > x0 and y1 > y0 else None
                mv = 0.0
                if roi is not None and best.id in prev_gray:
                    mv = float(np.mean(np.abs(roi.astype(np.float32) - prev_gray[best.id].astype(np.float32))))
                if roi is not None:
                    prev_gray[best.id] = roi
                best.mouth.append(mv)
        done += re_ - rs
        if progress:
            progress(min(1.0, done / total))
    cap.release()
    # scarta tracce effimere (falsi positivi)
    tracks = [t for t in tracks if len(t.t) >= max(3, 0.1 * max(1, len(times)))]
    return TrackingResult(tracks, times, with_face / max(1, len(times)), W, H)


def assign_speakers(tr: TrackingResult, speech: list[tuple[str, float, float]]) -> dict[str, int]:
    """speaker -> track id. `speech`: (speaker, start, end) dalla diarizzazione."""
    if not tr.tracks:
        return {}
    spks = sorted({s for s, _, _ in speech if s})
    if len(tr.tracks) == 1:
        return {s: tr.tracks[0].id for s in spks}
    score: dict[tuple[str, int], float] = {}
    for s in spks:
        iv = [(a, b) for sp, a, b in speech if sp == s]
        for t in tr.tracks:
            ts = np.asarray(t.t); mv = np.asarray(t.mouth)
            if len(ts) == 0:
                continue
            inside = np.zeros(len(ts), bool)
            for a, b in iv:
                inside |= (ts >= a) & (ts < b)
            if inside.sum() < 2 or (~inside).sum() < 2:
                score[(s, t.id)] = float(mv[inside].mean()) if inside.any() else 0.0
            else:
                score[(s, t.id)] = float(mv[inside].mean() - mv[~inside].mean())
    mapping: dict[str, int] = {}
    taken: set[int] = set()
    for (s, tid), v in sorted(score.items(), key=lambda kv: -kv[1]):
        if s not in mapping and tid not in taken:
            mapping[s] = tid; taken.add(tid)
    return mapping


@dataclass
class CropPath:
    t: np.ndarray            # tempi sorgente
    cx: np.ndarray
    cy: np.ndarray
    speaker_track: np.ndarray   # track id seguito per campione (-1 = nessuno)


def crop_window(src_w: int, src_h: int, target_aspect: float) -> tuple[float, float]:
    """Finestra massima con l'aspect del target dentro la sorgente."""
    if src_w / src_h > target_aspect:
        return src_h * target_aspect, float(src_h)
    return float(src_w), src_w / target_aspect


def build_path(tr: TrackingResult, mapping: dict[str, int], speech: list[tuple[str, float, float]],
               cw: float, ch: float, smooth: float = 0.85) -> CropPath:
    times = np.asarray(tr.sample_times)
    n = len(times)
    cx = np.full(n, tr.width / 2); cy = np.full(n, tr.height / 2)
    follow = np.full(n, -1)
    by_id = {t.id: t for t in tr.tracks}

    def speaker_at(t: float) -> str | None:
        for sp, a, b in speech:
            if a <= t < b:
                return sp
        return None

    # volti visibili in ogni campione
    last_tid = None
    for k, t in enumerate(times):
        vis = {}
        for tid, trk in by_id.items():
            c = trk.center_at(t)
            if c is not None and abs(np.min(np.abs(np.asarray(trk.t) - t))) < 0.2:
                vis[tid] = c
        if not vis:
            if k:
                cx[k], cy[k], follow[k] = cx[k - 1], cy[k - 1], follow[k - 1]
            continue
        # se tutti i volti stanno nella finestra: inquadra il gruppo (niente jitter)
        xs = [c[0] for c in vis.values()]
        if len(vis) > 1 and (max(xs) - min(xs)) <= 0.7 * cw:
            cx[k], cy[k] = float(np.mean(xs)), float(np.mean([c[1] for c in vis.values()]))
            follow[k] = -2
            continue
        tid = None
        sp = speaker_at(t)
        if sp is not None and mapping.get(sp) in vis:
            tid = mapping[sp]
        else:
            # volto con più movimento di bocca nell'intorno
            best = -1.0
            for cand in vis:
                trk = by_id[cand]
                idx = np.where(np.abs(np.asarray(trk.t) - t) < 0.35)[0]
                m = float(np.mean([trk.mouth[i] for i in idx])) if len(idx) else 0.0
                if m > best:
                    best, tid = m, cand
            if best <= 0.5 and last_tid in vis:
                tid = last_tid
        last_tid = tid
        cx[k], cy[k] = vis[tid]
        follow[k] = tid

    cy_t = cy - 0.0 * ch
    # smoothing: deadband + EMA, salto rapido quando cambia chi parla
    ox, oy = cx[0], cy_t[0]
    dead = 0.06 * cw
    for k in range(n):
        if k and abs(cx[k] - ox) > 0.35 * cw:       # cambio inquadratura: ci va in fretta
            ox = cx[k]
        elif abs(cx[k] - ox) > dead:
            ox = smooth * ox + (1 - smooth) * cx[k]
        oy = smooth * oy + (1 - smooth) * cy_t[k]
        cx[k], cy_t[k] = ox, oy
    return CropPath(times, cx, cy_t, follow)


def keyframes_for_segment(path: CropPath, src_start: float, src_end: float, cw: float, ch: float,
                          src_w: int, src_h: int, tol_px: float = 3.0, max_kf: int = 48) -> list[dict]:
    """Finestre di crop (x,y,w,h, t relativo al segmento), semplificate."""
    m = (path.t >= src_start - 0.15) & (path.t <= src_end + 0.15)
    t = path.t[m]; cx = path.cx[m]; cy = path.cy[m]
    if len(t) == 0:
        return [{"t": 0.0, "x": (src_w - cw) / 2, "y": (src_h - ch) / 2, "w": cw, "h": ch}]
    pts = [(float(tt - src_start), float(np.clip(x - cw / 2, 0, src_w - cw)), float(np.clip(y - ch / 2, 0, src_h - ch)))
           for tt, x, y in zip(t, cx, cy)]
    pts[0] = (0.0, pts[0][1], pts[0][2])
    pts[-1] = (max(src_end - src_start, pts[-1][0]), pts[-1][1], pts[-1][2])
    keep = _rdp(pts, tol_px)
    while len(keep) > max_kf:
        tol_px *= 1.6
        keep = _rdp(pts, tol_px)
    return [{"t": round(p[0], 3), "x": round(p[1], 1), "y": round(p[2], 1), "w": round(cw, 1), "h": round(ch, 1)} for p in keep]


def _rdp(pts: list[tuple[float, float, float]], tol: float) -> list[tuple[float, float, float]]:
    if len(pts) < 3:
        return pts
    t0, x0, y0 = pts[0]; t1, x1, y1 = pts[-1]
    dmax, idx = 0.0, 0
    for i in range(1, len(pts) - 1):
        a = (pts[i][0] - t0) / ((t1 - t0) or 1)
        d = max(abs(pts[i][1] - (x0 + a * (x1 - x0))), abs(pts[i][2] - (y0 + a * (y1 - y0))))
        if d > dmax:
            dmax, idx = d, i
    if dmax > tol:
        return _rdp(pts[:idx + 1], tol)[:-1] + _rdp(pts[idx:], tol)
    return [pts[0], pts[-1]]


def choose_strategy(requested: str, src_w: int, src_h: int, target_aspect: float, coverage: float) -> tuple[str, str]:
    sa = src_w / src_h
    if abs(sa - target_aspect) < 0.02:
        return "none", "la sorgente ha già questo aspect ratio"
    if requested == "blur_pad":
        return "blur_pad", "scelto dall'utente"
    narrower = target_aspect < sa
    if requested == "smart_crop":
        return ("smart_crop", "scelto dall'utente") if narrower else ("blur_pad", "crop impossibile: il target è più largo della sorgente")
    if not narrower:
        return "blur_pad", "target più largo della sorgente: sfondo sfocato invece di bande nere"
    if coverage >= 0.5:
        return "smart_crop", f"volti rilevati nel {coverage:.0%} del tempo: crop sul parlante attivo"
    return "blur_pad", f"nessun volto affidabile ({coverage:.0%}): sfondo sfocato per non tagliare il soggetto"
