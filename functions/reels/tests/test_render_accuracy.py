"""Frame-accuracy del render: ogni frame del sorgente codifica il proprio indice in blocchi bianco/nero.
Dopo il montaggio rileggo gli indici e li confronto con quelli attesi dal piano: nessun frame in più o in meno."""
import subprocess
from pathlib import Path

import numpy as np
import pytest

from app.render import render_reel
from app.schemas import (CutInfo, EditPlan, ExportTarget, Framing, Reel, Segment, Social, Source, SubtitleStyle)

W, H, FPS, NBITS, BLK = 320, 180, 30, 12, 20


def make_coded_video(path: Path, n_frames: int = 400) -> None:
    cmd = ["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "gray", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
           "-f", "lavfi", "-i", "anullsrc=r=48000:cl=mono", "-shortest",
           "-c:v", "libx264", "-preset", "ultrafast", "-crf", "12", "-pix_fmt", "yuv420p", "-g", "30",
           "-c:a", "aac", str(path)]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    for k in range(n_frames):
        f = np.full((H, W), 128, np.uint8)
        for b in range(NBITS):
            f[0:BLK, b * BLK:(b + 1) * BLK] = 255 if (k >> b) & 1 else 0
        p.stdin.write(f.tobytes())
    p.stdin.close(); p.wait()


def read_codes(path: Path) -> list[int]:
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-f", "rawvideo", "-pix_fmt", "gray", "-"],
                         capture_output=True, check=True).stdout
    vw, vh = _size(path)
    frames = np.frombuffer(raw, np.uint8).reshape(-1, vh, vw)
    sx, sy = vw / W, vh / H
    codes = []
    for f in frames:
        c = 0
        for b in range(NBITS):
            px = f[int(BLK * sy / 2), int((b * BLK + BLK / 2) * sx)]
            c |= (1 if px > 128 else 0) << b
        codes.append(c)
    return codes


def _size(path: Path) -> tuple[int, int]:
    out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height",
                          "-of", "csv=p=0", str(path)], capture_output=True, text=True).stdout.strip().split(",")
    return int(out[0]), int(out[1])


def _plan(src: Path, ranges: list[tuple[int, int]]) -> tuple[EditPlan, Reel]:
    segs, t = [], 0.0
    for i, (a, b) in enumerate(ranges):
        d = (b - a) / FPS
        ci = lambda f: CutInfo(asr_time=f / FPS, time=f / FPS, frame=f, method="silence_gap", confidence=1.0, reason="t")
        segs.append(Segment(id=f"s{i+1}", source_id="x", src_start=a / FPS, src_end=b / FPS, src_start_frame=a, src_end_frame=b,
                            out_start=t, out_end=t + d, cut_in=ci(a), cut_out=ci(b)))
        t += d
    reel = Reel(id="r", title="t", rank=1, duration=t, timeline=segs, words=[], transcript="",
                framing=[Framing(format_id="16:9", strategy="none", reason="")], subtitles=SubtitleStyle(), zooms=[],
                sfx=[], transitions=[], social=Social(title="t", caption="c", hashtags=[]))
    exp = ExportTarget(format_id="16:9", width=W, height=H, fps=FPS)
    plan = EditPlan(project_id="p", mode="script_assembly", sources=[Source(id="x", path=str(src), duration=400 / FPS, fps=FPS, width=W, height=H)],
                    exports=[exp], reels=[reel])
    return plan, reel


@pytest.fixture(scope="module")
def coded(tmp_path_factory):
    p = tmp_path_factory.mktemp("coded") / "coded.mp4"
    make_coded_video(p)
    return p


def test_source_codes_are_readable(coded):
    assert read_codes(coded)[:5] == [0, 1, 2, 3, 4]


@pytest.mark.parametrize("ranges", [
    [(30, 75), (120, 150), (200, 290)],
    [(1, 31), (31, 61)],                      # tagli adiacenti
    [(97, 98), (250, 299), (10, 40)],         # un solo frame; fuori ordine
])
def test_render_is_frame_exact(coded, tmp_path, ranges):
    plan, reel = _plan(coded, ranges)
    out = render_reel(plan, reel, plan.exports[0], tmp_path / "o.mp4", tmp_path / "w")
    expected = [f for a, b in ranges for f in range(a, b)]
    got = read_codes(out)
    assert got == expected, f"primi scarti: {[(i, g, e) for i, (g, e) in enumerate(zip(got, expected)) if g != e][:5]} len {len(got)} vs {len(expected)}"
