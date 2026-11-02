"""gfx.py — procedural graphics: dithered gradients (no banding), mesh gradients, real frosted glass, anti-aliased shapes,
stroke-draw icons, rings, stars, poster perspective tilt, duotone/halftone, light rays, bokeh, film perforations, grunge stamps."""
from __future__ import annotations

import math

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageEnhance, ImageFilter, ImageOps

from .core import hex2rgb, mix, rgba

SS = 3  # supersampling factor for AA shapes


def _dither(h, w, seed=0, amp=1.2):
    return np.random.default_rng(seed).uniform(-amp, amp, (h, w, 1)).astype(np.float32)


def to_img(arr: np.ndarray, mode="RGB") -> Image.Image:
    return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8), mode)


def linear_gradient(w, h, stops, angle=90.0, seed=0) -> Image.Image:
    """stops: ['#hex', ...] evenly spaced. angle 90 = top→bottom. Float maths + dither → no 8-bit banding."""
    cols = np.array([hex2rgb(c) for c in stops], dtype=np.float32)
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    a = math.radians(angle)
    p = (xx - w / 2) * math.cos(a - math.pi / 2) * -1 + (yy - h / 2) * math.sin(a)
    p = (p - p.min()) / max(1e-6, (p.max() - p.min()))
    seg = p * (len(cols) - 1)
    i = np.clip(seg.astype(int), 0, len(cols) - 2)
    f = (seg - i)[..., None]
    arr = cols[i] * (1 - f) + cols[i + 1] * f
    return to_img(arr + _dither(h, w, seed))


def radial_gradient(w, h, cx, cy, r, c_in, c_out, power=1.6, seed=0) -> Image.Image:
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    d = np.clip(np.hypot(xx - cx, yy - cy) / r, 0, 1) ** power
    a, b = (np.array(hex2rgb(c), dtype=np.float32) for c in (c_in, c_out))
    return to_img(a * (1 - d[..., None]) + b * d[..., None] + _dither(h, w, seed))


def mesh_gradient(w, h, colors: list[str], seed=0, blobs=5, softness=0.55) -> Image.Image:
    """Smooth multi-blob 'gradient mesh' computed at low res in OKLab-ish linear space, upscaled, then dithered."""
    rng = np.random.default_rng(seed)
    lw, lh = 90, 160
    yy, xx = np.mgrid[0:lh, 0:lw].astype(np.float32)
    acc = np.zeros((lh, lw, 3), np.float32)
    wsum = np.zeros((lh, lw, 1), np.float32)
    for i in range(blobs):
        c = np.array(hex2rgb(colors[i % len(colors)]), np.float32)
        cx, cy = rng.uniform(-0.1, 1.1) * lw, rng.uniform(-0.1, 1.1) * lh
        s = rng.uniform(0.35, 0.8) * lw * softness * 2
        wgt = np.exp(-((xx - cx) ** 2 + (yy - cy) ** 2) / (2 * s * s))[..., None] + 1e-4
        acc += c * wgt
        wsum += wgt
    small = Image.fromarray(np.clip(acc / wsum, 0, 255).astype(np.uint8))
    big = np.asarray(small.resize((w, h), Image.Resampling.BICUBIC), np.float32)
    return to_img(big + _dither(h, w, seed + 1, 1.5))


def value_noise(w, h, scale=64, octaves=4, seed=0) -> np.ndarray:
    """fBm value noise 0..1 (float32)."""
    rng = np.random.default_rng(seed)
    out = np.zeros((h, w), np.float32)
    amp, tot = 1.0, 0.0
    for o in range(octaves):
        s = max(2, int(scale / (2 ** o)))
        small = rng.random((h // s + 2, w // s + 2)).astype(np.float32)
        layer = np.asarray(Image.fromarray((small * 255).astype(np.uint8)).resize((w + s, h + s), Image.Resampling.BICUBIC),
                           np.float32)[:h, :w] / 255
        out += layer * amp
        tot += amp
        amp *= 0.5
    return out / tot


def shape_mask(w, h, kind="rounded", r=None) -> Image.Image:
    """Anti-aliased card masks: rounded | pill | sharp | cut (chamfer) | ticket | arch | circle."""
    r = int(min(w, h) * 0.08) if r is None else r
    m = Image.new("L", (w * SS, h * SS), 0)
    d = ImageDraw.Draw(m)
    W_, H_, R = w * SS - 1, h * SS - 1, r * SS
    if kind == "pill":
        d.rounded_rectangle([0, 0, W_, H_], radius=min(W_, H_) // 2, fill=255)
    elif kind == "sharp":
        d.rectangle([0, 0, W_, H_], fill=255)
    elif kind == "cut":
        c = R * 1.4
        d.polygon([(c, 0), (W_, 0), (W_, H_ - c), (W_ - c, H_), (0, H_), (0, c)], fill=255)
    elif kind == "ticket":
        d.rounded_rectangle([0, 0, W_, H_], radius=R // 2, fill=255)
        for cy in (H_ // 2,):
            d.ellipse([-R, cy - R, R, cy + R], fill=0)
            d.ellipse([W_ - R, cy - R, W_ + R, cy + R], fill=0)
    elif kind == "arch":
        d.rectangle([0, W_ // 2, W_, H_], fill=255)
        d.ellipse([0, 0, W_, W_], fill=255)
    elif kind == "circle":
        d.ellipse([0, 0, W_, H_], fill=255)
    else:
        d.rounded_rectangle([0, 0, W_, H_], radius=R, fill=255)
    return m.resize((w, h), Image.Resampling.LANCZOS)


def card(w, h, fill="#101018", alpha=235, kind="rounded", r=None, border=None, border_w=3, gradient=None) -> Image.Image:
    m = shape_mask(w, h, kind, r)
    base = linear_gradient(w, h, gradient, 90).convert("RGBA") if gradient else Image.new("RGBA", (w, h), rgba(fill))
    base.putalpha(m.point(lambda v: v * alpha // 255))
    if border:
        inner = shape_mask(max(1, w - 2 * border_w), max(1, h - 2 * border_w), kind, (r or int(min(w, h) * 0.08)) - border_w)
        ring = m.copy()
        hole = Image.new("L", (w, h), 0)
        hole.paste(inner, (border_w, border_w))
        ring = ImageChops.subtract(ring, hole)
        bl = Image.new("RGBA", (w, h), rgba(border))
        bl.putalpha(ring)
        base = Image.alpha_composite(base, bl)
    return base


def frosted_glass(bg: Image.Image, box, kind="rounded", r=None, tint="#FFFFFF", tint_alpha=0.10, blur=28, border_alpha=0.35,
                  dark=False) -> Image.Image:
    """REAL glassmorphism: blur the actual background region behind the card, tint lightly, add specular edge + noise."""
    x0, y0, x1, y1 = [int(v) for v in box]
    w, h = x1 - x0, y1 - y0
    region = bg.convert("RGB").crop((x0 - 40, y0 - 40, x1 + 40, y1 + 40)).filter(ImageFilter.GaussianBlur(blur)).crop((40, 40, 40 + w, 40 + h))
    region = ImageEnhance.Brightness(region).enhance(0.72 if dark else 1.08)
    region = ImageEnhance.Color(region).enhance(1.15)
    arr = np.asarray(region, np.float32)
    t = np.array(hex2rgb(tint), np.float32)
    arr = arr * (1 - tint_alpha) + t * tint_alpha
    arr += np.random.default_rng(5).normal(0, 2.2, arr.shape[:2] + (1,)).astype(np.float32)
    yy = np.linspace(0, 1, h, dtype=np.float32)[:, None, None]
    arr = arr + (1 - yy) * 14  # top sheen
    out = to_img(arr).convert("RGBA")
    m = shape_mask(w, h, kind, r)
    out.putalpha(m)
    # specular rim
    rim = ImageChops.subtract(m, m.filter(ImageFilter.MinFilter(5)))
    hl = Image.new("RGBA", (w, h), (255, 255, 255, 0))
    hl.putalpha(rim.point(lambda v: int(v * border_alpha)))
    return Image.alpha_composite(out, hl)


def soft_shadow(src: Image.Image, blur=24, alpha=0.55, color="#000000", spread=0) -> Image.Image:
    a = src.getchannel("A")
    if spread:
        a = a.filter(ImageFilter.MaxFilter(spread * 2 + 1))
    pad = blur * 3
    big = Image.new("L", (src.width + 2 * pad, src.height + 2 * pad), 0)
    big.paste(a, (pad, pad))
    big = big.filter(ImageFilter.GaussianBlur(blur)).point(lambda v: int(v * alpha))
    out = Image.new("RGBA", big.size, rgba(color, 0))
    out.putalpha(big)
    return out


def with_shadow(img: Image.Image, blur=26, alpha=0.6, dy=18, color="#000000") -> Image.Image:
    sh = soft_shadow(img, blur, alpha, color)
    pad = blur * 3
    out = Image.new("RGBA", sh.size, (0, 0, 0, 0))
    out.alpha_composite(sh, (0, min(dy, pad)))
    out.alpha_composite(img, (pad, pad))
    return out


def ring(size, thickness, frac, color, track=None, start=-90, cap=True) -> Image.Image:
    S = size * SS
    im = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    t = thickness * SS
    box = [t // 2, t // 2, S - t // 2, S - t // 2]
    if track:
        d.arc(box, 0, 360, fill=rgba(track), width=t)
    if frac > 0.001:
        end = start + 360 * min(1.0, frac)
        d.arc(box, start, end, fill=rgba(color), width=t)
        if cap:
            for ang in (start, end):
                cx = S / 2 + (S / 2 - t / 2) * math.cos(math.radians(ang))
                cy = S / 2 + (S / 2 - t / 2) * math.sin(math.radians(ang))
                d.ellipse([cx - t / 2, cy - t / 2, cx + t / 2, cy + t / 2], fill=rgba(color))
    return im.resize((size, size), Image.Resampling.LANCZOS)


def star(size, fill_frac=1.0, color="#FFC83D", empty="#FFFFFF33", points=5, inner=0.45) -> Image.Image:
    S = size * SS
    pts = []
    for i in range(points * 2):
        r = S / 2 * (1 if i % 2 == 0 else inner)
        a = -math.pi / 2 + i * math.pi / points
        pts.append((S / 2 + r * math.cos(a), S / 2 + r * math.sin(a)))
    m = Image.new("L", (S, S), 0)
    ImageDraw.Draw(m).polygon(pts, fill=255)
    base = Image.new("RGBA", (S, S), rgba(empty[:7], int(empty[7:9], 16) if len(empty) > 7 else 70))
    base.putalpha(m.point(lambda v: v * (int(empty[7:9], 16) if len(empty) > 7 else 70) // 255))
    if fill_frac > 0:
        f = Image.new("RGBA", (S, S), rgba(color))
        fm = m.copy()
        ImageDraw.Draw(fm).rectangle([int(S * fill_frac), 0, S, S], fill=0)
        f.putalpha(fm)
        base = Image.alpha_composite(base, f)
    return base.resize((size, size), Image.Resampling.LANCZOS)


def polyline_draw(size, pts, progress, color, width) -> Image.Image:
    """Stroke draw-on: draw the first `progress` fraction of a polyline (pts in 0..1 coords)."""
    S = size * SS
    im = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    if progress <= 0:
        return im.resize((size, size))
    P = [(x * S, y * S) for x, y in pts]
    segs = [math.dist(P[i], P[i + 1]) for i in range(len(P) - 1)]
    need = sum(segs) * min(1.0, progress)
    out = [P[0]]
    for i, L in enumerate(segs):
        if need >= L:
            out.append(P[i + 1])
            need -= L
        else:
            f = need / L if L else 0
            out.append((P[i][0] + (P[i + 1][0] - P[i][0]) * f, P[i][1] + (P[i + 1][1] - P[i][1]) * f))
            break
    d = ImageDraw.Draw(im)
    d.line(out, fill=rgba(color), width=int(width * SS), joint="curve")
    r = width * SS / 2
    for p in (out[0], out[-1]):
        d.ellipse([p[0] - r, p[1] - r, p[0] + r, p[1] + r], fill=rgba(color))
    return im.resize((size, size), Image.Resampling.LANCZOS)


CHECK = [(0.2, 0.55), (0.42, 0.76), (0.82, 0.28)]
CROSS_A = [(0.25, 0.25), (0.75, 0.75)]
CROSS_B = [(0.75, 0.25), (0.25, 0.75)]


def icon(kind, size, progress, color, width=None) -> Image.Image:
    width = width or max(6, size // 9)
    if kind == "check":
        return polyline_draw(size, CHECK, progress, color, width)
    a = polyline_draw(size, CROSS_A, min(1, progress * 2), color, width)
    b = polyline_draw(size, CROSS_B, max(0, progress * 2 - 1), color, width)
    return Image.alpha_composite(a, b)


def perspective(img: Image.Image, tilt_y=0.0, tilt_x=0.0) -> Image.Image:
    """Fake 3D card tilt (2x supersampled). tilt_y>0 → right edge recedes; tilt_x>0 → top edge recedes. |tilt| ≤ 1."""
    w, h = img.size
    W2, H2 = w * 2, h * 2
    ky, kx = tilt_y, tilt_x
    dyR, dyL = H2 * 0.10 * max(0, ky), H2 * 0.10 * max(0, -ky)
    dxR, dxL = W2 * 0.06 * max(0, ky), W2 * 0.06 * max(0, -ky)
    dxT, dxB = W2 * 0.08 * max(0, kx), W2 * 0.08 * max(0, -kx)
    dyT, dyB = H2 * 0.04 * max(0, kx), H2 * 0.04 * max(0, -kx)
    quad = [(dxL + dxT, dyL + dyT), (W2 - dxR - dxT, dyR + dyT), (W2 - dxR - dxB, H2 - dyR - dyB), (dxL + dxB, H2 - dyL - dyB)]
    c = _persp_coeffs(quad, [(0, 0), (W2, 0), (W2, H2), (0, H2)])
    src = img.convert("RGBA").resize((W2, H2), Image.Resampling.BICUBIC)
    out = src.transform((W2, H2), Image.Transform.PERSPECTIVE, c, Image.Resampling.BICUBIC)
    return out.resize((w, h), Image.Resampling.LANCZOS)


def _persp_coeffs(dst, src):
    A, B = [], []
    for (x, y), (u, v) in zip(dst, src):
        A.append([x, y, 1, 0, 0, 0, -u * x, -u * y])
        A.append([0, 0, 0, x, y, 1, -v * x, -v * y])
        B += [u, v]
    return np.linalg.solve(np.array(A, float), np.array(B, float)).tolist()


def reflection(img: Image.Image, height=0.28, alpha=0.32) -> Image.Image:
    w, h = img.size
    rh = int(h * height)
    ref = ImageOps.flip(img).crop((0, 0, w, rh)).filter(ImageFilter.GaussianBlur(3))
    grad = Image.linear_gradient("L").resize((w, rh)).point(lambda v: int((255 - v) * alpha))
    a = ImageChops.multiply(ref.getchannel("A"), grad)
    ref.putalpha(a)
    out = Image.new("RGBA", (w, h + rh + 6), (0, 0, 0, 0))
    out.alpha_composite(img, (0, 0))
    out.alpha_composite(ref, (0, h + 6))
    return out


def duotone(img: Image.Image, dark: str, light: str, contrast=1.2) -> Image.Image:
    g = ImageEnhance.Contrast(img.convert("L")).enhance(contrast)
    return ImageOps.colorize(g, dark, light).convert("RGB")


def halftone(img: Image.Image, cell=14, ink="#000000", paper="#F2E8D5", angle=22) -> Image.Image:
    g = img.convert("L").rotate(angle, expand=True, fillcolor=255)
    sw, sh = g.width // cell, g.height // cell
    small = np.asarray(g.resize((sw, sh), Image.Resampling.BOX), np.float32) / 255
    out = Image.new("L", (sw * cell * SS, sh * cell * SS), 255)
    d = ImageDraw.Draw(out)
    for j in range(sh):
        for i in range(sw):
            r = (1 - small[j, i]) ** 0.8 * cell * SS * 0.62
            if r > 0.6:
                cx, cy = (i + 0.5) * cell * SS, (j + 0.5) * cell * SS
                d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=0)
    out = out.resize((sw * cell, sh * cell), Image.Resampling.LANCZOS).rotate(-angle, expand=False, fillcolor=255)
    ox, oy = (out.width - img.width) // 2, (out.height - img.height) // 2
    out = out.crop((ox, oy, ox + img.width, oy + img.height))
    return ImageOps.colorize(out, ink, paper).convert("RGB")


def light_rays(w, h, origin, color, n=9, spread=70, alpha=0.18, seed=0) -> Image.Image:
    rng = np.random.default_rng(seed)
    m = Image.new("L", (w // 2, h // 2), 0)
    d = ImageDraw.Draw(m)
    ox, oy = origin[0] / 2, origin[1] / 2
    base = 90.0
    for i in range(n):
        a0 = math.radians(base - spread / 2 + spread * (i + rng.uniform(0, 0.5)) / n)
        da = math.radians(rng.uniform(1.0, 3.2))
        L = max(w, h) * 1.4
        d.polygon([(ox, oy), (ox + L * math.cos(a0), oy + L * math.sin(a0)), (ox + L * math.cos(a0 + da), oy + L * math.sin(a0 + da))],
                  fill=int(255 * rng.uniform(0.5, 1)))
    m = m.filter(ImageFilter.GaussianBlur(10)).resize((w, h), Image.Resampling.BICUBIC)
    out = Image.new("RGBA", (w, h), rgba(color, 0))
    out.putalpha(m.point(lambda v: int(v * alpha)))
    return out


def bokeh(radius, color, alpha=0.5, ring_w=0.0) -> Image.Image:
    S = radius * 2 + 8
    m = Image.new("L", (S, S), 0)
    d = ImageDraw.Draw(m)
    d.ellipse([4, 4, S - 4, S - 4], fill=int(255 * alpha))
    m = m.filter(ImageFilter.GaussianBlur(max(1, radius * 0.18)))
    out = Image.new("RGBA", (S, S), rgba(color, 0))
    out.putalpha(m)
    return out


def glow_dot(radius, color, alpha=0.9) -> Image.Image:
    return _glow(radius, color, alpha)


def _glow(radius, color, alpha):
    S = radius * 2
    yy, xx = np.mgrid[0:S, 0:S].astype(np.float32)
    d = np.clip(1 - np.hypot(xx - radius, yy - radius) / radius, 0, 1) ** 2.2
    out = Image.new("RGBA", (S, S), rgba(color, 0))
    out.putalpha(Image.fromarray((d * 255 * alpha).astype(np.uint8)))
    return out


def film_perfs(length, thickness=70, color="#0B0B0B", hole="#EDE6D6", vertical=True, hole_alpha=200) -> Image.Image:
    w, h = (thickness, length) if vertical else (length, thickness)
    im = Image.new("RGBA", (w, h), rgba(color, 235))
    d = ImageDraw.Draw(im)
    step, hw = int(thickness * 0.75), int(thickness * 0.38)
    for p in range(step // 2, length, step):
        if vertical:
            d.rounded_rectangle([w // 2 - hw // 2, p, w // 2 + hw // 2, p + int(hw * 0.75)], radius=4, fill=rgba(hole, hole_alpha))
        else:
            d.rounded_rectangle([p, h // 2 - hw // 2, p + int(hw * 0.75), h // 2 + hw // 2], radius=4, fill=rgba(hole, hole_alpha))
    return im


def grunge_mask(w, h, seed=0, amount=0.35) -> Image.Image:
    n = value_noise(w, h, scale=18, octaves=3, seed=seed)
    return Image.fromarray(((n > amount) * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(0.7))


def stamp(text_sprite_img: Image.Image, color="#E63946", pad=34, border=10, seed=1, kind="rounded") -> Image.Image:
    w, h = text_sprite_img.width + pad * 2, text_sprite_img.height + pad * 2
    frame = card(w, h, fill="#000000", alpha=0, kind=kind, r=18, border=color, border_w=border)
    t = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    t.alpha_composite(text_sprite_img, (pad, pad))
    col = Image.new("RGBA", (w, h), rgba(color))
    col.putalpha(t.getchannel("A"))
    out = Image.alpha_composite(frame, col)
    g = grunge_mask(w, h, seed, 0.22)
    out.putalpha(ImageChops.multiply(out.getchannel("A"), g))
    return out


def brush_swipe(w, h, color, seed=0, alpha=230) -> Image.Image:
    """Marker / highlighter stroke with ragged ends (for highlight captions & underlines)."""
    rng = np.random.default_rng(seed)
    S = SS
    m = Image.new("L", (w * S, h * S), 0)
    d = ImageDraw.Draw(m)
    pts_top = [(x, h * S * (0.12 + rng.uniform(-0.05, 0.05))) for x in np.linspace(0, w * S, 9)]
    pts_bot = [(x, h * S * (0.88 + rng.uniform(-0.05, 0.05))) for x in np.linspace(w * S, 0, 9)]
    d.polygon(pts_top + pts_bot, fill=alpha)
    m = m.resize((w, h), Image.Resampling.LANCZOS)
    out = Image.new("RGBA", (w, h), rgba(color, 0))
    out.putalpha(m)
    return out


def vignette(w, h, strength=0.45) -> Image.Image:
    yy, xx = np.mgrid[0:h // 4, 0:w // 4].astype(np.float32)
    d = np.hypot((xx - w / 8) / (w / 8), (yy - h / 8) / (h / 8)) / 1.41
    a = (np.clip(d, 0, 1) ** 2.0) * 255 * strength
    m = Image.fromarray(a.astype(np.uint8)).resize((w, h), Image.Resampling.BICUBIC)
    out = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    out.putalpha(m)
    return out


def cover_fit(img: Image.Image, w, h, focus=(0.5, 0.35)) -> Image.Image:
    return ImageOps.fit(img.convert("RGB"), (w, h), Image.Resampling.LANCZOS, centering=focus)


def crop_norm(img: Image.Image, box) -> Image.Image:
    x0, y0, x1, y1 = box
    W_, H_ = img.size
    return img.crop((int(x0 * W_), int(y0 * H_), int(x1 * W_), int(y1 * H_)))


def saliency_boxes(img: Image.Image, n=3, aspect=1.0, frac=0.42) -> list[tuple]:
    """Pick n interesting, non-overlapping crop boxes (normalized) by edge density × colourfulness. Cheap stand-in for a face
    detector — the Director can always pass exact 'focus' boxes after looking at the poster."""
    g = img.convert("RGB").resize((120, int(120 * img.height / img.width)))
    arr = np.asarray(g, np.float32)
    edges = np.asarray(g.convert("L").filter(ImageFilter.FIND_EDGES), np.float32)
    sat = arr.max(-1) - arr.min(-1)
    score = edges * 0.7 + sat * 0.3
    H_, W_ = score.shape
    bw = int(W_ * frac)
    bh = int(min(H_, bw / aspect))
    boxes = []
    ii = np.cumsum(np.cumsum(score, 0), 1)

    def rs(x, y):
        return ii[y + bh - 1, x + bw - 1] - (ii[y - 1, x + bw - 1] if y else 0) - (ii[y + bh - 1, x - 1] if x else 0) + (ii[y - 1, x - 1] if x and y else 0)
    taken = np.zeros_like(score, bool)
    for _ in range(n):
        best, bxy = -1, (0, 0)
        for y in range(0, H_ - bh + 1, 3):
            for x in range(0, W_ - bw + 1, 3):
                if taken[y + bh // 2, x + bw // 2]:
                    continue
                s = rs(x, y)
                if s > best:
                    best, bxy = s, (x, y)
        x, y = bxy
        taken[max(0, y - bh // 3):y + bh + bh // 3, max(0, x - bw // 3):x + bw + bw // 3] = True
        boxes.append((x / W_, y / H_, (x + bw) / W_, (y + bh) / H_))
    return boxes


def paper_texture(w, h, base="#F1E9DA", seed=0) -> Image.Image:
    n = value_noise(w // 2, h // 2, scale=6, octaves=3, seed=seed)
    fib = value_noise(w // 2, h // 2, scale=40, octaves=2, seed=seed + 3)
    b = np.array(hex2rgb(base), np.float32)
    arr = b * (0.93 + 0.07 * n[..., None]) * (0.97 + 0.03 * fib[..., None])
    return to_img(arr).resize((w, h), Image.Resampling.BICUBIC)


def grid_lines(w, h, step=90, color="#FFFFFF", alpha=22, width=1) -> Image.Image:
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    for x in range(0, w, step):
        d.line([(x, 0), (x, h)], fill=rgba(color, alpha), width=width)
    for y in range(0, h, step):
        d.line([(0, y), (w, y)], fill=rgba(color, alpha), width=width)
    return im


def scanlines(w, h, gap=4, alpha=26) -> Image.Image:
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    for y in range(0, h, gap):
        d.line([(0, y), (w, y)], fill=(0, 0, 0, alpha))
    return im


def tint(img: Image.Image, color, amount=0.3) -> Image.Image:
    c = Image.new("RGB", img.size, hex2rgb(color) if isinstance(color, str) else color)
    return Image.blend(img.convert("RGB"), c, amount)


def mixhex(a, b, t):
    from .core import rgb2hex
    return rgb2hex(mix(a, b, t))
