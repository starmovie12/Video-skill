"""engine.py — the motion engine. Layers (sprites + spring-driven enter/idle/exit), parallax camera with punches & shake,
scenes, designed transitions, and a frame compositor. Everything is a pure function of time → deterministic & parallel-safe."""
from __future__ import annotations

import math
from collections import OrderedDict

import numpy as np
from PIL import Image, ImageDraw

from .core import FPS, H, MOTION, W, clamp, ease_in_out_cubic, ease_out_cubic, ease_out_expo, hex2rgb, impulse, spring
from .typo import Sprite


class _LRU(OrderedDict):
    def __init__(self, n=10):
        super().__init__()
        self.n = n

    def get2(self, k):
        if k in self:
            self.move_to_end(k)
            return self[k]
        return None

    def put(self, k, v):
        self[k] = v
        if len(self) > self.n:
            self.popitem(last=False)


def alpha_mult(img: Image.Image, a: float) -> Image.Image:
    if a >= 0.999:
        return img
    out = img.copy()
    out.putalpha(img.getchannel("A").point(lambda v: int(v * a)))
    return out


def blit(frame: Image.Image, img: Image.Image, x: float, y: float) -> None:
    """alpha-composite img onto frame at (x,y) with clipping (Pillow refuses negative destinations)."""
    x, y = int(round(x)), int(round(y))
    sx0, sy0 = max(0, -x), max(0, -y)
    sx1, sy1 = min(img.width, frame.width - x), min(img.height, frame.height - y)
    if sx1 <= sx0 or sy1 <= sy0:
        return
    src = img if (sx0, sy0, sx1, sy1) == (0, 0, img.width, img.height) else img.crop((sx0, sy0, sx1, sy1))
    frame.alpha_composite(src, (x + sx0, y + sy0))


# ───────────────────────── layers ─────────────────────────
ENTERS = ("pop", "slam", "slide", "rise", "drop", "wipe", "flip", "blur_in", "zoom_out", "spin", "fade", "none", "stretch")


class Layer:
    """A sprite placed at (x, y) (anchor point, canvas px) with spring-driven enter, idle and exit behaviour.
    z = parallax depth (0 = far background, 1 = foreground). Times are scene-local seconds."""

    def __init__(self, sprite: Sprite, x, y, *, z=1.0, t_in=0.0, t_out=None, enter="pop", enter_dir=(0, 1), enter_dur=0.45,
                 idle="none", idle_amp=1.0, exit="fade", motion="snappy", scale=1.0, rot=0.0, opacity=1.0, role="deco",
                 name="", seed=0, travel=None, exit_dur=0.22):
        self.sprite, self.x, self.y, self.z = sprite, x, y, z
        self.t_in, self.t_out, self.enter, self.enter_dir, self.enter_dur = t_in, t_out, enter, enter_dir, enter_dur
        self.idle, self.idle_amp, self.exit, self.m = idle, idle_amp, exit, MOTION[motion]
        self.scale, self.rot, self.opacity, self.role, self.name, self.seed = scale, rot, opacity, role, name, seed
        self.travel = travel if travel is not None else self.m["travel"]
        self.exit_dur = exit_dur
        self.cache = _LRU(12)
        self.phase = (seed * 0.6180339) % 1.0

    # returns (x, y, sx, sy, rot, alpha, reveal) or None
    def state(self, t):
        dt = t - self.t_in
        if dt < 0:
            return None
        m = self.m
        x, y, sx, sy, r, a, rev = self.x, self.y, self.scale, self.scale, self.rot, self.opacity, 1.0
        p = spring(dt, m["omega"], m["zeta"])
        e = self.enter
        if e == "pop":
            k = 0.35 + 0.65 * p
            sx *= k
            sy *= k
            a *= clamp(dt / 0.10)
        elif e == "slam":
            q = spring(dt, m["omega"] * 1.5, max(0.45, m["zeta"]))
            k = 1 + (1.4 if self.sprite.w < 600 else 0.55) * (1 - q)  # wide words slam less (stay on screen)
            sx *= k
            sy *= k
            a *= clamp(dt / 0.06)
        elif e == "slide":
            dx, dy = self.enter_dir
            x -= dx * self.travel * (1 - p)
            y -= dy * self.travel * (1 - p)
            a *= clamp(dt / 0.12)
        elif e == "rise":
            q = ease_out_cubic(dt / self.enter_dur)
            y += 70 * (1 - q)
            a *= q
        elif e == "drop":
            q = spring(dt, m["omega"] * 0.9, min(m["zeta"], 0.45))
            y -= 520 * (1 - q)
            a *= clamp(dt / 0.08)
        elif e == "wipe":
            rev = ease_out_expo(dt / self.enter_dur)
            a *= clamp(dt / 0.05)
        elif e == "flip":
            sx *= max(0.02, p)
            a *= clamp(dt / 0.08)
        elif e == "stretch":
            sx *= 0.6 + 0.4 * p
            sy *= 1.25 - 0.25 * p
            a *= clamp(dt / 0.08)
        elif e == "blur_in":
            q = ease_out_cubic(dt / self.enter_dur)
            k = 1.18 - 0.18 * q
            sx *= k
            sy *= k
            a *= q
        elif e == "zoom_out":
            q = ease_out_expo(dt / self.enter_dur)
            sx *= max(0.01, q)
            sy *= max(0.01, q)
        elif e == "spin":
            r += -80 * (1 - p)
            k = 0.3 + 0.7 * p
            sx *= k
            sy *= k
            a *= clamp(dt / 0.1)
        elif e == "fade":
            a *= ease_out_cubic(dt / self.enter_dur)
        # idle
        if self.idle != "none" and dt > 0:
            ia = self.idle_amp * m["idle"]
            ph = 2 * math.pi * self.phase
            if self.idle == "float":
                y += 9 * ia * math.sin(dt * 1.9 + ph)
                r += 0.6 * ia * math.sin(dt * 1.3 + ph)
            elif self.idle == "breathe":
                k = 1 + 0.018 * ia * math.sin(dt * 2.4 + ph)
                sx *= k
                sy *= k
            elif self.idle == "drift":
                x += 14 * ia * dt
            elif self.idle == "sway":
                r += 2.2 * ia * math.sin(dt * 1.7 + ph)
            elif self.idle == "spin":
                r += 18 * dt * ia
            elif self.idle == "scroll_up":
                y -= 60 * ia * dt
            elif self.idle == "scroll_down":
                y += 60 * ia * dt
            elif self.idle == "pulse":
                k = 1 + 0.05 * ia * max(0, math.sin(dt * 5.0 + ph)) ** 6
                sx *= k
                sy *= k
        if m.get("jitter") and dt > 0:
            j = int(t * FPS)
            if (j * 7 + self.seed) % 23 == 0:
                x += ((j * 13) % 9 - 4) * 3
        # exit
        if self.t_out is not None and t > self.t_out:
            q = clamp((t - self.t_out) / self.exit_dur)
            if self.exit == "pop_out":
                k = 1 - 0.6 * ease_in_out_cubic(q)
                sx *= k
                sy *= k
            elif self.exit == "slide_out":
                x += self.enter_dir[0] * 300 * ease_in_out_cubic(q)
                y += self.enter_dir[1] * 300 * ease_in_out_cubic(q)
            a *= 1 - q
            if q >= 1:
                return None
        if a <= 0.003:
            return None
        return x, y, sx, sy, r, a, rev

    def image(self, t, st):
        return self.sprite

    def render(self, frame, t, cam):
        st = self.state(t)
        if st is None:
            return
        spr = self.image(t, st)
        if spr is None:
            return
        x, y, sx, sy, r, a, rev = st
        X, Y, Z, R = cam.apply(x, y, self.z)
        sx, sy, r = sx * Z, sy * Z, r + R
        big = spr.w * spr.h > 250_000
        q = 1.0 if big else 2.0  # big sprites rotate in 1° steps (bilinear), small ones in 0.5° steps (bicubic)
        r = round(r * q) / q if abs(r) >= 0.5 else 0.0  # sub-degree jitter (camera shake) is invisible but very expensive to rotate
        sx, sy = round(sx * 200) / 200, round(sy * 200) / 200  # 0.5 % scale steps → cache hits during idle "breathe"
        key = (id(spr), sx, sy, r, int(a * 40), round(rev, 3))
        img = self.cache.get2(key)
        if img is None:
            img = spr.img
            if rev < 0.999:
                d = self.enter_dir
                w, h = img.size
                if abs(d[0]) >= abs(d[1]):
                    cw = max(1, int(w * rev))
                    img = img.crop((0, 0, cw, h)) if d[0] >= 0 else img.crop((w - cw, 0, w, h))
                else:
                    ch = max(1, int(h * rev))
                    img = img.crop((0, 0, w, ch)) if d[1] >= 0 else img.crop((0, h - ch, w, h))
            if abs(sx - 1) > 0.002 or abs(sy - 1) > 0.002:
                img = img.resize((max(1, int(img.width * abs(sx))), max(1, int(img.height * abs(sy)))), Image.Resampling.BILINEAR)
            if r:
                img = img.rotate(-r, Image.Resampling.BILINEAR if big else Image.Resampling.BICUBIC, expand=True)
            img = alpha_mult(img, a)
            self.cache.put(key, img)
        # anchor: wipe keeps the un-revealed anchor
        bw, bh = spr.w * abs(sx), spr.h * abs(sy)
        ox = X - spr.ax * bw
        oy = Y - spr.ay * bh
        if r:
            ox, oy = X - img.width / 2, Y - img.height / 2
        elif rev < 0.999 and self.enter_dir[0] < 0:
            ox += bw - img.width
        elif rev < 0.999 and self.enter_dir[1] < 0 and abs(self.enter_dir[1]) > abs(self.enter_dir[0]):
            oy += bh - img.height
        blit(frame, img, ox, oy)

    def rest_box(self, t):
        """Bounding box at a given time (no camera) — used by design QA (safe zones, text size)."""
        st = self.state(t)
        if st is None:
            return None
        x, y, sx, sy, r, a, rev = st
        bw, bh = self.sprite.w * sx, self.sprite.h * sy
        pad = self.sprite.meta.get("pad", 0) * sx
        return (x - self.sprite.ax * bw + pad, y - self.sprite.ay * bh + pad, x + (1 - self.sprite.ax) * bw - pad,
                y + (1 - self.sprite.ay) * bh - pad)


class DynLayer(Layer):
    """A layer whose sprite is regenerated from time (count-ups, ring draw-on, progress bars). fn(t_local) → (key, builder)."""

    def __init__(self, fn, x, y, **kw):
        self.fn = fn
        self.dcache = _LRU(6)
        first = fn(10 ** 6)[1]()
        super().__init__(first, x, y, **kw)

    def image(self, t, st):
        k, build = self.fn(t - self.t_in)
        s = self.dcache.get2(k)
        if s is None:
            s = build()
            self.dcache.put(k, s)
        return s


class Particles:
    """Deterministic drifting particles (dust, bokeh, sparks, embers). Rendered as a layer-like object."""

    def __init__(self, sprites: list[Sprite], n=36, seed=0, area=(0, 0, W, H), vel=(0, -30), z=0.5, alpha=0.8, t_in=0.0,
                 burst=None, twinkle=True):
        rng = np.random.default_rng(seed)
        self.sprites, self.n, self.z, self.alpha, self.t_in, self.twinkle = sprites, n, z, alpha, t_in, twinkle
        x0, y0, x1, y1 = area
        self.p = np.stack([rng.uniform(x0, x1, n), rng.uniform(y0, y1, n)], 1)
        self.v = np.stack([rng.normal(vel[0], abs(vel[0]) * 0.5 + 6, n), rng.normal(vel[1], abs(vel[1]) * 0.4 + 6, n)], 1)
        self.k = rng.integers(0, len(sprites), n)
        self.ph = rng.uniform(0, 6.28, n)
        self.area = area
        self.burst = burst  # (cx, cy, speed) → explode outward at t_in
        self.role = "deco"
        self.cache = {}

    def render(self, frame, t, cam):
        dt = t - self.t_in
        if dt < 0:
            return
        x0, y0, x1, y1 = self.area
        for i in range(self.n):
            if self.burst:
                cx, cy, sp = self.burst
                ang = self.ph[i]
                spd = sp * (0.4 + (i % 7) / 7)
                d = spd * (1 - math.exp(-dt * 3.2)) / 3.2
                px, py = cx + math.cos(ang) * d, cy + math.sin(ang) * d + 140 * dt * dt
                a = self.alpha * max(0.0, 1 - dt / 1.2)
            else:
                px = x0 + (self.p[i, 0] + self.v[i, 0] * dt - x0) % (x1 - x0)
                py = y0 + (self.p[i, 1] + self.v[i, 1] * dt - y0) % (y1 - y0)
                a = self.alpha * (0.55 + 0.45 * math.sin(dt * 2.2 + self.ph[i])) if self.twinkle else self.alpha
                a *= clamp(dt / 0.4)
            if a <= 0.02:
                continue
            spr = self.sprites[self.k[i]]
            key = (int(self.k[i]), int(a * 20))
            img = self.cache.get(key)
            if img is None:
                img = alpha_mult(spr.img, a)
                self.cache[key] = img
            X, Y, Z, _ = cam.apply(px, py, self.z)
            blit(frame, img, X - img.width / 2, Y - img.height / 2)

    def rest_box(self, t):
        return None


# ───────────────────────── camera ─────────────────────────
class Camera:
    """Scene camera: a base move + spring punches (hero-word kicks) + decaying shake. Parallax via layer depth z."""

    def __init__(self, move="push", amount=0.06, dur=4.0, seed=0, punch_gain=1.0):
        self.move, self.amount, self.dur, self.seed = move, amount, max(0.5, dur), seed
        self.punches, self.shakes, self.punch_gain = [], [], punch_gain
        self.cx, self.cy = W / 2, H / 2
        self._st = None

    def punch(self, t, strength=0.05):
        self.punches.append((t, strength * self.punch_gain))

    def shake(self, t, amp=18.0, dur=0.35):
        self.shakes.append((t, amp, dur))

    def at(self, t):
        u = clamp(t / self.dur)
        e = ease_in_out_cubic(u)
        zoom, px, py, rot = 1.0, 0.0, 0.0, 0.0
        a = self.amount
        mv = self.move
        if mv == "push":
            zoom = 1 + a * e
        elif mv == "pull":
            zoom = 1 + a * (1 - e)
        elif mv == "drift_l":
            px, zoom = -a * 900 * (e - 0.5), 1 + a * 0.5
        elif mv == "drift_r":
            px, zoom = a * 900 * (e - 0.5), 1 + a * 0.5
        elif mv == "rise":
            py, zoom = -a * 1100 * (e - 0.5), 1 + a * 0.4
        elif mv == "orbit":
            rot = a * 18 * (e - 0.5)
            zoom = 1 + a * 0.6
            px = a * 400 * math.sin(u * math.pi)
        elif mv == "dolly":
            zoom = 1 + a * 1.6 * ease_out_expo(u)
        elif mv == "handheld":
            zoom = 1 + a * 0.5
            px = 7 * math.sin(t * 1.3 + self.seed) + 4 * math.sin(t * 2.9)
            py = 6 * math.sin(t * 1.1 + 2 * self.seed) + 3 * math.sin(t * 3.7)
            rot = 0.25 * math.sin(t * 0.9 + self.seed)
        for tp, s in self.punches:
            if t >= tp:
                zoom += s * max(0.0, impulse(t - tp, 16, 0.42)) if t - tp > 0.12 else s * spring(t - tp, 30, 0.7)
        for ts, amp, dur in self.shakes:
            dt = t - ts
            if 0 <= dt <= dur:
                k = amp * (1 - dt / dur) ** 2
                px += k * math.sin(dt * 91 + ts * 7)
                py += k * math.cos(dt * 77 + ts * 3)
                rot += k * 0.02 * math.sin(dt * 60)
        return zoom, px, py, rot

    def bind(self, t):
        self._st = self.at(t)
        return self

    def apply(self, x, y, z):
        zoom, px, py, rot = self._st
        zz = 1 + (zoom - 1) * (0.35 + 0.65 * z)
        X = self.cx + (x - self.cx) * zz + px * (0.3 + 0.7 * z)
        Y = self.cy + (y - self.cy) * zz + py * (0.3 + 0.7 * z)
        if abs(rot) > 0.01:
            rr = math.radians(rot * z)
            dx, dy = X - self.cx, Y - self.cy
            X, Y = self.cx + dx * math.cos(rr) - dy * math.sin(rr), self.cy + dx * math.sin(rr) + dy * math.cos(rr)
        return X, Y, zz, rot * z


# ───────────────────────── background ─────────────────────────
class Background:
    """Pre-rendered plate (canvas × margin, so the camera can move). depth < 1 → moves slower than the foreground.
    Soft plates are stored at half resolution (they are blurred anyway) → ~2.5× faster per frame."""

    def __init__(self, img: Image.Image, depth=0.3, margin=1.18, sharp=False):
        from PIL import ImageOps
        bw, bh = int(W * margin), int(H * margin)
        self.ps = 1.0 if sharp else 0.5
        size = (int(bw * self.ps), int(bh * self.ps))
        self.img = ImageOps.fit(img.convert("RGB"), size, Image.Resampling.LANCZOS) if img.size != size else img.convert("RGB")
        self.depth, self.margin = depth, margin

    def render(self, cam: Camera) -> Image.Image:
        zoom, px, py, rot = cam._st
        z = 1 + (zoom - 1) * self.depth
        bw, bh = self.img.size
        ps = self.ps
        w, h = W / z * ps, H / z * ps
        cx = bw / 2 - px * self.depth * 0.5 * ps
        cy = bh / 2 - py * self.depth * 0.5 * ps
        if abs(rot) * self.depth > 0.05:
            rr = math.radians(-rot * self.depth)
            ca, sa = math.cos(rr), math.sin(rr)
            s = ps / z
            a, b, d, e = s * ca, -s * sa, s * sa, s * ca
            c = cx - (a * W / 2 + b * H / 2)
            f = cy - (d * W / 2 + e * H / 2)
            return self.img.transform((W, H), Image.Transform.AFFINE, (a, b, c, d, e, f), Image.Resampling.BILINEAR).convert("RGBA")
        box = (max(0.0, cx - w / 2), max(0.0, cy - h / 2), min(bw, cx + w / 2), min(bh, cy + h / 2))
        return self.img.resize((W, H), Image.Resampling.BILINEAR, box=box).convert("RGBA")


# ───────────────────────── scene ─────────────────────────
class Scene:
    """One beat = one designed frame. Built lazily (sprites are created in the worker that renders it)."""

    def __init__(self, idx, t0, t1, archetype, builder, meta=None):
        self.idx, self.t0, self.t1, self.archetype, self.builder = idx, t0, t1, archetype, builder
        self.meta = meta or {}
        self.built = False
        self.layers, self.bg, self.cam, self.cues, self.events, self.post = [], None, None, [], [], []
        self.layout = archetype

    def ensure(self):
        if not self.built:
            self.builder(self)
            self.layers.sort(key=lambda l: l.z)
            self.built = True
        return self

    # API used by archetypes
    def add(self, layer):
        self.layers.append(layer)
        return layer

    def cue(self, t, kind, gain=1.0, pan=0.0):
        self.cues.append({"t": round(self.t0 + t, 3), "kind": kind, "gain": gain, "pan": pan, "scene": self.idx})

    def event(self, t, what):
        self.events.append((self.t0 + t, what))

    def frame(self, tg: float) -> Image.Image:
        self.ensure()
        t = tg - self.t0
        self.cam.bind(t)
        fr = self.bg.render(self.cam, t) if getattr(self.bg, "dynamic", False) else self.bg.render(self.cam)
        for ly in self.layers:
            ly.render(fr, t, self.cam)
        for fn in self.post:
            fr = fn(fr, t)
        return fr

    def text_boxes(self):
        """(role, px, box) of every text layer at rest (just before the scene ends)."""
        self.ensure()
        out = []
        t = (self.t1 - self.t0) - 0.05
        for ly in self.layers:
            if isinstance(ly, Layer) and ly.sprite.meta.get("px"):
                b = ly.rest_box(min(t, (ly.t_out - 0.01) if ly.t_out else t))
                if b:
                    out.append((ly.role, ly.sprite.meta["px"] * ly.scale, b, ly.sprite.meta.get("text", "")))
        return out


# ───────────────────────── transitions ─────────────────────────
TRANSITIONS = ("whip", "zoom_through", "flash", "slide_push", "iris", "diag_wipe", "glitch", "shutter", "ink", "spin",
               "luma_fade", "stripes", "split")
TRANSITION_SFX = {"whip": "whoosh", "zoom_through": "impact", "flash": "hit", "slide_push": "swish", "iris": "riser_short",
                  "diag_wipe": "swish", "glitch": "glitch", "shutter": "shutter", "ink": "swell", "spin": "whoosh",
                  "luma_fade": "swell", "stripes": "whoosh", "split": "swish"}
_INK = {}


def _ink_field(seed):
    if seed not in _INK:
        from .gfx import value_noise
        n = value_noise(W // 4, H // 4, scale=40, octaves=4, seed=seed)
        yy, xx = np.mgrid[0:H // 4, 0:W // 4].astype(np.float32)
        rad = np.hypot(xx - W / 8, yy - H / 8) / np.hypot(W / 8, H / 8)
        f = 0.55 * rad + 0.45 * n
        _INK[seed] = (f - f.min()) / (f.max() - f.min())
    return _INK[seed]


def _shift(arr, dx, dy):
    out = np.zeros_like(arr)
    h, w = arr.shape[:2]
    dx, dy = int(dx), int(dy)
    xs0, xs1 = max(0, -dx), min(w, w - dx)
    ys0, ys1 = max(0, -dy), min(h, h - dy)
    if xs1 > xs0 and ys1 > ys0:
        out[ys0 + dy:ys1 + dy, xs0 + dx:xs1 + dx] = arr[ys0:ys1, xs0:xs1]
    return out


def _mblur(arr, dx, dy, n=5):
    if abs(dx) + abs(dy) < 2:
        return arr
    acc = np.zeros(arr.shape, np.float32)
    for i in range(n):
        f = (i / (n - 1) - 0.5)
        acc += _shift(arr, dx * f, dy * f)
    return (acc / n).astype(np.uint8)


def _zoom(img: Image.Image, s: float) -> Image.Image:
    if abs(s - 1) < 0.002:
        return img
    w2, h2 = int(W * s), int(H * s)
    big = img.resize((w2, h2), Image.Resampling.BILINEAR)
    if s >= 1:
        x0, y0 = (w2 - W) // 2, (h2 - H) // 2
        return big.crop((x0, y0, x0 + W, y0 + H))
    out = Image.new("RGB", (W, H), (0, 0, 0))
    out.paste(big, ((W - w2) // 2, (H - h2) // 2))
    return out


def transition(kind: str, A: Image.Image, B: Image.Image, p: float, accent="#FFD400", seed=0, direction=1) -> Image.Image:
    """Blend outgoing frame A → incoming frame B at progress p ∈ [0,1]."""
    A, B = A.convert("RGB"), B.convert("RGB")
    e = ease_in_out_cubic(p)
    if kind == "whip":
        a, b = np.asarray(A), np.asarray(B)
        if p < 0.5:
            q = ease_in_out_cubic(p * 2)
            return Image.fromarray(_mblur(_shift(a, -direction * W * 0.5 * q, 0), -direction * 260 * q, 0, 7))
        q = 1 - ease_in_out_cubic((p - 0.5) * 2)
        return Image.fromarray(_mblur(_shift(b, direction * W * 0.5 * q, 0), direction * 260 * q, 0, 7))
    if kind == "zoom_through":
        if p < 0.5:
            out = _zoom(A, 1 + 1.4 * ease_in_out_cubic(p * 2) ** 2)
        else:
            out = _zoom(B, 1 + 0.5 * (1 - ease_out_cubic((p - 0.5) * 2)))
        fl = max(0.0, 1 - abs(p - 0.5) * 7)
        return Image.blend(out, Image.new("RGB", (W, H), (255, 255, 255)), fl * 0.85) if fl > 0 else out
    if kind == "flash":
        base = A if p < 0.5 else B
        fl = max(0.0, 1 - abs(p - 0.5) * 3.2)
        return Image.blend(base, Image.new("RGB", (W, H), hex2rgb(accent) if seed % 2 else (255, 255, 255)), fl)
    if kind == "slide_push":
        a, b = np.asarray(A), np.asarray(B)
        off = int(H * e) * direction
        out = _shift(a, 0, -off) + _shift(b, 0, H * direction - off)
        return Image.fromarray(out)
    if kind == "split":
        # top half slides left, bottom half slides right, revealing B underneath
        a, b = np.asarray(A), np.asarray(B)
        off = int(W * e)
        out = b.copy()
        if off < W:
            out[: H // 2, : W - off] = a[: H // 2, off:]
            out[H // 2:, off:] = a[H // 2:, : W - off]
        return Image.fromarray(out)
    if kind == "iris":
        r = (math.hypot(W, H) / 2 + 40) * ease_in_out_cubic(p)
        m = Image.new("L", (W // 2, H // 2), 0)
        ImageDraw.Draw(m).ellipse([W / 4 - r / 2, H / 4 - r / 2, W / 4 + r / 2, H / 4 + r / 2], fill=255)
        m = m.resize((W, H), Image.Resampling.BILINEAR)
        out = Image.composite(B, A, m)
        if 0.02 < p < 0.98:
            ring = Image.new("L", (W, H), 0)
            ImageDraw.Draw(ring).ellipse([W / 2 - r, H / 2 - r, W / 2 + r, H / 2 + r], outline=255, width=14)
            out = Image.composite(Image.new("RGB", (W, H), hex2rgb(accent)), out, ring)
        return out
    if kind == "diag_wipe":
        m = Image.new("L", (W, H), 0)
        x = -H * 0.6 + (W + H * 1.2) * e
        poly = [(-10, 0), (x, 0), (x - H * 0.55, H), (-10, H)]
        ImageDraw.Draw(m).polygon(poly, fill=255)
        out = Image.composite(B, A, m)
        band = Image.new("L", (W, H), 0)
        ImageDraw.Draw(band).line([(x, 0), (x - H * 0.55, H)], fill=255, width=26)
        return Image.composite(Image.new("RGB", (W, H), hex2rgb(accent)), out, band) if 0.01 < p < 0.99 else out
    if kind == "glitch":
        base = np.asarray(A if p < 0.5 else B).copy()
        rng = np.random.default_rng(seed + int(p * 30))
        amt = 1 - abs(p - 0.5) * 2
        out = base.copy()
        sh = int(26 * amt)
        out[..., 0] = np.roll(base[..., 0], sh, 1)
        out[..., 2] = np.roll(base[..., 2], -sh, 1)
        for _ in range(int(9 * amt)):
            y0 = int(rng.integers(0, H - 40))
            hh = int(rng.integers(10, 90))
            out[y0:y0 + hh] = np.roll(out[y0:y0 + hh], int(rng.integers(-120, 120)), 1)
        return Image.fromarray(out)
    if kind == "shutter":
        # blinds sweep across (alternating accent / dark), fully closed for ~1 frame at the cut
        n = 9
        out = (A if p < 0.5 else B).copy()
        d = ImageDraw.Draw(out)
        bh = H / n + 1
        cols = [hex2rgb(accent), (14, 14, 18)]
        for i in range(n):
            q = clamp(1 - abs(p - 0.5) * 2.4 + (0.12 if i % 2 else 0) * (1 - abs(p - 0.5) * 2))
            wd = W * ease_in_out_cubic(q)
            x0 = 0 if (i % 2 == 0) == (p < 0.5) else W - wd
            d.rectangle([x0, i * bh, x0 + wd, (i + 1) * bh], fill=cols[i % 2])
        return out
    if kind == "ink":
        f = _ink_field(seed % 4)
        thr = e * 1.08
        m = np.clip((thr - f) * 18, 0, 1)
        m = Image.fromarray((m * 255).astype(np.uint8)).resize((W, H), Image.Resampling.BILINEAR)
        return Image.composite(B, A, m)
    if kind == "spin":
        if p < 0.5:
            q = ease_in_out_cubic(p * 2)
            out = _zoom(A, 1 + 0.5 * q).rotate(-direction * 25 * q, Image.Resampling.BILINEAR)
        else:
            q = 1 - ease_in_out_cubic((p - 0.5) * 2)
            out = _zoom(B, 1 + 0.5 * q).rotate(direction * 25 * q, Image.Resampling.BILINEAR)
        return out
    if kind == "stripes":
        n = 3
        cols = [hex2rgb(accent), (16, 16, 20), (245, 245, 245)]
        out = (A if p < 0.55 else B).copy()
        d = ImageDraw.Draw(out)
        for i in range(n):
            q = clamp(p * 1.6 - i * 0.18)
            x0 = -W + 2 * W * ease_in_out_cubic(q)
            d.polygon([(x0, 0), (x0 + W * 0.9, 0), (x0 + W * 0.9 - 300, H), (x0 - 300, H)], fill=cols[i % 3])
        return out
    # luma_fade (default)
    if p < 0.5:
        return Image.blend(A, Image.new("RGB", (W, H), (0, 0, 0)), ease_in_out_cubic(p * 2) * 0.85)
    return Image.blend(Image.new("RGB", (W, H), (0, 0, 0)), B, 0.15 + 0.85 * ease_in_out_cubic((p - 0.5) * 2))
