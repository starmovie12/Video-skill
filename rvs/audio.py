"""audio.py — voice (edge-tts with EXACT word timings → Kokoro → espeak-ng fallbacks), procedural licence-free music that is
composed to the video's timeline (hits on transitions, drop on the verdict), designed SFX (not plain sines), and the final mix
(voice chain, sidechain ducking, two-pass loudnorm to −14 LUFS / −1.5 dBTP)."""
from __future__ import annotations

import asyncio
import hashlib
import importlib.util
import json
import math
import os
import re
import shutil
import subprocess
from pathlib import Path

import numpy as np

from .core import RvsError, Rng, clamp, log, rvs_home

SR = 48000


# ───────────────────────── small DSP toolkit ─────────────────────────
def ffmpeg_decode(path, sr=SR, ch=1) -> np.ndarray:
    out = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-f", "f32le", "-ac", str(ch), "-ar", str(sr), "-"],
                         capture_output=True, timeout=300).stdout
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


def fft_filter(x: np.ndarray, sr=SR, lp=None, hp=None, order=2, peak=None):
    """Zero-phase magnitude filter in the frequency domain. peak=(freq, gain_db, q)."""
    n = len(x)
    N = 1 << (n - 1).bit_length()
    X = np.fft.rfft(x, N, axis=0)
    f = np.fft.rfftfreq(N, 1 / sr)
    g = np.ones_like(f)
    if lp:
        g *= 1 / np.sqrt(1 + (f / lp) ** (2 * order))
    if hp:
        g *= 1 / np.sqrt(1 + (hp / np.maximum(f, 1e-3)) ** (2 * order))
    if peak:
        f0, gdb, q = peak
        bw = f0 / q
        g *= 1 + (10 ** (gdb / 20) - 1) * np.exp(-((f - f0) / bw) ** 2)
    if X.ndim > 1:
        g = g[:, None]
    return np.fft.irfft(X * g, N, axis=0)[:n].astype(np.float32)


def env(n, a=0.005, d=0.1, s=0.6, r=0.2, sr=SR):
    e = np.zeros(n, np.float32)
    A, D, R = int(a * sr), int(d * sr), int(r * sr)
    A = max(1, min(A, n))
    e[:A] = np.linspace(0, 1, A)
    D2 = max(0, min(D, n - A))
    e[A:A + D2] = np.linspace(1, s, D2) if D2 else e[A:A + D2]
    e[A + D2:] = s
    if R and n > R:
        e[-R:] *= np.linspace(1, 0, R)
    return e


def expdecay(n, tau, sr=SR):
    return np.exp(-np.arange(n) / (tau * sr)).astype(np.float32)


def saw(freq, n, sr=SR, phase=0.0):
    t = np.arange(n) / sr
    return (2 * ((freq * t + phase) % 1.0) - 1).astype(np.float32)


def sine(freq, n, sr=SR, phase=0.0):
    if np.ndim(freq):
        ph = 2 * np.pi * np.cumsum(freq) / sr
        return np.sin(ph + phase).astype(np.float32)
    return np.sin(2 * np.pi * freq * np.arange(n) / sr + phase).astype(np.float32)


def noise(n, seed=0):
    return np.random.default_rng(seed).uniform(-1, 1, n).astype(np.float32)


def reverb_ir(sec=1.8, seed=1, bright=6000):
    n = int(sec * SR)
    out = []
    for c in range(2):
        x = noise(n, seed + c) * expdecay(n, sec / 5.5)
        out.append(fft_filter(x, lp=bright, order=1))
    ir = np.stack(out, 1)
    ir[: int(0.012 * SR)] *= np.linspace(0, 1, int(0.012 * SR))[:, None]
    return ir / np.abs(ir).sum(0).max() * 6


def convolve(x: np.ndarray, ir: np.ndarray):
    n = len(x) + len(ir) - 1
    N = 1 << (n - 1).bit_length()
    if x.ndim == 1:
        x = np.stack([x, x], 1)
    Y = np.fft.rfft(x, N, axis=0) * np.fft.rfft(ir, N, axis=0)
    return np.fft.irfft(Y, N, axis=0)[: len(x)].astype(np.float32)


def place(buf: np.ndarray, x: np.ndarray, t: float, gain=1.0, pan=0.0):
    i = int(t * SR)
    if i >= len(buf) or i + len(x) <= 0:
        return
    if i < 0:
        x, i = x[-i:], 0
    seg = x[: len(buf) - i]
    if buf.ndim == 2:
        if seg.ndim == 1:
            lg, rg = math.cos((pan + 1) * math.pi / 4), math.sin((pan + 1) * math.pi / 4)
            buf[i:i + len(seg), 0] += seg * gain * lg * 1.414
            buf[i:i + len(seg), 1] += seg * gain * rg * 1.414
        else:
            buf[i:i + len(seg)] += seg * gain
    else:
        buf[i:i + len(seg)] += seg * gain


def midi(n):
    return 440.0 * 2 ** ((n - 69) / 12)


# ───────────────────────── instruments ─────────────────────────
def kick(seed=0, punch=1.0, dur=0.42):
    n = int(dur * SR)
    t = np.arange(n) / SR
    f = 46 + 110 * np.exp(-t / 0.035) * punch
    body = sine(f, n) * expdecay(n, 0.16)
    click = fft_filter(noise(int(0.006 * SR), seed), hp=2000) * 0.5
    body[: len(click)] += click
    return np.tanh(body * 1.6) * 0.9


def snare(seed=0, dur=0.26, tone=185):
    n = int(dur * SR)
    nz = fft_filter(noise(n, seed), lp=8000, hp=1200) * expdecay(n, 0.06)
    tn = sine(tone, n) * expdecay(n, 0.05) * 0.6
    return (nz * 0.9 + tn) * 0.8


def clap(seed=0):
    n = int(0.22 * SR)
    nz = fft_filter(noise(n, seed), lp=5000, hp=900)
    e = np.zeros(n, np.float32)
    for k, off in enumerate((0, 0.011, 0.022)):
        i = int(off * SR)
        e[i:] += expdecay(n - i, 0.008 if k < 2 else 0.07) * (0.7 if k < 2 else 1)
    return nz * e * 0.8


def hat(seed=0, open_=False):
    n = int((0.28 if open_ else 0.05) * SR)
    return fft_filter(noise(n, seed), hp=7000, lp=14000) * expdecay(n, 0.09 if open_ else 0.014) * 0.5


def tom(seed=0, f0=95, dur=0.9):
    n = int(dur * SR)
    t = np.arange(n) / SR
    f = f0 * (0.62 + 0.38 * np.exp(-t / 0.08))
    b = sine(f, n) * expdecay(n, 0.28)
    hit = fft_filter(noise(int(0.03 * SR), seed), lp=2500) * 0.5
    b[: len(hit)] += hit
    return np.tanh(b * 1.4)


def bass808(freq, dur, glide_from=None):
    n = int(dur * SR)
    t = np.arange(n) / SR
    f = np.full(n, freq, np.float32) if glide_from is None else freq + (glide_from - freq) * np.exp(-t / 0.06)
    x = sine(f, n) * env(n, 0.003, 0.08, 0.8, min(0.15, dur * 0.4))
    return np.tanh(x * 2.2) * 0.55


def bass_saw(freq, dur, cutoff=420):
    n = int(dur * SR)
    x = (saw(freq, n) + saw(freq * 1.005, n, phase=0.3)) * 0.5
    x = fft_filter(x, lp=cutoff, order=2)
    return x * env(n, 0.004, 0.1, 0.7, min(0.08, dur * 0.3)) * 0.8


def pluck(freq, dur, bright=1.0, seed=0):
    n = int(dur * SR)
    t = np.arange(n) / SR
    idx = 2.6 * bright * np.exp(-t / 0.09)
    mod = np.sin(2 * np.pi * freq * 2 * t) * idx
    x = np.sin(2 * np.pi * freq * t + mod).astype(np.float32)
    return x * expdecay(n, 0.22 + 0.1 * bright) * env(n, 0.002, 0.0, 1.0, 0.03) * 0.5


def keys(freq, dur):
    n = int(dur * SR)
    t = np.arange(n) / SR
    idx = 1.2 * np.exp(-t / 0.3)
    x = np.sin(2 * np.pi * freq * t + idx * np.sin(2 * np.pi * freq * t)) * (1 + 0.15 * np.sin(2 * np.pi * 4.5 * t))
    return (x * env(n, 0.006, 0.4, 0.55, min(0.25, dur * 0.5))).astype(np.float32) * 0.35


def bell(freq, dur=1.2):
    n = int(dur * SR)
    t = np.arange(n) / SR
    x = np.sin(2 * np.pi * freq * t + 3.0 * np.exp(-t / 0.25) * np.sin(2 * np.pi * freq * 3.5 * t))
    return (x * expdecay(n, dur / 3.2)).astype(np.float32) * 0.35


def pad(freqs, dur, cutoff=1600, attack=0.6, seed=0):
    n = int(dur * SR)
    x = np.zeros(n, np.float32)
    r = np.random.default_rng(seed)
    for f in freqs:
        for d in (-0.006, 0.0, 0.007):
            x += saw(f * (1 + d), n, phase=r.uniform(0, 1))
    x = fft_filter(x / (len(freqs) * 3), lp=cutoff, order=2)
    return x * env(n, attack, 0.3, 0.85, min(0.8, dur * 0.4)) * 0.6


def braam(freq, dur=2.2, seed=0):
    n = int(dur * SR)
    x = sum(saw(freq * m * (1 + d), n) for m in (0.5, 1.0) for d in (-0.01, 0.0, 0.012))
    x = np.tanh(x * 0.9)
    lo = fft_filter(x, lp=380)
    hi = fft_filter(x, lp=2200)
    k = np.clip(np.linspace(1.2, -0.2, n), 0, 1)
    y = hi * k + lo * (1 - k)
    return (y * env(n, 0.01, 0.4, 0.7, dur * 0.6)).astype(np.float32) * 0.35


def riser(dur=1.2, seed=0):
    n = int(dur * SR)
    t = np.linspace(0, 1, n)
    nz = noise(n, seed)
    bands = [fft_filter(nz, lp=lp, hp=lp / 4) for lp in (900, 2500, 7000)]
    k = t[:, None]
    w = np.stack([np.clip(1 - k[:, 0] * 2, 0, 1), 1 - np.abs(k[:, 0] - 0.5) * 2, np.clip(k[:, 0] * 2 - 1, 0, 1)], 1)
    y = sum(b * w[:, i] for i, b in enumerate(bands))
    tone = sine(200 + 900 * t ** 2, n) * 0.15
    return ((y * 0.7 + tone) * t ** 1.6).astype(np.float32) * 0.6


# ───────────────────────── designed SFX ─────────────────────────
def sfx(kind: str, seed=0) -> np.ndarray:
    r = Rng(seed)
    if kind in ("whoosh", "swish"):
        dur = r.uniform(0.38, 0.6) if kind == "whoosh" else r.uniform(0.22, 0.32)
        n = int(dur * SR)
        nz = noise(n, seed)
        t = np.linspace(0, 1, n)
        lo, mid, hi = (fft_filter(nz, lp=f, hp=f / 3) for f in ((700, 2200, 6000) if kind == "whoosh" else (1500, 4000, 9000)))
        pos = np.sin(np.pi * t)
        y = lo * (1 - pos) + mid * pos * 0.8 + hi * pos ** 3 * 0.6
        return (y * np.sin(np.pi * t) ** 1.5).astype(np.float32) * (0.9 if kind == "whoosh" else 0.6)
    if kind == "impact":
        n = int(1.6 * SR)
        t = np.arange(n) / SR
        sub = sine(38 + 40 * np.exp(-t / 0.08), n) * expdecay(n, 0.45)
        nz = fft_filter(noise(int(0.2 * SR), seed), lp=2500) * expdecay(int(0.2 * SR), 0.05)
        y = sub.copy()
        y[: len(nz)] += nz * 0.8
        y = np.tanh(y * 1.8)
        wet = convolve(y, reverb_ir(1.6, seed))[:, 0]
        return (y * 0.8 + wet * 0.35).astype(np.float32) * 0.9
    if kind == "hit":
        k = kick(seed, 1.3, 0.35)
        sn = snare(seed + 1, 0.18, 220) * 0.6
        y = k.copy()
        y[: len(sn)] += sn
        return np.tanh(y * 1.3) * 0.8
    if kind == "pop":
        n = int(0.09 * SR)
        t = np.arange(n) / SR
        f0 = r.uniform(520, 760)
        y = sine(f0 * (0.45 + 0.55 * np.exp(-t / 0.018)), n) * expdecay(n, 0.025)
        return y * 0.55
    if kind == "tick":
        n = int(0.025 * SR)
        return fft_filter(noise(n, seed), lp=7000, hp=2500) * expdecay(n, 0.005) * 0.5
    if kind == "ding":
        return bell(r.choice([1046.5, 1174.7, 1318.5, 1568.0]), 0.9) * 0.9
    if kind == "shimmer":
        y = np.zeros(int(0.9 * SR), np.float32)
        for i, f in enumerate((1568, 1975, 2349, 3136)):
            place(y, bell(f, 0.6) * 0.5, i * 0.06)
        return y
    if kind in ("stamp", "thud"):
        n = int(0.5 * SR)
        t = np.arange(n) / SR
        y = sine(95 * (0.6 + 0.4 * np.exp(-t / 0.04)), n) * expdecay(n, 0.09)
        slap = fft_filter(noise(int(0.08 * SR), seed), lp=2400, hp=700) * expdecay(int(0.08 * SR), 0.02)
        y[: len(slap)] += slap * (1.0 if kind == "stamp" else 0.3)
        return np.tanh(y * 1.5) * 0.85
    if kind == "glitch":
        n = int(0.28 * SR)
        y = np.zeros(n, np.float32)
        rr = np.random.default_rng(seed)
        for _ in range(6):
            i = int(rr.uniform(0, n - 2000))
            ln = int(rr.uniform(400, 2400))
            sq = np.sign(sine(rr.uniform(200, 1800), ln)) * 0.3
            y[i:i + ln] += sq
        nz = noise(n, seed)
        y += np.round(nz * 4) / 4 * 0.15
        return y * 0.6
    if kind == "shutter":
        y = np.zeros(int(0.25 * SR), np.float32)
        for off in (0.0, 0.07):
            place(y, fft_filter(noise(int(0.02 * SR), seed), hp=1800) * expdecay(int(0.02 * SR), 0.004), off)
        return y * 0.8
    if kind in ("swell", "riser_short"):
        dur = 0.7 if kind == "swell" else 0.5
        n = int(dur * SR)
        t = np.linspace(0, 1, n)
        y = fft_filter(noise(n, seed), lp=3000 if kind == "swell" else 7000, hp=200) * t ** 2.2
        y[-int(0.03 * SR):] *= np.linspace(1, 0, int(0.03 * SR))
        return y * 0.5
    return np.zeros(10, np.float32)


# ───────────────────────── music composer ─────────────────────────
NOTE = {"C": 0, "Db": 1, "D": 2, "Eb": 3, "E": 4, "F": 5, "Gb": 6, "G": 7, "Ab": 8, "A": 9, "Bb": 10, "B": 11}
SCALES = {"minor": [0, 2, 3, 5, 7, 8, 10], "major": [0, 2, 4, 5, 7, 9, 11], "dorian": [0, 2, 3, 5, 7, 9, 10]}
MOODS = {
    "epic_trailer": dict(bpm=(84, 96), scale="minor", prog=[0, 5, 2, 6], kick="x...............", snare="........x.......", hat="", taiko=True,
                         bass="sub8", lead="", pad_cut=1400, braam=True),
    "dark_pulse":   dict(bpm=(96, 108), scale="minor", prog=[0, 0, 5, 4], kick="x.......x..x....", snare="....x.......x...", hat="x.x.x.x.x.x.x.x.",
                         bass="pulse16", lead="bell_sparse", pad_cut=900, braam=True),
    "upbeat_pop":   dict(bpm=(116, 124), scale="major", prog=[0, 4, 5, 3], kick="x...x...x...x...", snare="....x.......x...", hat="..x...x...x...x.",
                         bass="saw8", lead="pluck", pad_cut=2600, clap=True),
    "lofi_soft":    dict(bpm=(76, 86), scale="dorian", prog=[1, 4, 0, 5], kick="x.....x...x.....", snare="....x.......x...", hat="x.x.x.x.x.x.x.x.",
                         bass="sub", lead="keys", pad_cut=1200, swing=0.18, vinyl=True),
    "synthwave":    dict(bpm=(100, 110), scale="minor", prog=[0, 5, 3, 4], kick="x...x...x...x...", snare="....x.......x...", hat="x.x.x.x.x.x.x.x.",
                         bass="saw16", lead="arp", pad_cut=2200),
    "ambient_luxe": dict(bpm=(68, 76), scale="major", prog=[0, 3, 5, 4], kick="x...............", snare="", hat="", bass="sub",
                         lead="keys_sparse", pad_cut=1800, shimmer=True),
    "hype_trap":    dict(bpm=(138, 146), scale="minor", prog=[0, 5, 6, 4], kick="x......x..x.....", snare="........x.......", hat="xxxxxxxxxxxxxxxx",
                         bass="808", lead="bell_sparse", pad_cut=1000, half=True),
    "playful_pluck": dict(bpm=(108, 116), scale="major", prog=[0, 3, 4, 0], kick="x.......x.......", snare="....x.......x...", hat="..x...x...x...x.",
                          bass="bounce", lead="pluck", pad_cut=2400, clap=True),
}


def chord(root_midi, scale, degree, size=3):
    sc = SCALES[scale]
    notes = []
    for k in range(size):
        d = degree + 2 * k
        notes.append(root_midi + sc[d % 7] + 12 * (d // 7))
    return notes


def compose(mood: str, duration: float, key="D", seed=0, sections=None, hits=None) -> np.ndarray:
    """Render a stereo music bed of `duration` s. sections=[(t0,t1,'hook'|'body'|'build'|'drop'|'outro')], hits=[t,...] (transitions)."""
    M = MOODS.get(mood, MOODS["upbeat_pop"])
    r = Rng(seed)
    bpm = r.uniform(*M["bpm"])
    beat = 60 / bpm
    bar = beat * 4
    step = bar / 16
    n = int((duration + 2.0) * SR)
    drums = np.zeros((n, 2), np.float32)
    tonal = np.zeros((n, 2), np.float32)
    root = 36 + NOTE.get(key, 2)
    sections = sections or [(0, duration, "body")]

    def sec_at(t):
        for a, b, s in sections:
            if a <= t < b:
                return s
        return "outro"
    k_s, s_s, h_s = kick(seed, 1.0), snare(seed), hat(seed)
    cl = clap(seed)
    nbars = int(duration / bar) + 2
    for b in range(nbars):
        tb = b * bar
        sec = sec_at(tb + 0.01)
        deg = M["prog"][b % len(M["prog"])]
        ch = chord(root + 12, M["scale"], deg, 3)
        full = sec in ("hook", "drop")
        light = sec in ("body",)
        if sec != "outro":
            pc = pad([midi(x) for x in ch], bar + 0.4, M["pad_cut"] * (1.3 if full else 1.0), 0.35 if full else 0.7, seed + b)
            place(tonal, pad_stereo(pc, b), tb, 0.55 if full else 0.42)
        else:
            pc = pad([midi(x) for x in ch], bar * 1.5, M["pad_cut"] * 0.7, 1.0, seed + b)
            place(tonal, pad_stereo(pc, b), tb, 0.35)
            continue
        if sec == "build":
            continue
        for i in range(16):
            t = tb + i * step + (M.get("swing", 0) * step if i % 2 else 0)
            if M["kick"] and M["kick"][i] == "x" and (full or light):
                place(drums, k_s, t, 0.95 if full else 0.7)
            if M["snare"] and M["snare"][i] == "x" and (full or light):
                place(drums, cl if M.get("clap") and full else s_s, t, 0.6, 0.1)
            if M["hat"] and M["hat"][i] == "x" and (full or (light and i % 2 == 0)):
                place(drums, h_s, t, 0.35 if full else 0.25, r.uniform(-0.4, 0.4))
            if M.get("taiko") and i in (0, 6, 8, 12 if full else 99):
                place(drums, tom(seed + i, 70 if i == 0 else 92), t, 0.7 if full else 0.45, -0.3 if i % 2 else 0.3)
        bass = M["bass"]
        bn = midi(ch[0] - 12)
        if bass == "sub8":
            for i in range(0, 16, 2):
                place(tonal, bass_saw(bn, step * 1.8, 260), tb + i * step, 0.5 if full else 0.35)
        elif bass == "pulse16":
            for i in range(16):
                place(tonal, bass_saw(bn, step * 0.9, 380), tb + i * step, 0.38)
        elif bass in ("saw8", "saw16"):
            for i in range(0, 16, 1 if bass == "saw16" else 2):
                place(tonal, bass_saw(bn * (2 if (bass == "saw16" and i % 4 == 2) else 1), step * 0.9, 650), tb + i * step, 0.36)
        elif bass == "808":
            for i in (0, 7, 10):
                place(tonal, bass808(bn, step * 3.0, glide_from=bn * 1.5 if i == 10 else None), tb + i * step, 0.7)
        elif bass == "bounce":
            for i in (0, 3, 6, 8, 11, 14):
                place(tonal, pluck(bn * 2, step * 1.6, 0.4), tb + i * step, 0.55)
        else:
            place(tonal, bass808(bn, bar * 0.95), tb, 0.45)
        lead = M["lead"]
        scale_notes = [root + 24 + SCALES[M["scale"]][(deg + k) % 7] + 12 * ((deg + k) // 7) for k in range(8)]
        if lead == "pluck":
            for i in range(0, 16, 2):
                if r.random() < (0.75 if full else 0.5):
                    place(tonal, pluck(midi(r.choice(ch) + 12), step * 2, 0.9, seed + i), tb + i * step, 0.3, r.uniform(-0.5, 0.5))
        elif lead == "arp":
            for i in range(16):
                place(tonal, pluck(midi(ch[i % 3] + 12 + (12 if i % 8 >= 4 else 0)), step * 1.2, 1.2), tb + i * step, 0.24, -0.4 + 0.8 * (i % 2))
        elif lead in ("keys", "keys_sparse"):
            hits_ = (0, 6, 10) if lead == "keys" else (0, 8)
            for i in hits_:
                for x in ch:
                    place(tonal, keys(midi(x + 12), step * 5), tb + i * step, 0.3)
        elif lead == "bell_sparse" and b % 2 == 0:
            place(tonal, bell(midi(r.choice(scale_notes) + 12), 1.4), tb + r.choice([0, 4, 8]) * step, 0.22, r.uniform(-0.5, 0.5))
    # timeline-synced hits (transitions) + braam on the drop
    for t in hits or []:
        place(drums, tom(seed + int(t * 10), 64, 1.0), t, 0.55)
    for a, b, s in sections:
        if s == "build":
            ln = min(b - a, 2.5)
            place(tonal, riser(ln, seed), b - ln, 0.55)
        if s == "drop" and M.get("braam"):
            place(tonal, braam(midi(root - 12 + 12), 2.4, seed), a, 0.6)
        if s == "drop":
            place(drums, sfx("impact", seed), a, 0.55)
    if M.get("shimmer"):
        for t in np.arange(0, duration, bar * 2):
            place(tonal, sfx("shimmer", seed + int(t)), float(t) + bar, 0.18, r.uniform(-0.6, 0.6))
    mix_ = tonal * 0.9 + drums
    wet = convolve(mix_.mean(1) * 0.6, reverb_ir(2.0, seed, 5000))
    mix_ = mix_ + wet * 0.22
    if M.get("vinyl"):
        crackle = (np.random.default_rng(seed).random(n) > 0.9993).astype(np.float32) * 0.25
        mix_ += np.stack([crackle, np.roll(crackle, 37)], 1) + noise(n, seed)[:, None] * 0.004
    mix_ = mix_[: int(duration * SR)]
    fade = int(min(1.5, duration * 0.1) * SR)
    mix_[-fade:] *= np.linspace(1, 0, fade)[:, None]
    peak = np.abs(mix_).max() + 1e-9
    return (mix_ / peak * 0.8).astype(np.float32)


def pad_stereo(x, b):
    d = 120 + (b % 3) * 40
    return np.stack([x, np.concatenate([np.zeros(d, np.float32), x[:-d]])], 1)


# ───────────────────────── TTS ─────────────────────────
DEVA_VOWELS = re.compile(r"[अ-औा-ौॠ-ॣ]")
LAT_VOWELS = re.compile(r"[aeiouy]+", re.I)


def syllables(w: str) -> float:
    d = len(DEVA_VOWELS.findall(w))
    consonants = len(re.findall(r"[क-ह]", w))
    lat = len(LAT_VOWELS.findall(w))
    return max(1.0, d + 0.5 * max(0, consonants - d) + lat + (0.6 if any(ch.isdigit() for ch in w) else 0))


def _norm(s):
    return re.sub(r"[^\wऀ-ॿ]", "", (s or "").lower())


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


def _align(tokens: list[str], bounds: list[tuple]) -> list[tuple]:
    """Map edge-tts word boundaries onto the script tokens (greedy, tolerant to punctuation/number splitting)."""
    out = [None] * len(tokens)
    bi = 0
    for ti, tok in enumerate(tokens):
        nt = _norm(tok)
        if not nt:
            continue
        for look in range(bi, min(len(bounds), bi + 4)):
            nb = _norm(bounds[look][2])
            if nb and (nb == nt or nt.startswith(nb) or nb.startswith(nt) or nb in nt):
                t0, t1 = bounds[look][0], bounds[look][1]
                j = look + 1
                while j < len(bounds) and _norm(bounds[j][2]) and _norm(bounds[j][2]) in nt and not (ti + 1 < len(tokens) and _norm(bounds[j][2]) == _norm(tokens[ti + 1])):
                    t1 = bounds[j][1]
                    j += 1
                out[ti] = (t0, t1)
                bi = j
                break
    # interpolate gaps
    known = [i for i, v in enumerate(out) if v]
    for i in range(len(out)):
        if out[i] is None:
            prev = max([k for k in known if k < i], default=None)
            nxt = min([k for k in known if k > i], default=None)
            a = out[prev][1] if prev is not None else 0.0
            b = out[nxt][0] if nxt is not None else a + 0.3
            out[i] = (a, max(a + 0.08, b))
    return out


def _trim(x: np.ndarray, thr=0.012):
    idx = np.where(np.abs(x) > thr)[0]
    if len(idx) == 0:
        return x, 0.0
    a = max(0, idx[0] - int(0.025 * SR))
    b = min(len(x), idx[-1] + int(0.07 * SR))
    return x[a:b], a / SR


def _estimate_words(x: np.ndarray, tokens: list[str]) -> list[tuple]:
    """For engines without word events: voiced span split by syllable weight, snapped to energy dips (labelled ESTIMATED)."""
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


def kokoro_paths():
    m = os.environ.get("RVS_KOKORO_MODEL") or str(rvs_home() / "models/kokoro-v1.0.onnx")
    v = os.environ.get("RVS_KOKORO_VOICES") or str(rvs_home() / "models/voices-v1.0.bin")
    return (m, v) if os.path.exists(m) and os.path.exists(v) else (None, None)


def synth_voice(project: dict, work: Path, rate_override: str | None = None) -> dict:
    """Synthesize every beat → voice.wav + words.json (global word timings, beat spans). Cached by content hash."""
    vcfg = project.get("voice", {})
    engine = vcfg.get("engine", "auto")
    voice = vcfg.get("voice", "hi-IN-MadhurNeural")
    base_rate = rate_override or vcfg.get("rate", "+18%")
    pitch = vcfg.get("pitch", "+0Hz")
    beats = project["beats"]
    tdir = work / "tts"
    tdir.mkdir(parents=True, exist_ok=True)

    def beat_rate(b):
        if "rate" in b:
            return b["rate"]
        bonus = {"hook": 4, "verdict": -3, "cta": 0, "rating": -2}.get(b.get("role", ""), 0)
        r0 = int(re.sub(r"[^\-\d]", "", base_rate) or 0)
        return f"{r0 + bonus:+d}%"
    clips, used_engine, timing = [], None, "exact"
    order = ["edge", "kokoro", "espeak"] if engine == "auto" else [engine]
    last_err = None
    for eng in order:
        try:
            clips = []
            if eng == "edge":
                if importlib.util.find_spec("edge_tts") is None:
                    raise RvsError("TTS_EDGE", "edge-tts not installed")
                jobs, metas = [], []
                for i, b in enumerate(beats):
                    say = b.get("say") or b.get("show")
                    h = hashlib.sha1(json.dumps([eng, voice, beat_rate(b), pitch, say]).encode()).hexdigest()[:16]
                    mp3, js = tdir / f"{h}.mp3", tdir / f"{h}.json"
                    metas.append((mp3, js, say))
                    if not js.exists():
                        jobs.append((i, (say, voice, beat_rate(b), pitch, str(mp3))))
                if jobs:
                    log(f"voice: edge-tts {voice} · {len(jobs)} beats to synthesize (cached {len(beats) - len(jobs)})")
                    res = asyncio.run(_edge_all([j for _, j in jobs]))
                    for (i, _), bounds in zip(jobs, res):
                        metas[i][1].write_text(json.dumps(bounds, ensure_ascii=False))
                for mp3, js, say in metas:
                    x = ffmpeg_decode(mp3)
                    bounds = json.loads(js.read_text())
                    x, off = _trim(x)
                    toks = say.split()
                    tw = [(max(0.0, a - off), max(0.0, b - off)) for a, b in _align(toks, bounds)]
                    clips.append((x, toks, tw))
                timing = "exact (edge-tts WordBoundary)"
            elif eng == "kokoro":
                from kokoro_onnx import Kokoro
                m, v = kokoro_paths()
                if not m:
                    raise RvsError("TTS_KOKORO", "Kokoro model files not found (set RVS_KOKORO_MODEL / RVS_KOKORO_VOICES)")
                k = Kokoro(m, v)
                kv = vcfg.get("kokoro_voice", "hm_omega")
                spd = 1.0 + int(re.sub(r"[^\-\d]", "", base_rate) or 0) / 100 * 0.8
                for b in beats:
                    say = b.get("say") or b.get("show")
                    a, sr = k.create(say, voice=kv, speed=float(clamp(spd, 0.8, 1.35)), lang=vcfg.get("kokoro_lang", "hi"))
                    x = np.asarray(a, np.float32)
                    if sr != SR:
                        x = np.interp(np.linspace(0, len(x) - 1, int(len(x) * SR / sr)), np.arange(len(x)), x).astype(np.float32)
                    x, _ = _trim(x)
                    toks = say.split()
                    clips.append((x, toks, _estimate_words(x, toks)))
                timing = "estimated (Kokoro: syllable-weighted + energy snapping)"
            else:
                exe = shutil.which("espeak-ng") or shutil.which("espeak")
                if not exe:
                    raise RvsError("TTS_NONE", "no espeak-ng")
                for b in beats:
                    say = b.get("say") or b.get("show")
                    wav = tdir / f"es_{hashlib.sha1(say.encode()).hexdigest()[:10]}.wav"
                    subprocess.run([exe, "-v", vcfg.get("espeak_voice", "hi"), "-s", "185", "-w", str(wav), say], check=True, timeout=120)
                    x, _ = _trim(ffmpeg_decode(wav))
                    toks = say.split()
                    clips.append((x, toks, _estimate_words(x, toks)))
                timing = "estimated (espeak-ng)"
            used_engine = eng
            break
        except Exception as e:  # try the next engine, but remember why
            last_err = e
            log(f"voice: engine {eng} failed → {type(e).__name__}: {str(e)[:160]}")
    if used_engine is None:
        raise RvsError("TTS_FAIL", f"all TTS engines failed: {last_err}")
    # assemble with designed pauses
    out, words, spans, cur = [], [], [], 0.0
    lead = 0.12
    out.append(np.zeros(int(lead * SR), np.float32))
    cur = lead
    for i, (b, (x, toks, tw)) in enumerate(zip(beats, clips)):
        show = (b.get("show") or b.get("say")).split()
        start = cur
        k, m = len(toks), len(show)
        if m == k:
            for j in range(k):
                words.append({"say": toks[j], "show": show[j], "t0": round(start + tw[j][0], 3), "t1": round(start + tw[j][1], 3), "beat": i})
        elif m < k:  # several spoken tokens → one displayed word
            for s_ in range(m):
                j0 = int(s_ * k / m)
                j1 = max(j0, int((s_ + 1) * k / m) - 1)
                words.append({"say": " ".join(toks[j0:j1 + 1]), "show": show[s_], "t0": round(start + tw[j0][0], 3),
                              "t1": round(start + tw[j1][1], 3), "beat": i})
        else:  # one spoken token → several displayed words: split its interval
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
            gap = 90 if b.get("role") == "hook" else 380 if (nxt and nxt.get("role") == "verdict") else 260 if str(b.get("say", "")).strip().endswith("?") else 170
        gap = gap / 1000 if nxt else 0.25
        spans.append({"beat": i, "t0": round(start, 3), "t1": round(cur, 3)})
        out.append(np.zeros(int(gap * SR), np.float32))
        cur += gap
    voice_x = np.concatenate(out)
    wav = work / "voice.wav"
    write_wav(wav, voice_x)
    info = {"engine": used_engine, "voice": voice, "rate": base_rate, "timing": timing, "duration": round(len(voice_x) / SR, 3),
            "words": words, "spans": spans}
    (work / "words.json").write_text(json.dumps(info, ensure_ascii=False, indent=1), encoding="utf-8")
    log(f"voice: {used_engine} · {info['duration']:.1f}s · {len(words)} words · timing {timing}")
    return info


def voice_with_duration_control(project: dict, work: Path) -> dict:
    """Hit the target duration: if the first pass misses by >7 %, re-synthesize once with a corrected rate (bounded +0…+35 %)."""
    info = synth_voice(project, work)
    tgt = project.get("target_sec")
    if not tgt or info["engine"] != "edge":
        return info
    err = info["duration"] / tgt - 1
    if abs(err) <= 0.07:
        return info
    r0 = int(re.sub(r"[^\-\d]", "", info["rate"]) or 0)
    r1 = int(round((1 + r0 / 100) * (1 + err) * 100 - 100))
    r1 = int(clamp(r1, 10, 32))  # keep the voice energetic; bigger misses must be fixed in the script
    if r1 == r0:
        return info
    log(f"duration control: {info['duration']:.1f}s vs target {tgt}s → rate {r0:+d}% → {r1:+d}%")
    return synth_voice(project, work, rate_override=f"{r1:+d}%")


# ───────────────────────── mix ─────────────────────────
def ducking_env(voice: np.ndarray, hop=480):
    n = len(voice)
    fr = np.sqrt(np.add.reduceat(voice[: n - n % hop] ** 2, np.arange(0, n - n % hop, hop)) / hop) if n > hop else np.zeros(1)
    act = np.clip((20 * np.log10(fr + 1e-6) + 45) / 15, 0, 1)
    out = np.zeros_like(act)
    a_up, a_dn = 0.5, 0.06
    for i, v in enumerate(act):
        prev = out[i - 1] if i else 0
        out[i] = prev + (v - prev) * (a_up if v > prev else a_dn)
    r = np.repeat(out, hop)[:n] if len(out) else np.zeros(n)
    return np.pad(r, (0, n - len(r)), mode="edge") if 0 < len(r) < n else r


def loudnorm(inp: Path, outp: Path, I=-14.0, TP=-1.5, LRA=11):
    r = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(inp), "-af", f"loudnorm=I={I}:TP={TP}:LRA={LRA}:print_format=json",
                        "-f", "null", "-"], capture_output=True, text=True, timeout=300).stderr
    m = json.loads(r[r.rfind("{"): r.rfind("}") + 1])
    af = (f"loudnorm=I={I}:TP={TP}:LRA={LRA}:measured_I={m['input_i']}:measured_TP={m['input_tp']}:measured_LRA={m['input_lra']}:"
          f"measured_thresh={m['input_thresh']}:offset={m['target_offset']}:linear=true,aresample=48000")
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(inp), "-af", af, "-ar", "48000", str(outp)], check=True, timeout=300)
    return m


def measure_loudness(path: Path) -> dict:
    r = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(path), "-af", "loudnorm=print_format=json", "-f", "null", "-"],
                       capture_output=True, text=True, timeout=300).stderr
    m = json.loads(r[r.rfind("{"): r.rfind("}") + 1])
    return {"I": float(m["input_i"]), "TP": float(m["input_tp"]), "LRA": float(m["input_lra"])}


def build_mix(work: Path, voice_info: dict, duration: float, dna: dict, cues: list[dict], sections, hits, music_file=None) -> dict:
    vx = ffmpeg_decode(work / "voice.wav")
    # voice chain (MEASURED earlier on this stack): HPF, gentle compression, presence
    proc = work / "voice_proc.wav"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(work / "voice.wav"), "-af",
                    "highpass=f=75,acompressor=threshold=0.125:ratio=3:attack=6:release=90:makeup=1.6,equalizer=f=3200:t=q:w=1.1:g=2.2,"
                    "equalizer=f=250:t=q:w=1.0:g=-1.5", "-ar", "48000", "-ac", "1", str(proc)], check=True, timeout=300)
    vx = ffmpeg_decode(proc)
    n = int((duration + 0.05) * SR)
    vx = np.pad(vx, (0, max(0, n - len(vx))))[:n]
    seed = dna["seed"] % 100000
    if music_file and Path(music_file).exists():
        mus = ffmpeg_decode(music_file, ch=2)
        if len(mus) < n:
            mus = np.concatenate([mus] * (n // max(1, len(mus)) + 1))
        mus = mus[:n]
        fade = int(1.2 * SR)
        mus[-fade:] *= np.linspace(1, 0, fade)[:, None]
        mus = mus / (np.abs(mus).max() + 1e-9) * 0.8
        music_src = f"operator file {Path(music_file).name}"
    else:
        mus = compose(dna["music_mood"], duration + 0.05, dna.get("music_key", "D"), seed, sections, hits)
        mus = np.pad(mus, ((0, max(0, n - len(mus))), (0, 0)))[:n]
        music_src = f"procedural {dna['music_mood']} (original, licence-free)"
    duck = ducking_env(vx)[:n]
    g_music = (0.30 * (1 - 0.72 * duck))[:, None]
    fx = np.zeros((n, 2), np.float32)
    for i, c in enumerate(cues):
        x = sfx(c["kind"], seed + i)
        place(fx, x, max(0.0, c["t"]), 0.55 * c.get("gain", 1.0), c.get("pan", 0.0))
    out = np.stack([vx, vx], 1) * 0.92 + mus * g_music + fx * 0.85
    raw = work / "mix_raw.wav"
    write_wav(raw, out / max(1.0, np.abs(out).max()))
    final = work / "mix.wav"
    m = loudnorm(raw, final)
    stems = {"music_rms_db_no_voice": float(20 * np.log10(np.sqrt(np.mean((mus * g_music)[duck < 0.2] ** 2)) + 1e-9)) if (duck < 0.2).any() else None,
             "music_rms_db": float(20 * np.log10(np.sqrt(np.mean((mus * g_music) ** 2)) + 1e-9)),
             "sfx_count": len(cues), "music_source": music_src, "loudnorm_in": {k: m[k] for k in ("input_i", "input_tp")}}
    (work / "mix_stats.json").write_text(json.dumps(stems, indent=1))
    log(f"mix: music={music_src} · sfx={len(cues)} · loudnorm two-pass → −14 LUFS")
    return stems
