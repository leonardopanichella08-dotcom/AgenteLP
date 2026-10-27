"""Probe e decodifica con ffmpeg/ffprobe."""
from __future__ import annotations

import json
import math
import subprocess
from dataclasses import dataclass
from pathlib import Path

import numpy as np


@dataclass
class MediaInfo:
    path: str
    duration: float
    fps: float
    width: int
    height: int
    has_audio: bool
    audio_sample_rate: int | None


def _fps(s: str) -> float:
    n, _, d = s.partition("/")
    return float(n) / float(d or 1) if float(d or 1) else 0.0


def probe(path: str | Path) -> MediaInfo:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-print_format", "json", "-show_streams", "-show_format", str(path)],
        capture_output=True, text=True, check=True,
    ).stdout
    j = json.loads(out)
    v = next((s for s in j["streams"] if s["codec_type"] == "video"), None)
    a = next((s for s in j["streams"] if s["codec_type"] == "audio"), None)
    if v is None:
        raise ValueError("nessuna traccia video")
    dur = float(j["format"].get("duration") or v.get("duration") or 0)
    return MediaInfo(
        path=str(path), duration=dur,
        fps=_fps(v.get("avg_frame_rate") or v["r_frame_rate"]) or _fps(v["r_frame_rate"]),
        width=int(v["width"]), height=int(v["height"]),
        has_audio=a is not None,
        audio_sample_rate=int(a["sample_rate"]) if a else None,
    )


def read_audio(path: str | Path, sr: int = 16000) -> np.ndarray:
    """Audio mono float32 [-1,1] a `sr` Hz."""
    proc = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(path), "-vn", "-ac", "1", "-ar", str(sr), "-f", "f32le", "-"],
        capture_output=True, check=True,
    )
    return np.frombuffer(proc.stdout, dtype=np.float32).copy()


def frame_floor(t: float, fps: float) -> float:
    return math.floor(t * fps + 1e-6) / fps


def frame_ceil(t: float, fps: float) -> float:
    return math.ceil(t * fps - 1e-6) / fps


def frame_round(t: float, fps: float) -> float:
    return round(t * fps) / fps
