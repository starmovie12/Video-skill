"""captions.py — big, word-synced, animated captions built from the SPOKEN words (exact TTS word timings).
7 styles chosen by Style DNA: pill | pop_color | box_line | highlighter | glow | outline_bold | underline. Always inside safe zones."""
from __future__ import annotations

import re

from PIL import Image

from . import gfx
from .core import clamp, ease_out_cubic, mix, rgb2hex, spring
from .engine import alpha_mult, blit
from .typo import apply_case, text_sprite

CAP_X0, CAP_X1 = 70, 940          # right margin keeps clear of Reels buttons
CAP_Y = {"low": 1330, "mid_low": 1240}
PUNCT_BREAK = re.compile(r"[,.!?;:।|—]$")


class Captioner:
    def __init__(self, words: list[dict], dna: dict, base_px: int | None = None):
        self.dna, self.p, self.F = dna, dna["palette"], dna["fonts"]
        self.style = dna["caption_style"]
        self.case = "upper" if self.style in ("outline_bold", "pop_color", "pill") and dna.get("caption_case", "auto") != "lower" else "any"
        self.px = base_px or {"pill": 76, "pop_color": 80, "box_line": 72, "highlighter": 74, "glow": 76, "outline_bold": 82, "underline": 74}[self.style]
        self.y = CAP_Y.get(dna.get("caption_pos", "low"), 1330)
        self.groups = self._group([w for w in words if w.get("caption", True)])
        self.cache = {}
        self.sizes = []

    def _group(self, words):
        groups, cur = [], []
        maxw = 3 if self.px < 80 else 2
        for i, w in enumerate(words):
            cur.append(w)
            nxt = words[i + 1] if i + 1 < len(words) else None
            gap = (nxt["t0"] - w["t1"]) if nxt else 9
            chars = sum(len(x["show"]) for x in cur)
            if (len(cur) >= maxw or chars >= 15 or gap > 0.32 or PUNCT_BREAK.search(w["show"]) or not nxt
                    or nxt.get("beat") != w.get("beat")):
                groups.append(cur)
                cur = []
        out = []
        for gi, g in enumerate(groups):
            nxt = groups[gi + 1][0]["t0"] if gi + 1 < len(groups) else None
            end = g[-1]["t1"] + 0.35
            if nxt is not None:
                end = min(end, nxt - 0.02) if nxt - g[-1]["t1"] < 0.6 else min(end, nxt)
            out.append({"words": g, "t0": g[0]["t0"] - 0.04, "t1": max(end, g[-1]["t1"] + 0.05)})
        return out

    def _sprites(self, gi):
        if gi in self.cache:
            return self.cache[gi]
        g = self.groups[gi]
        p, st = self.p, self.style
        texts = [apply_case(re.sub(r"[,.;:!?।]+$", "", w["show"]), self.case) or w["show"] for w in g["words"]]
        px = self.px
        stroke = {"outline_bold": 0.13, "pill": 0.07, "pop_color": 0.08, "glow": 0.0, "box_line": 0.0, "highlighter": 0.0, "underline": 0.06}[st]
        dark_text = st == "highlighter" or (st == "box_line" and not self.dna["tone"] != "light")
        base_col = p["text"] if self.dna["tone"] != "light" or st in ("outline_bold", "pill", "pop_color", "underline") else p["text"]
        light = self.dna["tone"] == "light"
        if st in ("outline_bold", "pill", "pop_color", "underline", "glow"):
            base_col = "#FFFFFF" if not light else p["text"]
        shadow = (0, 6, 10, 0.75, "#000000") if not light else (0, 4, 8, 0.25, "#000000")
        sc_col = "#000000" if not light else "#FFFFFF"
        while True:
            norm = [text_sprite(t, self.F["caption"], px, deva_fid=self.F["deva"], color=base_col if not dark_text else p["text"], box=(5000, 900),
                                max_lines=1, stroke=stroke, stroke_color=sc_col, shadow=shadow if st != "box_line" else None, role="caption")
                    for t in texts]
            pads = [s.meta["pad"] for s in norm]
            widths = [s.w - 2 * pd for s, pd in zip(norm, pads)]
            gap = px * 0.4
            total = sum(widths) + gap * (len(widths) - 1)
            if total <= (CAP_X1 - CAP_X0) or px <= 60:
                break
            px -= 4
        act_col = {"pill": p["ink"], "pop_color": p["accent"], "box_line": p["accent"], "highlighter": p["ink"], "glow": p["accent"],
                   "outline_bold": p["accent"] if gfx_contrast_ok(p["accent"]) else "#FFE14D", "underline": "#FFFFFF" if not light else p["accent"]}[st]
        act = [text_sprite(t, self.F["caption"], px, deva_fid=self.F["deva"], color=act_col, box=(5000, 900), max_lines=1,
                           stroke=0.0 if st in ("pill", "highlighter") else stroke, stroke_color=sc_col,
                           shadow=None if st in ("pill", "highlighter") else shadow,
                           glow=(14, 0.9, p["accent"]) if st == "glow" else None, role="caption") for t in texts]
        xs = []
        x = (CAP_X0 + CAP_X1) / 2 - total / 2
        for wd in widths:
            xs.append(x + wd / 2)
            x += wd + gap
        box = None
        if st == "box_line":
            bh = int(px * 1.55)
            bw = int(total + px * 0.9)
            box = gfx.card(bw, bh, fill=rgb2hex(mix(p["bg0"], "#000000", 0.25)) if self.dna["tone"] != "light" else "#FFFFFF", alpha=225,
                           kind="rounded" if self.dna["card_shape"] != "sharp" else "sharp", r=int(bh * 0.25))
        res = {"norm": norm, "act": act, "xs": xs, "widths": widths, "px": px, "total": total, "box": box, "cache": {}}
        self.sizes.append(px)
        self.cache[gi] = res
        return res

    def active_group(self, t):
        for gi, g in enumerate(self.groups):
            if g["t0"] <= t < g["t1"]:
                return gi
        return None

    def render(self, frame: Image.Image, t: float) -> None:
        gi = self.active_group(t)
        if gi is None:
            return
        g = self.groups[gi]
        R = self._sprites(gi)
        p, st = self.p, self.style
        dt = t - g["t0"]
        k = 0.82 + 0.18 * spring(dt, 26, 0.55)
        a = clamp(dt / 0.06) * clamp((g["t1"] - t) / 0.06)
        y = self.y + 18 * (1 - ease_out_cubic(dt / 0.18))
        ai = None
        for i, w in enumerate(g["words"]):
            if w["t0"] - 0.03 <= t:
                ai = i
        if R["box"] is not None:
            b = R["box"] if k > 0.995 and a > 0.99 else alpha_mult(R["box"].resize((max(1, int(R["box"].width * k)), max(1, int(R["box"].height * k)))), a)
            blit(frame, b, (CAP_X0 + CAP_X1) / 2 - b.width / 2, y - b.height / 2)
        # moving pill / highlighter / underline under the active word
        if ai is not None and st in ("pill", "highlighter", "underline"):
            w0 = g["words"][ai]
            q = spring(t - w0["t0"] + 0.03, 30, 0.7)
            prev = ai - 1 if ai > 0 else ai
            cx = R["xs"][prev] + (R["xs"][ai] - R["xs"][prev]) * q
            ww = R["widths"][prev] + (R["widths"][ai] - R["widths"][prev]) * q
            if st == "pill":
                ph = int(R["px"] * 1.28)
                pw = int(ww + R["px"] * 0.5)
                key = ("pill", pw // 2)
                im = R["cache"].get(key) or R["cache"].setdefault(key, gfx.card(pw, ph, fill=p["accent"], kind="pill"))
                blit(frame, alpha_mult(im, a), cx - im.width / 2, y - ph / 2 + R["px"] * 0.06)
            elif st == "highlighter":
                ph = int(R["px"] * 1.05)
                grow = clamp((t - w0["t0"] + 0.03) / 0.16)
                pw = max(4, int((R["widths"][ai] + R["px"] * 0.3) * ease_out_cubic(grow)))
                key = ("hl", ai, pw // 3)
                im = R["cache"].get(key) or R["cache"].setdefault(key, gfx.brush_swipe(pw, ph, p["accent"], seed=ai))
                blit(frame, alpha_mult(im, a), R["xs"][ai] - (R["widths"][ai] + R["px"] * 0.3) / 2, y - ph / 2 + R["px"] * 0.08)
            else:
                uh = max(8, R["px"] // 9)
                key = ("ul", int(ww) // 2)
                im = R["cache"].get(key) or R["cache"].setdefault(key, gfx.card(int(ww), uh, fill=p["accent"], kind="pill"))
                blit(frame, alpha_mult(im, a), cx - im.width / 2, y + R["px"] * 0.62)
        for i, (sn, sa) in enumerate(zip(R["norm"], R["act"])):
            is_act = i == ai
            spr = sa if is_act else sn
            s = k
            if is_act and st in ("pop_color", "outline_bold", "glow"):
                s *= 1 + 0.12 * (1 - clamp((t - g["words"][i]["t0"]) / 0.22)) + 0.04
            alpha = a * (1.0 if (is_act or st not in ("glow",)) else 0.78)
            if i > (ai if ai is not None else -1) and st in ("pop_color", "glow", "outline_bold"):
                alpha *= 0.92
            key = (i, is_act, round(s, 2), int(alpha * 20))
            im = R["cache"].get(key)
            if im is None:
                im = spr.img
                if abs(s - 1) > 0.01:
                    im = im.resize((max(1, int(im.width * s)), max(1, int(im.height * s))), Image.Resampling.BILINEAR)
                im = alpha_mult(im, alpha)
                if len(R["cache"]) > 80:
                    R["cache"].clear()
                R["cache"][key] = im
            cx = (CAP_X0 + CAP_X1) / 2 + (R["xs"][i] - (CAP_X0 + CAP_X1) / 2) * k
            blit(frame, im, cx - im.width / 2, y - im.height / 2)


def gfx_contrast_ok(c) -> bool:
    from .core import contrast
    return contrast(c, "#000000") >= 7

