"""scenes.py — the Scene Archetype library. Each archetype is a *motion design*, not a template: layouts, enters, camera
punches and SFX are synced to the exact spoken words, and every visual parameter comes from the video's Style DNA.
The Director may also pass an unknown archetype name → it falls back to `kinetic_line` with the requested data (never empty)."""
from __future__ import annotations

import math
import re
from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageOps

from . import gfx
from .core import H, W, Rng, clamp, ease_out_cubic, impulse, mix, rgb2hex, rgba, spring, stable_seed
from .engine import Background, Camera, DynLayer, Layer, Particles
from .typo import REG, Sprite, apply_case, font, has_deva, text_sprite

# Safe zones for 1080×1920 Reels (see docs/SAFE_ZONES.md — conservative organic profile, ESTIMATE from public guides):
SAFE = {"top": 250, "bottom": 1480, "left": 70, "right_top": 1010, "right_low": 940, "low_from": 1000}
CAP_BAND = (1215, 1450)  # captions live here (low); content above.

ARCH: dict[str, dict] = {}


def archetype(name, roles, cats=("*",), variants=("a",), captions=True, needs=()):
    def deco(fn):
        ARCH[name] = dict(fn=fn, roles=roles, cats=cats, variants=variants, captions=captions, needs=needs)
        return fn
    return deco


def _norm(s: str) -> str:
    return re.sub(r"[^\wऀ-ॿ]", "", (s or "").lower())


# ───────────────────────── context ─────────────────────────
class Ctx:
    def __init__(self, dna, beat, words, dur, idx, n_scenes, assets, facts):
        self.dna, self.pal, self.F = dna, dna["palette"], dna["fonts"]
        self.motion, self.align, self.shape = dna["motion"], dna["layout_align"], dna["card_shape"]
        self.beat, self.data, self.words, self.dur, self.idx, self.n = beat, beat.get("data", {}) or {}, words, dur, idx, n_scenes
        self.assets, self.facts = assets, facts
        self.poster = assets.get("poster")
        self.footage = (assets.get("media_segments") or {}).get(idx)
        self.rng = Rng(stable_seed(dna["seed"], idx, beat.get("id", "")))
        self.dark = dna["tone"] != "light"
        self.hero_set = {_norm(h) for hw in beat.get("hero", []) for h in hw.split()}
        self.cap_on = beat.get("captions", ARCH.get(beat["archetype"], {}).get("captions", True))
        self.bottom = CAP_BAND[0] - 40 if self.cap_on else SAFE["bottom"] - 30
        self.top = SAFE["top"] + 20
        self.variant = beat.get("variant") or dna.get("variants", {}).get(beat["archetype"]) or "a"
        self.case = dna.get("hero_case", "upper")

    # timing ─────────────────────────────────────────
    def t_word(self, key, frac=0.2, at=None):
        """Local time when `key` (first words of it) is spoken. Fallback: `at` seconds, else `frac` × scene duration."""
        if key:
            toks = [_norm(k) for k in str(key).split() if _norm(k)]
            for tk in toks[:2]:
                for w in self.words:
                    for cand in (_norm(w.get("show")), _norm(w.get("say"))):
                        if cand and (cand == tk or (len(tk) >= 4 and (cand.startswith(tk) or tk.startswith(cand)))):
                            return max(0.0, w["t0"] - 0.05)
        return at if at is not None else frac * self.dur

    def spread(self, n, start=0.15, end=0.75):
        if n <= 1:
            return [start * self.dur]
        return [(start + (end - start) * i / (n - 1)) * self.dur for i in range(n)]

    # text ─────────────────────────────────────────
    def shadow(self, k=1.0):
        return (0, int(8 * k), int(14 * k), 0.6 if self.dark else 0.22, "#000000")

    def hero(self, text, box, color=None, max_lines=3, min_px=56, max_px=380, case=None, stroke=None, glow=False, role="hero",
             highlight=None, gradient=None, align=None, fid=None, px=None):
        fid = fid or self.F["hero"]
        st = stroke if stroke is not None else (0.035 if self.footage else 0.0)  # outline keeps type readable on busy footage
        return text_sprite(text, fid, px, deva_fid=self.F["deva"], color=color or self.pal["text"], box=box, max_lines=max_lines,
                           min_px=min_px, max_px=max_px, align=align or ("left" if self.align == "left" else "center"),
                           case=case or self.case, stroke=st, stroke_color=self.pal["bg0"], shadow=self.shadow(),
                           glow=(18, 0.55, self.pal["accent"]) if glow else None, role=role, highlight=highlight,
                           highlight_color=self.pal["accent"], gradient=gradient)

    def body(self, text, box=(860, 200), px=None, color=None, max_lines=3, min_px=34, max_px=90, role="body", align=None, case="any",
             fid=None):
        return text_sprite(text, fid or self.F["support"], px, deva_fid=self.F["deva"], color=color or self.pal["text"], box=box,
                           max_lines=max_lines, min_px=min_px, max_px=max_px, align=align or ("left" if self.align == "left" else "center"),
                           case=case, shadow=self.shadow(1.0 if self.footage else 0.6), role=role,
                           stroke=0.03 if self.footage else 0.0, stroke_color="#000000")

    def chip(self, text, fill=None, color=None, px=42, shape=None, pad=(30, 14), border=None, role="label", fid=None, case="upper"):
        t = text_sprite(text, fid or self.F["support"], px, deva_fid=self.F["deva"], color=color or self.pal["ink"], box=(2000, 400),
                        max_lines=1, case=case, role=role)
        pw, ph = t.w - 2 * t.meta["pad"] + 2 * pad[0], t.h - 2 * t.meta["pad"] + 2 * pad[1]
        c = gfx.card(int(pw), int(ph), fill=fill or self.pal["accent"], alpha=255, kind=shape or ("pill" if self.shape in ("pill", "rounded") else self.shape),
                     r=int(ph * 0.3), border=border, border_w=3)
        c.alpha_composite(t.img, (int((pw - t.w) / 2), int((ph - t.h) / 2)))
        return Sprite(c, 0.5, 0.5, {"role": role, "px": px, "text": text, "pad": 0})

    def layer(self, spr, x, y, **kw):
        kw.setdefault("motion", self.motion)
        kw.setdefault("seed", self.rng.randint(0, 999))
        return Layer(spr, x, y, **kw)

    def enter(self, kind="main"):
        m = self.motion
        table = {"snappy": {"main": "slide", "hero": "pop", "minor": "rise"}, "elastic": {"main": "pop", "hero": "drop", "minor": "pop"},
                 "smooth": {"main": "rise", "hero": "blur_in", "minor": "fade"}, "heavy": {"main": "slam", "hero": "slam", "minor": "rise"},
                 "glitchy": {"main": "pop", "hero": "stretch", "minor": "fade"}}
        return table[m][kind]

    def x_text(self):
        return SAFE["left"] + 10 if self.align == "left" else W / 2

    def anchor(self, spr: Sprite):
        if self.align == "left":
            spr.ax = 0.0
        return spr

    # images ─────────────────────────────────────────
    def focus(self, i=0, aspect=1.0):
        boxes = self.assets.get("focus") or []
        if boxes:
            return boxes[i % len(boxes)]
        if self.poster is not None:
            auto = self.assets.setdefault("_auto_focus", gfx.saliency_boxes(self.poster, 4, aspect))
            return auto[i % len(auto)]
        return (0.1, 0.1, 0.9, 0.9)

    def poster_crop(self, box, w, h):
        img = gfx.crop_norm(self.poster, box)
        return ImageOps.fit(img.convert("RGB"), (w, h), Image.Resampling.LANCZOS, centering=(0.5, 0.4))


# ───────────────────────── backgrounds ─────────────────────────
def make_bg(ctx: Ctx, kind=None, variant_seed=0) -> Background:
    if ctx.footage:  # footage-first: real visuals under the graphics whenever the beat has media
        from .media import CLEAN_LOOKS, build_background
        light = ctx.beat["archetype"] in ("footage_clean", "host_cam") or (
            ctx.dna.get("look") in CLEAN_LOOKS and ctx.beat["archetype"] in ("hook_slam", "cta_loop"))
        return build_background(ctx.footage, ctx.assets["root"], ctx.dna, dark=True, heavy_text=not light)
    if kind is None:
        kind = ctx.dna["background"] if ctx.idx % 3 != 1 else ctx.dna.get("background2", ctx.dna["background"])
    if not ctx.dark and kind in ("grid_tech", "bokeh_night", "spotlight"):
        kind = "paper" if ctx.idx % 2 else "mesh"
    p = ctx.pal
    bw, bh = int(W * 1.18), int(H * 1.18)
    seed = ctx.dna["seed"] % 10000 + ctx.idx * 31 + variant_seed
    r = Rng(seed)
    if ctx.poster is None and kind in ("poster_ambilight", "poster_duotone", "halftone", "poster_mosaic"):
        kind = "mesh"
    if kind == "poster_ambilight":
        im = poster_plate(ctx, ctx.idx, (bw // 3, bh // 3), 2.2)
        im = im.filter(ImageFilter.GaussianBlur(14)).resize((bw, bh), Image.Resampling.BICUBIC)
        im = ImageEnhance.Color(im).enhance(1.35)
        im = ImageEnhance.Brightness(im).enhance(0.42 if ctx.dark else 0.95)
        grad = gfx.linear_gradient(bw, bh, [p["bg0"], mix_hex(p["bg0"], p["bg1"], 0.3), p["bg0"]], 90, seed)
        im = Image.blend(im, grad, 0.35)
    elif kind == "poster_duotone":
        im = poster_plate(ctx, ctx.idx + 1, (bw // 2, bh // 2), 1.5)
        im = gfx.duotone(im, p["bg0"], mix_hex(p["accent"], p["bg0"], 0.35 if ctx.dark else 0.1), 1.3).filter(ImageFilter.GaussianBlur(5))
        im = ImageEnhance.Brightness(im).enhance(0.55 if ctx.dark else 1.0).resize((bw, bh), Image.Resampling.BICUBIC)
    elif kind == "halftone":
        src = poster_plate(ctx, ctx.idx, (bw // 2, bh // 2), 1.4)
        paper = p["bg1"] if ctx.dark else p["bg0"]
        ink = p["bg0"] if ctx.dark else mix_hex(p["accent"], p["text"], 0.5)
        im = gfx.halftone(src, 9, ink, paper, angle=r.choice([15, 22, 45])).resize((bw, bh), Image.Resampling.BICUBIC)
        if ctx.dark:
            im = ImageEnhance.Brightness(im).enhance(0.55)
    elif kind == "poster_mosaic":
        im = Image.new("RGB", (bw, bh), rgba(p["bg0"])[:3])
        cols, rows, gap = 3, 5, 14
        cw, ch = (bw - gap * (cols + 1)) // cols, (bh - gap * (rows + 1)) // rows
        boxes = gfx.saliency_boxes(ctx.poster, 6, cw / ch)
        for j in range(rows):
            for i in range(cols):
                b = boxes[(i + j * cols + ctx.idx) % len(boxes)]
                tile = ctx.poster_crop(b, cw, ch)
                tile = ImageEnhance.Color(tile).enhance(0.6)
                im.paste(tile, (gap + i * (cw + gap), gap + j * (ch + gap)))
        im = ImageEnhance.Brightness(im.filter(ImageFilter.GaussianBlur(3))).enhance(0.38 if ctx.dark else 0.8)
    elif kind == "spotlight":
        im = gfx.radial_gradient(bw, bh, bw * r.uniform(0.35, 0.65), bh * r.uniform(0.15, 0.35), bh * 0.75,
                                 mix_hex(p["bg1"], p["accent"], 0.22), p["bg0"], 1.4, seed).convert("RGBA")
        im.alpha_composite(gfx.light_rays(bw, bh, (bw * r.uniform(0.3, 0.7), -60), p["accent"], 8, 50, 0.13, seed))
        im = im.convert("RGB")
    elif kind == "paper":
        im = gfx.paper_texture(bw, bh, p["bg0"], seed).convert("RGBA")
        sh = Image.new("RGBA", (bw, bh), (0, 0, 0, 0))
        d = ImageDraw.Draw(sh)
        for _ in range(3):
            rr = r.uniform(250, 520)
            x, y = r.uniform(0, bw), r.uniform(0, bh)
            d.ellipse([x - rr, y - rr, x + rr, y + rr], fill=rgba(p["bg1"], 150))
        im.alpha_composite(sh.filter(ImageFilter.GaussianBlur(60)))
        im = im.convert("RGB")
    elif kind == "grid_tech":
        im = gfx.linear_gradient(bw, bh, [p["bg0"], p["bg1"], p["bg0"]], r.choice([80, 100, 120]), seed).convert("RGBA")
        for _ in range(2):
            g = gfx.glow_dot(int(r.uniform(300, 520)), r.choice([p["accent"], p["accent2"]]), 0.28)
            im.alpha_composite(g, (int(r.uniform(-200, bw - 300)), int(r.uniform(0, bh - 500))))
        im.alpha_composite(gfx.grid_lines(bw, bh, 90, p["text"], 16))
        im = im.convert("RGB")
    elif kind == "split_tone":
        im = gfx.linear_gradient(bw, bh, [p["bg0"], p["bg1"]], 90, seed).convert("RGBA")
        m = Image.new("L", (bw, bh), 0)
        k = r.uniform(0.35, 0.6)
        ImageDraw.Draw(m).polygon([(0, bh * k), (bw, bh * (k - 0.22)), (bw, bh), (0, bh)], fill=255)
        layer = gfx.linear_gradient(bw, bh, [mix_hex(p["bg1"], p["accent"], 0.25), p["bg1"]], 90, seed + 1).convert("RGBA")
        layer.putalpha(m)
        im.alpha_composite(layer)
        im = im.convert("RGB")
    elif kind == "bokeh_night":
        im = gfx.linear_gradient(bw, bh, [p["bg0"], mix_hex(p["bg0"], p["bg1"], 0.6), p["bg0"]], 90, seed).convert("RGBA")
        lay = Image.new("RGBA", (bw, bh), (0, 0, 0, 0))
        for _ in range(16):
            rr = int(r.uniform(30, 120))
            b = gfx.bokeh(rr, r.choice([p["accent"], p["accent2"], p["muted"]]), r.uniform(0.15, 0.45))
            lay.alpha_composite(b, (int(r.uniform(0, bw - b.width)), int(r.uniform(0, bh - b.height))))
        im.alpha_composite(lay.filter(ImageFilter.GaussianBlur(3)))
        im = im.convert("RGB")
    else:  # mesh
        cols = [p["bg0"], p["bg1"], mix_hex(p["accent"], p["bg0"], 0.55 if ctx.dark else 0.75), mix_hex(p["accent2"], p["bg0"], 0.6 if ctx.dark else 0.8)]
        im = gfx.mesh_gradient(bw, bh, cols, seed, blobs=6)
    if ctx.dark:
        v = gfx.vignette(bw, bh, 0.55)
        im = im.convert("RGBA")
        im.alpha_composite(v)
        im = im.convert("RGB")
    return Background(im, depth=0.3)


def glass(ctx: Ctx, sc, x0, y0, w, h, kind=None, r=30) -> Image.Image:
    """Real frosted glass: blur the actual background plate region behind a card at canvas box (x0, y0, w, h)."""
    bg = sc.bg
    ps = bg.ps
    ox, oy = W * (bg.margin - 1) / 2, H * (bg.margin - 1) / 2
    reg = bg.img.crop((int((x0 + ox - 40) * ps), int((y0 + oy - 40) * ps), int((x0 + ox + w + 40) * ps), int((y0 + oy + h + 40) * ps)))
    reg = reg.resize((int(w + 80), int(h + 80)), Image.Resampling.BILINEAR)
    return gfx.frosted_glass(reg, (40, 40, 40 + int(w), 40 + int(h)), kind or ctx.shape, r, dark=ctx.dark,
                             tint="#FFFFFF" if ctx.dark else ctx.pal["bg0"], tint_alpha=0.08 if ctx.dark else 0.55)


def poster_plate(ctx: Ctx, i: int, size, zoom=1.6) -> Image.Image:
    """Zoomed crop around focus box i, cover-fitted to `size` — so backgrounds never repeat the whole poster (and its title)."""
    f = ctx.focus(i)
    pw, ph = ctx.poster.size
    cx, cy = (f[0] + f[2]) / 2 * pw, (f[1] + f[3]) / 2 * ph
    aspect = size[0] / size[1]
    ch = min((f[3] - f[1]) * ph * zoom, ph * 0.8, pw / aspect)
    cw = ch * aspect
    x0, y0 = clamp(cx - cw / 2, 0, pw - cw), clamp(cy - ch / 2, 0, ph - ch)
    return ctx.poster.crop((int(x0), int(y0), int(x0 + cw), int(y0 + ch))).convert("RGB").resize(size, Image.Resampling.LANCZOS)


def mix_hex(a, b, t):
    return rgb2hex(mix(a, b, t))


# ───────────────────────── motifs (DNA-level decoration that moves) ─────────────────────────
def add_motif(ctx: Ctx, sc, strength=1.0):
    m, p, r = ctx.dna["motif"], ctx.pal, ctx.rng
    if m == "film_perfs":
        strip = Sprite(gfx.film_perfs(H * 2, 64, mix_hex(p["bg0"], "#000000", 0.4), p["muted"], True, 150), 0.5, 0.5)
        for x, idle in ((34, "scroll_up"), (W - 34, "scroll_down")):
            sc.add(ctx.layer(strip, x, H / 2 + (300 if idle == "scroll_up" else -300), z=0.6, enter="fade", idle=idle, idle_amp=1.4, role="deco"))
    elif m == "brackets":
        sz = 110
        im = Image.new("RGBA", (sz, sz), (0, 0, 0, 0))
        d = ImageDraw.Draw(im)
        d.line([(4, sz - 4), (4, 4), (sz - 4, 4)], fill=rgba(p["accent"]), width=8)
        corners = [(SAFE["left"] + 20, SAFE["top"] + 10, 0), (W - 90, SAFE["top"] + 10, 90), (W - 90, ctx.bottom - 10, 180), (SAFE["left"] + 20, ctx.bottom - 10, 270)]
        for i, (x, y, rot) in enumerate(corners):
            spr = Sprite(im.rotate(-rot, expand=True), 0.5, 0.5)
            sc.add(ctx.layer(spr, x + 40, y + 40 * (1 if i < 2 else -1), z=0.9, t_in=0.05 + 0.04 * i, enter="pop", role="deco"))
    elif m == "slashes":
        for i in range(3):
            w_, h_ = int(r.uniform(500, 900)), int(r.uniform(18, 46))
            bar = Image.new("RGBA", (w_, h_), rgba(r.choice([p["accent"], p["accent2"]]), int(r.uniform(90, 200))))
            spr = Sprite(bar.rotate(r.choice([-24, -18, 24]), expand=True, resample=Image.Resampling.BICUBIC), 0.5, 0.5)
            sc.add(ctx.layer(spr, r.uniform(100, W - 100), r.uniform(SAFE["top"], ctx.bottom), z=0.35, t_in=0.1 * i, enter="slide",
                             enter_dir=(r.choice([-1, 1]), 0), travel=700, idle="drift", idle_amp=r.uniform(-1.5, 1.5), role="deco"))
    elif m == "circles":
        for i in range(2):
            sz = int(r.uniform(520, 900))
            spr = Sprite(gfx.ring(sz, 5, 1.0, mix_hex(p["accent"], p["bg0"], 0.4)), 0.5, 0.5)
            sc.add(ctx.layer(spr, r.uniform(0, W), r.uniform(SAFE["top"], H - 400), z=0.3, enter="zoom_out", enter_dur=0.9, idle="breathe",
                             idle_amp=2, opacity=0.6, role="deco"))
    elif m == "light_rays":
        rays = gfx.light_rays(W, H, (r.uniform(200, 900), -100), p["accent"], 9, 46, 0.16, ctx.idx)
        sc.add(ctx.layer(Sprite(rays, 0.5, 0.5), W / 2, H / 2, z=0.4, enter="fade", enter_dur=0.8, idle="sway", idle_amp=0.6, role="deco"))
    elif m == "scanlines":
        sc.add(ctx.layer(Sprite(gfx.scanlines(W, H, 5, 34), 0.5, 0.5), W / 2, H / 2, z=1.2, enter="none", role="deco"))
        bar = Image.new("RGBA", (W, 160), (0, 0, 0, 0))
        bar.alpha_composite(gfx.linear_gradient(W, 160, ["#000000", p["accent"], "#000000"], 90).convert("RGBA").point(lambda v: v))
        bar.putalpha(Image.linear_gradient("L").resize((W, 160)).point(lambda v: int(60 * math.sin(v / 255 * math.pi))))
        sc.add(ctx.layer(Sprite(bar, 0.5, 0.5), W / 2, -100, z=1.1, enter="none", idle="scroll_down", idle_amp=9, role="deco"))
    elif m == "dust":
        dots = [Sprite(gfx.glow_dot(int(s), p["text"], 0.55)) for s in (3, 5, 8)]
        sc.add(Particles(dots, n=42, seed=ctx.idx, vel=(4, -22), z=0.8, alpha=0.7))
    elif m == "sparkles":
        st = [Sprite(gfx.star(s, 1.0, p["accent"], "#00000000", 4, 0.28)) for s in (18, 28, 40)]
        sc.add(Particles(st, n=16, seed=ctx.idx + 3, vel=(0, -10), z=0.9, alpha=0.9, area=(60, SAFE["top"], W - 60, ctx.bottom)))
    elif m == "grid_dots":
        im = Image.new("RGBA", (W + 200, H + 200), (0, 0, 0, 0))
        d = ImageDraw.Draw(im)
        for y in range(0, H + 200, 60):
            for x in range(0, W + 200, 60):
                d.ellipse([x - 2, y - 2, x + 2, y + 2], fill=rgba(p["text"], 46))
        sc.add(ctx.layer(Sprite(im, 0.5, 0.5), W / 2, H / 2, z=0.25, enter="fade", idle="drift", idle_amp=0.6, role="deco"))
    elif m == "thin_frames":
        im = Image.new("RGBA", (W - 90, H - 380), (0, 0, 0, 0))
        ImageDraw.Draw(im).rectangle([2, 2, im.width - 3, im.height - 3], outline=rgba(p["accent"], 170), width=3)
        sc.add(ctx.layer(Sprite(im, 0.5, 0.5), W / 2, H / 2 - 30, z=0.95, enter="wipe", enter_dir=(1, 0), enter_dur=0.8, role="deco"))
    elif m == "stamps":
        s = ctx.chip(str(ctx.facts.get("year", "REVIEW")), fill=mix_hex(p["bg0"], p["accent"], 0.15), color=p["accent"], px=34,
                     border=p["accent"], role="deco")
        sc.add(ctx.layer(s, W - 220, SAFE["top"] + 40, z=0.9, rot=-8, t_in=0.25, enter="slam", role="deco"))
    elif m == "tape":
        tape = Image.new("RGBA", (220, 54), rgba(mix_hex(p["accent2"], "#FFFFFF", 0.4), 190))
        spr = Sprite(tape.rotate(-35, expand=True, resample=Image.Resampling.BICUBIC), 0.5, 0.5)
        sc.add(ctx.layer(spr, 120, SAFE["top"] + 30, z=0.95, t_in=0.15, enter="pop", role="deco"))


def camera_for(ctx: Ctx, sc, kind=None):
    calm = ctx.dna.get("camera") == "calm"
    kind = kind or ctx.rng.choice(["push", "push", "drift_l", "drift_r", "rise", "orbit"] if not calm else ["push", "pull", "drift_l", "drift_r"])
    sc.cam = Camera(kind, (0.035 if calm else 0.06) * ctx.rng.uniform(0.8, 1.25), ctx.dur + 0.5, ctx.idx,
                    punch_gain=0.6 if calm else 1.0)
    return sc.cam


# ───────────────────────── kinetic typography core ─────────────────────────
def kinetic_stack(ctx: Ctx, sc, words, box, *, hero_set=None, max_words_page=7, style="hero", t_offset=0.0, sfx=True, colors=None,
                  justify=True):
    """Spoken words appear one by one exactly when spoken, laid out as a justified typographic poster (each line scaled to
    the full box width). Hero words are bigger, accent-coloured and hit with a camera punch + SFX."""
    hero_set = hero_set if hero_set is not None else ctx.hero_set
    x0, y0, x1, y1 = box
    bw, bh = x1 - x0, y1 - y0
    n_pages = max(1, -(-len(words) // max_words_page))
    target = -(-len(words) // n_pages)  # balanced pages: 11 words / max 8 → 6 + 5, never a 2-word leftover
    pages, cur = [], []
    for i, w in enumerate(words):
        cur.append(w)
        nxt = words[i + 1] if i + 1 < len(words) else None
        brk = bool(re.search(r"[,.!?…;:।]$", w["show"])) or (nxt is not None and nxt["t0"] - w["t1"] > 0.28)
        left = len(words) - i - 1
        if nxt is None or len(cur) >= target + (1 if brk is False and left == 1 else 0) or (brk and len(cur) >= 3 and left >= 3):
            pages.append(cur)
            cur = []
    if y1 > 1000:
        x1 = min(x1, SAFE["right_low"] + 10)
        bw = x1 - x0
    per_line = 2 if ctx.beat.get("role") == "hook" else 3
    fid = ctx.F["hero"] if style == "hero" else ctx.F["support"]
    out_layers = []
    for pi, page in enumerate(pages):
        texts = [apply_case(w["show"], ctx.case) for w in page]
        # line breaking: aim for 1–3 words per line, hero words alone on their line when possible
        lines, cur = [], []
        for i, w in enumerate(page):
            is_h = _norm(w["show"]) in hero_set or _norm(w.get("say")) in hero_set
            if is_h and cur:
                lines.append(cur)
                cur = []
            cur.append(i)
            if is_h or sum(len(texts[j]) for j in cur) >= 9 or len(cur) >= per_line:
                lines.append(cur)
                cur = []
        if cur:
            lines.append(cur)
        # size each line to box width
        line_px = []
        for ln in lines:
            f = font(fid, 100)
            wid = sum(font(fid if ("deva" in REG[fid]["scripts"] or not has_deva(texts[j])) else ctx.F["deva"], 100).getlength(texts[j])
                      for j in ln) + f.getlength(" ") * (len(ln) - 1)
            px = 100 * bw / max(1, wid) if justify else 150
            is_h = any(_norm(page[j]["show"]) in hero_set for j in ln)
            px = min(px, 330 if is_h else 230, (bh / max(1, len(lines))) / 1.05)
            line_px.append(max(58, px))
        total = sum(p * 1.04 for p in line_px)
        if total > bh:  # shrink the whole stack until it fits its box (never spill out of the safe area)
            k = bh / total
            line_px = [max(40, p * k) for p in line_px]
            total = sum(p * 1.04 for p in line_px)
        y = y0 + (bh - total) / 2 if ctx.align != "left" else y0 + (bh - total) * 0.35
        t_page_end = (pages[pi + 1][0]["t0"] - 0.16) if pi + 1 < len(pages) else None
        for li, ln in enumerate(lines):
            px = int(line_px[li])
            sprs = []
            for j in ln:
                w = page[j]
                is_h = _norm(w["show"]) in hero_set or _norm(w.get("say")) in hero_set
                col = (colors or {}).get("hero" if is_h else "word") or (ctx.pal["accent"] if is_h else ctx.pal["text"])
                sp = text_sprite(texts[j], fid, px, deva_fid=ctx.F["deva"], color=col, box=(4000, 2000), max_lines=1,
                                 shadow=ctx.shadow(1.2), stroke=0.04 if ctx.footage else 0.0, stroke_color="#000000",
                                 role="hero" if is_h else "kinetic",
                                 glow=(16, 0.45, ctx.pal["accent"]) if (is_h and ctx.dna["caption_style"] == "glow") else None)
                sprs.append((sp, is_h, w))
            pads = [s.meta["pad"] for s, _, _ in sprs]
            widths = [s.w - 2 * pd for (s, _, _), pd in zip(sprs, pads)]
            gap = px * 0.26
            lw = sum(widths) + gap * (len(sprs) - 1)
            x = x0 if ctx.align == "left" else x0 + (bw - lw) / 2
            for (sp, is_h, w), wd in zip(sprs, widths):
                t_in = max(0.0, w["t0"] - 0.06 + t_offset)
                ly = ctx.layer(sp, x + wd / 2, y + px * 0.52, z=1.0, t_in=t_in, t_out=t_page_end,
                               enter=("slam" if ctx.motion in ("heavy", "snappy") else "pop") if is_h else ctx.enter("minor") if ctx.motion != "smooth" else "rise",
                               exit="pop_out", exit_dur=0.12, role="hero" if is_h else "kinetic", idle="breathe" if is_h else "none")
                sc.add(ly)
                out_layers.append(ly)
                if is_h:
                    sc.cam.punch(t_in + 0.05, 0.05)
                    if ctx.motion == "heavy":
                        sc.cam.shake(t_in + 0.04, 14, 0.3)
                    if sfx:
                        sc.cue(t_in, "hit" if ctx.motion in ("heavy", "snappy") else "pop", 0.8)
                x += wd + gap
            y += px * 1.04
    return out_layers


def words_or_text(ctx: Ctx, text=None):
    if ctx.words:
        return ctx.words
    toks = (text or ctx.beat.get("show") or ctx.beat.get("say") or "").split()
    return [{"show": t, "say": t, "t0": ctx.dur * 0.8 * i / max(1, len(toks)), "t1": 0} for i, t in enumerate(toks)]


# ───────────────────────── archetypes ─────────────────────────
@archetype("hook_slam", roles=("hook",), variants=("word_smash", "poster_punch", "rating_first", "question_flash", "split_reveal", "countdown"),
           captions=False)
def hook_slam(ctx: Ctx, sc):
    """Pattern-interrupt opening: something hits the screen in frame 1 — never a greeting."""
    op = ctx.beat.get("variant") or ctx.dna["opening"]
    sc.bg = make_bg(ctx)
    cam = camera_for(ctx, sc, "dolly")
    p = ctx.pal
    words = words_or_text(ctx)
    box = (SAFE["left"] + 10, 640, SAFE["right_top"] - 10, SAFE["bottom"] - 40)
    sc.cue(0.0, "impact", 1.0)
    cam.punch(0.02, 0.08)
    if op == "poster_punch" and ctx.poster is not None:
        pw = 600
        ph = int(pw * ctx.poster.height / ctx.poster.width)
        im = ImageOps.fit(ctx.poster.convert("RGB"), (pw, ph), Image.Resampling.LANCZOS).convert("RGBA")
        im = gfx.with_shadow(_round(im, 22), 34, 0.7, 26)
        sc.add(ctx.layer(Sprite(im, 0.5, 0.5), W / 2, 330 + ph / 2 * 0.62, z=0.8, scale=0.62, t_in=0.0, enter="slam", idle="float", role="image"))
        sc.cam.shake(0.05, 22, 0.4)
        box = (SAFE["left"] + 10, 330 + ph * 0.62 + 30, SAFE["right_top"] - 10, SAFE["bottom"] - 30)
    elif op == "rating_first":
        rating = ctx.data.get("rating", ctx.facts.get("rating"))
        if rating is not None:
            num = text_sprite(f"{rating}", ctx.F["hero"], 300, color=p["accent"], box=(2000, 2000), max_lines=1, shadow=ctx.shadow(1.5),
                              role="hero", glow=(24, 0.5, p["accent"]))
            sc.add(ctx.layer(num, W / 2, 470, z=1.0, t_in=0.0, enter="slam", idle="pulse", role="hero"))
            stars = _stars(ctx, float(rating), float(ctx.facts.get("out_of", 5)), 92)
            for i, s in enumerate(stars):
                sc.add(ctx.layer(s, W / 2 + (i - (len(stars) - 1) / 2) * 104, 680, z=1.0, t_in=0.25 + 0.08 * i, enter="pop", role="deco"))
                sc.cue(0.25 + 0.08 * i, "tick", 0.5)
            box = (SAFE["left"] + 10, 780, SAFE["right_top"] - 10, SAFE["bottom"] - 30)
    elif op == "question_flash":
        q = text_sprite("?", ctx.F["hero"], 900, color=mix_hex(p["accent"], p["bg0"], 0.25), box=(3000, 3000), max_lines=1, role="deco")
        sc.add(ctx.layer(q, W * 0.72, 760, z=0.5, t_in=0.0, enter="slam", idle="sway", opacity=0.55, rot=12, role="deco"))
        sc.cue(0.0, "glitch", 0.6)
        box = (SAFE["left"] + 10, 380, SAFE["right_top"] - 10, SAFE["bottom"] - 40)
    elif op == "split_reveal":
        for side in (-1, 1):
            panel = Image.new("RGBA", (W // 2 + 4, H), rgba(p["accent"] if side < 0 else p["bg1"]))
            sc.add(Layer(Sprite(panel, 0.5, 0.5), W / 4 if side < 0 else W * 3 / 4, H / 2, z=1.3, t_in=0.0, t_out=0.12, exit="slide_out",
                         enter="none", enter_dir=(side, 0), role="deco", motion="snappy"))
        sc.cue(0.1, "swish", 0.9)
        box = (SAFE["left"] + 10, 420, SAFE["right_top"] - 10, SAFE["bottom"] - 40)
    elif op == "countdown":
        for i, n in enumerate(("3", "2", "1")):
            s = text_sprite(n, ctx.F["hero"], 520, color=p["accent"], box=(3000, 3000), max_lines=1, shadow=ctx.shadow(1.5), role="deco")
            sc.add(ctx.layer(s, W / 2, 900, z=1.0, t_in=0.0 + i * 0.16, t_out=0.13 + i * 0.16, enter="slam", exit="fade", exit_dur=0.03, role="deco"))
            sc.cue(i * 0.16, "tick", 0.9)
        words = [dict(w, t0=max(w["t0"], 0.5)) for w in words]
        box = (SAFE["left"] + 10, 420, SAFE["right_top"] - 10, SAFE["bottom"] - 60)
    else:  # word_smash: lightning flash + streak
        streak = Image.new("RGBA", (W * 2, 26), rgba(p["accent"], 230))
        sc.add(Layer(Sprite(streak.rotate(-12, expand=True), 0.5, 0.5), W / 2, 560, z=0.6, t_in=0.0, t_out=0.35, enter="slide",
                     enter_dir=(1, 0), travel=1600, role="deco", motion="snappy"))
        box = (SAFE["left"] + 10, 360, SAFE["right_top"] - 10, SAFE["bottom"] - 40)
    frame1 = str(ctx.data.get("frame1") or "").strip()
    if frame1:
        # Frame-1 hook: the whole hook text is already on screen at t=0 (Reels-tab viewers judge the first frame, not
        # the cover). The spoken words it covers are not stacked again; the rest of the hook line builds below it.
        t1 = ctx.hero(frame1, (940, 560), max_lines=3, max_px=210, color=p["accent"], role="hero")
        h1 = t1.h - 2 * t1.meta["pad"]
        y1 = max(box[1], ctx.top + 40)
        sc.add(ctx.layer(t1, W / 2, y1 + h1 / 2, z=1.1, t_in=0.0, enter="none", idle="pulse", role="hero"))
        skip = int(ctx.data.get("frame1_words", len(frame1.split())))
        words = words[skip:]
        box = (box[0], y1 + h1 + 50, box[2], box[3])
    else:
        flash = Image.new("RGBA", (W, H), (255, 255, 255, 255))
        sc.add(Layer(Sprite(flash, 0.5, 0.5), W / 2, H / 2, z=2.0, t_in=0.0, t_out=0.0, exit="fade", enter="none", role="deco"))
    if words:
        kinetic_stack(ctx, sc, words, box, max_words_page=8)
    add_motif(ctx, sc)


@archetype("poster_hero", roles=("intro", "title"), cats=("movie_review", "game", "story"), variants=("tilt_card", "full_bleed", "framed"),
           needs=("poster",), captions=False)
def poster_hero(ctx: Ctx, sc):
    p = ctx.pal
    v = ctx.variant if ctx.variant in ("tilt_card", "full_bleed", "framed") else ctx.rng.choice(["tilt_card", "full_bleed", "framed"])
    title = ctx.data.get("title") or ctx.facts.get("title", "")
    chips = ctx.data.get("chips") or [str(x) for x in (ctx.facts.get("year"), (ctx.facts.get("genre") or [None])[0], ctx.facts.get("runtime")) if x]
    t_title = ctx.t_word(title, 0.12)
    top, bot = ctx.top, ctx.bottom
    chip_h = 84 if chips else 0
    if v == "full_bleed" and ctx.poster is not None:
        f = ctx.focus(0)
        im = ImageOps.fit(ctx.poster.convert("RGB"), (int(W * 1.18), int(H * 1.18)), Image.Resampling.LANCZOS,
                          centering=((f[0] + f[2]) / 2, (f[1] + f[3]) / 2))
        sc.bg = Background(im, depth=0.55, sharp=True)
        camera_for(ctx, sc, "push")
        shade = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        shade.putalpha(Image.linear_gradient("L").resize((W, H)).point(lambda v_: int(min(235, max(0, (v_ - 60) * 1.6)))))
        sc.add(ctx.layer(Sprite(shade, 0.5, 0.5), W / 2, H / 2, z=0.0, enter="none", role="deco"))
        t = ctx.anchor(ctx.hero(title, (SAFE["right_low"] - SAFE["left"] - 20, 420), max_lines=3, max_px=230, role="hero"))
        y_t = bot - chip_h - t.h / 2 + t.meta["pad"]
    else:
        sc.bg = make_bg(ctx)
        camera_for(ctx, sc)
        y_t = None
        title_first = v == "framed"
        if title_first:
            t = ctx.anchor(ctx.hero(title, (SAFE["right_low"] - SAFE["left"] - 10, 380), max_lines=3, max_px=210))
            y_t = top + t.h / 2 - t.meta["pad"]
            top = top + t.h - 2 * t.meta["pad"] + 40
        if ctx.poster is not None:
            avail = bot - top - chip_h - (40 if title_first else 280)
            ph = int(min(780, avail))
            pw = int(min(600, ph * ctx.poster.width / ctx.poster.height))
            ph = int(pw * ctx.poster.height / ctx.poster.width)
            im = ImageOps.fit(ctx.poster.convert("RGB"), (pw, ph), Image.Resampling.LANCZOS).convert("RGBA")
            im = _round(im, 18 if ctx.shape != "sharp" else 2)
            if v == "framed":
                fr = gfx.card(pw + 36, ph + 36, fill=p["accent"], kind="sharp" if ctx.shape in ("sharp", "cut") else "rounded", r=26)
                fr.alpha_composite(im, (18, 18))
                im = fr
            else:
                im = gfx.perspective(im, tilt_y=-0.5 if ctx.rng.random() < 0.5 else 0.5)
            im = gfx.with_shadow(im, 30, 0.65, 24)
            pad = 90  # with_shadow padding
            y = top + (im.height - 2 * pad) / 2 + 10
            sc.add(ctx.layer(Sprite(im, 0.5, 0.5), W / 2, y, z=0.85, t_in=0.0, enter="flip" if v == "framed" else ctx.enter("main"),
                             enter_dir=(0, 1), idle="float", role="image"))
            sc.cue(0.02, "whoosh", 0.7)
            title_top = y + (im.height - 2 * pad) / 2 + 30
        else:
            title_top = top + 120
        if not title_first:
            t = ctx.anchor(ctx.hero(title, (SAFE["right_low"] - SAFE["left"] - 20, max(200, bot - title_top - chip_h)), max_lines=3, max_px=230))
            y_t = title_top + t.h / 2 - t.meta["pad"]
    sc.add(ctx.layer(t, ctx.x_text(), y_t, z=1.0, t_in=t_title, enter=ctx.enter("hero"), role="hero"))
    sc.cue(t_title, "pop", 0.7)
    sc.cam.punch(t_title + 0.05, 0.03)
    y_chip = (y_t + t.h / 2 - t.meta["pad"] + 50) if not (v == "framed" and ctx.poster is not None) else bot - 30
    sprs = [ctx.chip(c, fill=p["accent"] if i == 0 else mix_hex(p["bg1"], p["text"], 0.14), color=p["ink"] if i == 0 else p["text"], px=40)
            for i, c in enumerate(chips[:3])]
    # wrap chips into rows that fit the safe width (long names never run off the right edge)
    avail = SAFE["right_low"] - SAFE["left"] - 20
    rows, cur, cw = [], [], 0.0
    for i, s_ in enumerate(sprs):
        need = s_.w + (18 if cur else 0)
        if cur and cw + need > avail:
            rows.append(cur)
            cur, cw, need = [], 0.0, s_.w
        cur.append(i)
        cw += need
    if cur:
        rows.append(cur)
    row_h = (max(s_.h for s_ in sprs) + 14) if sprs else 0
    y_row = min(y_chip, bot - (sprs[0].h / 2 if sprs else 0) - row_h * (len(rows) - 1))
    for row in rows:
        total = sum(sprs[i].w for i in row) + 18 * (len(row) - 1)
        x = SAFE["left"] + 10 if ctx.align == "left" else W / 2 - total / 2
        for i in row:
            s_ = sprs[i]
            tt = ctx.t_word(chips[i], at=t_title + 0.35 + 0.18 * i)
            sc.add(ctx.layer(s_, x + s_.w / 2, y_row, z=1.0, t_in=tt, enter="pop", role="label"))
            sc.cue(tt, "tick", 0.45)
            x += s_.w + 18
        y_row += row_h
    add_motif(ctx, sc)



@archetype("rating_meter", roles=("rating",), cats=("movie_review", "game", "product", "software"), variants=("ring", "bars", "giant"))
def rating_meter(ctx: Ctx, sc):
    p = ctx.pal
    rating = float(ctx.data.get("rating", ctx.facts.get("rating", 0)))
    out_of = float(ctx.data.get("out_of", ctx.facts.get("out_of", 5)))
    v = ctx.variant if ctx.variant in ("ring", "bars", "giant") else ctx.rng.choice(["ring", "bars", "giant"])
    sc.bg = make_bg(ctx, "spotlight" if ctx.dark and ctx.dna["background"] not in ("paper",) else None)
    camera_for(ctx, sc, "push")
    t0 = 0.12
    t_final = ctx.t_word(ctx.data.get("say_at"), at=None) if ctx.data.get("say_at") else None
    label = ctx.data.get("label", "RATING")
    lab = ctx.anchor(ctx.hero(label, (860, 120), max_lines=1, max_px=96, color=p["muted"], role="label"))
    sc.add(ctx.layer(lab, ctx.x_text(), ctx.top + 40, z=1.0, t_in=0.0, enter=ctx.enter("main"), enter_dir=(-1, 0), role="label"))
    dur_count = max(0.8, min(1.6, (t_final - t0) if t_final else ctx.dur * 0.5))
    decimals = 1 if rating % 1 else 0
    cy = (ctx.top + ctx.bottom) / 2 - 60
    if v == "ring":
        size = 640

        def fn(tl):
            q = ease_out_cubic(clamp((tl) / dur_count))
            val = rating * q
            key = (round(val, decimals), int(q * 90))

            def build():
                im = gfx.ring(size, 34, (val / out_of), p["accent"], track=mix_hex(p["bg1"], p["text"], 0.15))
                num = text_sprite(f"{val:.{decimals}f}", ctx.F["hero"], 250, color=p["text"], box=(3000, 3000), max_lines=1, role="hero")
                im.alpha_composite(num.img, (int(size / 2 - num.w / 2), int(size / 2 - num.h / 2 - 20)))
                sub = text_sprite(f"/ {out_of:g}", ctx.F["support"], 64, color=p["muted"], box=(3000, 3000), max_lines=1, role="label")
                im.alpha_composite(sub.img, (int(size / 2 - sub.w / 2), int(size / 2 + 95)))
                return Sprite(im, 0.5, 0.5, {"role": "hero", "px": 250, "text": f"{rating}", "pad": 0})
            return key, build
        sc.add(DynLayer(fn, W / 2, cy, z=1.0, t_in=t0, enter="pop", motion=ctx.motion, role="hero", idle="breathe"))
        star_y = cy + size / 2 + 90
    elif v == "bars":
        n = int(out_of) if out_of <= 10 else 10
        bw_, gap = 120 if n <= 5 else 62, 26 if n <= 5 else 14
        x0 = W / 2 - (n * bw_ + (n - 1) * gap) / 2
        for i in range(n):
            fillf = clamp(rating - i)
            hgt = 200 + i * 55 if n <= 5 else 160 + i * 30
            tr = gfx.card(bw_, hgt, fill=mix_hex(p["bg1"], p["text"], 0.1), kind="rounded", r=16, alpha=220)
            if fillf > 0:
                fh = int(hgt * fillf)
                fill = gfx.card(bw_, fh, fill=p["accent"], kind="rounded", r=16)
                tr.alpha_composite(fill, (0, hgt - fh))
            ti = t0 + 0.12 * i
            sc.add(ctx.layer(Sprite(tr, 0.5, 1.0), x0 + i * (bw_ + gap) + bw_ / 2, cy + 300, z=1.0, t_in=ti, enter="wipe", enter_dir=(0, -1),
                             enter_dur=0.35, role="deco"))
            sc.cue(ti, "tick", 0.5)
        num = text_sprite(f"{rating:g}/{out_of:g}", ctx.F["hero"], 200, color=p["text"], box=(3000, 3000), max_lines=1, shadow=ctx.shadow(1.3),
                          role="hero")
        sc.add(ctx.layer(num, W / 2, ctx.top + 230, z=1.0, t_in=t0 + 0.12 * n, enter="slam", role="hero"))
        sc.cam.punch(t0 + 0.12 * n + 0.05, 0.05)
        star_y = cy + 390
    else:  # giant number with fill rising inside an outline
        txt = f"{rating:g}"
        gpx = text_sprite(txt, ctx.F["hero"], None, box=(860, 520), max_lines=1, max_px=520, min_px=200, role="hero").meta["px"]
        outline = text_sprite(txt, ctx.F["hero"], gpx, color="#00000000", box=(3000, 3000), max_lines=1, stroke=0.02, stroke_color=p["accent"],
                              role="hero")
        filled = text_sprite(txt, ctx.F["hero"], gpx, color=p["accent"], box=(3000, 3000), max_lines=1, role="hero", glow=(20, 0.4, p["accent"]))
        sc.add(ctx.layer(outline, W / 2, cy - 40, z=1.0, t_in=t0 - 0.2, enter="fade", role="deco"))
        sc.add(ctx.layer(filled, W / 2, cy - 40, z=1.0, t_in=t0, enter="wipe", enter_dir=(0, -1), enter_dur=1.0, role="hero"))
        sub = text_sprite(f"OUT OF {out_of:g}", ctx.F["support"], 58, color=p["muted"], box=(3000, 3000), max_lines=1, role="label")
        sc.add(ctx.layer(sub, W / 2, cy + 260, z=1.0, t_in=t0 + 0.7, enter="rise", role="label"))
        star_y = cy + 380
    stars = _stars(ctx, rating, out_of, 96)
    for i, s in enumerate(stars):
        ti = t0 + dur_count * (i + 1) / len(stars)
        sc.add(ctx.layer(s, W / 2 + (i - (len(stars) - 1) / 2) * 112, min(star_y, ctx.bottom - 60), z=1.0, t_in=ti, enter="pop", role="deco"))
        sc.cue(ti, "tick", 0.55)
    sc.cue(t0 + dur_count + 0.05, "ding", 0.8)
    if ctx.dna["motif"] in ("sparkles", "dust", "light_rays"):
        add_motif(ctx, sc)


@archetype("story_panels", roles=("story", "plot", "setup"), cats=("movie_review", "story", "game"), variants=("stack", "filmstrip", "split"))
def story_panels(ctx: Ctx, sc):
    p = ctx.pal
    pts = list(ctx.data.get("points") or [])[:3] or [w["show"] for w in ctx.words if _norm(w["show"]) in ctx.hero_set][:3]
    if not pts:
        pts = [ctx.beat.get("show", "")[:40]]
    v = ctx.variant if ctx.variant in ("stack", "filmstrip", "split") else ctx.rng.choice(["stack", "filmstrip", "split"])
    if ctx.poster is None and v != "stack":
        v = "stack"
    sc.bg = make_bg(ctx)
    camera_for(ctx, sc, ctx.rng.choice(["drift_l", "drift_r", "push"]))
    times = [ctx.t_word(pt, f) for pt, f in zip(pts, [0.04, 0.34, 0.62])]
    top, bot = ctx.top, ctx.bottom
    n = len(pts)
    if v == "filmstrip":
        fw, fh = 520, 340
        strip_h = (fh + 40) * (n + 1) + 40
        strip = Image.new("RGBA", (fw + 140, strip_h), rgba("#0B0B0E", 245))
        perf = gfx.film_perfs(strip_h, 70, "#0B0B0E", "#E9E2D0", True, 210)
        strip.alpha_composite(perf, (0, 0))
        strip.alpha_composite(perf, (fw + 70, 0))
        for i in range(n + 1):
            strip.paste(ctx.poster_crop(ctx.focus(i, fw / fh), fw, fh), (70, 40 + i * (fh + 40)))
        st = Sprite(gfx.with_shadow(strip, 26, 0.6), 0.5, 0.5)
        sc.add(ctx.layer(st, W * 0.36, (top + bot) / 2 + 140, z=0.8, rot=-6, t_in=0.0, enter="slide", enter_dir=(0, 1), travel=900,
                         idle="scroll_up", idle_amp=0.8, role="image"))
        sc.cue(0.0, "whoosh", 0.7)
        slot = (bot - top) / n
        for i, (pt, ti) in enumerate(zip(pts, times)):
            lab = ctx.chip(pt, fill=p["accent"] if i % 2 == 0 else p["text"], color=p["ink"] if i % 2 == 0 else p["bg0"], px=52, case="any", role="body")
            y = top + slot * (i + 0.5)
            sc.add(ctx.layer(lab, min(W - lab.w / 2 - 70, max(W * 0.62, lab.w / 2 + 70)), y, z=1.0, t_in=ti, enter="slide", enter_dir=(1, 0), role="body"))
            sc.cue(ti, "swish", 0.6)
            sc.cam.punch(ti + 0.08, 0.02)
        return add_motif(ctx, sc)
    if v == "split":
        gap = 24
        ph = int((bot - top - gap * (n - 1)) / n)
        for i, (pt, ti) in enumerate(zip(pts, times)):
            fr = ctx.poster_crop(ctx.focus(i, 940 / ph), 940, ph).convert("RGBA")
            fr = _round(fr, 26 if ctx.shape != "sharp" else 0)
            shade = Image.new("RGBA", fr.size, (0, 0, 0, 0))
            shade.putalpha(Image.linear_gradient("L").rotate(90, expand=True).resize(fr.size).point(lambda v_: int(255 - v_ * 0.8)))
            fr.alpha_composite(shade)
            t = ctx.hero(pt, (600, ph - 50), max_lines=3, max_px=130, min_px=52, role="body", align="left")
            fr.alpha_composite(t.img, (34 - t.meta["pad"], int(ph / 2 - t.h / 2)))
            y = top + i * (ph + gap) + ph / 2
            sc.add(ctx.layer(Sprite(fr, 0.5, 0.5, {"role": "body", "px": t.meta["px"], "text": pt, "pad": 0}), W / 2 - 15, y, z=1.0, t_in=ti,
                             enter="wipe", enter_dir=(1 if i % 2 == 0 else -1, 0), enter_dur=0.5, role="body"))
            sc.cue(ti, "swish", 0.6)
            sc.cam.punch(ti + 0.1, 0.02)
        return add_motif(ctx, sc)
    # stack: big numbered cards, poster thumbnail when available
    gap = 30
    ch = int(min(300, (bot - top - gap * (n - 1)) / n))
    total = n * ch + gap * (n - 1)
    y0 = top + (bot - top - total) / 2
    cw = 930
    for i, (pt, ti) in enumerate(zip(pts, times)):
        yy = y0 + i * (ch + gap)
        c = glass(ctx, sc, W / 2 - 15 - cw / 2, yy, cw, ch)
        # left: thumbnail (poster crop) or a big number; right: the point, vertically centred over the full card height
        side = ch - 36
        num = text_sprite(f"{i + 1:02d}", ctx.F["hero"], int(side * (0.3 if ctx.poster is not None else 0.62)), color=p["accent"],
                          box=(3000, 3000), max_lines=1, role="label", stroke=0.06 if ctx.poster is not None else 0.0, stroke_color="#000000")
        if ctx.poster is not None:
            th = ctx.poster_crop(ctx.focus(i, 1.0), side, side).convert("RGBA")
            th.putalpha(gfx.shape_mask(side, side, "rounded" if ctx.shape != "sharp" else "sharp", 20))
            c.alpha_composite(th, (18, 18))
            c.alpha_composite(num.img, (18 + 8 - num.meta["pad"], 18 + side - num.h + num.meta["pad"] - 4))
        else:
            c.alpha_composite(num.img, (18 + side // 2 - num.w // 2, ch // 2 - num.h // 2))
        x_text = side + 50
        t = ctx.body(pt, (cw - x_text - 30, ch - 40), max_lines=2, max_px=96, min_px=44, align="left", color=p["text"])
        c.alpha_composite(t.img, (x_text - t.meta["pad"], int(ch / 2 - t.h / 2)))
        sc.add(ctx.layer(Sprite(c, 0.5, 0.5, {"role": "body", "px": t.meta["px"], "text": pt, "pad": 0}), W / 2 - 15, yy + ch / 2, z=1.0,
                         t_in=ti, enter="slide", enter_dir=(-1 if i % 2 == 0 else 1, 0), role="body"))
        sc.cue(ti, "swish", 0.6)
        sc.cam.punch(ti + 0.08, 0.02)
    add_motif(ctx, sc)


@archetype("cast_spotlight", roles=("cast", "performance"), cats=("movie_review", "story", "game"), variants=("portraits", "lower_third", "big_name"))
def cast_spotlight(ctx: Ctx, sc):
    """Cast cards. A face crop is used ONLY when the Director gives that person's own focus box / image — otherwise an honest
    monogram (never someone else's face under a name)."""
    p = ctx.pal
    cast = list(ctx.data.get("cast") or [])[:3]
    if not cast:
        cast = [{"name": w["show"], "role": ""} for w in ctx.words if _norm(w["show"]) in ctx.hero_set][:2] or [{"name": ctx.beat.get("show", "")[:24], "role": ""}]
    v = ctx.variant if ctx.variant in ("portraits", "lower_third", "big_name") else ctx.rng.choice(["portraits", "lower_third", "big_name"])
    if v == "big_name" and any(c.get("image") or (c.get("focus") and ctx.poster is not None) for c in cast):
        v = "portraits"  # real faces exist → show them
    sc.bg = make_bg(ctx, "spotlight" if ctx.dark else None)
    camera_for(ctx, sc, "push")
    times = [ctx.t_word(c["name"], f) for c, f in zip(cast, (0.05, 0.4, 0.68))]
    top, bot = ctx.top, ctx.bottom

    def face(c, size):
        if c.get("focus") and ctx.poster is not None:
            fr = ctx.poster_crop(tuple(c["focus"]), size, size).convert("RGBA")
        elif c.get("image"):
            src = Image.open(ctx.assets.get("root", Path(".")) / c["image"]).convert("RGB")
            if c.get("image_focus"):  # crop THIS person's face from a still the Director looked at
                src = gfx.crop_norm(src, c["image_focus"])
            fr = ImageOps.fit(src, (size, size), Image.Resampling.LANCZOS, centering=(0.5, 0.4)).convert("RGBA")
        else:
            fr = gfx.radial_gradient(size, size, size * 0.35, size * 0.3, size, mix_hex(p["accent"], p["bg1"], 0.35), p["bg0"], 1.2).convert("RGBA")
            ini = "".join(x[0] for x in c["name"].split()[:2]).upper()
            t = text_sprite(ini, ctx.F["hero"], int(size * 0.42), color=p["text"], box=(4000, 4000), max_lines=1, role="deco")
            fr.alpha_composite(t.img, (int(size / 2 - t.w / 2), int(size / 2 - t.h / 2)))
        fr.putalpha(gfx.shape_mask(size, size, "circle"))
        return fr
    if v == "big_name":
        n = len(cast)
        slot = (bot - top) / n
        for i, (c, ti) in enumerate(zip(cast, times)):
            y = top + slot * (i + 0.5)
            fill = ctx.hero(c["name"], (900, slot * 0.6), max_lines=2, max_px=220, role="hero")
            outline = text_sprite(fill.meta["text"], ctx.F["hero"], fill.meta["px"], color="#00000000", box=(900, slot * 0.6), max_lines=2,
                                  stroke=0.03, stroke_color=p["accent"], role="deco", align="center")
            sc.add(ctx.layer(outline, W / 2 + 12, y - 10 + 10, z=0.7, t_in=ti - 0.1, enter="fade", role="deco"))
            sc.add(ctx.layer(fill, W / 2, y - 10, z=1.0, t_in=ti, enter="slide", enter_dir=(-1 if i % 2 else 1, 0), role="hero"))
            if c.get("role"):
                rl = ctx.chip(c["role"], fill=p["accent"], color=p["ink"], px=40)
                sc.add(ctx.layer(rl, W / 2, y + fill.h / 2 - fill.meta["pad"] + 20, z=1.0, t_in=ti + 0.25, enter="pop", role="label"))
            sc.cue(ti, "hit", 0.6)
            sc.cam.punch(ti + 0.05, 0.03)
        return add_motif(ctx, sc)
    if v == "lower_third":
        c = cast[0]
        size = int(min(620, bot - top - 300))
        sc.add(ctx.layer(Sprite(gfx.with_shadow(face(c, size), 30, 0.6), 0.5, 0.5), W / 2, top + size / 2 + 20, z=0.85, t_in=0.0,
                         enter="blur_in", idle="float", role="image"))
        y_bar = top + size + 120
        for i, (c, ti) in enumerate(zip(cast, times)):
            nm = ctx.hero(c["name"], (820, 150), max_lines=1, max_px=130, color=p["text"], align="left")
            bar = gfx.card(880, nm.h - 2 * nm.meta["pad"] + 50, fill=mix_hex(p["bg0"], "#000000", 0.25) if ctx.dark else "#FFFFFF", kind=ctx.shape, r=18, alpha=235)
            bar.alpha_composite(Image.new("RGBA", (16, bar.height), rgba(p["accent"])), (0, 0))
            bar.alpha_composite(nm.img, (40 - nm.meta["pad"], 25 - nm.meta["pad"]))
            yy = min(y_bar + i * (bar.height + 70), bot - bar.height / 2)
            sc.add(ctx.layer(Sprite(bar, 0.5, 0.5, {"role": "hero", "px": nm.meta["px"], "text": c["name"], "pad": 0}), W / 2, yy, z=1.0,
                             t_in=ti, enter="wipe", enter_dir=(1, 0), enter_dur=0.45, role="hero"))
            if c.get("role"):
                rl = ctx.chip(c["role"], fill=p["accent"], color=p["ink"], px=36)
                sc.add(ctx.layer(rl, W / 2 + 440 - rl.w / 2, yy + bar.height / 2 + 6, z=1.05, t_in=ti + 0.3, enter="pop", role="label"))
            sc.cue(ti, "swish", 0.8)
        return add_motif(ctx, sc)
    # portraits: alternating rows, circle + name block, ring stroke-draws on
    n = len(cast)
    slot = (bot - top) / n
    # rows alternate sides, so a row's name block sits beside the NEXT row's circle: size the circles so every name block
    # (name + role chip, ≥ ~220 px) fits between the neighbouring rings and never runs into them
    size = int(max(200, min(360 if n >= 2 else 460, 2 * slot - 284))) if n >= 2 else 460
    ring_r = (size + 40) / 2 + 12
    text_h = (2 * (slot - ring_r)) if n >= 2 else 420
    for i, (c, ti) in enumerate(zip(cast, times)):
        y = top + slot * (i + 0.5)
        left = i % 2 == 0
        xc = SAFE["left"] + 20 + size / 2 if left else SAFE["right_low"] - size / 2 + 40
        sc.add(ctx.layer(Sprite(face(c, size), 0.5, 0.5), xc, y, z=0.9, t_in=ti, enter="pop", role="image"))

        def ring_fn(tl, size=size):
            q = round(ease_out_cubic(clamp(tl / 0.6)) * 60) / 60
            return q, lambda: Sprite(gfx.ring(size + 40, 10, q, p["accent"]), 0.5, 0.5)
        sc.add(DynLayer(ring_fn, xc, y, z=1.0, t_in=ti + 0.05, enter="none", motion=ctx.motion, role="deco"))
        bw_ = W - size - 2 * SAFE["left"] - 90
        rl = ctx.chip(c["role"], fill=p["accent"], color=p["ink"], px=38) if c.get("role") else None
        chip_h = (rl.h + 10) if rl is not None else 0
        nm = ctx.hero(c["name"], (bw_, max(90, min(260, text_h - chip_h))), max_lines=2, max_px=130, align="left" if left else "right",
                      role="hero")
        nh = nm.h - 2 * nm.meta["pad"]
        y_top = y - (nh + chip_h) / 2  # name + chip block centred on the row
        if left:
            nm.ax, nx = 0.0, xc + size / 2 + 50 - nm.meta["pad"]
        else:
            nm.ax, nx = 1.0, xc - size / 2 - 50 + nm.meta["pad"]
        sc.add(ctx.layer(nm, nx, y_top + nh / 2, z=1.0, t_in=ti + 0.15, enter="slide", enter_dir=(1 if not left else -1, 0), role="hero"))
        if rl is not None:
            rx = nx + rl.w / 2 if left else nx - rl.w / 2
            sc.add(ctx.layer(rl, rx, y_top + nh + 10 + rl.h / 2, z=1.0, t_in=ti + 0.3, enter="pop", role="label"))
        sc.cue(ti, "pop", 0.6)
    add_motif(ctx, sc)



@archetype("pros_cons", roles=("pros_cons", "pros", "cons", "analysis"), variants=("cards", "balance"), needs=("pros_or_cons",))
def pros_cons(ctx: Ctx, sc):
    p = ctx.pal
    pros, cons = list(ctx.data.get("pros") or [])[:3], list(ctx.data.get("cons") or [])[:3]
    if not pros and not cons:
        pros = [w["show"] for w in ctx.words if _norm(w["show"]) in ctx.hero_set][:2] or [ctx.beat.get("show", "")[:30]]
    v = ctx.variant if ctx.variant in ("cards", "balance") else ctx.rng.choice(["cards", "balance"])
    sc.bg = make_bg(ctx)
    camera_for(ctx, sc, "push")
    items = [("+", t) for t in pros] + [("-", t) for t in cons]
    times = [ctx.t_word(t, f) for (_, t), f in zip(items, [0.04 + 0.85 * i / max(1, len(items)) for i in range(len(items))])]
    top, bot = ctx.top, ctx.bottom
    if v == "balance" and max(len(t) for _, t in items) > 18:
        v = "cards"  # long points don't fit on a balance beam → readable cards instead
    if v == "balance" and pros and cons:
        cx, cy = W / 2, (top + bot) / 2 + 60
        beam = gfx.card(880, 24, fill=p["text"], kind="pill")
        post = gfx.card(28, 300, fill=mix_hex(p["text"], p["bg0"], 0.35), kind="pill")
        sc.add(ctx.layer(Sprite(post, 0.5, 0.0), cx, cy, z=0.9, enter="rise", role="deco"))
        tilt_events, score = [], 0
        for (kind, _), ti in zip(items, times):
            score += 1 if kind == "+" else -1
            tilt_events.append((ti, score))

        class Beam(Layer):
            def state(self, t):
                st = Layer.state(self, t)
                if st is None:
                    return None
                x, y, sx, sy, r, a, rev = st
                prev, ang = 0.0, 0.0
                for te, sc_ in tilt_events:
                    if t >= te:
                        target = max(-12, min(12, -sc_ * 6))
                        ang = prev + (target - prev) * spring(t - te, 7, 0.3)
                        prev = target
                return x, y, sx, sy, r + ang, a, rev
        sc.add(Beam(Sprite(beam, 0.5, 0.5), cx, cy, z=1.0, enter="pop", motion=ctx.motion, role="deco"))
        counts = {"+": 0, "-": 0}
        for (kind, txt), ti in zip(items, times):
            good = kind == "+"
            px_ = 44
            while True:
                ch = ctx.chip(txt, fill=p["good"] if good else p["bad"], color="#FFFFFF" if (not good or ctx.dark) else p["ink"], px=px_,
                              case="any", role="body")
                if ch.w <= 430 or px_ <= 32:
                    break
                px_ -= 3
            x = cx - 230 if good else cx + 230
            x = clamp(x, SAFE["left"] + ch.w / 2, SAFE["right_low"] - ch.w / 2)
            y = cy - 70 - counts[kind] * (ch.h + 16)
            counts[kind] += 1
            sc.add(ctx.layer(ch, x, y, z=1.0, t_in=ti, enter="drop", role="body"))
            sc.cue(ti, "pop" if good else "thud", 0.7)
        for lbl, x, col in (("PROS", cx - 230, p["good"]), ("CONS", cx + 230, p["bad"])):
            s_ = ctx.hero(lbl, (380, 120), max_lines=1, max_px=100, color=col, role="label")
            sc.add(ctx.layer(s_, x, cy + 110, z=1.0, t_in=0.05, enter="pop", role="label"))
        return add_motif(ctx, sc)
    n = len(items)
    gap = 26
    ch = int(min(250, (bot - top - gap * (n - 1)) / max(1, n)))
    total = n * ch + gap * (n - 1)
    y0 = top + (bot - top - total) / 2
    cw = 930
    for i, ((kind, txt), ti) in enumerate(zip(items, times)):
        good = kind == "+"
        col = p["good"] if good else p["bad"]
        yy = y0 + i * (ch + gap)
        c = glass(ctx, sc, W / 2 - 15 - cw / 2, yy, cw, ch)
        c.alpha_composite(gfx.card(14, ch - 34, fill=col, kind="pill"), (20, 17))
        t = ctx.body(txt, (cw - ch - 70, ch - 40), max_lines=2, max_px=92, min_px=48, align="left", color=p["text"])
        c.alpha_composite(t.img, (ch + 20 - t.meta["pad"], int(ch / 2 - t.h / 2)))
        sc.add(ctx.layer(Sprite(c, 0.5, 0.5, {"role": "body", "px": t.meta["px"], "text": txt, "pad": 0}), W / 2 - 15, yy + ch / 2, z=1.0,
                         t_in=ti, enter="slide", enter_dir=(-1 if good else 1, 0), role="body"))
        isz = int(ch * 0.6)

        def icon_fn(tl, good=good, isz=isz, col=col):
            q = round(ease_out_cubic(clamp(tl / 0.45)) * 30) / 30
            return q, lambda: Sprite(gfx.icon("check" if good else "cross", isz, q, col, max(8, isz // 7)), 0.5, 0.5)
        sc.add(DynLayer(icon_fn, W / 2 - 15 - cw / 2 + 40 + ch / 2 - 10, yy + ch / 2, z=1.05, t_in=ti + 0.15, enter="none", motion=ctx.motion,
                        role="deco"))
        sc.cue(ti, "swish", 0.5)
        sc.cue(ti + 0.2, "pop" if good else "thud", 0.7)
    add_motif(ctx, sc)


@archetype("quote_kinetic", roles=("quote", "opinion", "line", "hot_take"), variants=("a",), captions=False)
def quote_kinetic(ctx: Ctx, sc):
    p = ctx.pal
    sc.bg = make_bg(ctx)
    camera_for(ctx, sc, "push")
    q = text_sprite("“", ctx.F["hero"] if ctx.F["hero"] not in ("bebas", "anton", "oswald") else "playfair", 700,
                    color=mix_hex(p["accent"], p["bg0"], 0.35), box=(3000, 3000), max_lines=1, role="deco")
    sc.add(ctx.layer(q, 240, SAFE["top"] + 200, z=0.6, t_in=0.0, enter="drop", idle="float", role="deco"))
    kinetic_stack(ctx, sc, words_or_text(ctx), (SAFE["left"] + 20, SAFE["top"] + 220, SAFE["right_top"] - 20, SAFE["bottom"] - 60), max_words_page=9)
    if ctx.data.get("attribution"):
        a = ctx.body("— " + ctx.data["attribution"], (800, 80), px=46, color=p["muted"], role="label")
        sc.add(ctx.layer(a, W / 2, SAFE["bottom"] - 40, z=1.0, t_in=ctx.dur * 0.6, enter="rise", role="label"))
    add_motif(ctx, sc)


@archetype("kinetic_line", roles=("line", "any", "transition", "bridge"), variants=("stack", "diagonal"), captions=False)
def kinetic_line(ctx: Ctx, sc):
    sc.bg = make_bg(ctx)
    camera_for(ctx, sc, ctx.rng.choice(["orbit", "push", "drift_l"]))
    box = (SAFE["left"] + 10, SAFE["top"] + 120, SAFE["right_top"] - 10, SAFE["bottom"] - 80)
    layers = kinetic_stack(ctx, sc, words_or_text(ctx), box, max_words_page=8)
    if ctx.variant == "diagonal":
        for ly in layers:
            ly.rot = -7
    add_motif(ctx, sc)


@archetype("stat_counter", roles=("stat", "number", "box_office", "fact"), variants=("arc", "bar"))
def stat_counter(ctx: Ctx, sc):
    p = ctx.pal
    val = float(ctx.data.get("value", 0))
    pre, suf, dec = ctx.data.get("prefix", ""), ctx.data.get("suffix", ""), int(ctx.data.get("decimals", 0 if val == int(val) else 1))
    label = ctx.data.get("label", "")
    sc.bg = make_bg(ctx)
    camera_for(ctx, sc, "push")
    t0 = ctx.t_word(ctx.data.get("say_at") or (str(int(val)) if val else label), 0.08)
    cnt = 1.2

    def fn(tl):
        q = ease_out_cubic(clamp(tl / cnt))
        cur = val * q
        key = round(cur, dec)

        def build():
            s = text_sprite(f"{pre}{cur:,.{dec}f}{suf}", ctx.F["hero"], None, color=p["accent"], box=(920, 420), max_lines=1, max_px=380,
                            min_px=120, shadow=ctx.shadow(1.4), role="hero", glow=(18, 0.35, p["accent"]))
            return s
        return key, build
    sc.add(DynLayer(fn, W / 2, 640, z=1.0, t_in=t0, enter="pop", motion=ctx.motion, role="hero"))
    for k in range(6):
        sc.cue(t0 + cnt * k / 6, "tick", 0.35)
    sc.cue(t0 + cnt, "ding", 0.7)
    sc.cam.punch(t0 + cnt, 0.04)
    if label:
        lb = ctx.hero(label, (900, 260), max_lines=2, max_px=120, color=p["text"], role="body")
        sc.add(ctx.layer(lb, W / 2, 940, z=1.0, t_in=t0 + 0.4, enter=ctx.enter("main"), enter_dir=(0, 1), role="body"))
    # progress bar under
    bw_ = 860

    def bar_fn(tl):
        q = round(ease_out_cubic(clamp(tl / cnt)) * 50) / 50

        def build():
            tr = gfx.card(bw_, 26, fill=mix_hex(p["bg1"], p["text"], 0.15), kind="pill", alpha=230)
            if q > 0.02:
                tr.alpha_composite(gfx.card(max(26, int(bw_ * q)), 26, fill=p["accent"], kind="pill"), (0, 0))
            return Sprite(tr, 0.5, 0.5)
        return q, build
    sc.add(DynLayer(bar_fn, W / 2, 1100 if ctx.cap_on is False else min(1100, ctx.bottom - 20), z=1.0, t_in=t0, enter="none", motion=ctx.motion, role="deco"))
    add_motif(ctx, sc)


@archetype("verdict_stamp", roles=("verdict", "final"), variants=("stamp", "seal", "neon"))
def verdict_stamp(ctx: Ctx, sc):
    p = ctx.pal
    verdict = ctx.data.get("verdict", "WATCH IT")
    rating = ctx.data.get("rating", ctx.facts.get("rating"))
    where = ctx.data.get("where") or ctx.facts.get("where_to_watch")
    v = ctx.variant if ctx.variant in ("stamp", "seal", "neon") else ctx.rng.choice(["stamp", "seal", "neon"])
    sc.bg = make_bg(ctx, "spotlight" if ctx.dark and v != "seal" else None)
    camera_for(ctx, sc, "push")
    t0 = ctx.t_word(verdict, 0.18)
    cy = (ctx.top + ctx.bottom) / 2 - 150
    if v == "seal":
        size = 640

        def seal_fn(tl):
            ang = int(tl * 24) % 360
            return ang, lambda: Sprite(_seal(ctx, size, verdict, ang), 0.5, 0.5, {"role": "hero", "px": 120, "text": verdict, "pad": 0})
        sc.add(DynLayer(seal_fn, W / 2, cy, z=1.0, t_in=t0, enter="spin", motion=ctx.motion, role="hero"))
        sc.cue(t0, "impact", 0.9)
    elif v == "neon":
        t = ctx.hero(verdict, (900, 420), max_lines=2, max_px=230, color="#FFFFFF", glow=True, role="hero")
        t2 = text_sprite(t.meta["text"], ctx.F["hero"], t.meta["px"], color=p["accent"], box=(900, 420), max_lines=2,
                         glow=(30, 0.9, p["accent"]), role="deco")
        sc.add(ctx.layer(t2, W / 2, cy, z=0.95, t_in=t0, enter="fade", enter_dur=0.08, idle="pulse", role="deco"))
        sc.add(ctx.layer(t, W / 2, cy, z=1.0, t_in=t0 + 0.12, enter="fade", enter_dur=0.05, role="hero"))
        sc.cue(t0, "glitch", 0.5)
        sc.cue(t0 + 0.12, "hit", 0.8)
    else:
        t = text_sprite(apply_case(verdict, "upper"), ctx.F["hero"], None, color=p["bad"] if ctx.data.get("negative") else p["accent"],
                        box=(820, 360), max_lines=2, max_px=200, min_px=90, role="hero")
        st = gfx.stamp(t.img, color=p["bad"] if ctx.data.get("negative") else p["accent"], seed=ctx.idx, kind="rounded" if ctx.shape != "sharp" else "sharp")
        sc.add(ctx.layer(Sprite(st, 0.5, 0.5, {"role": "hero", "px": t.meta["px"], "text": verdict, "pad": 0}), W / 2, cy, z=1.0, t_in=t0,
                         rot=-7, enter="slam", role="hero"))
        sc.cue(t0, "stamp", 1.0)
        sc.cam.shake(t0 + 0.06, 20, 0.35)
        dust = [Sprite(gfx.glow_dot(s, p["text"], 0.8)) for s in (4, 7, 10)]
        sc.add(Particles(dust, n=40, seed=ctx.idx, z=1.1, alpha=0.9, t_in=t0 + 0.06, burst=(W / 2, cy, 900)))
    sc.cam.punch(t0 + 0.06, 0.06)
    y = cy + 380
    if rating is not None:
        stars = _stars(ctx, float(rating), float(ctx.facts.get("out_of", 5)), 84)
        for i, s in enumerate(stars):
            ti = t0 + 0.4 + 0.09 * i
            sc.add(ctx.layer(s, W / 2 + (i - (len(stars) - 1) / 2) * 98, y, z=1.0, t_in=ti, enter="pop", role="deco"))
            sc.cue(ti, "tick", 0.4)
        y += 120
    if where:
        tw = ctx.t_word(where, at=t0 + 0.9)
        ch = ctx.chip(f"WATCH: {where}", fill=p["text"], color=p["bg0"], px=44)
        sc.add(ctx.layer(ch, W / 2, min(y, ctx.bottom - 40), z=1.0, t_in=tw, enter="pop", role="label"))
        sc.cue(tw, "pop", 0.6)
    add_motif(ctx, sc)


@archetype("cta_loop", roles=("cta", "outro", "question"), variants=("question", "follow"))
def cta_loop(ctx: Ctx, sc):
    """Ending that asks a comment-bait question and visually loops back towards the opening (re-watch)."""
    p = ctx.pal
    sc.bg = make_bg(ctx, variant_seed=-ctx.idx * 31)  # same plate seed as scene 0 → loops visually
    camera_for(ctx, sc, "pull")
    qtxt = ctx.data.get("question") or ctx.beat.get("show", "")
    q = ctx.hero(qtxt, (900, 560), max_lines=4, max_px=170, role="hero", highlight=ctx.hero_set)
    qy = (ctx.top + ctx.bottom) / 2 - 120
    sc.add(ctx.layer(q, W / 2, qy, z=1.0, t_in=0.0, enter=ctx.enter("hero"), role="hero"))
    sc.cue(0.0, "pop", 0.7)
    cta = ctx.data.get("cta", "FOLLOW")
    tc = ctx.t_word(cta, 0.55)
    c = ctx.chip(cta, fill=p["accent"], color=p["ink"], px=54)
    sc.add(ctx.layer(c, W / 2, qy + q.h / 2 - q.meta["pad"] + 80, z=1.0, t_in=tc, enter="pop", idle="pulse", role="label"))
    sc.cue(tc, "ding", 0.6)
    y_cm = qy + q.h / 2 - q.meta["pad"] + 80 + c.h + 20
    cm_text = ctx.data.get("comment_cta", "COMMENT KARO")
    cm = ctx.chip(cm_text, fill=mix_hex(p["bg1"], p["text"], 0.12), color=p["text"], px=40) if cm_text else None
    if cm is not None:  # "" = one CTA only (Script Doctor v4: the comment question is the single call to action)
        sc.add(ctx.layer(cm, W / 2, y_cm, z=1.0, t_in=tc + 0.25, enter="rise", role="label"))
    if ctx.assets.get("handle"):  # the channel's handle on the end card: a shared reel still says whose it is
        hd = ctx.body(ctx.assets["handle"], (800, 70), px=44, color=p["text"], role="label", max_lines=1)
        sc.add(ctx.layer(hd, W / 2, min(y_cm + (cm.h / 2 + 50 if cm is not None else 0), ctx.bottom - 30), z=1.0, t_in=tc + 0.4,
                         enter="rise", role="label"))
    add_motif(ctx, sc)


@archetype("list_reveal", roles=("list", "reasons", "top"), variants=("numbers",))
def list_reveal(ctx: Ctx, sc):
    p = ctx.pal
    items = list(ctx.data.get("items") or [])[:5] or [ctx.beat.get("show", "")]
    sc.bg = make_bg(ctx)
    camera_for(ctx, sc, "rise")
    top, bot = SAFE["top"] + 30, ctx.bottom
    if ctx.data.get("title"):
        tt = ctx.anchor(ctx.hero(ctx.data["title"], (900, 160), max_lines=1, max_px=120, color=p["accent"]))
        sc.add(ctx.layer(tt, ctx.x_text(), top + 60, z=1.0, t_in=0.0, enter=ctx.enter("main"), role="hero"))
        top += 160
    n = len(items)
    slot = (bot - top) / n
    for i, it in enumerate(items):
        ti = ctx.t_word(it, 0.05 + 0.8 * i / max(1, n))
        y = top + slot * (i + 0.5)
        num = text_sprite(str(i + 1), ctx.F["hero"], int(min(240, slot * 0.9)), color=p["accent"], box=(3000, 3000), max_lines=1,
                          shadow=ctx.shadow(), role="label")
        sc.add(ctx.layer(num, SAFE["left"] + 80, y, z=1.0, t_in=ti, enter="slam" if ctx.motion == "heavy" else "pop", role="label"))
        x_t = SAFE["left"] + 180
        r_lim = SAFE["right_low"] if y + slot * 0.4 > SAFE["low_from"] else SAFE["right_top"]  # lower items avoid the Reels buttons
        t = ctx.body(it, (min(760, r_lim - x_t - 60), slot * 0.8), max_lines=2, max_px=96, min_px=48, align="left")
        t.ax = 0.0
        sc.add(ctx.layer(t, x_t, y, z=1.0, t_in=ti + 0.12, enter="wipe", enter_dir=(1, 0), role="body"))
        sc.cue(ti, "pop", 0.6)
    add_motif(ctx, sc)


@archetype("split_compare", roles=("compare", "vs"), variants=("diagonal", "stacked"))
def split_compare(ctx: Ctx, sc):
    p = ctx.pal
    left, right = ctx.data.get("left", {}), ctx.data.get("right", {})
    sc.bg = make_bg(ctx, "split_tone" if ctx.dark else None)
    camera_for(ctx, sc, "push")
    tl, tr = ctx.t_word(left.get("title"), 0.05), ctx.t_word(right.get("title"), 0.45)
    top, bot = ctx.top, ctx.bottom
    half = (bot - top) / 2
    vs = ctx.chip("VS", fill=p["accent"], color=p["ink"], px=96, shape="pill")
    clear = vs.h / 2 + 34  # each side's block stays clear of the VS badge + the tilted divider
    zones = ((top, top + half - clear), (top + half + clear, bot))
    for side, d, ti, (z0, z1), col in ((left, -1, tl, zones[0], p["text"]), (right, 1, tr, zones[1], p["accent"])):
        sb, sub_h, gap = None, 0, 0
        if side.get("sub"):
            sb = ctx.body(side["sub"], (880, 90), px=54, color=p["muted"], role="label", max_lines=1)
            sub_h, gap = sb.h - 2 * sb.meta["pad"], 18
        t = ctx.hero(side.get("title", ""), (900, max(90, min(half * 0.62, (z1 - z0) - sub_h - gap))), max_lines=2, max_px=200, color=col)
        th = t.h - 2 * t.meta["pad"]
        y0 = z0 + max(0, ((z1 - z0) - (th + gap + sub_h)) / 2)
        sc.add(ctx.layer(t, W / 2, y0 + th / 2, z=1.0, t_in=ti, enter="slide", enter_dir=(d, 0), role="hero"))
        if sb is not None:
            sc.add(ctx.layer(sb, W / 2, y0 + th + gap + sub_h / 2, z=1.0, t_in=ti + 0.2, enter="rise", role="label"))
        sc.cue(ti, "swish", 0.7)
    line = Image.new("RGBA", (900, 8), rgba(p["accent"], 230))
    sc.add(ctx.layer(Sprite(line.rotate(-6, expand=True, resample=Image.Resampling.BICUBIC), 0.5, 0.5), W / 2, top + half, z=0.95,
                     t_in=(tl + tr) / 2 - 0.1, enter="wipe", enter_dir=(1, 0), enter_dur=0.35, role="deco"))
    sc.add(ctx.layer(vs, W / 2, top + half, z=1.1, t_in=(tl + tr) / 2, enter="slam", role="label"))
    sc.cue((tl + tr) / 2, "hit", 0.9)
    sc.cam.punch((tl + tr) / 2 + 0.05, 0.04)
    add_motif(ctx, sc)


@archetype("fact_bomb", roles=("fact", "hook_fact", "number"), cats=("facts", "story", "movie_review", "software", "game"), variants=("big",))
def fact_bomb(ctx: Ctx, sc):
    p = ctx.pal
    big, line = str(ctx.data.get("big", "")), ctx.data.get("line", "")
    sc.bg = make_bg(ctx)
    camera_for(ctx, sc, "dolly")
    t0 = ctx.t_word(big, 0.05)
    zone = ctx.bottom - ctx.top
    b = ctx.hero(big, (920, zone * (0.55 if line else 0.8)), max_lines=2, max_px=420, color=p["accent"],
                 glow=ctx.dna["caption_style"] == "glow", role="hero")
    bh = b.h - 2 * b.meta["pad"]
    l2 = ctx.body(line, (900, zone * 0.32), max_lines=3, max_px=88, min_px=46) if line else None
    lh = (l2.h - 2 * l2.meta["pad"]) if l2 else 0
    gap = 40 if l2 else 0
    y = ctx.top + (zone - bh - gap - lh) / 2
    sc.add(ctx.layer(b, W / 2, y + bh / 2, z=1.0, t_in=t0, enter="slam", idle="breathe", role="hero"))
    sc.cue(t0, "impact", 0.9)
    sc.cam.shake(t0 + 0.05, 16, 0.3)
    if l2:
        sc.add(ctx.layer(l2, W / 2, y + bh + gap + lh / 2, z=1.0, t_in=ctx.t_word(line, at=t0 + 0.5), enter=ctx.enter("main"), role="body"))
    add_motif(ctx, sc)


@archetype("timeline", roles=("timeline", "history"), variants=("vertical",))
def timeline(ctx: Ctx, sc):
    p = ctx.pal
    ev = list(ctx.data.get("events") or [])[:4]
    sc.bg = make_bg(ctx)
    camera_for(ctx, sc, "rise")
    top, bot = ctx.top + 40, ctx.bottom - 20
    x = SAFE["left"] + 70

    def line_fn(tl):
        q = round(ease_out_cubic(clamp(tl / (ctx.dur * 0.8))) * 60) / 60
        return q, lambda: Sprite(Image.new("RGBA", (10, max(1, int((bot - top) * q))), rgba(p["accent"])), 0.5, 0.0)
    sc.add(DynLayer(line_fn, x, top, z=1.0, enter="none", motion=ctx.motion, role="deco"))
    n = max(1, len(ev))
    tw = SAFE["right_low"] - x - 70
    for i, e in enumerate(ev):
        y = top + (bot - top) * (i + 0.5) / n
        ti = ctx.t_word(str(e.get("year", "")), 0.8 * (i + 0.5) / n)
        sc.add(ctx.layer(Sprite(gfx.ring(64, 16, 1.0, p["accent"]), 0.5, 0.5), x, y, z=1.0, t_in=ti, enter="pop", role="deco"))
        yr = ctx.hero(str(e.get("year", "")), (tw, 150), max_lines=1, max_px=140, color=p["accent"], align="left")
        yr.ax = 0.0
        sc.add(ctx.layer(yr, x + 60 - yr.meta["pad"], y - 50, z=1.0, t_in=ti + 0.05, enter="slide", enter_dir=(-1, 0), role="hero"))
        lb = ctx.body(e.get("label", ""), (tw, 150), max_lines=2, max_px=70, min_px=44, align="left")
        lb.ax = 0.0
        sc.add(ctx.layer(lb, x + 60 - lb.meta["pad"], y + 60, z=1.0, t_in=ti + 0.2, enter="rise", role="body"))
        sc.cue(ti, "pop", 0.6)
    add_motif(ctx, sc)


@archetype("product_hero", roles=("product", "intro", "showcase"), cats=("product",), variants=("float", "arch"))
def product_hero(ctx: Ctx, sc):
    p = ctx.pal
    sc.bg = make_bg(ctx)
    camera_for(ctx, sc, "push")
    img = ctx.assets.get("product")
    v = ctx.variant if ctx.variant in ("float", "arch") else ctx.rng.choice(["float", "arch"])
    top, bot = ctx.top + 70, ctx.bottom
    name = ctx.data.get("name") or ctx.beat.get("show", "")
    t = ctx.hero(name, (900, 230), max_lines=2, max_px=150, role="hero")
    th = t.h - 2 * t.meta["pad"]
    ih = int(min(860, bot - top - th - 60))
    size = (int(ih * 0.84), ih)
    if img is not None:
        im = ImageOps.contain(img.convert("RGBA"), size, Image.Resampling.LANCZOS)
    else:
        im = _fabric(ctx, size)
    if v == "arch":
        frame = Image.new("RGBA", (size[0] + 40, size[1] + 40), (0, 0, 0, 0))
        m = gfx.shape_mask(size[0], size[1], "arch")
        fill = ImageOps.fit(im.convert("RGB"), size, Image.Resampling.LANCZOS).convert("RGBA")
        fill.putalpha(m)
        ring = gfx.shape_mask(size[0] + 40, size[1] + 40, "arch")
        frame.paste(Image.new("RGBA", frame.size, rgba(p["accent"])), (0, 0), ring)
        frame.alpha_composite(fill, (20, 20))
        im = frame
    im = gfx.with_shadow(im, 34, 0.35 if not ctx.dark else 0.6, 30)
    sc.add(ctx.layer(Sprite(im, 0.5, 0.5), W / 2, top + ih / 2 + 10, z=0.9, t_in=0.0, enter="blur_in", enter_dur=0.7, idle="float", role="image"))
    sc.cue(0.0, "swell", 0.6)
    tag = ctx.data.get("tag")
    if tag:
        tg = ctx.chip(tag, fill=p["accent"], color=p["ink"], px=40, case="upper")
        sc.add(ctx.layer(tg, W / 2, ctx.top + 20, z=1.0, t_in=ctx.t_word(tag, 0.1), enter="drop", role="label"))
    tn = ctx.t_word(name, 0.25)
    sc.add(ctx.layer(t, W / 2, top + ih + 50 + th / 2, z=1.0, t_in=tn, enter=ctx.enter("hero"), role="hero"))
    sc.cue(tn, "shimmer", 0.6)
    add_motif(ctx, sc)


@archetype("price_tag", roles=("price", "offer"), cats=("product",), variants=("swing",))
def price_tag(ctx: Ctx, sc):
    p = ctx.pal
    sc.bg = make_bg(ctx)
    camera_for(ctx, sc, "push")
    price, old = str(ctx.data.get("price", "")), ctx.data.get("old_price")
    tp = ctx.t_word(price.replace("₹", "").replace(",", ""), 0.1)
    t = text_sprite(price, ctx.F["hero"], None, color=p["ink"] if not ctx.dark else p["bg0"], box=(560, 260), max_lines=1, max_px=200, role="hero")
    tw, th = t.w + 120, t.h + 140
    tag = gfx.card(tw, th, fill=p["accent"] if ctx.dark else p["accent"], kind="ticket", r=30)
    tag.alpha_composite(t.img, (60, 90))
    d = ImageDraw.Draw(tag)
    d.ellipse([tw / 2 - 18, 22, tw / 2 + 18, 58], fill=(0, 0, 0, 0), outline=rgba(p["text"] if ctx.dark else p["bg0"]), width=6)
    string = Image.new("RGBA", (6, 300), rgba(p["text"] if ctx.dark else p["accent"], 200))
    sc.add(ctx.layer(Sprite(string, 0.5, 1.0), W / 2, SAFE["top"] + 300, z=0.95, t_in=tp - 0.05, enter="drop", role="deco"))

    class Swing(Layer):
        def state(self, t):
            st = super().state(t)
            if st is None:
                return None
            x, y, sx, sy, r, a, rev = st
            return x, y, sx, sy, r + 16 * impulse(t - self.t_in, 6.5, 0.18), a, rev
    sc.add(Swing(Sprite(tag, 0.5, 0.0, {"role": "hero", "px": t.meta["px"], "text": price, "pad": 0}), W / 2, SAFE["top"] + 290, z=1.0,
                 t_in=tp, enter="drop", motion=ctx.motion, role="hero"))
    sc.cue(tp, "pop", 0.8)
    y = SAFE["top"] + 300 + th + 60
    if old:
        o = ctx.body(str(old), (600, 120), px=90, color=p["muted"], role="label")
        sc.add(ctx.layer(o, W / 2, y, z=1.0, t_in=tp + 0.4, enter="rise", role="label"))

        def strike_fn(tl, ow=o.w - 2 * o.meta["pad"]):
            q = round(ease_out_cubic(clamp(tl / 0.35)) * 30) / 30
            return q, lambda: Sprite(Image.new("RGBA", (max(1, int(ow * q)), 10), rgba(p["bad"])), 0.0, 0.5)
        sc.add(DynLayer(strike_fn, W / 2 - (o.w - 2 * o.meta["pad"]) / 2, y + 6, z=1.05, t_in=tp + 0.7, enter="none", motion=ctx.motion, role="deco"))
        sc.cue(tp + 0.7, "swish", 0.5)
        y += 140
    if ctx.data.get("note"):
        n = ctx.chip(ctx.data["note"], fill=p["text"], color=p["bg0"], px=44, case="any")
        sc.add(ctx.layer(n, W / 2, min(y, ctx.bottom - 40), z=1.0, t_in=ctx.t_word(ctx.data["note"], at=tp + 1.0), enter="pop", role="label"))
    add_motif(ctx, sc)


@archetype("feature_callouts", roles=("features", "details"), cats=("product", "software", "game"), variants=("radial",))
def feature_callouts(ctx: Ctx, sc):
    p = ctx.pal
    feats = list(ctx.data.get("features") or [])[:4]
    sc.bg = make_bg(ctx)
    camera_for(ctx, sc, "push")
    img = ctx.assets.get("product")
    cx, cy = W / 2, (ctx.top + ctx.bottom) / 2
    im = ImageOps.contain(img.convert("RGBA"), (560, 640)) if img is not None else _fabric(ctx, (520, 600))
    sc.add(ctx.layer(Sprite(gfx.with_shadow(im, 26, 0.4), 0.5, 0.5), cx, cy, z=0.9, enter="pop", idle="float", role="image"))
    anchors = [(-1, -1), (1, -1), (-1, 1), (1, 1)]
    for i, (f, (sx, sy)) in enumerate(zip(feats, anchors)):
        ti = ctx.t_word(f, 0.1 + 0.2 * i)
        ex, ey = cx + sx * 140, cy + sy * 160
        lx, ly = cx + sx * 290, cy + sy * 360
        chip = ctx.chip(f, fill=p["accent"] if i % 2 == 0 else p["text"], color=p["ink"] if i % 2 == 0 else p["bg0"], px=50, case="any")
        lx = clamp(lx, SAFE["left"] + chip.w / 2, SAFE["right_low"] - chip.w / 2)
        ly = clamp(ly, ctx.top + 40, ctx.bottom - 40)

        def line_fn(tl, ex=ex, ey=ey, lx=lx, ly=ly):
            q = round(ease_out_cubic(clamp(tl / 0.4)) * 24) / 24
            x0, y0 = min(ex, lx) - 10, min(ey, ly) - 10
            w_, h_ = int(abs(lx - ex) + 20), int(abs(ly - ey) + 20)

            def build():
                im2 = Image.new("RGBA", (w_, h_), (0, 0, 0, 0))
                d = ImageDraw.Draw(im2)
                ax, ay, bx, by = ex - x0, ey - y0, lx - x0, ly - y0
                d.line([(ax, ay), (ax + (bx - ax) * q, ay + (by - ay) * q)], fill=rgba(p["text"]), width=4)
                d.ellipse([ax - 9, ay - 9, ax + 9, ay + 9], fill=rgba(p["accent"]))
                return Sprite(im2, 0.0, 0.0)
            return q, build
        sc.add(DynLayer(line_fn, min(ex, lx) - 10, min(ey, ly) - 10, z=1.0, t_in=ti, enter="none", motion=ctx.motion, role="deco"))
        sc.add(ctx.layer(chip, lx, ly, z=1.05, t_in=ti + 0.3, enter="pop", role="label"))
        sc.cue(ti + 0.3, "pop", 0.5)
    add_motif(ctx, sc)


@archetype("chapter_title", roles=("chapter", "part"), cats=("story", "facts", "movie_review"), variants=("outline",))
def chapter_title(ctx: Ctx, sc):
    p = ctx.pal
    sc.bg = make_bg(ctx)
    camera_for(ctx, sc, "pull")
    num = str(ctx.data.get("number", ctx.idx))
    n = text_sprite(num.zfill(2), ctx.F["hero"], 560, color="#00000000", box=(3000, 3000), max_lines=1, stroke=0.018, stroke_color=p["accent"], role="deco")
    sc.add(ctx.layer(n, W / 2, 620, z=0.7, t_in=0.0, enter="zoom_out", enter_dur=0.6, role="deco"))
    t = ctx.hero(ctx.data.get("title", ctx.beat.get("show", "")), (900, 320), max_lines=2, max_px=180, role="hero")
    sc.add(ctx.layer(t, W / 2, 1000, z=1.0, t_in=0.25, enter="wipe", enter_dir=(1, 0), enter_dur=0.6, role="hero"))
    sc.cue(0.0, "swell", 0.7)
    add_motif(ctx, sc)


# ───────────────────────── helpers ─────────────────────────
def _round(im: Image.Image, r) -> Image.Image:
    im = im.convert("RGBA")
    im.putalpha(gfx.shape_mask(im.width, im.height, "rounded", r) if r > 2 else Image.new("L", im.size, 255))
    return im


def _stars(ctx: Ctx, rating: float, out_of: float, size: int) -> list[Sprite]:
    n = 5
    val = rating / out_of * n
    out = []
    for i in range(n):
        f = clamp(val - i)
        out.append(Sprite(gfx.star(size, f, ctx.pal["accent"], (ctx.pal["muted"] + "55")), 0.5, 0.5))
    return out


def _recolor_stroke(img: Image.Image, color) -> Image.Image:
    out = Image.new("RGBA", img.size, rgba(color))
    out.putalpha(img.getchannel("A"))
    return out


def _seal(ctx: Ctx, size: int, verdict: str, ang: int) -> Image.Image:
    p = ctx.pal
    S = size
    im = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    disc = gfx.card(S - 40, S - 40, fill=p["accent"], kind="circle")
    im.alpha_composite(disc, (20, 20))
    ring_txt = (" ★ " + apply_case(ctx.facts.get("title", "REVIEW"), "upper") + " ★ VERDICT") * 2
    f = font(ctx.F["support"], 34)
    R = S / 2 - 52
    chars = list(ring_txt)[:64]
    for i, ch in enumerate(chars):
        a = math.radians(ang + i * 360 / len(chars))
        g = Image.new("RGBA", (50, 50), (0, 0, 0, 0))
        ImageDraw.Draw(g).text((25, 25), ch, font=f, fill=rgba(p["ink"]), anchor="mm")
        g = g.rotate(-math.degrees(a) - 90, Image.Resampling.BICUBIC)
        im.alpha_composite(g, (int(S / 2 + R * math.cos(a) - 25), int(S / 2 + R * math.sin(a) - 25)))
    inner = text_sprite(apply_case(verdict, "upper"), ctx.F["hero"], None, color=p["ink"], box=(int(S * 0.62), int(S * 0.42)), max_lines=3,
                        max_px=170, min_px=60, role="hero")
    im.alpha_composite(inner.img, (int(S / 2 - inner.w / 2), int(S / 2 - inner.h / 2)))
    return im


def _fabric(ctx: Ctx, size) -> Image.Image:
    """Poster-free premium stand-in: procedural silk/fabric folds in the palette (never a rainbow gradient)."""
    import numpy as np
    w, h = size
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    r = Rng(ctx.dna["seed"] + 5)
    f1, f2, ph = r.uniform(0.006, 0.012), r.uniform(0.01, 0.02), r.uniform(0, 6)
    wave = np.sin(xx * f1 + np.sin(yy * f2 + ph) * 2.2) * 0.5 + 0.5
    wave = wave ** 1.4
    a = np.array(gfx.hex2rgb(mix_hex(ctx.pal["accent"], "#000000", 0.35)), np.float32)
    b = np.array(gfx.hex2rgb(mix_hex(ctx.pal["accent"], "#FFFFFF", 0.35)), np.float32)
    arr = a * (1 - wave[..., None]) + b * wave[..., None]
    arr += np.random.default_rng(3).normal(0, 1.5, arr.shape[:2] + (1,))
    im = Image.fromarray(np.clip(arr, 0, 255).astype("uint8")).convert("RGBA")
    im.putalpha(gfx.shape_mask(w, h, "rounded", 40))
    return im


def choose_archetype(role: str, category: str, used: list[str], rng: Rng, has_poster: bool) -> str:
    """Director fallback when the plan says archetype='auto'. Never repeats the previous archetype; ≤2 uses per video."""
    cands = [n for n, a in ARCH.items() if role in a["roles"] and ("*" in a["cats"] or category in a["cats"])
             and not ("poster" in a["needs"] and not has_poster)]
    cands = [c for c in cands if not used or c != used[-1]] or cands
    cands = [c for c in cands if used.count(c) < 2] or cands
    if not cands:
        cands = [c for c in ("kinetic_line", "quote_kinetic", "fact_bomb") if not used or c != used[-1]]
    return rng.choice(cands)


# ───────────────────────── top-creator layouts (looks: clean / rush / bar / split) ─────────────────────────
SERIES_DEFAULT = {"numbers": "BOX OFFICE DECODE", "decode": "SCENE DECODE", "facts": "FILMY FACTS", "this_week": "IS HAFTE KYA DEKHEIN",
                  "theory": "FAN THEORY"}


def series_label(ctx: Ctx) -> str:
    return str(ctx.assets.get("series") or "SCENE SAMJHO").upper()


def beat_tag(ctx: Ctx) -> str:
    """The ONE short line a clean scene shows (top creators show only the number / name, never the whole sentence)."""
    d = ctx.data
    if d.get("tag"):
        return str(d["tag"])
    if d.get("big"):
        return str(d["big"])
    if d.get("value") is not None:
        v = d["value"]
        dec = int(d.get("decimals", 0))
        num = f"{float(v):,.{dec}f}" if dec else f"{int(round(float(v))):,}"
        return f"{d.get('prefix', '')}{num}{d.get('suffix', '')}".strip()
    if d.get("left") and d.get("right"):
        return f"{d['left'].get('title', '')} vs {d['right'].get('title', '')}"
    if d.get("title"):
        return str(d["title"])
    return ""


def _tag_layer(ctx: Ctx, sc, text, y, style):
    p = ctx.pal
    if not text:
        return
    t_in = ctx.t_word(text, 0.08)
    if style == "news":  # white bold italic over the footage, hard shadow (v1 style: "₹1300 Crores!!!")
        spr = ctx.hero(text, (960, 260), max_lines=2, max_px=170, min_px=72, color="#FFFFFF", case="title", stroke=0.07, role="hero")
        sc.add(ctx.layer(spr, W / 2, y, z=1.0, t_in=t_in, enter="pop", idle="breathe", role="hero"))
    else:  # "label": small caps label on a dark strip at the top (v2 style: "1.71 BILLION HOURS")
        spr = ctx.chip(text, fill="#0B0B0F", color=p["accent"], px=64, case="upper")
        sc.add(ctx.layer(spr, W / 2, y, z=1.0, t_in=t_in, enter="drop", role="label"))
    sc.cue(t_in, "pop", 0.5)


@archetype("footage_clean", roles=("fact", "story", "line", "context", "stat", "compare", "opinion", "list", "cast"),
           variants=("news", "label"))
def footage_clean(ctx: Ctx, sc):
    """Full-bleed, bright footage; only the number / name on screen (plus captions). The look of top creators' shorts."""
    sc.bg = make_bg(ctx)
    camera_for(ctx, sc, "push")
    v = ctx.variant if ctx.variant in ("news", "label") else "news"
    y = 560 if v == "news" else SAFE["top"] + 40
    _tag_layer(ctx, sc, beat_tag(ctx), y, v)


def _host_source(ctx: Ctx, size):
    h = ctx.assets.get("host")
    if not h:
        return None
    from .media import ClipSource
    t0 = float(ctx.beat.get("_t0", 0.0)) + float(h.get("offset", 0.0))
    return ClipSource(h["path"], t0, t0 + ctx.dur + 1.0, ctx.dur + 1.0, size=size)


@archetype("split_top", roles=("fact", "story", "line", "context", "stat", "compare", "opinion", "cast"), variants=("bar", "plain"))
def split_top(ctx: Ctx, sc):
    """Footage band on top (~44 %), the operator's face-cam below (assets.host) — or, without a host, a solid panel with the
    beat's words as kinetic type. A label strip sits on the seam ("1 MIN REVIEW" style)."""
    from .media import SplitBackground, make_source
    p = ctx.pal
    band_h = 840 if ctx.assets.get("host") else 1060  # without a face-cam the word panel needs less room
    panel = gfx.linear_gradient(W, H, [p["bg0"], mix_hex(p["bg0"], p["accent"], 0.18), p["bg0"]], 90, ctx.idx).convert("RGBA")
    band = [(t, make_source(ctx.assets["root"], seg, size=(W, band_h))) for t, seg in (ctx.footage or [])]
    host = _host_source(ctx, (W, H - band_h))
    sc.bg = SplitBackground(band, band_h, panel, host=host)
    camera_for(ctx, sc, "pull")
    if ctx.variant != "plain":
        lab = ctx.chip(series_label(ctx), fill=p["accent"], color=p["ink"], px=54, case="upper")
        sc.add(ctx.layer(lab, W / 2, band_h, z=1.1, t_in=0.0, enter="none", role="label"))
    tag = beat_tag(ctx)
    if tag:
        spr = ctx.hero(tag, (860, 150), max_lines=1, max_px=104, min_px=56, color="#FFFFFF", stroke=0.06, role="hero")
        sc.add(ctx.layer(spr, W / 2, min(band_h - 120, 900), z=1.0, t_in=ctx.t_word(tag, 0.1), enter="pop", role="hero"))
    if host is None:  # words on the lower panel (captions are off for this scene)
        kinetic_stack(ctx, sc, words_or_text(ctx), (SAFE["left"] + 20, band_h + 70, SAFE["right_low"], SAFE["bottom"] - 110),
                      max_words_page=4)


@archetype("host_cam", roles=("hook", "opinion", "verdict", "line", "cta"), variants=("a",))
def host_cam(ctx: Ctx, sc):
    """The operator on camera, full frame (needs assets.host). Falls back to footage_clean when there is no host video."""
    host = _host_source(ctx, (W, H))
    if host is None:
        return footage_clean(ctx, sc)
    from .media import SplitBackground
    sc.bg = SplitBackground([], 0, Image.new("RGBA", (W, H), (0, 0, 0, 255)), host=host)
    camera_for(ctx, sc, "push")
    _tag_layer(ctx, sc, beat_tag(ctx), SAFE["top"] + 120, "news")


ROLE_DEFAULTS = {"hook": "hook_slam", "intro": "poster_hero", "title": "poster_hero", "rating": "rating_meter", "story": "story_panels",
                 "plot": "story_panels", "cast": "cast_spotlight", "performance": "cast_spotlight", "pros_cons": "pros_cons", "pros": "pros_cons",
                 "cons": "pros_cons", "quote": "quote_kinetic", "opinion": "quote_kinetic", "verdict": "verdict_stamp", "cta": "cta_loop",
                 "stat": "stat_counter", "list": "list_reveal", "compare": "split_compare", "fact": "fact_bomb", "timeline": "timeline",
                 "product": "product_hero", "price": "price_tag", "features": "feature_callouts", "chapter": "chapter_title",
                 "line": "kinetic_line"}


# ───────────────────────── editing polish: stickers, light leaks, cut flashes ─────────────────────────
def add_stickers(ctx: Ctx, sc):
    """Pop a 3D emoji sticker on the word it illustrates (Director override: beat.sticker = name | 'none')."""
    from . import stickers as ST
    want = ctx.beat.get("sticker")
    if want == "none":
        return
    if want:
        hit = (want, ctx.t_word(" ".join(ctx.beat.get("hero", [])) or None, 0.15))
    else:
        if ctx.rng.random() > ctx.dna.get("sticker_rate", 0.6):
            return
        hit = ST.match(ctx.words, ctx.hero_set)
    if not hit:
        return
    name, t = hit
    size = 230 if ctx.beat.get("role") != "hook" else 270
    im = ST.load(name, size)
    if im is None:
        return
    spr = Sprite(gfx.with_shadow(im, 14, 0.45, 12), 0.5, 0.5, {"role": "sticker", "text": name})
    t_in = max(0.05, t - 0.05)
    # pick the first free spot (no overlap with any text block at that moment)
    boxes = []
    for ly in sc.layers:
        if getattr(ly, "role", "") in ("hero", "body", "label", "kinetic", "image") and isinstance(ly, Layer):
            b = ly.rest_box(min(ctx.dur - 0.05, t_in + 0.6))
            if b:
                boxes.append(b)
    half = size / 2 + 10
    L, R = SAFE["left"] + half, SAFE["right_low"] - half + 30
    spots = [(R, ctx.top + half), (L, ctx.top + half), (R, (ctx.top + ctx.bottom) / 2), (L, (ctx.top + ctx.bottom) / 2),
             (R, ctx.bottom - half), (L, ctx.bottom - half)]
    if ctx.idx % 2:
        spots = [spots[i ^ 1] for i in range(len(spots))]
    x, y = spots[0]
    for (cx_, cy_) in spots:
        if not any(cx_ + half > b[0] and cx_ - half < b[2] and cy_ + half > b[1] and cy_ - half < b[3] for b in boxes):
            x, y = cx_, cy_
            break
    else:
        return  # no free spot → no sticker (never cover text)
    left = x < W / 2
    sc.add(ctx.layer(spr, x, y, z=1.15, t_in=t_in, t_out=min(ctx.dur - 0.05, t_in + 2.4), enter="pop", exit="pop_out",
                     motion="elastic", idle="float", idle_amp=1.6, rot=-8 if left else 8, role="sticker"))
    sc.cue(t_in, "pop", 0.75)


def _leak_sprite(color, seed):
    import numpy as np
    w, h = int(W * 1.3), int(H * 0.9)
    r = Rng(seed)
    yy, xx = np.mgrid[0:h // 4, 0:w // 4].astype(np.float32)
    a = np.zeros_like(xx)
    for _ in range(3):
        cx, cy, s = r.uniform(0, w / 4), r.uniform(0, h / 4), r.uniform(40, 90)
        a += np.exp(-((xx - cx) ** 2 + (yy - cy) ** 2) / (2 * s * s))
    a = np.clip(a / a.max(), 0, 1) ** 1.4 * 0.55
    m = Image.fromarray((a * 255).astype("uint8")).resize((w, h), Image.Resampling.BICUBIC)
    out = Image.new("RGBA", (w, h), rgba(color, 0))
    out.putalpha(m)
    return Sprite(out, 0.5, 0.5)


def add_grade_fx(ctx: Ctx, sc):
    """On footage cuts: a 2-frame flash + a warm light-leak sweep (film-trailer energy)."""
    warm = mix_hex(ctx.pal["accent"], "#FF8A3D", 0.5)
    for k, tc in enumerate(sc.bg.cut_times()):
        fl = Image.new("RGBA", (W, H), (255, 255, 255, 150))
        sc.add(Layer(Sprite(fl, 0.5, 0.5), W / 2, H / 2, z=1.3, t_in=tc, t_out=tc + 0.03, exit_dur=0.1, enter="none", role="deco"))
        if ctx.rng.random() < 0.6:
            lk = _leak_sprite(warm, ctx.dna["seed"] + ctx.idx * 7 + k)
            sc.add(Layer(lk, W * 0.2, H * 0.4, z=1.25, t_in=tc - 0.05, t_out=tc + 0.45, exit_dur=0.3, enter="slide", enter_dir=(-1, 0),
                         travel=900, motion="smooth", role="deco"))
