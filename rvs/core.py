"""core.py — shared helpers: paths, logging, seeded randomness, easing + spring physics, colour science (OKLab), palettes."""
from __future__ import annotations

import colorsys
import hashlib
import json
import math
import os
import random
import sys
import time
from pathlib import Path

import numpy as np

SKILL_ROOT = Path(__file__).resolve().parent.parent
ASSETS = SKILL_ROOT / "assets"
W, H, FPS = 1080, 1920, 30


# ───────────────────────── logging / io ─────────────────────────
_T0 = time.time()


def log(msg: str) -> None:
    print(f"[rvs {time.time() - _T0:6.1f}s] {msg}", file=sys.stderr, flush=True)


class RvsError(RuntimeError):
    """A user-facing failure with a short code, e.g. RvsError('QA_FAIL', '...')."""

    def __init__(self, code: str, msg: str):
        super().__init__(f"{code}: {msg}")
        self.code = code


def read_json(p, default=None):
    p = Path(p)
    if not p.exists():
        return default
    return json.loads(p.read_text(encoding="utf-8"))


def write_json(p, obj) -> None:
    p = Path(p)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + ".part")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, p)


def rvs_home() -> Path:
    """Where the variety ledger + taste memory live (shared across projects)."""
    p = Path(os.environ.get("RVS_HOME", Path.home() / ".rvs"))
    p.mkdir(parents=True, exist_ok=True)
    return p


def state_home() -> Path:
    """Variety ledger + taste memory. RVS_HOME wins; else the committed `channel/state/` of the skill repo (so a new cloud
    session still remembers past videos' looks); else ~/.rvs. Models/caches stay in rvs_home()."""
    if os.environ.get("RVS_HOME"):
        return rvs_home()
    p = Path(__file__).resolve().parent.parent / "channel" / "state"
    if p.is_dir():
        return p
    return rvs_home()


def stable_seed(*parts) -> int:
    return int(hashlib.sha256("|".join(map(str, parts)).encode()).hexdigest()[:12], 16)


class Rng(random.Random):
    def wchoice(self, options: dict | list, weights=None):
        if isinstance(options, dict):
            keys = list(options)
            ws = [max(0.0, float(options[k])) for k in keys]
        else:
            keys, ws = list(options), list(weights or [1.0] * len(options))
        if sum(ws) <= 0:
            return self.choice(keys)
        return self.choices(keys, ws, k=1)[0]


# ───────────────────────── easing + springs ─────────────────────────
def clamp(x, a=0.0, b=1.0):
    return a if x < a else b if x > b else x


def lerp(a, b, t):
    return a + (b - a) * t


def smoothstep(t):
    t = clamp(t)
    return t * t * (3 - 2 * t)


def ease_out_cubic(t):
    t = clamp(t)
    return 1 - (1 - t) ** 3


def ease_in_out_cubic(t):
    t = clamp(t)
    return 4 * t * t * t if t < 0.5 else 1 - (-2 * t + 2) ** 3 / 2


def ease_out_expo(t):
    t = clamp(t)
    return 1.0 if t >= 1 else 1 - 2 ** (-10 * t)


def ease_in_cubic(t):
    t = clamp(t)
    return t * t * t


def spring(t: float, omega: float = 16.0, zeta: float = 0.5) -> float:
    """Step response of a damped harmonic oscillator, 0 → 1 (overshoots when zeta < 1). t in seconds."""
    if t <= 0:
        return 0.0
    if zeta < 1:
        wd = omega * math.sqrt(1 - zeta * zeta)
        return 1 - math.exp(-zeta * omega * t) * (math.cos(wd * t) + (zeta * omega / wd) * math.sin(wd * t))
    return 1 - math.exp(-omega * t) * (1 + omega * t)


def impulse(t: float, omega: float = 18.0, zeta: float = 0.35) -> float:
    """Decaying oscillation starting at 1 (for punches / shakes / wobble)."""
    if t < 0:
        return 0.0
    wd = omega * math.sqrt(max(1e-6, 1 - zeta * zeta))
    return math.exp(-zeta * omega * t) * math.cos(wd * t)


# Motion personalities (spring constants + timing). Chosen per video by Style DNA.
MOTION = {
    "snappy":  {"omega": 24.0, "zeta": 0.55, "stagger": 0.07, "travel": 140, "idle": 0.5, "punch": 0.045},
    "elastic": {"omega": 17.0, "zeta": 0.33, "stagger": 0.09, "travel": 180, "idle": 1.0, "punch": 0.06},
    "smooth":  {"omega": 9.5,  "zeta": 1.0,  "stagger": 0.12, "travel": 90,  "idle": 0.7, "punch": 0.025},
    "heavy":   {"omega": 13.0, "zeta": 0.68, "stagger": 0.10, "travel": 220, "idle": 0.4, "punch": 0.08},
    "glitchy": {"omega": 30.0, "zeta": 0.8,  "stagger": 0.05, "travel": 120, "idle": 0.3, "punch": 0.05, "jitter": True},
}


# ───────────────────────── colour ─────────────────────────
def hex2rgb(h: str) -> tuple:
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def rgb2hex(c) -> str:
    return "#%02X%02X%02X" % tuple(int(clamp(round(v), 0, 255)) for v in c[:3])


def rgba(c, a=255):
    c = hex2rgb(c) if isinstance(c, str) else tuple(c)
    return (int(c[0]), int(c[1]), int(c[2]), int(a))


def mix(c1, c2, t):
    a, b = (hex2rgb(c) if isinstance(c, str) else c for c in (c1, c2))
    return tuple(int(round(lerp(a[i], b[i], t))) for i in range(3))


def _lin(c):
    c = c / 255.0
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def _delin(c):
    c = np.clip(c, 0, 1)
    return np.where(c <= 0.0031308, c * 12.92, 1.055 * c ** (1 / 2.4) - 0.055) * 255.0


def srgb_to_oklab(rgb):
    """rgb: array (...,3) 0..255 → OKLab (...,3)."""
    r, g, b = np.moveaxis(_lin(np.asarray(rgb, dtype=np.float64)), -1, 0)
    l_ = np.cbrt(0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b)
    m_ = np.cbrt(0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b)
    s_ = np.cbrt(0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b)
    return np.stack([0.2104542553 * l_ + 0.7936177850 * m_ - 0.0040720468 * s_,
                     1.9779984951 * l_ - 2.4285922050 * m_ + 0.4505937099 * s_,
                     0.0259040371 * l_ + 0.7827717662 * m_ - 0.8086757660 * s_], axis=-1)


def oklab_to_srgb(lab):
    L, a, b = np.moveaxis(np.asarray(lab, dtype=np.float64), -1, 0)
    l_ = (L + 0.3963377774 * a + 0.2158037573 * b) ** 3
    m_ = (L - 0.1055613458 * a - 0.0638541728 * b) ** 3
    s_ = (L - 0.0894841775 * a - 1.2914855480 * b) ** 3
    rgb = np.stack([4.0767416621 * l_ - 3.3077115913 * m_ + 0.2309699292 * s_,
                    -1.2684380046 * l_ + 2.6097574011 * m_ - 0.3413193965 * s_,
                    -0.0041960863 * l_ - 0.7034186147 * m_ + 1.7076147010 * s_], axis=-1)
    return _delin(rgb)


def oklch(c):
    """'#hex' or rgb → (L, C, h_degrees)."""
    rgb = hex2rgb(c) if isinstance(c, str) else c
    L, a, b = srgb_to_oklab(np.array(rgb, dtype=np.float64))
    return float(L), float(math.hypot(a, b)), float(math.degrees(math.atan2(b, a)) % 360)


def _oklab_to_lin(L, a, b):
    l_ = (L + 0.3963377774 * a + 0.2158037573 * b) ** 3
    m_ = (L - 0.1055613458 * a - 0.0638541728 * b) ** 3
    s_ = (L - 0.0894841775 * a - 1.2914855480 * b) ** 3
    return np.array([4.0767416621 * l_ - 3.3077115913 * m_ + 0.2309699292 * s_,
                     -1.2684380046 * l_ + 2.6097574011 * m_ - 0.3413193965 * s_,
                     -0.0041960863 * l_ - 0.7034186147 * m_ + 1.7076147010 * s_])


def from_oklch(L, C, h) -> str:
    """OKLCH → '#hex', reducing chroma until the colour is inside the sRGB gamut."""
    for _ in range(40):
        lin = _oklab_to_lin(L, C * math.cos(math.radians(h)), C * math.sin(math.radians(h)))
        if np.all(lin >= -0.001) and np.all(lin <= 1.001):
            return rgb2hex(_delin(lin))
        C *= 0.92
    return rgb2hex(_delin(_oklab_to_lin(L, 0.0, 0.0)))


def rel_lum(c) -> float:
    r, g, b = _lin(np.array(hex2rgb(c) if isinstance(c, str) else c, dtype=np.float64))
    return float(0.2126 * r + 0.7152 * g + 0.0722 * b)


def contrast(c1, c2) -> float:
    a, b = sorted((rel_lum(c1), rel_lum(c2)), reverse=True)
    return (a + 0.05) / (b + 0.05)


def ensure_contrast(fg: str, bg: str, ratio: float = 4.5) -> str:
    """Push fg lightness away from bg until the WCAG ratio is met."""
    if contrast(fg, bg) >= ratio:
        return fg
    L, C, h = oklch(fg)
    up = rel_lum(bg) < 0.25
    for _ in range(60):
        L = clamp(L + (0.02 if up else -0.02), 0, 1)
        cand = from_oklch(L, C * 0.97, h)
        if contrast(cand, bg) >= ratio:
            return cand
    return "#FFFFFF" if up else "#0A0A0A"


def hue_name(h: float) -> str:
    names = ["red", "orange", "amber", "yellow", "lime", "green", "teal", "cyan", "azure", "blue", "violet", "magenta"]
    return names[int(((h + 15) % 360) // 30)]


def extract_palette(img, k: int = 6, seed: int = 7) -> list[dict]:
    """k-means in OKLab on a 72×72 thumbnail → [{'hex','weight','L','C','h'}] sorted by weight."""
    from PIL import Image
    im = img.convert("RGB").resize((72, 72), Image.Resampling.BILINEAR)
    px = np.asarray(im, dtype=np.float64).reshape(-1, 3)
    lab = srgb_to_oklab(px)
    rng = np.random.default_rng(seed)
    cent = lab[rng.choice(len(lab), k, replace=False)]
    for _ in range(14):
        d = ((lab[:, None, :] - cent[None, :, :]) ** 2).sum(-1)
        lab_i = d.argmin(1)
        for j in range(k):
            sel = lab[lab_i == j]
            if len(sel):
                cent[j] = sel.mean(0)
    out = []
    for j in range(k):
        wgt = float((lab_i == j).mean())
        if wgt <= 0:
            continue
        hexv = rgb2hex(oklab_to_srgb(cent[j]))
        L, C, h = oklch(hexv)
        out.append({"hex": hexv, "weight": round(wgt, 4), "L": round(L, 3), "C": round(C, 3), "h": round(h, 1)})
    return sorted(out, key=lambda c: -c["weight"])


def hsv_jitter(c: str, dh=0.0, ds=0.0, dv=0.0) -> str:
    r, g, b = (v / 255 for v in hex2rgb(c))
    h, s, v = colorsys.rgb_to_hsv(r, g, b)
    r, g, b = colorsys.hsv_to_rgb((h + dh) % 1, clamp(s + ds), clamp(v + dv))
    return rgb2hex((r * 255, g * 255, b * 255))


def ffprobe_duration(path) -> float:
    import subprocess
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", str(path)],
                         capture_output=True, text=True, timeout=60).stdout.strip()
    return float(out) if out else 0.0
