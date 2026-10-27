"""I tagli devono cadere nel silenzio reale, non dove "dice" l'ASR."""
import numpy as np
import pytest

from app.audio_analysis import compute_envelope
from app.config import POLICIES
from app.cutting import analyze_gaps, build_segments, split_sentences
from app.media import probe, read_audio
from app.transcript import lexical
from helpers import split_words


@pytest.fixture(scope="module")
def ctx(podcast):
    info = probe(podcast["path"])
    env = compute_envelope(read_audio(podcast["path"], 16000), 16000)
    lex = lexical(podcast["transcript"].words)
    return podcast, info, env, lex


def test_envelope_finds_speech_and_silence(ctx):
    pod, info, env, lex = ctx
    # in mezzo a ogni parola vera c'è voce, nelle pause lunghe silenzio
    for w in pod["truth"]:
        assert env.active[env.idx((w.start + w.end) / 2)], w
    assert not env.active[env.idx(0.2)]


def test_asr_timestamps_are_actually_wrong(ctx):
    """Sanity del test: il jitter ASR sintetico è davvero tale da mozzare parole se si taglia 'ingenuamente'."""
    pod, _, _, lex = ctx
    naive = [(lex[0].start, lex[-1].end)]
    gaps_naive = []
    errs = [abs(a.start - b.start) for a, b in zip([w for w in pod["truth"] if w.transcribed], lex)]
    assert max(errs) > 0.05


@pytest.mark.parametrize("policy", ["tight", "natural", "relaxed"])
def test_no_word_is_ever_split(ctx, policy):
    pod, info, env, lex = ctx
    gaps = analyze_gaps(lex, env, POLICIES[policy])
    segs = build_segments(lex, gaps, env, 0, len(lex) - 1, info.fps, POLICIES[policy], media_duration=info.duration)
    spans = [(s.start, s.end) for s in segs]
    assert split_words(pod["truth"], spans) == []
    assert len(segs) > 3  # ha davvero tagliato


def test_naive_asr_cutting_would_split_words(ctx):
    """Controprova: con gli stessi timestamp ASR 'grezzi' si mozzano parole."""
    pod, info, env, lex = ctx
    naive = []
    for a, b in zip(lex, lex[1:]):
        if b.start - a.end > 0.4:
            naive.append((a.end, b.start))
    spans, cur = [], lex[0].start
    for end, nxt in naive:
        spans.append((cur, end)); cur = nxt
    spans.append((cur, lex[-1].end))
    assert split_words(pod["truth"], spans) != []


def test_cut_points_are_in_silence_and_on_frames(ctx):
    pod, info, env, lex = ctx
    pol = POLICIES["natural"]
    gaps = analyze_gaps(lex, env, pol)
    segs = build_segments(lex, gaps, env, 0, len(lex) - 1, info.fps, pol, media_duration=info.duration)
    for s in segs:
        for c in (s.cut_in, s.cut_out):
            assert abs(c.time * info.fps - round(c.time * info.fps)) < 1e-6        # frame-perfect
            assert not env.active[env.idx(c.time)], (c.reason, c.time)             # dentro silenzio
            assert c.confidence >= 0.3


def test_long_pauses_and_untranscribed_filler_are_removed(ctx):
    pod, info, env, lex = ctx
    pol = POLICIES["natural"]
    gaps = analyze_gaps(lex, env, pol)
    segs = build_segments(lex, gaps, env, 0, len(lex) - 1, info.fps, pol, media_duration=info.duration)
    # nessuna pausa interna rimasta oltre max_gap + padding; l'"eh" non trascritto (0.38s) è sparito
    for a, b in zip(segs, segs[1:]):
        pass
    kept = sum(s.end - s.start for s in segs)
    total_speech = sum(w.end - w.start for w in pod["truth"] if w.transcribed)
    unlisted = [w for w in pod["truth"] if w.filler and not w.transcribed]
    assert unlisted
    for f in unlisted:
        assert not any(s.start <= f.start and f.end <= s.end for s in segs), "filler non trascritto ancora presente"
    # pause tra parole nel risultato non superano max_gap
    for s in segs:
        ws = [w for w in pod["truth"] if w.transcribed and s.start <= w.start and w.end <= s.end]
        for x, y in zip(ws, ws[1:]):
            assert y.start - x.end <= pol.max_gap + 0.05, (x.text, y.text)
    assert kept < total_speech + 0.06 * len(lex) + 0.5 * len(segs)


def test_jump_cut_keeps_natural_cadence(ctx):
    pod, info, env, lex = ctx
    pol = POLICIES["natural"]
    gaps = analyze_gaps(lex, env, pol)
    segs = build_segments(lex, gaps, env, 0, len(lex) - 1, info.fps, pol, media_duration=info.duration)
    # tra due segmenti: rimane silenzio da entrambi i lati del taglio (pad), mai attacco secco
    for s in segs[1:]:
        assert s.start - s.cut_in.silence[0] >= 0.0
    for s in segs:
        # 20ms prima dell'ingresso e dopo l'uscita deve essere silenzio
        assert env.db[env.idx(max(s.start, 0))] < env.threshold
        assert env.db[env.idx(s.end)] < env.threshold


def test_sentences_split_on_punctuation_and_speaker(ctx):
    pod, info, env, lex = ctx
    gaps = analyze_gaps(lex, env, POLICIES["natural"])
    sents = split_sentences(lex, gaps)
    assert 6 <= len(sents) <= 14
    for s in sents:
        assert s.a <= s.b
    # copertura completa e senza sovrapposizioni
    assert sents[0].a == 0 and sents[-1].b == len(lex) - 1
    assert all(x.b + 1 == y.a for x, y in zip(sents, sents[1:]))
