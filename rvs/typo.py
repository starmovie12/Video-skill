"""typo.py — font registry, mixed-script (Latin + Devanagari) text layout, fit-to-box hero typography, stroke/shadow/glow sprites.
Devanagari is shaped by Pillow's RAQM layout (HarfBuzz) — every word is drawn as a whole cluster, never split into letters."""
from __future__ import annotations

import re
from functools import lru_cache

from PIL import Image, ImageDraw, ImageFilter, ImageFont, features

from .core import ASSETS, RvsError, hex2rgb, read_json, rgba

FONT_DIR = ASSETS / "fonts"
REG = read_json(FONT_DIR / "fonts.json")["fonts"]
RAQM = features.check("raqm")
DEVA = re.compile(r"[ऀ-ॿ]")
LAYOUT = ImageFont.Layout.RAQM if RAQM else ImageFont.Layout.BASIC


def has_deva(s: str) -> bool:
    return bool(DEVA.search(s or ""))


@lru_cache(maxsize=512)
def font(fid: str, px: int) -> ImageFont.FreeTypeFont:
    spec = REG[fid]
    f = ImageFont.truetype(str(FONT_DIR / spec["file"]), int(px), layout_engine=LAYOUT)
    if "wght" in spec:
        try:
            f.set_variation_by_axes([spec["wght"]])
        except (OSError, ValueError):
            pass
    return f


@lru_cache(maxsize=64)
def cmap(fid: str) -> frozenset:
    try:
        from fontTools.ttLib import TTFont
        return frozenset(TTFont(str(FONT_DIR / REG[fid]["file"]), lazy=True).getBestCmap().keys())
    except Exception:  # fontTools missing → trust the registry's script tags
        return frozenset()


def supports(fid: str, text: str) -> bool:
    cm = cmap(fid)
    if cm:
        return all(ord(ch) in cm for ch in text if not ch.isspace())
    return "deva" in REG[fid]["scripts"] or not has_deva(text)


def apply_case(text: str, case: str) -> str:
    if case == "upper":
        return text.upper()
    if case == "title":
        return " ".join(w[:1].upper() + w[1:] if w[:1].isalpha() else w for w in text.split(" "))
    return text


class Sprite:
    """An RGBA image + anchor + metadata (role, font px, text) used by QA for size / safe-zone checks."""
    __slots__ = ("img", "ax", "ay", "meta")

    def __init__(self, img: Image.Image, ax=0.5, ay=0.5, meta=None):
        self.img, self.ax, self.ay, self.meta = img, ax, ay, meta or {}

    @property
    def w(self):
        return self.img.width

    @property
    def h(self):
        return self.img.height


FALLBACKS = ("poppins-blk", "mukta-xb", "baloo")


def _word_font(word: str, fid: str, deva_fid: str, px: int):
    """Per-word font fallback: Devanagari → the DNA's Devanagari font; any missing glyph (₹, ★ …) → first font that has it."""
    if supports(fid, word):
        return font(fid, px), fid
    for f in (deva_fid,) + FALLBACKS:
        if supports(f, word):
            return font(f, int(px * (0.86 if has_deva(word) else 0.92))), f
    return font(deva_fid, int(px * 0.86)), deva_fid


def _wlen(f, s):
    return f.getlength(s)


def layout_lines(text: str, fid: str, deva_fid: str, px: int, max_w: int, max_lines: int = 3, tracking: float = 0.0):
    """Greedy word wrap with per-word font fallback. Returns (lines=[[(word, font, w)]], line widths, line height)."""
    words = [w for w in text.split() if w]
    sp = font(fid, px).getlength(" ") * 0.9
    lines, cur, cur_w = [], [], 0.0
    for w in words:
        f, _ = _word_font(w, fid, deva_fid, px)
        ww = _wlen(f, w) + tracking * px * max(0, len(w) - 1)
        add = ww if not cur else sp + ww
        if cur and cur_w + add > max_w:
            lines.append(cur)
            cur, cur_w = [(w, f, ww)], ww
        else:
            cur.append((w, f, ww))
            cur_w += add
    if cur:
        lines.append(cur)
    widths = [sum(x[2] for x in ln) + sp * (len(ln) - 1) for ln in lines]
    asc, desc = font(fid, px).getmetrics()
    return lines, widths, asc + desc, sp, len(lines) <= max_lines and all(w <= max_w + 1 for w in widths)


def fit_px(text, fid, deva_fid, max_w, max_h, max_lines=3, lo=20, hi=420, line_gap=0.92, tracking=0.0) -> int:
    """Largest font size whose wrapped layout fits inside max_w × max_h (binary search) — hero type fills its box."""
    best = lo
    while lo <= hi:
        mid = (lo + hi) // 2
        lines, widths, lh, _, ok = layout_lines(text, fid, deva_fid, mid, max_w, max_lines, tracking)
        total_h = lh * (1 + (len(lines) - 1) * line_gap)
        if ok and total_h <= max_h:
            best, lo = mid, mid + 1
        else:
            hi = mid - 1
    return best


def text_sprite(text: str, fid: str, px: int | None = None, *, deva_fid: str = "mukta-xb", color="#FFFFFF", box=(900, 400),
                max_lines=3, min_px=40, max_px=400, align="center", case="any", stroke=0.0, stroke_color="#000000",
                shadow=None, glow=None, gradient=None, line_gap=0.92, tracking=0.0, role="text", highlight=None,
                highlight_color=None) -> Sprite:
    """Render text to an RGBA sprite. px=None → fit to box. stroke is a fraction of px. shadow=(dx,dy,blur,alpha,'#hex').
    glow=(radius, alpha, '#hex'). gradient=('#top','#bottom'). highlight = set of lowercase words drawn in highlight_color."""
    text = apply_case(" ".join(str(text).split()), case)
    if not text:
        raise RvsError("EMPTY_TEXT", f"empty text for role={role}")
    if px is None:
        px = fit_px(text, fid, deva_fid, box[0], box[1], max_lines, lo=min_px, hi=max_px, line_gap=line_gap, tracking=tracking)
    lines, widths, lh, sp, ok = layout_lines(text, fid, deva_fid, px, box[0], max_lines, tracking)
    sw = int(round(stroke * px))
    pad = sw + 8 + (int(shadow[2] * 2 + abs(shadow[0]) + abs(shadow[1])) if shadow else 0) + (int(glow[0] * 2) if glow else 0)
    step = int(lh * line_gap)
    tw = int(max(widths)) + 2 * pad
    th = int(step * (len(lines) - 1) + lh) + 2 * pad
    mask = Image.new("L", (tw, th), 0)
    smask = Image.new("L", (tw, th), 0) if sw else None
    hl_mask = Image.new("L", (tw, th), 0) if highlight else None
    dm, ds = ImageDraw.Draw(mask), (ImageDraw.Draw(smask) if sw else None)
    dh = ImageDraw.Draw(hl_mask) if highlight else None
    asc = font(fid, px).getmetrics()[0]
    for i, (ln, lw) in enumerate(zip(lines, widths)):
        x = pad + (0 if align == "left" else (tw - 2 * pad - lw) if align == "right" else (tw - 2 * pad - lw) / 2)
        base_y = pad + i * step + asc
        for w, f, ww in ln:
            fa = f.getmetrics()[0]
            y = base_y - fa
            target = dh if (highlight and re.sub(r"\W", "", w.lower()) in highlight) else dm
            if tracking and not has_deva(w):
                cx = x
                for ch in w:
                    target.text((cx, y), ch, font=f, fill=255)
                    if ds:
                        ds.text((cx, y), ch, font=f, fill=255, stroke_width=sw, stroke_fill=255)
                    cx += f.getlength(ch) + tracking * px
            else:
                target.text((x, y), w, font=f, fill=255)
                if ds:
                    ds.text((x, y), w, font=f, fill=255, stroke_width=sw, stroke_fill=255)
            x += ww + sp
    out = Image.new("RGBA", (tw, th), (0, 0, 0, 0))
    full = mask if not hl_mask else Image.composite(Image.new("L", (tw, th), 255), mask, hl_mask)
    if glow:
        g = (smask or full).filter(ImageFilter.GaussianBlur(glow[0]))
        layer = Image.new("RGBA", (tw, th), rgba(glow[2], 0))
        layer.putalpha(g.point(lambda v: int(min(255, v * glow[1] * 1.6))))
        out = Image.alpha_composite(out, layer)
    if shadow:
        dx, dy, blur, alpha, col = shadow
        a = (smask or full).filter(ImageFilter.GaussianBlur(blur)).point(lambda v: int(v * alpha))
        layer = Image.new("RGBA", (tw, th), rgba(col, 0))
        layer.putalpha(a)
        tmp = Image.new("RGBA", (tw, th), (0, 0, 0, 0))
        tmp.paste(layer, (int(dx), int(dy)))
        out = Image.alpha_composite(out, tmp)
    if smask:
        layer = Image.new("RGBA", (tw, th), rgba(stroke_color))
        layer.putalpha(smask)
        out = Image.alpha_composite(out, layer)
    if gradient:
        fill = vertical_gradient(tw, th, gradient[0], gradient[1])
    else:
        fill = Image.new("RGBA", (tw, th), rgba(color))
    fill.putalpha(mask)
    out = Image.alpha_composite(out, fill)
    if hl_mask:
        hl = Image.new("RGBA", (tw, th), rgba(highlight_color or "#FFD400"))
        hl.putalpha(hl_mask)
        out = Image.alpha_composite(out, hl)
    return Sprite(out, 0.5, 0.5, {"role": role, "px": px, "text": text, "fits": ok, "lines": len(lines), "pad": pad})


def vertical_gradient(w, h, c1, c2) -> Image.Image:
    import numpy as np
    a, b = (np.array(hex2rgb(c), dtype=np.float32) for c in (c1, c2))
    t = np.linspace(0, 1, h, dtype=np.float32)[:, None, None]
    arr = a * (1 - t) + b * t
    arr = np.broadcast_to(arr, (h, w, 3)) + np.random.default_rng(3).uniform(-0.6, 0.6, (h, w, 3))
    rgb = Image.fromarray(np.clip(arr, 0, 255).astype("uint8"), "RGB").convert("RGBA")
    return rgb


def word_sprites(words: list[str], fid: str, px: int, deva_fid: str, color, stroke=0.0, stroke_color="#000", shadow=None,
                 case="any") -> list[Sprite]:
    """One sprite per word, same baseline box height (for kinetic type and captions)."""
    out = []
    for w in words:
        out.append(text_sprite(w, fid, px, deva_fid=deva_fid, color=color, box=(4000, 4000), max_lines=1, stroke=stroke,
                               stroke_color=stroke_color, shadow=shadow, case=case, role="word"))
    return out
