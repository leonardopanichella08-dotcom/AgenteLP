import numpy as np

from app.media import probe
from app.reframe import (assign_speakers, build_path, choose_strategy, crop_window,
                         keyframes_for_segment, track_faces)


class BoxDetector:
    """Rileva i due volti-cartone alle posizioni vere (il rilevatore reale è Haar)."""
    def __init__(self, boxes):
        self.boxes = list(boxes.values())

    def detect(self, frame):
        return self.boxes


def test_active_speaker_follows_whoever_is_talking(podcast):
    info = probe(podcast["path"])
    det = BoxDetector(podcast["faces"])
    tr = track_faces(str(podcast["path"]), [(0, info.duration - 0.5)], det)
    assert len(tr.tracks) == 2 and tr.coverage > 0.95
    speech = [(w.speaker, w.start, w.end) for w in podcast["transcript"].words]
    mapping = assign_speakers(tr, speech)
    # A sta a sinistra (x piccolo), B a destra
    left = min(tr.tracks, key=lambda t: t.box[0][0]).id
    right = max(tr.tracks, key=lambda t: t.box[0][0]).id
    assert mapping == {"A": left, "B": right}

    cw, ch = crop_window(info.width, info.height, 9 / 16)
    path = build_path(tr, mapping, speech, cw, ch, smooth=0.8)
    # mentre parla B (es. "Davvero?" ~7.8s) il crop è a destra, mentre parla A a sinistra
    def cx_at(t):
        return path.cx[int(np.argmin(np.abs(path.t - t)))]
    truth = podcast["truth"]
    b_words = [w for w in truth if w.speaker == "B" and w.end - w.start > 0.3]
    a_words = [w for w in truth if w.speaker == "A" and w.end - w.start > 0.3 and not w.filler]
    b_ok = np.mean([cx_at(w.end - 0.05) > info.width / 2 for w in b_words])
    a_ok = np.mean([cx_at(w.end - 0.05) < info.width / 2 for w in a_words])
    assert a_ok > 0.9 and b_ok > 0.8, (a_ok, b_ok)


def test_keyframes_stay_inside_frame_and_are_compact(podcast):
    info = probe(podcast["path"])
    det = BoxDetector(podcast["faces"])
    tr = track_faces(str(podcast["path"]), [(0, 30)], det)
    speech = [(w.speaker, w.start, w.end) for w in podcast["transcript"].words]
    cw, ch = crop_window(info.width, info.height, 9 / 16)
    path = build_path(tr, assign_speakers(tr, speech), speech, cw, ch)
    kf = keyframes_for_segment(path, 8.0, 20.0, cw, ch, info.width, info.height)
    assert 2 <= len(kf) <= 48
    for k in kf:
        assert 0 <= k["x"] <= info.width - cw + 1e-6 and 0 <= k["y"] <= info.height - ch + 1e-6


def test_strategy_selection():
    assert choose_strategy("auto", 1920, 1080, 9 / 16, 0.9)[0] == "smart_crop"
    assert choose_strategy("auto", 1920, 1080, 9 / 16, 0.1)[0] == "blur_pad"
    assert choose_strategy("auto", 1080, 1920, 16 / 9, 0.9)[0] == "blur_pad"
    assert choose_strategy("auto", 1920, 1080, 16 / 9, 0.9)[0] == "none"
    assert choose_strategy("smart_crop", 1080, 1920, 16 / 9, 0.9)[0] == "blur_pad"
