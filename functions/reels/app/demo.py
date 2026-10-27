"""Media sintetici con verità-terreno nota.

Servono a due cose: test deterministici (il sandbox non ha Whisper né volti
veri) e la modalità demo della dashboard. L'audio è sintetico ma ha le
patologie che rompono i tagli reali: parole brevi, dip di ampiezza dentro la
parola, intercalari non trascritti, pause lunghe, e un ASR con jitter
di ±`jitter` secondi sui timestamp.
"""
from __future__ import annotations

import subprocess
import wave
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from .transcript import Transcript, Word

SR = 48000
F0 = {"A": 118.0, "B": 205.0}


@dataclass
class TruthWord:
    text: str
    start: float
    end: float
    speaker: str
    transcribed: bool = True   # False = intercalare non finito nel trascritto ASR
    filler: bool = False


def _voice(dur: float, f0: float, amp: float, rng: np.random.Generator) -> np.ndarray:
    n = int(dur * SR)
    t = np.arange(n) / SR
    vib = 1 + 0.02 * np.sin(2 * np.pi * 5.5 * t)
    ph = 2 * np.pi * np.cumsum(f0 * vib) / SR
    sig = sum(np.sin(h * ph) / h for h in range(1, 9))
    syll = 0.65 + 0.35 * np.sin(2 * np.pi * 4.5 * t + rng.uniform(0, 6)) ** 2   # dip interni (mai silenzio)
    att, rel = int(0.012 * SR), int(0.03 * SR)
    env = np.ones(n)
    env[:att] = np.linspace(0, 1, min(att, n))
    env[-rel:] = np.linspace(1, 0, min(rel, n))
    return (sig * syll * env * amp / 3.0).astype(np.float32)


def synth_track(items: list[dict], seed: int = 0, jitter: float = 0.10,
                noise_db: float = -62.0) -> tuple[np.ndarray, list[TruthWord], Transcript]:
    """items: {"w": testo, "spk": "A"} | {"pause": sec} | {"filler": "eh", "spk": "A", "listed": bool, "dur": 0.4}"""
    rng = np.random.default_rng(seed)
    chunks: list[np.ndarray] = [np.zeros(int(0.5 * SR), dtype=np.float32)]
    t = 0.5
    truth: list[TruthWord] = []
    for idx, it in enumerate(items):
        if "pause" in it:
            n = int(it["pause"] * SR)
            chunks.append(np.zeros(n, dtype=np.float32)); t += n / SR
            continue
        if "filler" in it:
            dur = it.get("dur", 0.4)
            chunks.append(_voice(dur, F0[it.get("spk", "A")] * 0.9, 0.5, rng))
            truth.append(TruthWord(it["filler"], t, t + dur, it.get("spk", "A"),
                                   transcribed=it.get("listed", False), filler=True))
            t += dur
            continue
        text = it["w"]
        core = text.strip(".,!?;:…")
        dur = it.get("dur") or (0.11 + 0.042 * len(core))
        chunks.append(_voice(dur, F0[it.get("spk", "A")] * rng.uniform(0.95, 1.08), 1.0, rng))
        truth.append(TruthWord(text, t, t + dur, it.get("spk", "A")))
        t += dur
        # coarticolazione: gap minuscolo tra parole non separate da pausa
        if not (idx + 1 < len(items) and "pause" in items[idx + 1]):
            g = int(it.get("gap", rng.uniform(0.03, 0.09)) * SR)
            chunks.append(np.zeros(g, dtype=np.float32)); t += g / SR
    chunks.append(np.zeros(int(0.5 * SR), dtype=np.float32))
    audio = np.concatenate(chunks)
    audio += (10 ** (noise_db / 20) * rng.standard_normal(len(audio))).astype(np.float32)

    words = []
    for w in truth:
        if not w.transcribed:
            continue
        js = rng.uniform(-jitter, jitter)
        je = rng.uniform(-jitter, jitter)
        s, e = max(0.0, w.start + js), w.end + je
        if e <= s + 0.03:
            e = s + 0.05
        words.append(Word(w.text, round(s, 3), round(e, 3), speaker=w.speaker, source_id=""))
    # l'ASR mantiene l'ordine
    for k in range(1, len(words)):
        if words[k].start < words[k - 1].start:
            words[k].start = words[k - 1].start
    return audio, truth, Transcript("", words, "it", "synthetic-asr")


def write_wav(path: Path, audio: np.ndarray) -> None:
    pcm = (np.clip(audio, -1, 1) * 32767).astype(np.int16)
    with wave.open(str(path), "wb") as f:
        f.setnchannels(1); f.setsampwidth(2); f.setframerate(SR)
        f.writeframes(pcm.tobytes())


def render_video(path: Path, audio: np.ndarray, truth: list[TruthWord], layout: str = "two",
                 fps: int = 30, size: tuple[int, int] = (960, 540)) -> dict:
    """MP4 con volti-cartone che aprono la bocca quando parlano. Ritorna i box reali dei volti."""
    import cv2
    W, H = size
    dur = len(audio) / SR
    n = int(dur * fps)
    wav = path.with_suffix(".tmp.wav")
    write_wav(wav, audio)
    if layout == "two":
        faces = {"A": (int(W * 0.25), int(H * 0.45)), "B": (int(W * 0.75), int(H * 0.45))}
    else:
        faces = {"A": (int(W * 0.5), int(H * 0.45)), "B": (int(W * 0.5), int(H * 0.45))}
    fr = int(H * 0.2)
    bg = np.zeros((H, W, 3), np.uint8)
    bg[:] = (60, 50, 45)
    cv2.rectangle(bg, (0, int(H * 0.8)), (W, H), (40, 35, 30), -1)
    cmd = ["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{W}x{H}", "-r", str(fps),
           "-i", "-", "-i", str(wav), "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
           "-c:a", "aac", "-b:a", "128k", "-shortest", str(path)]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    for k in range(n):
        t = k / fps
        f = bg.copy()
        speaking = {w.speaker for w in truth if w.start <= t < w.end}
        for spk, (cx, cy) in faces.items():
            if layout != "two" and spk == "B":
                continue
            cv2.ellipse(f, (cx, cy), (fr, int(fr * 1.25)), 0, 0, 360, (150, 190, 235), -1)
            for dx in (-fr // 2, fr // 2):
                cv2.circle(f, (cx + dx, cy - fr // 3), max(3, fr // 9), (30, 30, 30), -1)
            mh = int(fr * 0.35) if (spk in speaking and (k // 3) % 2 == 0) else int(fr * 0.04)
            cv2.rectangle(f, (cx - fr // 3, cy + fr // 2), (cx + fr // 3, cy + fr // 2 + mh), (20, 20, 120), -1)
        p.stdin.write(f.tobytes())
    p.stdin.close(); p.wait()
    wav.unlink(missing_ok=True)
    return {s: (cx - fr, cy - int(fr * 1.25), 2 * fr, int(2.5 * fr)) for s, (cx, cy) in faces.items()}


# ── scenari ───────────────────────────────────────────────────────────────

def _words(text: str, spk: str) -> list[dict]:
    return [{"w": w, "spk": spk} for w in text.split()]


def podcast_items() -> list[dict]:
    """~50 s, due parlanti, frasi con ganci, pause lunghe, eh non trascritti e un 'ehm' trascritto."""
    S = _words
    it: list[dict] = []
    def sent(text, spk, pause=0.9):
        it.extend(S(text, spk)); it.append({"pause": pause})
    sent("Benvenuti a tutti.", "A", 1.1)
    sent("Oggi parliamo di una cosa che nessuno vi dice sul montaggio video.", "A", 0.8)
    sent("Davvero?", "B", 0.7)
    it.extend(S("Sì, il segreto", "A")); it.append({"filler": "eh", "spk": "A", "listed": False, "dur": 0.38})
    it.append({"pause": 0.15}); it.extend(S("non è il software.", "A")); it.append({"pause": 0.9})
    sent("È il ritmo! Ogni pausa morta di mezzo secondo vi costa il quaranta per cento della ritenzione.", "A", 1.3)
    sent("Ma io ho sempre tagliato a occhio.", "B", 0.8)
    it.extend(S("Ecco l'errore", "A")); it.append({"filler": "ehm", "spk": "A", "listed": True, "dur": 0.42})
    it.extend(S("più comune: tagliare dove sembra giusto invece che dove il suono finisce davvero.", "A"))
    it.append({"pause": 1.0})
    sent("Quindi come si fa?", "B", 0.6)
    sent("Si guarda l'onda audio, si cerca il silenzio vero e si taglia lì, mai dentro una parola.", "A", 0.9)
    sent("Fantastico, grazie mille per la spiegazione.", "B", 0.8)
    return it


def make_podcast(dirpath: Path, seed: int = 7, jitter: float = 0.10) -> dict:
    audio, truth, tr = synth_track(podcast_items(), seed=seed, jitter=jitter)
    v = dirpath / "podcast.mp4"
    boxes = render_video(v, audio, truth, "two")
    tr.source_id = "podcast"
    for w in tr.words:
        w.source_id = "podcast"
    return {"path": v, "audio": audio, "truth": truth, "transcript": tr, "faces": boxes}


SCRIPT_TEXT = """Smetti di perdere tempo nel montaggio.
Il primo errore è tagliare a occhio le pause.
Il secondo è non guardare mai l'onda audio.
Prova oggi stesso e vedrai la differenza."""


def script_takes() -> dict[str, list[dict]]:
    """Tre clip con più take, esitazioni e false partenze."""
    S = _words
    c1: list[dict] = []
    # take 1 inciampa, take 2 pulito
    c1 += S("Smetti di perdere", "A") + [{"pause": 0.5}] + S("scusa", "A") + [{"pause": 1.2}]
    c1 += S("Smetti di perdere tempo nel montaggio.", "A") + [{"pause": 1.6}]
    c1 += S("Il primo errore è", "A") + [{"filler": "eh", "spk": "A", "listed": False, "dur": 0.4}] + [{"pause": 0.2}]
    c1 += S("tagliare a occhio le pause.", "A") + [{"pause": 1.4}]
    c2: list[dict] = []
    c2 += S("Il secondo è è non guardare mai", "A") + [{"pause": 0.6}] + S("Il secondo è non guardare mai l'onda audio.", "A") + [{"pause": 1.5}]
    c2 += S("Il primo errore è tagliare a occhio le pause.", "A") + [{"pause": 1.0}]
    c3: list[dict] = []
    c3 += S("Prova oggi stesso e vedrai la differenza.", "A") + [{"pause": 1.0}]
    return {"clip1": c1, "clip2": c2, "clip3": c3}


def make_script_project(dirpath: Path, seed: int = 11, jitter: float = 0.09) -> dict:
    out = {"script": SCRIPT_TEXT, "clips": {}}
    for k, (cid, items) in enumerate(script_takes().items()):
        audio, truth, tr = synth_track(items, seed=seed + k, jitter=jitter)
        v = dirpath / f"{cid}.mp4"
        render_video(v, audio, truth, "one")
        tr.source_id = cid
        for w in tr.words:
            w.source_id = cid
        out["clips"][cid] = {"path": v, "audio": audio, "truth": truth, "transcript": tr}
    return out


LONG_SENTENCES = [
    "Oggi vi racconto come ho triplicato le visualizzazioni in soli trenta giorni.",
    "Il segreto non è postare di più, è postare meglio.",
    "Molti creator commettono questo errore enorme senza accorgersene mai.",
    "Pensano che la qualità del video conti più di tutto il resto.",
    "Invece i primi tre secondi decidono il novanta per cento del risultato!",
    "Hai mai guardato quanto durano le tue pause morte?",
    "Ogni mezzo secondo di silenzio fa scappare lo spettatore.",
    "Quindi la prima regola è tagliare tutto quello che non serve davvero.",
    "La seconda regola riguarda il gancio: devi promettere un risultato concreto subito.",
    "Perché nessuno resta per ascoltare un'introduzione lunga e noiosa.",
    "Terzo punto: i sottotitoli animati aumentano la ritenzione del quaranta per cento.",
    "Lo dicono i dati di milioni di video analizzati negli ultimi due anni.",
    "Ma attenzione, non basta mettere le parole sullo schermo senza criterio.",
    "Bisogna evidenziare solo le parole chiave, quelle che portano il significato.",
    "Come si sceglie la parola giusta da colorare?",
    "Si guarda quella che cambia il senso della frase, di solito un numero o un verbo forte.",
    "Poi c'è il suono, che molti ignorano completamente.",
    "Un piccolo effetto sonoro sul cambio di scena risveglia l'attenzione.",
    "Non esagerate però, perché troppi effetti stancano subito.",
    "Ricordate sempre che il montaggio deve servire la storia e mai il contrario.",
    "Infine pubblicate con costanza, almeno tre volte a settimana.",
    "Chi smette dopo dieci giorni non vedrà mai i risultati veri.",
    "Questo è tutto quello che ho imparato, ora tocca a voi provare.",
    "Fatemi sapere nei commenti quale consiglio vi è piaciuto di più.",
]


def long_items(seed: int = 3) -> list[dict]:
    rng = np.random.default_rng(seed)
    it: list[dict] = []
    for k, s in enumerate(LONG_SENTENCES):
        spk = "A" if k % 5 != 4 else "B"
        words = s.split()
        for wi, w in enumerate(words):
            it.append({"w": w, "spk": spk})
            if wi == len(words) // 2 and rng.random() < 0.35:   # eh non trascritto a metà frase
                it.append({"filler": "eh", "spk": spk, "listed": False, "dur": 0.35}); it.append({"pause": 0.18})
        it.append({"pause": float(rng.choice([0.45, 0.7, 0.9, 1.2, 1.6]))})
    return it


def make_long(dirpath: Path, seed: int = 5, jitter: float = 0.10) -> dict:
    audio, truth, tr = synth_track(long_items(), seed=seed, jitter=jitter)
    v = dirpath / "long.mp4"
    boxes = render_video(v, audio, truth, "two", size=(320, 180))
    tr.source_id = "long"
    for w in tr.words:
        w.source_id = "long"
    return {"path": v, "audio": audio, "truth": truth, "transcript": tr, "faces": boxes}
