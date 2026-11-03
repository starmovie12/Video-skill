"""voice.py — the voice layer.

Engines (pick with project.voice.engine; "auto" tries them in order):
  elevenlabs  premium, most natural; exact word timings from the /with-timestamps endpoint (needs ELEVENLABS_API_KEY)
  recording   the operator's OWN voice (one file for the whole script, or one per beat) → Whisper forced alignment
  files       audio made with ANY other TTS (Sarvam, Gemini, OpenAI …), one file per beat → Whisper forced alignment
  edge        free Microsoft neural voices, exact WordBoundary timings (needs internet)
  kokoro / espeak   offline fallbacks (timings aligned by Whisper if installed, else estimated)

After synthesis every beat goes through the "reel voice" treatment:
  tighten long pauses → dramatic micro-pause before hero words → designed gaps between beats → (in the mix) broadcast chain.
"""
from __future__ import annotations

import asyncio
import base64
import difflib
import hashlib
import importlib.util
import json
import os
import re
import shutil
import subprocess
import urllib.error
import urllib.request
from pathlib import Path

import numpy as np

from .core import RvsError, clamp, log, rvs_home

SR = 48000

# Free voice presets (edge-tts). The Multilingual voices are the newer, more conversational generation; Madhur/Swara are native Hindi.
PRESETS = {
    "hindi_male": {"voice": "hi-IN-MadhurNeural", "rate": "+20%", "pitch": "-2Hz"},
    "hindi_female": {"voice": "hi-IN-SwaraNeural", "rate": "+16%", "pitch": "+0Hz"},
    "multi_male": {"voice": "en-US-AndrewMultilingualNeural", "rate": "+12%", "pitch": "+0Hz"},
    "multi_male2": {"voice": "en-US-BrianMultilingualNeural", "rate": "+12%", "pitch": "+0Hz"},  # most conversational; Hindi intelligibility 0.87 vs 0.88 Madhur (Whisper, MEASURED)
    "multi_female": {"voice": "en-US-AvaMultilingualNeural", "rate": "+12%", "pitch": "+0Hz"},
}

# Reel voice chain (ffmpeg): rumble cut, mud cut, presence + air, de-ess, firm compression, safety limiter.
VOICE_CHAIN = ("highpass=f=80,equalizer=f=220:t=q:w=1.0:g=-2.5,"
               "acompressor=threshold=0.05:ratio=6:attack=2:release=50:knee=4:makeup=3,"          # level the syllables
               "equalizer=f=3600:t=q:w=1.3:g=3,treble=g=1.5:f=9000,deesser=i=0.4,"                 # presence + air, tame 's'
               "acompressor=threshold=0.3:ratio=3:attack=1:release=30:makeup=1.5,alimiter=limit=0.9:level=disabled")  # glue + safety


# ───────────────────────── small helpers ─────────────────────────
def ffmpeg_decode(path, sr=SR, ch=1) -> np.ndarray:
    out = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-f", "f32le", "-ac", str(ch), "-ar", str(sr), "-"],
                         capture_output=True, timeout=600).stdout
    a = np.frombuffer(out, np.float32).copy()
    return a.reshape(-1, ch) if ch > 1 else a


def write_wav(path, x: np.ndarray, sr=SR):
    import wave
    x = np.clip(x, -1, 1)
    if x.ndim == 1:
        x = x[:, None]
    pcm = (x * 32767).astype("<i2")
    with wave.open(str(path), "wb") as w:
        w.setnchannels(pcm.shape[1])
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(pcm.tobytes())


def _norm(s):
    return re.sub(r"[^\wऀ-ॿ]", "", (s or "").lower())


DEVA_VOWELS = re.compile(r"[अ-औा-ौॠ-ॣ]")
LAT_VOWELS = re.compile(r"[aeiouy]+", re.I)


def syllables(w: str) -> float:
    d = len(DEVA_VOWELS.findall(w))
    consonants = len(re.findall(r"[क-ह]", w))
    lat = len(LAT_VOWELS.findall(w))
    return max(1.0, d + 0.5 * max(0, consonants - d) + lat + (0.6 if any(ch.isdigit() for ch in w) else 0))


def _trim(x: np.ndarray, thr=0.012):
    idx = np.where(np.abs(x) > thr)[0]
    if len(idx) == 0:
        return x, 0.0
    a = max(0, idx[0] - int(0.025 * SR))
    b = min(len(x), idx[-1] + int(0.07 * SR))
    return x[a:b], a / SR


def _estimate_words(x: np.ndarray, tokens: list[str]) -> list[tuple]:
    """No timing source at all: voiced span split by syllable weight, snapped to energy dips (ESTIMATED)."""
    hop = int(0.01 * SR)
    e = np.array([np.sqrt(np.mean(x[i:i + hop] ** 2)) for i in range(0, max(1, len(x) - hop), hop)])
    dur = len(x) / SR
    wts = np.array([syllables(t) for t in tokens], float)
    cum = np.concatenate([[0], np.cumsum(wts)]) / wts.sum() * dur
    out = []
    for i in range(len(tokens)):
        a, b = cum[i], cum[i + 1]
        j = int(a * 100)
        lo, hi = max(0, j - 8), min(len(e) - 1, j + 8)
        if hi > lo and i > 0:
            a = (lo + int(np.argmin(e[lo:hi]))) / 100
        out.append((a, b))
    for i in range(len(out) - 1):
        out[i] = (out[i][0], max(out[i][0] + 0.06, out[i + 1][0]))
    return out


# ───────────────────────── forced alignment (Whisper) ─────────────────────────
_WHISPER = {}
DEVA_SKEL = re.compile(r"[ा-्ँ-ः़॑-॔ॢॣ]")


def _skel(s: str) -> str:
    """Comparison skeleton: lowercase, no punctuation, Devanagari vowel signs/nukta/halant removed (robust to spelling variants)."""
    s = _norm(s)
    s = DEVA_SKEL.sub("", s)
    return re.sub(r"[aeiou]", "", s) if not re.search(r"[ऀ-ॿ]", s) else s


def whisper_available() -> bool:
    return importlib.util.find_spec("faster_whisper") is not None


def whisper_words(x: np.ndarray, lang="hi", model=None) -> list[tuple]:
    """Word-level timestamps from faster-whisper (CPU, int8). Returns [(word, start, end)]."""
    from faster_whisper import WhisperModel
    name = model or os.environ.get("RVS_WHISPER_MODEL", "small")
    if name not in _WHISPER:
        log(f"align: loading Whisper '{name}' (first time downloads the model)")
        _WHISPER[name] = WhisperModel(name, device="cpu", compute_type="int8", download_root=str(rvs_home() / "whisper"))
    pad = 0.6  # Whisper tends to drop words that start at sample 0 → pad both ends with silence
    xp = np.concatenate([np.zeros(int(pad * SR), np.float32), x.astype(np.float32), np.zeros(int(pad * SR), np.float32)])
    a16 = np.frombuffer(subprocess.run(["ffmpeg", "-v", "error", "-f", "f32le", "-ar", str(SR), "-ac", "1", "-i", "-", "-f", "f32le", "-ar", "16000",
                                        "-ac", "1", "-"], input=xp.tobytes(), capture_output=True, timeout=600).stdout, np.float32)
    segs, _ = _WHISPER[name].transcribe(a16, language=lang, word_timestamps=True, beam_size=1, condition_on_previous_text=False)
    return [(w.word.strip(), max(0.0, float(w.start) - pad), max(0.0, float(w.end) - pad)) for s in segs for w in s.words if w.word.strip()]


def align_tokens(tokens: list[str], words: list[tuple]) -> list[tuple | None]:
    """Monotonic DTW between script tokens and recognised words (many-to-one both ways). Returns per-token (t0,t1) or None."""
    n, m = len(tokens), len(words)
    if not n or not m:
        return [None] * n
    A = [_skel(t) for t in tokens]
    B = [_skel(w[0]) for w in words]
    sim = np.zeros((n, m))
    for i in range(n):
        for j in range(m):
            if A[i] and B[j]:
                sim[i, j] = difflib.SequenceMatcher(None, A[i], B[j]).ratio()
    cost = 1 - sim
    D = np.full((n + 1, m + 1), np.inf)
    D[0, 0] = 0
    back = np.zeros((n + 1, m + 1), int)
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            opts = (D[i - 1, j - 1], D[i, j - 1] + 0.35, D[i - 1, j] + 0.35)
            k = int(np.argmin(opts))
            D[i, j] = cost[i - 1, j - 1] + opts[k]
            back[i, j] = k
    i, j = n, m
    match = [[] for _ in range(n)]
    while i > 0 and j > 0:
        match[i - 1].append(j - 1)
        k = back[i, j]
        if k == 0:
            i, j = i - 1, j - 1
        elif k == 1:
            j -= 1
        else:
            i -= 1
    out = []
    for i in range(n):
        js = [j for j in match[i] if sim[i, j] >= 0.34]
        if js:  # keep only the strongest matches (a weak neighbour must not stretch the word)
            top = max(sim[i, j] for j in js)
            js = [j for j in js if sim[i, j] >= 0.8 * top]
        out.append((min(words[j][1] for j in js), max(words[j][2] for j in js)) if js else None)
    # keep monotonic + fill gaps by interpolation
    known = [k for k, v in enumerate(out) if v]
    for k in range(n):
        if out[k] is None:
            prev = max([q for q in known if q < k], default=None)
            nxt = min([q for q in known if q > k], default=None)
            a = out[prev][1] if prev is not None else (words[0][1] if words else 0.0)
            b = out[nxt][0] if nxt is not None else a + 0.35
            span = max(0.08, b - a)
            gap_tokens = (nxt if nxt is not None else n) - (prev if prev is not None else -1) - 1
            pos = k - (prev if prev is not None else -1) - 1
            out[k] = (a + span * pos / max(1, gap_tokens), a + span * (pos + 1) / max(1, gap_tokens))
    for k in range(1, n):
        if out[k][0] < out[k - 1][0]:
            out[k] = (out[k - 1][1], max(out[k - 1][1] + 0.05, out[k][1]))
    return out


def timings_for(x: np.ndarray, tokens: list[str], lang="hi") -> tuple[list[tuple], str]:
    if whisper_available():
        try:
            ws = whisper_words(x, lang)
            al = align_tokens(tokens, ws)
            return al, f"aligned (Whisper {os.environ.get('RVS_WHISPER_MODEL', 'small')} forced alignment)"
        except Exception as e:  # alignment is best-effort; fall back but say so
            log(f"align: Whisper failed ({type(e).__name__}: {e}) → estimated timings")
    return _estimate_words(x, tokens), "estimated (no Whisper installed: syllable-weighted)"


# ───────────────────────── engines ─────────────────────────
def _ssl_connector():
    import ssl
    import aiohttp
    ca = os.environ.get("RVS_CA_BUNDLE") or os.environ.get("SSL_CERT_FILE") or os.environ.get("REQUESTS_CA_BUNDLE")
    if ca and os.path.exists(ca):
        return aiohttp.TCPConnector(ssl=ssl.create_default_context(cafile=ca))
    return None


async def _edge_one(text, voice, rate, pitch, out_mp3):
    import edge_tts
    kw = {"boundary": "WordBoundary"}
    conn = _ssl_connector()
    if conn is not None:
        kw["connector"] = conn
    if os.environ.get("HTTPS_PROXY"):
        kw["proxy"] = os.environ["HTTPS_PROXY"]
    c = edge_tts.Communicate(text, voice, rate=rate, pitch=pitch, **kw)
    bounds = []
    with open(out_mp3, "wb") as f:
        async for ch in c.stream():
            if ch["type"] == "audio":
                f.write(ch["data"])
            elif ch["type"] == "WordBoundary":
                bounds.append((ch["offset"] / 1e7, (ch["offset"] + ch["duration"]) / 1e7, ch["text"]))
    if not bounds or os.path.getsize(out_mp3) < 500:
        raise RvsError("TTS_EMPTY", "edge-tts returned no audio/boundaries")
    return bounds


async def _edge_all(jobs, conc=4):
    sem = asyncio.Semaphore(conc)

    async def run(j):
        async with sem:
            for attempt in range(3):
                try:
                    return await asyncio.wait_for(_edge_one(*j), timeout=45)
                except Exception as e:  # network flakiness → retry, then surface
                    if attempt == 2:
                        raise RvsError("TTS_EDGE", f"{type(e).__name__}: {e}") from e
                    await asyncio.sleep(1.5 * (attempt + 1))
    return await asyncio.gather(*(run(j) for j in jobs))


def _align_edge(tokens: list[str], bounds: list[tuple]) -> list[tuple]:
    """Map edge-tts WordBoundary events onto script tokens."""
    words = [(b[2], b[0], b[1]) for b in bounds]
    return align_tokens(tokens, words)


def eleven_chars_to_words(text: str, alignment: dict) -> list[tuple]:
    """ElevenLabs character alignment → per-token (t0, t1) for text.split()."""
    chars = alignment["characters"]
    st, en = alignment["character_start_times_seconds"], alignment["character_end_times_seconds"]
    out, cur = [], None
    for ch, a, b in zip(chars, st, en):
        if ch.isspace():
            if cur:
                out.append(cur)
                cur = None
            continue
        cur = (a, b) if cur is None else (cur[0], b)
    if cur:
        out.append(cur)
    n = len(text.split())
    if len(out) != n:  # normalisation changed token count → align by text instead
        words, buf, t0 = [], "", None
        for ch, a, b in zip(chars, st, en):
            if ch.isspace():
                if buf:
                    words.append((buf, t0, b))
                buf, t0 = "", None
            else:
                buf += ch
                t0 = a if t0 is None else t0
        if buf:
            words.append((buf, t0, en[-1]))
        return align_tokens(text.split(), words)
    return out


def _eleven_one(text, cfg, prev_text, next_text, out_mp3):
    key = os.environ.get("ELEVENLABS_API_KEY")
    if not key:
        raise RvsError("TTS_ELEVEN", "ELEVENLABS_API_KEY not set")
    vid = cfg.get("voice_id") or os.environ.get("RVS_ELEVENLABS_VOICE_ID")
    if not vid:
        raise RvsError("TTS_ELEVEN", "voice.voice_id (or RVS_ELEVENLABS_VOICE_ID) not set")
    body = {"text": text, "model_id": cfg.get("model", os.environ.get("RVS_ELEVENLABS_MODEL", "eleven_multilingual_v2")),
            "voice_settings": {"stability": cfg.get("stability", 0.38), "similarity_boost": cfg.get("similarity", 0.8),
                               "style": cfg.get("style", 0.35), "use_speaker_boost": True, "speed": cfg.get("speed", 1.08)}}
    if prev_text:
        body["previous_text"] = prev_text
    if next_text:
        body["next_text"] = next_text
    req = urllib.request.Request(f"https://api.elevenlabs.io/v1/text-to-speech/{vid}/with-timestamps?output_format=mp3_44100_128",
                                 data=json.dumps(body).encode(), method="POST",
                                 headers={"xi-api-key": key, "Content-Type": "application/json", "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            res = json.loads(r.read())
    except urllib.error.HTTPError as e:
        raise RvsError("TTS_ELEVEN", f"HTTP {e.code}: {e.read()[:200]!r}") from e
    Path(out_mp3).write_bytes(base64.b64decode(res["audio_base64"]))
    al = res.get("alignment") or res.get("normalized_alignment")
    if not al:
        raise RvsError("TTS_ELEVEN", "no alignment in response")
    return eleven_chars_to_words(text, al)


def kokoro_paths():
    m = os.environ.get("RVS_KOKORO_MODEL") or str(rvs_home() / "models/kokoro-v1.0.onnx")
    v = os.environ.get("RVS_KOKORO_VOICES") or str(rvs_home() / "models/voices-v1.0.bin")
    return (m, v) if os.path.exists(m) and os.path.exists(v) else (None, None)


def _pct(s, default=0) -> int:
    return int(re.sub(r"[^\-\d]", "", str(s)) or default)


# ───────────────────────── reel voice treatment ─────────────────────────
def tighten(x: np.ndarray, tw: list[tuple], toks=None, max_gap=0.2, keep=0.13):
    """Shorten inner pauses longer than max_gap to `keep` seconds (punchy reel pacing). Pauses after … ? ! stay dramatic (0.3 s)."""
    cuts = []
    for i in range(len(tw) - 1):
        g0, g1 = tw[i][1], tw[i + 1][0]
        k = 0.3 if (toks and re.search(r"[…?!]$", toks[i])) else keep
        if g1 - g0 > max(max_gap, k + 0.07):
            cuts.append((g0 + k / 2, g1 - k / 2))
    return _apply_edits(x, tw, cuts=cuts)


def hero_pauses(x: np.ndarray, tw: list[tuple], toks: list[str], hero: set, pause=0.16):
    """Dramatic micro-pause right before a hero word (only where the voice did not already pause)."""
    ins = []
    for i, tok in enumerate(toks):
        if i > 0 and _norm(tok) in hero:
            gap = tw[i][0] - tw[i - 1][1]
            if gap < pause * 0.6:
                ins.append((max(tw[i - 1][1], tw[i][0] - 0.01), pause - max(0.0, gap)))
    return _apply_edits(x, tw, inserts=ins)


def _apply_edits(x, tw, cuts=(), inserts=()):
    """Remove [a,b) spans and insert silence at points; shift word timings consistently (with 8 ms crossfades)."""
    ev = sorted([(a, "cut", b) for a, b in cuts] + [(t, "ins", d) for t, d in inserts])
    if not ev:
        return x, list(tw)
    out, pos = [], 0
    fade = int(0.008 * SR)
    shifts = []  # (time, delta)
    for t, kind, v in ev:
        i = int(t * SR)
        if i < pos:
            continue
        seg = x[pos:i].copy()
        if len(seg) > fade:
            seg[-fade:] *= np.linspace(1, 0, fade)
        out.append(seg)
        if kind == "cut":
            j = int(v * SR)
            shifts.append((t, -(v - t)))
            pos = j
        else:
            out.append(np.zeros(int(v * SR), np.float32))
            shifts.append((t, v))
            pos = i
        if pos < len(x):
            k = min(fade, len(x) - pos)
            x = x.copy()
            x[pos:pos + k] *= np.linspace(0, 1, k)
    out.append(x[pos:])

    def sh(t, start):  # a word that STARTS at the edit point moves; a word that ENDS there does not
        return t + sum(d for (st, d) in shifts if (st <= t if start else st < t))
    return np.concatenate(out).astype(np.float32), [(sh(a, True), sh(b, False)) for a, b in tw]


# ───────────────────────── main entry ─────────────────────────
def _voice_cfg(project):
    v = dict(project.get("voice", {}))
    preset = v.get("preset") or ("hindi_female" if project.get("category") == "product" and not v.get("voice") else None)
    if preset in PRESETS:
        for k, val in PRESETS[preset].items():
            v.setdefault(k, val)
    v.setdefault("voice", PRESETS["hindi_male"]["voice"])
    v.setdefault("rate", PRESETS["hindi_male"]["rate"])
    v.setdefault("pitch", "-2Hz" if "Madhur" in v["voice"] else "+0Hz")
    return v


def synth_voice(project: dict, work: Path, rate_override: str | None = None) -> dict:
    vcfg = _voice_cfg(project)
    engine = vcfg.get("engine", "auto")
    beats = project["beats"]
    tdir = work / "tts"
    tdir.mkdir(parents=True, exist_ok=True)
    lang = vcfg.get("lang", "hi")
    base_rate = rate_override or vcfg["rate"]

    def beat_rate(b):
        if "rate" in b:
            return b["rate"]
        bonus = {"hook": 5, "verdict": -3, "rating": -2}.get(b.get("role", ""), 0)
        return f"{_pct(base_rate) + bonus:+d}%"
    order = {"auto": ["elevenlabs", "edge", "kokoro", "espeak"]}.get(engine, [engine])
    if engine == "auto" and not os.environ.get("ELEVENLABS_API_KEY"):
        order = ["edge", "kokoro", "espeak"]
    clips, used, timing, last_err = [], None, "", None
    for eng in order:
        try:
            clips = []
            if eng == "edge":
                if importlib.util.find_spec("edge_tts") is None:
                    raise RvsError("TTS_EDGE", "edge-tts not installed")
                jobs, metas = [], []
                for i, b in enumerate(beats):
                    say = b.get("say") or b.get("show")
                    h = hashlib.sha1(json.dumps([eng, vcfg["voice"], beat_rate(b), vcfg["pitch"], say]).encode()).hexdigest()[:16]
                    mp3, js = tdir / f"{h}.mp3", tdir / f"{h}.json"
                    metas.append((mp3, js, say))
                    if not js.exists():
                        jobs.append((i, (say, vcfg["voice"], beat_rate(b), vcfg["pitch"], str(mp3))))
                if jobs:
                    log(f"voice: edge-tts {vcfg['voice']} · {len(jobs)} beats to synthesize (cached {len(beats) - len(jobs)})")
                    res = asyncio.run(_edge_all([j for _, j in jobs]))
                    for (i, _), bounds in zip(jobs, res):
                        metas[i][1].write_text(json.dumps(bounds, ensure_ascii=False))
                for mp3, js, say in metas:
                    x, off = _trim(ffmpeg_decode(mp3))
                    toks = say.split()
                    tw = [(max(0.0, a - off), max(0.0, b - off)) for a, b in _align_edge(toks, json.loads(js.read_text()))]
                    clips.append((x, toks, tw))
                timing = "exact (edge-tts WordBoundary)"
            elif eng == "elevenlabs":
                for i, b in enumerate(beats):
                    say = b.get("say") or b.get("show")
                    prev = beats[i - 1].get("say") if i else None
                    nxt = beats[i + 1].get("say") if i + 1 < len(beats) else None
                    h = hashlib.sha1(json.dumps([eng, vcfg.get("voice_id"), vcfg.get("model"), say]).encode()).hexdigest()[:16]
                    mp3, js = tdir / f"el_{h}.mp3", tdir / f"el_{h}.json"
                    if not js.exists():
                        js.write_text(json.dumps(_eleven_one(say, vcfg, prev, nxt, mp3)))
                    x, off = _trim(ffmpeg_decode(mp3))
                    tw = [(max(0.0, a - off), max(0.0, b_ - off)) for a, b_ in json.loads(js.read_text())]
                    clips.append((x, say.split(), tw))
                timing = "exact (ElevenLabs character alignment)"
            elif eng in ("recording", "files"):
                timing = _recorded(project, vcfg, beats, work, lang, clips)
            elif eng == "kokoro":
                from kokoro_onnx import Kokoro
                m, v = kokoro_paths()
                if not m:
                    raise RvsError("TTS_KOKORO", "Kokoro model files not found (set RVS_KOKORO_MODEL / RVS_KOKORO_VOICES)")
                k = Kokoro(m, v)
                spd = float(clamp(1.0 + _pct(base_rate) / 100 * 0.8, 0.8, 1.35))
                for b in beats:
                    say = b.get("say") or b.get("show")
                    a, sr = k.create(say, voice=vcfg.get("kokoro_voice", "hm_omega"), speed=spd, lang=vcfg.get("kokoro_lang", "hi"))
                    x = np.asarray(a, np.float32)
                    if sr != SR:
                        x = np.interp(np.linspace(0, len(x) - 1, int(len(x) * SR / sr)), np.arange(len(x)), x).astype(np.float32)
                    x, _ = _trim(x)
                    tw, timing = timings_for(x, say.split(), lang)
                    clips.append((x, say.split(), tw))
            else:
                exe = shutil.which("espeak-ng") or shutil.which("espeak")
                if not exe:
                    raise RvsError("TTS_NONE", "no espeak-ng")
                for b in beats:
                    say = b.get("say") or b.get("show")
                    wav = tdir / f"es_{hashlib.sha1(say.encode()).hexdigest()[:10]}.wav"
                    subprocess.run([exe, "-v", vcfg.get("espeak_voice", "hi"), "-s", "185", "-w", str(wav), say], check=True, timeout=120)
                    x, _ = _trim(ffmpeg_decode(wav))
                    tw, timing = timings_for(x, say.split(), lang)
                    clips.append((x, say.split(), tw))
            used = eng
            break
        except Exception as e:  # try the next engine, but remember why
            last_err = e
            log(f"voice: engine {eng} failed → {type(e).__name__}: {str(e)[:200]}")
    if used is None:
        raise RvsError("TTS_FAIL", f"all TTS engines failed: {last_err}")
    return _assemble(project, dict(vcfg, rate=base_rate), beats, clips, used, timing, work)


def _recorded(project, vcfg, beats, work, lang, clips) -> str:
    """Operator recording(s) or per-beat files from any TTS → Whisper alignment."""
    root = work.parent
    per_beat = [b.get("audio") for b in beats]
    if all(per_beat):
        for b, f in zip(beats, per_beat):
            x, _ = _trim(ffmpeg_decode(root / f))
            toks = (b.get("say") or b.get("show")).split()
            tw, how = timings_for(x, toks, lang)
            clips.append((x, toks, tw))
        return how
    f = vcfg.get("file")
    if not f:
        raise RvsError("TTS_REC", "voice.file (whole script) or beats[i].audio (per beat) required for engine 'recording'/'files'")
    x, _ = _trim(ffmpeg_decode(root / f))
    toks_all, owner = [], []
    for i, b in enumerate(beats):
        t = (b.get("say") or b.get("show")).split()
        toks_all += t
        owner += [i] * len(t)
    tw, how = timings_for(x, toks_all, lang)
    # split the recording into beats at the midpoint of the gap between beats
    cuts = [0.0]
    for i in range(1, len(beats)):
        last = max(k for k, o in enumerate(owner) if o == i - 1)
        first = min(k for k, o in enumerate(owner) if o == i)
        cuts.append((tw[last][1] + tw[first][0]) / 2)
    cuts.append(len(x) / SR)
    for i in range(len(beats)):
        a, b_ = cuts[i], cuts[i + 1]
        seg = x[int(a * SR):int(b_ * SR)]
        ks = [k for k, o in enumerate(owner) if o == i]
        clips.append((seg, [toks_all[k] for k in ks], [(tw[k][0] - a, tw[k][1] - a) for k in ks]))
    return how + " · operator recording"


def _assemble(project, vcfg, beats, clips, used, timing, work) -> dict:
    out, words, spans = [], [], []
    cur = 0.12
    out.append(np.zeros(int(cur * SR), np.float32))
    style = vcfg.get("pacing", "reel")  # reel = tightened pauses + hero micro-pauses; natural = untouched
    for i, (b, (x, toks, tw)) in enumerate(zip(beats, clips)):
        show = (b.get("show") or b.get("say")).split()
        if style == "reel" and len(tw) == len(toks) and used != "recording":
            x, tw = tighten(x, tw, toks)
            ref = show if len(show) == len(toks) else toks  # hero words are written in the caption (show) form
            x, tw = hero_pauses(x, tw, ref, {_norm(h) for hw in b.get("hero", []) for h in hw.split()})
        start = cur
        k, m = len(toks), len(show)
        if m == k:
            for j in range(k):
                words.append({"say": toks[j], "show": show[j], "t0": round(start + tw[j][0], 3), "t1": round(start + tw[j][1], 3), "beat": i})
        elif m < k:
            for s_ in range(m):
                j0 = int(s_ * k / m)
                j1 = max(j0, int((s_ + 1) * k / m) - 1)
                words.append({"say": " ".join(toks[j0:j1 + 1]), "show": show[s_], "t0": round(start + tw[j0][0], 3),
                              "t1": round(start + tw[j1][1], 3), "beat": i})
        else:
            groups = {}
            for s_ in range(m):
                groups.setdefault(int(s_ * k / m), []).append(s_)
            for j, ss in sorted(groups.items()):
                a, e_ = tw[j]
                for q, s_ in enumerate(ss):
                    words.append({"say": toks[j], "show": show[s_], "t0": round(start + a + (e_ - a) * q / len(ss), 3),
                                  "t1": round(start + a + (e_ - a) * (q + 1) / len(ss), 3), "beat": i})
        out.append(x)
        cur += len(x) / SR
        nxt = beats[i + 1] if i + 1 < len(beats) else None
        gap = b.get("pause_after_ms")
        if gap is None:
            gap = 70 if b.get("role") == "hook" else 320 if (nxt and nxt.get("role") == "verdict") else 200 if str(b.get("say", "")).strip().endswith("?") else 120
        if used == "recording":
            gap = 0
        gap = gap / 1000 if nxt else 0.25
        spans.append({"beat": i, "t0": round(start, 3), "t1": round(cur, 3)})
        out.append(np.zeros(int(gap * SR), np.float32))
        cur += gap
    voice_x = np.concatenate(out)
    write_wav(work / "voice.wav", voice_x)
    info = {"engine": used, "voice": vcfg.get("voice_id") or vcfg.get("voice"), "rate": vcfg.get("rate"), "timing": timing,
            "pacing": vcfg.get("pacing", "reel"), "duration": round(len(voice_x) / SR, 3), "words": words, "spans": spans}
    (work / "words.json").write_text(json.dumps(info, ensure_ascii=False, indent=1), encoding="utf-8")
    log(f"voice: {used} · {info['duration']:.1f}s · {len(words)} words · timing {timing}")
    return info


def voice_with_duration_control(project: dict, work: Path) -> dict:
    """Hit the target duration: if the first pass misses by >7 %, re-synthesize once with a corrected rate (+10…+32 %)."""
    info = synth_voice(project, work)
    tgt = project.get("target_sec")
    if not tgt or info["engine"] != "edge":
        return info
    err = info["duration"] / tgt - 1
    if abs(err) <= 0.07:
        return info
    r0 = _pct(info["rate"])
    r1 = int(clamp(int(round((1 + r0 / 100) * (1 + err) * 100 - 100)), 10, 32))
    if r1 == r0:
        return info
    log(f"duration control: {info['duration']:.1f}s vs target {tgt}s → rate {r0:+d}% → {r1:+d}%")
    return synth_voice(project, work, rate_override=f"{r1:+d}%")
