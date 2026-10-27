"""Pipeline completa su media sintetici: piano → render → verifiche sull'OUTPUT, contro la verità-terreno."""
import numpy as np
import pytest

from app.audio_analysis import compute_envelope
from app.config import POLICIES
from app.media import probe, read_audio
from app.pipeline import Options, Pipeline
from app.render import render_reel
from app.script_align import tokens
from conftest import BoxDetector
from helpers import split_words

TERMINAL = ".!?…"


def seg_spans(reel):
    return [(s.src_start, s.src_end) for s in reel.timeline]


def check_output_cuts(reel, video, policy):
    """Sull'audio renderizzato: i bordi dei segmenti sono silenzio e nessuna pausa interna supera la policy."""
    env = compute_envelope(read_audio(video, 16000), 16000)
    for s in reel.timeline[1:]:
        for dt in (0.0, 0.004):   # alla giunzione nessuna parola: >=25 dB sotto il parlato
            # (non "sotto soglia": il pre-echo dell'AAC a una giunzione sale a ~-30 dBc ed e' inudibile)
            assert env.db[env.idx(s.out_start + dt)] < env.speech_level - 25, (s.id, s.out_start)
    assert not env.active[env.idx(0.0)] or env.db[env.idx(0.0)] < env.threshold + 6
    # pause interne al parlato: nessuna oltre max_gap (+ padding su entrambi i lati + tolleranza)
    runs = env.runs(0, env.duration)
    gaps = [b[0] - a[1] for a, b in zip(runs, runs[1:])]
    limit = policy.max_gap + 0.12
    assert max(gaps, default=0) <= limit + 0.08, f"pausa residua {max(gaps):.2f}s > {limit:.2f}"


def test_mode_b_podcast_end_to_end(podcast, tmp_path):
    opts = Options(formats=["9:16", "1:1", "16:9", "4:5"], min_dur=8, max_dur=35, n_min=1)
    plan = Pipeline("p", [("podcast", str(podcast["path"]))], opts, transcripts={"podcast": podcast["transcript"]},
                    detector=BoxDetector(podcast["faces"])).run()
    reel = plan.reels[0]
    assert 8 <= reel.duration <= 35
    # nessuna parola vera mozzata dal piano
    assert split_words(podcast["truth"], seg_spans(reel)) == []
    # il reel inizia a inizio frase e finisce a fine frase
    assert reel.transcript[0].isupper() and reel.transcript.rstrip()[-1] in TERMINAL
    # gli intercalari non trascritti sono spariti
    for f in (w for w in podcast["truth"] if w.filler and not w.transcribed):
        assert not any(a <= f.start and f.end <= b for a, b in seg_spans(reel))
    # ogni taglio: nel silenzio, sul frame, con metodo e confidenza dichiarati
    for s in reel.timeline:
        for c in (s.cut_in, s.cut_out):
            assert abs(c.time * 30 - c.frame) < 1e-3 and c.confidence >= 0.3   # sul frame (6 decimali)
    # render in tutti i formati
    dims = {"9:16": (540, 960), "1:1": (540, 540), "16:9": (960, 540), "4:5": (540, 676)}
    for e in plan.exports:
        out = render_reel(plan, reel, e, tmp_path / f"{e.format_id.replace(':', 'x')}.mp4", tmp_path / "w", quality="draft")
        i = probe(out)
        assert (i.width, i.height) == dims[e.format_id]
        assert abs(i.duration - reel.duration) < 1 / 30 + 1e-3
        if e.format_id == "9:16":
            check_output_cuts(reel, out, POLICIES["natural"])


def test_full_resolution_vertical_spec(podcast, tmp_path):
    opts = Options(formats=["9:16"], min_dur=8, max_dur=20, n_min=1, fps=30)
    plan = Pipeline("p", [("podcast", str(podcast["path"]))], opts, transcripts={"podcast": podcast["transcript"]},
                    detector=BoxDetector(podcast["faces"])).run()
    out = render_reel(plan, plan.reels[0], plan.exports[0], tmp_path / "full.mp4", tmp_path / "w", quality="final")
    i = probe(out)
    assert (i.width, i.height, i.fps) == (1080, 1920, 30.0) and i.has_audio


def test_mode_a_script_assembly(script_project, tmp_path):
    sp = script_project
    srcs = [(k, str(v["path"])) for k, v in sp["clips"].items()]
    trs = {k: v["transcript"] for k, v in sp["clips"].items()}
    plan = Pipeline("a", srcs, Options(mode="script_assembly", formats=["9:16", "16:9"], script=sp["script"]),
                    transcripts=trs).run()
    reel = plan.reels[0]
    # le parole montate sono ESATTAMENTE lo script: via false partenze, ripetizioni ed "eh"
    assert [w.norm if hasattr(w, "norm") else None for w in []] == []
    got = [t for w in reel.words for t in tokens(w.text)]
    assert got == tokens(sp["script"]), (got, tokens(sp["script"]))
    assert all(r.status == "matched" for r in plan.script_report)
    # niente parola vera spezzata, in nessuna clip
    for cid, v in sp["clips"].items():
        spans = [(s.src_start, s.src_end) for s in reel.timeline if s.source_id == cid]
        assert split_words(v["truth"], spans) == [], cid
    # le take scelte sono quelle pulite (non l'inciampo "scusa" ne' il doppio "è è")
    assert "scusa" not in reel.transcript.lower()
    assert reel.transcript.lower().count("secondo") == 1
    # unità in ordine script
    units = [s.script_unit for s in reel.timeline]
    assert units == sorted(units) and set(units) == {0, 1, 2, 3}
    out = render_reel(plan, reel, plan.exports[0], tmp_path / "a.mp4", tmp_path / "w", quality="draft")
    assert abs(probe(out).duration - reel.duration) < 1 / 30 + 1e-3
    check_output_cuts(reel, out, POLICIES["natural"])
    # blur_pad su 16:9 da sorgente 16:9? aspect uguale -> none
    assert next(f for f in reel.framing if f.format_id == "16:9").strategy == "none"


def test_long_form_extracts_3_to_5_clean_reels(long_video):
    lv = long_video
    plan = Pipeline("l", [("long", str(lv["path"]))], Options(formats=["9:16"], n_min=3, n_max=5),
                    transcripts={"long": lv["transcript"]}, detector=BoxDetector(lv["faces"])).run()
    assert 3 <= len(plan.reels) <= 5, plan.diagnostics
    last_end = []
    for r in plan.reels:
        assert 15 <= r.duration <= 60
        assert split_words(lv["truth"], seg_spans(r)) == []
        assert r.transcript[0].isupper() and r.transcript.rstrip()[-1] in TERMINAL, r.transcript
        assert r.virality and 0 <= r.virality.score <= 100 and r.virality.reasons
        assert r.social.hashtags and r.social.caption
        last_end.append((min(s.src_start for s in r.timeline), max(s.src_end for s in r.timeline)))
    # non sovrapposti
    last_end.sort()
    assert all(a[1] <= b[0] for a, b in zip(last_end, last_end[1:]))
    assert [r.virality.score for r in plan.reels] == sorted((r.virality.score for r in plan.reels), reverse=True)


def test_60fps_export_keeps_duration_and_sync(podcast, tmp_path):
    opts = Options(formats=["9:16"], min_dur=8, max_dur=20, n_min=1, fps=60)
    plan = Pipeline("p", [("podcast", str(podcast["path"]))], opts, transcripts={"podcast": podcast["transcript"]},
                    detector=BoxDetector(podcast["faces"])).run()
    reel = plan.reels[0]
    out = render_reel(plan, reel, plan.exports[0], tmp_path / "f60.mp4", tmp_path / "w", quality="draft")
    i = probe(out)
    assert i.fps == 60.0 and abs(i.duration - reel.duration) < 1 / 60 + 1e-3
    # il timeline del piano è sulla griglia a 60 fps
    assert all(abs(s.out_start * 60 - round(s.out_start * 60)) < 1e-3 for s in reel.timeline)
