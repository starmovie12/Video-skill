"""dna.py — Style DNA (a unique visual identity per video), the Variety Ledger (memory of every past video that FORCES the next
one to differ), and Taste Memory (operator approvals/rejections + reference images/videos)."""
from __future__ import annotations

import datetime
import math
import subprocess
from pathlib import Path

import numpy as np
from PIL import Image

from .core import Rng, clamp, ensure_contrast, extract_palette, from_oklch, hue_name, log, read_json, stable_seed, state_home, write_json
from .typo import REG

CATEGORIES = ("movie_review", "product", "facts", "story", "software", "game", "generic")

# The DNA dimensions that define "looks different". Novelty is counted over these.
DIMS = ("palette_family", "hero_font", "background", "motif", "motion", "transitions", "caption_style", "opening",
        "card_shape", "layout_align", "music_mood", "tone")

BACKGROUNDS = ("poster_ambilight", "poster_duotone", "halftone", "mesh", "spotlight", "paper", "grid_tech", "split_tone",
               "poster_mosaic", "bokeh_night")
POSTER_BG = {"poster_ambilight", "poster_duotone", "halftone", "poster_mosaic"}
MOTIFS = ("film_perfs", "brackets", "slashes", "circles", "light_rays", "scanlines", "dust", "stamps", "thin_frames", "sparkles",
          "grid_dots", "tape")
CAPTION_STYLES = ("viral", "viral_box", "pill", "pop_color", "box_line", "highlighter", "glow", "outline_bold", "underline")
VIRAL_BOOST = {"viral": 3.5, "viral_box": 2.0}  # the proven Reels caption looks get a strong prior in every profile
OPENINGS = ("word_smash", "poster_punch", "rating_first", "question_flash", "split_reveal", "countdown")
SHAPES = ("rounded", "sharp", "cut", "pill", "ticket")
MUSIC = ("epic_trailer", "dark_pulse", "upbeat_pop", "lofi_soft", "synthwave", "ambient_luxe", "hype_trap", "playful_pluck", "phonk")

# Profiles: weights per dimension value. Genre profiles (movies) and category profiles (non-movie).
P = {
    "horror":    dict(tone={"dark": 6}, vibes=["horror", "condensed", "cinematic", "vintage"], motion={"heavy": 3, "glitchy": 3, "snappy": 1},
                      background={"poster_duotone": 3, "spotlight": 3, "halftone": 1, "poster_ambilight": 2, "bokeh_night": 1},
                      motif={"scanlines": 3, "dust": 3, "brackets": 1, "stamps": 1, "film_perfs": 2},
                      transitions={"glitch": 4, "flash": 3, "ink": 3, "shutter": 2, "zoom_through": 2, "iris": 1},
                      music={"dark_pulse": 5, "epic_trailer": 1}, caption_style={"glow": 3, "box_line": 2, "pop_color": 1, "outline_bold": 2},
                      opening={"question_flash": 3, "poster_punch": 3, "word_smash": 2, "countdown": 2}),
    "thriller":  dict(tone={"dark": 6}, vibes=["condensed", "thriller", "cinematic", "news", "crime"], motion={"snappy": 3, "heavy": 2, "glitchy": 1},
                      background={"poster_duotone": 3, "spotlight": 2, "poster_ambilight": 3, "grid_tech": 1, "split_tone": 1},
                      motif={"brackets": 3, "scanlines": 2, "slashes": 2, "thin_frames": 2},
                      transitions={"whip": 3, "glitch": 2, "flash": 2, "shutter": 2, "split": 2, "zoom_through": 1},
                      music={"phonk": 2, "dark_pulse": 5, "epic_trailer": 2}, caption_style={"box_line": 3, "pill": 2, "underline": 2, "outline_bold": 1},
                      opening={"question_flash": 3, "word_smash": 3, "split_reveal": 2, "poster_punch": 2}),
    "action":    dict(tone={"dark": 5, "mid": 1}, vibes=["action", "condensed", "bold", "cinematic", "poster"], motion={"heavy": 4, "snappy": 3},
                      background={"poster_ambilight": 3, "poster_duotone": 2, "split_tone": 2, "spotlight": 1, "poster_mosaic": 2},
                      motif={"slashes": 4, "light_rays": 2, "film_perfs": 1, "dust": 2},
                      transitions={"whip": 4, "zoom_through": 4, "stripes": 2, "flash": 2, "spin": 2},
                      music={"phonk": 3, "epic_trailer": 5, "hype_trap": 2}, caption_style={"pill": 3, "pop_color": 3, "outline_bold": 2},
                      opening={"word_smash": 4, "poster_punch": 3, "rating_first": 2, "countdown": 1}),
    "scifi":     dict(tone={"dark": 6}, vibes=["scifi", "tech", "future", "modern"], motion={"snappy": 3, "glitchy": 2, "smooth": 1},
                      background={"grid_tech": 4, "poster_duotone": 2, "bokeh_night": 2, "poster_ambilight": 2},
                      motif={"scanlines": 3, "grid_dots": 3, "brackets": 3, "circles": 2},
                      transitions={"glitch": 3, "iris": 2, "zoom_through": 3, "shutter": 2, "whip": 1},
                      music={"synthwave": 5, "epic_trailer": 2, "dark_pulse": 1}, caption_style={"glow": 3, "box_line": 2, "underline": 2},
                      opening={"countdown": 3, "word_smash": 2, "split_reveal": 2, "rating_first": 1}),
    "comedy":    dict(tone={"mid": 4, "light": 2, "dark": 1}, vibes=["playful", "comedy", "retro", "friendly"], motion={"elastic": 5, "snappy": 2},
                      background={"mesh": 3, "split_tone": 3, "halftone": 2, "paper": 2},
                      motif={"circles": 3, "sparkles": 2, "tape": 3, "stamps": 1},
                      transitions={"stripes": 3, "slide_push": 3, "spin": 2, "iris": 2, "split": 1},
                      music={"playful_pluck": 4, "upbeat_pop": 4}, caption_style={"pop_color": 4, "highlighter": 3, "pill": 2},
                      opening={"word_smash": 3, "question_flash": 2, "rating_first": 2, "split_reveal": 1}),
    "romance":   dict(tone={"dark": 2, "light": 3, "mid": 1}, vibes=["romance", "elegant", "editorial", "luxury", "handmade"], motion={"smooth": 5, "elastic": 1},
                      background={"poster_ambilight": 3, "bokeh_night": 3, "mesh": 2, "paper": 2},
                      motif={"sparkles": 3, "circles": 2, "thin_frames": 3, "light_rays": 1},
                      transitions={"luma_fade": 3, "ink": 3, "iris": 2, "slide_push": 1},
                      music={"lofi_soft": 4, "ambient_luxe": 3}, caption_style={"highlighter": 2, "underline": 3, "glow": 2},
                      opening={"poster_punch": 2, "word_smash": 2, "split_reveal": 2}),
    "drama":     dict(tone={"dark": 4, "light": 1}, vibes=["editorial", "drama", "classic", "story"], motion={"smooth": 4, "heavy": 1},
                      background={"poster_ambilight": 3, "spotlight": 2, "halftone": 2, "paper": 1, "poster_duotone": 1},
                      motif={"thin_frames": 3, "film_perfs": 2, "dust": 2, "brackets": 1},
                      transitions={"luma_fade": 2, "ink": 2, "slide_push": 2, "diag_wipe": 2, "iris": 1},
                      music={"ambient_luxe": 3, "lofi_soft": 2, "epic_trailer": 2}, caption_style={"underline": 3, "box_line": 2, "pill": 1},
                      opening={"word_smash": 3, "poster_punch": 2, "question_flash": 2}),
    "crime":     dict(tone={"dark": 6}, vibes=["crime", "mystery", "vintage", "condensed", "news"], motion={"snappy": 3, "heavy": 2},
                      background={"halftone": 3, "spotlight": 3, "poster_duotone": 2, "paper": 1},
                      motif={"tape": 2, "stamps": 3, "brackets": 2, "dust": 2},
                      transitions={"shutter": 3, "flash": 2, "diag_wipe": 2, "glitch": 1, "whip": 2},
                      music={"phonk": 2, "dark_pulse": 5}, caption_style={"box_line": 3, "highlighter": 2, "outline_bold": 2},
                      opening={"question_flash": 3, "word_smash": 2, "poster_punch": 2}),
    "fantasy":   dict(tone={"dark": 5}, vibes=["epic", "fantasy", "history", "cinematic", "luxury"], motion={"smooth": 3, "heavy": 2},
                      background={"poster_ambilight": 4, "bokeh_night": 2, "spotlight": 2, "poster_duotone": 1},
                      motif={"light_rays": 4, "sparkles": 3, "dust": 2, "thin_frames": 2},
                      transitions={"zoom_through": 3, "luma_fade": 2, "iris": 2, "ink": 2},
                      music={"epic_trailer": 5, "ambient_luxe": 2}, caption_style={"glow": 3, "underline": 2, "pill": 1},
                      opening={"poster_punch": 3, "word_smash": 3, "rating_first": 1}),
    "animation": dict(tone={"mid": 4, "light": 2}, vibes=["playful", "animation", "friendly", "kids"], motion={"elastic": 6},
                      background={"mesh": 4, "split_tone": 2, "paper": 2, "bokeh_night": 1},
                      motif={"circles": 3, "sparkles": 4, "tape": 1},
                      transitions={"iris": 3, "spin": 3, "stripes": 2, "slide_push": 2},
                      music={"playful_pluck": 5, "upbeat_pop": 3}, caption_style={"pop_color": 4, "pill": 3, "highlighter": 2},
                      opening={"word_smash": 3, "rating_first": 2, "split_reveal": 2}),
    "documentary": dict(tone={"dark": 3, "light": 2}, vibes=["documentary", "clean", "editorial", "news"], motion={"smooth": 4, "snappy": 1},
                      background={"paper": 2, "halftone": 2, "spotlight": 2, "poster_ambilight": 2, "grid_tech": 1},
                      motif={"thin_frames": 3, "grid_dots": 2, "brackets": 2},
                      transitions={"slide_push": 3, "diag_wipe": 2, "luma_fade": 2, "shutter": 1},
                      music={"ambient_luxe": 3, "lofi_soft": 2, "dark_pulse": 1}, caption_style={"underline": 3, "box_line": 3},
                      opening={"question_flash": 3, "word_smash": 2, "countdown": 2}),
    # ── non-movie categories ──
    "product":   dict(tone={"light": 6, "dark": 2}, vibes=["luxury", "boutique", "elegant", "fashion", "minimal"], motion={"smooth": 5, "elastic": 1},
                      background={"paper": 4, "mesh": 3, "bokeh_night": 1, "split_tone": 2},
                      motif={"sparkles": 4, "thin_frames": 3, "circles": 2},
                      transitions={"luma_fade": 2, "slide_push": 3, "iris": 2, "ink": 2, "split": 2},
                      music={"ambient_luxe": 4, "lofi_soft": 4, "upbeat_pop": 1}, caption_style={"highlighter": 3, "underline": 3, "pill": 2},
                      opening={"split_reveal": 3, "word_smash": 2, "question_flash": 1}),
    "facts":     dict(tone={"dark": 4, "mid": 2, "light": 1}, vibes=["bold", "facts", "punchy", "news", "modern"], motion={"snappy": 4, "elastic": 2},
                      background={"grid_tech": 3, "mesh": 2, "spotlight": 2, "split_tone": 3, "halftone": 1},
                      motif={"grid_dots": 3, "brackets": 3, "circles": 2, "slashes": 2},
                      transitions={"whip": 3, "zoom_through": 2, "stripes": 3, "slide_push": 2, "glitch": 1},
                      music={"phonk": 2, "hype_trap": 3, "upbeat_pop": 3, "synthwave": 2}, caption_style={"pill": 3, "pop_color": 3, "box_line": 2},
                      opening={"question_flash": 4, "countdown": 2, "word_smash": 3}),
    "story":     dict(tone={"dark": 4, "light": 2}, vibes=["story", "editorial", "handmade", "vintage", "drama"], motion={"smooth": 4, "heavy": 1},
                      background={"paper": 3, "spotlight": 2, "bokeh_night": 2, "halftone": 2, "mesh": 1},
                      motif={"dust": 3, "thin_frames": 2, "light_rays": 2, "film_perfs": 1},
                      transitions={"ink": 4, "luma_fade": 3, "iris": 1, "slide_push": 1},
                      music={"ambient_luxe": 3, "lofi_soft": 3, "dark_pulse": 1}, caption_style={"underline": 3, "highlighter": 2, "glow": 2},
                      opening={"question_flash": 3, "word_smash": 3}),
    "software":  dict(tone={"dark": 5, "light": 2}, vibes=["tech", "software", "modern", "clean"], motion={"snappy": 5},
                      background={"grid_tech": 5, "mesh": 2, "split_tone": 1},
                      motif={"brackets": 4, "grid_dots": 3, "scanlines": 1},
                      transitions={"slide_push": 3, "zoom_through": 2, "glitch": 2, "split": 2},
                      music={"synthwave": 3, "upbeat_pop": 3, "lofi_soft": 1}, caption_style={"box_line": 3, "pill": 3},
                      opening={"question_flash": 3, "countdown": 2, "word_smash": 2}),
    "game":      dict(tone={"dark": 5, "mid": 1}, vibes=["game", "tech", "bold", "retro", "pixel", "scifi"], motion={"snappy": 3, "glitchy": 3, "elastic": 1},
                      background={"grid_tech": 3, "bokeh_night": 2, "poster_ambilight": 2, "split_tone": 2, "poster_duotone": 1},
                      motif={"scanlines": 3, "slashes": 3, "grid_dots": 2, "brackets": 2},
                      transitions={"glitch": 4, "zoom_through": 3, "whip": 2, "stripes": 2},
                      music={"phonk": 4, "hype_trap": 4, "synthwave": 4}, caption_style={"pop_color": 3, "glow": 3, "pill": 2},
                      opening={"countdown": 3, "word_smash": 3, "rating_first": 2}),
}
GENRE_ALIASES = {"sci-fi": "scifi", "science fiction": "scifi", "horror": "horror", "thriller": "thriller", "mystery": "crime",
                 "crime": "crime", "action": "action", "adventure": "action", "war": "action", "comedy": "comedy", "romance": "romance",
                 "drama": "drama", "biopic": "drama", "fantasy": "fantasy", "history": "fantasy", "epic": "fantasy",
                 "animation": "animation", "family": "animation", "kids": "animation", "documentary": "documentary",
                 "silent": "drama", "expressionist": "horror", "musical": "romance", "sports": "action", "superhero": "action"}


def profile_for(category: str, genres: list[str]) -> dict:
    """Blend the profiles of the film's genres (movies) or take the category profile; viral caption styles get a strong prior."""
    prof = _profile_for(category, genres)
    cs = dict(prof.get("caption_style", {}))
    for k, v in VIRAL_BOOST.items():
        cs[k] = cs.get(k, 0) + (v * 0.5 if category in ("product", "story") else v)
    return dict(prof, caption_style=cs)


def _profile_for(category: str, genres: list[str]) -> dict:
    if category != "movie_review":
        return P.get(category, P["facts"])
    keys = [GENRE_ALIASES.get(g.lower().strip(), None) for g in genres or []]
    keys = [k for k in keys if k] or ["drama"]
    out = {}
    for i, k in enumerate(keys[:3]):
        w = 1.0 / (i + 1)
        for dim, vals in P[k].items():
            if dim == "vibes":
                out.setdefault("vibes", [])
                out["vibes"] += [v for v in vals if v not in out["vibes"]]
                continue
            d = out.setdefault(dim, {})
            for v, x in vals.items():
                d[v] = d.get(v, 0) + x * w
    return out


# ───────────────────────── palette ─────────────────────────
BOUND = {"tone", "music"}
RELATIONS = {"complement": (180, 200), "analogous": (35, -35), "triad": (120, 240), "split": (150, 210), "mono": (0, 18)}


def build_palette(tone: str, rng: Rng, poster_cols: list[dict] | None, base_hue=None, relation=None) -> dict:
    """Derive a cohesive palette. With a poster: hues come FROM the poster (identity of the film). Without: from mood + seed."""
    chroma = sorted([c for c in (poster_cols or []) if c["C"] > 0.05], key=lambda c: -(c["weight"] * 0.6 + c["C"] * 2.2))
    if chroma:
        h0 = chroma[0]["h"] if tone != "dark" else min(poster_cols, key=lambda c: c["L"])["h"]
        c0 = chroma[0]
        acc_h = c0["h"]
        others = [c for c in chroma[1:] if abs(((c["h"] - acc_h + 180) % 360) - 180) > 40]
        h2 = others[0]["h"] if others else (acc_h + rng.choice([150, 180, 210, 40, -40])) % 360
        relation = relation or "poster"
    else:
        h0 = base_hue if base_hue is not None else rng.uniform(0, 360)
        relation = relation or rng.choice(list(RELATIONS))
        d1, d2 = RELATIONS[relation]
        acc_h, h2 = (h0 + d1) % 360, (h0 + d2) % 360
        if relation == "mono":
            acc_h = h0
    j = rng.uniform(-8, 8)
    if tone == "dark":
        pal = dict(bg0=from_oklch(0.14, 0.03, h0 + j), bg1=from_oklch(0.22, 0.05, h0 + j), accent=from_oklch(0.76, 0.2, acc_h),
                   accent2=from_oklch(0.70, 0.16, h2), text=from_oklch(0.97, 0.012, h0), muted=from_oklch(0.74, 0.03, h0),
                   ink=from_oklch(0.16, 0.03, acc_h))
    elif tone == "light":
        pal = dict(bg0=from_oklch(0.965, 0.014, h0 + j), bg1=from_oklch(0.90, 0.035, h0 + j), accent=from_oklch(0.48, 0.13, acc_h),
                   accent2=from_oklch(0.66, 0.10, h2), text=from_oklch(0.22, 0.02, h0), muted=from_oklch(0.46, 0.02, h0),
                   ink=from_oklch(0.98, 0.01, acc_h))
    else:  # mid = saturated pop backgrounds
        pal = dict(bg0=from_oklch(0.44, 0.16, h0 + j), bg1=from_oklch(0.36, 0.15, h0 + j), accent=from_oklch(0.92, 0.17, acc_h if acc_h != h0 else (h0 + 60) % 360),
                   accent2=from_oklch(0.80, 0.15, h2), text=from_oklch(0.99, 0.005, h0), muted=from_oklch(0.88, 0.04, h0),
                   ink=from_oklch(0.16, 0.03, h0))
    pal["accent"] = ensure_contrast(pal["accent"], pal["bg0"], 3.0)
    pal["text"] = ensure_contrast(pal["text"], pal["bg0"], 7.0 if tone != "mid" else 4.5)  # mid: saturated bg, big text → AA
    pal["good"] = from_oklch(0.78 if tone != "light" else 0.5, 0.16, 150)
    pal["bad"] = from_oklch(0.68 if tone != "light" else 0.5, 0.19, 25)
    pal["family"] = f"{tone}-{hue_name(h0)}-{hue_name(acc_h)}"
    pal["relation"] = relation
    return pal


# ───────────────────────── fonts ─────────────────────────
def pick_fonts(vibes: list[str], rng: Rng, need_deva_hero: bool, caption_script: str, taste: dict) -> dict:
    def score(fid, role):
        sp = REG[fid]
        if role not in sp["role"]:
            return 0.0
        s = 0.2 + sum(2.0 / (1 + i) for i, v in enumerate(vibes) if v in sp["vibes"])
        s += taste.get("hero_font", {}).get(fid, 0.0) if role == "hero" else 0
        return max(0.01, s)
    heroes = {f: score(f, "hero") for f in REG if (not need_deva_hero or "deva" in REG[f]["scripts"])}
    hero = rng.wchoice({k: v ** 2 for k, v in heroes.items() if v > 0.01})
    caps = [f for f in REG if "caption" in REG[f]["role"] and (caption_script != "devanagari" or "deva" in REG[f]["scripts"])]
    support = rng.wchoice({f: score(f, "support") for f in REG if "support" in REG[f]["role"] and f != hero})
    devas = {f: 1.0 + score(f, "hero") for f in REG if "deva" in REG[f]["scripts"] and ("deva" in REG[f]["role"] or "hero" in REG[f]["role"])}
    deva = hero if "deva" in REG[hero]["scripts"] else rng.wchoice(devas)
    return {"hero": hero, "support": support, "caption": rng.choice(caps), "deva": deva}


# ───────────────────────── ledger + taste ─────────────────────────
def ledger_path() -> Path:
    return state_home() / "ledger.json"


def load_ledger() -> list[dict]:
    return read_json(ledger_path(), {"videos": []})["videos"]


def save_ledger_entry(entry: dict) -> None:
    led = read_json(ledger_path(), {"videos": []})
    led["videos"] = [v for v in led["videos"] if v.get("id") != entry["id"]] + [entry]
    write_json(ledger_path(), led)


def load_taste() -> dict:
    return read_json(state_home() / "taste.json", {"weights": {}, "refs": [], "notes": []})


def dna_signature(dna: dict) -> dict:
    return {k: (",".join(sorted(dna[k])) if isinstance(dna[k], list) else dna[k]) for k in DIMS if k in dna}


def diff_count(a: dict, b: dict) -> int:
    return sum(1 for k in DIMS if k in a and k in b and a[k] != b[k])


# ───────────────────────── DNA generation ─────────────────────────
def generate(project: dict, poster: Image.Image | None, seed_extra: str = "") -> dict:
    """Sample many candidate DNAs that fit the film/category, keep the one that best balances fit + novelty vs the ledger."""
    cat = project.get("category", "movie_review")
    facts = project.get("facts", {})
    genres = facts.get("genre", []) if isinstance(facts.get("genre"), list) else [facts.get("genre", "drama")]
    prof = profile_for(cat, genres)
    taste = load_taste()
    tw = taste.get("weights", {})
    history = [v["dna_sig"] for v in reversed(load_ledger()) if v.get("dna_sig")][:12]
    seed = stable_seed(project.get("title", ""), project.get("id", ""), len(history), seed_extra, datetime.date.today().isoformat())
    poster_cols = extract_palette(poster, 7) if poster is not None else None
    caption_script = project.get("caption_script", "roman")
    need_deva_hero = caption_script == "devanagari"
    over = project.get("dna", {}) or {}
    best, best_score = None, -1e9
    openings = tuple(o for o in OPENINGS if not (o == "poster_punch" and poster is None) and not (o == "rating_first" and cat != "movie_review"))
    for i in range(160):
        r = Rng(seed + i * 7919)

        def pick(dim, universe):
            if dim in over:
                return over[dim]
            pd = prof.get(dim, {})
            if dim in BOUND and pd:  # tone + music must fit the film; novelty can't override genre fit
                universe = [v for v in universe if pd.get(v, 0) > 0] or list(universe)
            w = {v: pd.get(v, 0.15) * (1 + tw.get(dim, {}).get(v, 0.0)) for v in universe}
            return r.wchoice({k: max(0.01, x) for k, x in w.items()})
        tone = pick("tone", ("dark", "light", "mid"))
        bgs = BACKGROUNDS if poster is not None else tuple(b for b in BACKGROUNDS if b not in POSTER_BG)
        trans_w = {t: prof.get("transitions", {}).get(t, 0.3) for t in ("whip", "zoom_through", "flash", "slide_push", "iris", "diag_wipe",
                                                                         "glitch", "shutter", "ink", "spin", "luma_fade", "stripes", "split")}
        trans = over.get("transitions") or sorted(set(r.wchoice(trans_w) for _ in range(6)))[:4]
        if len(trans) < 2:
            trans = sorted(set(trans) | {r.choice(list(trans_w))})
        cand = {
            "tone": tone,
            "background": pick("background", bgs),
            "background2": pick("background", bgs),
            "motif": pick("motif", MOTIFS),
            "motion": pick("motion", ("snappy", "elastic", "smooth", "heavy", "glitchy")),
            "transitions": trans,
            "caption_style": pick("caption_style", CAPTION_STYLES),
            "opening": pick("opening", openings),
            "card_shape": pick("card_shape", SHAPES),
            "layout_align": pick("layout_align", ("left", "center", "center", "left")),
            "music_mood": pick("music", MUSIC) if "music_mood" not in over else over["music_mood"],
        }
        if tone == "light" and cand["background"] in ("grid_tech", "bokeh_night", "spotlight"):
            continue
        pal = build_palette(tone, r, poster_cols, relation=None)
        fonts = over.get("fonts") or pick_fonts(prof.get("vibes", []), r, need_deva_hero, caption_script, tw)
        cand.update(palette=pal, fonts=fonts, palette_family=pal["family"], hero_font=fonts["hero"])
        sig = dna_signature(cand)
        fit = sum(math.log(1 + prof.get(d, {}).get(cand.get(d if d != "music_mood" else "music_mood"), 0.1)) for d in ("background", "motif", "motion", "caption_style", "opening"))
        novelty = min([diff_count(sig, h) for h in history[:3]] or [len(DIMS)])
        novelty_all = min([diff_count(sig, h) for h in history] or [len(DIMS)])
        reused = sum(1 for h in history[:5] for k in ("hero_font", "background", "opening", "caption_style") if h.get(k) == sig.get(k))
        score = fit + 1.1 * novelty + 0.5 * novelty_all - 0.6 * reused + r.uniform(0, 1.2)
        if novelty < 5 and history:
            score -= 8
        if score > best_score:
            best, best_score = cand, score
    dna = best
    m = Rng(seed + 1)
    dna.update({
        "seed": seed, "category": cat, "genres": genres,
        "caption_script": caption_script,
        "caption_pos": over.get("caption_pos", m.choice(["low", "low", "mid_low"])),
        "hero_case": over.get("hero_case", REG[dna["fonts"]["hero"]].get("case", "upper") if REG[dna["fonts"]["hero"]].get("case") != "any" else m.choice(["upper", "title"])),
        "camera": over.get("camera", m.wchoice({"dynamic": 3, "calm": 1} if dna["motion"] != "smooth" else {"calm": 3, "dynamic": 1})),
        "grade": {"contrast": round(m.uniform(1.0, 1.1), 3), "saturation": round(m.uniform(0.95, 1.18) if dna["tone"] != "light" else m.uniform(0.9, 1.05), 3),
                  "vignette": round(m.uniform(0.25, 0.6) if dna["tone"] == "dark" else m.uniform(0.0, 0.2), 2), "grain": m.choice([4, 5, 6, 7])},
        "music_key": m.choice(["C", "D", "E", "F", "G", "A", "Bb"]),
        "sticker_rate": over.get("sticker_rate", round({"story": 0.35, "product": 0.5}.get(cat, 0.65) * m.uniform(0.8, 1.2), 2)),
        "variants": {},
        "palette_source": "poster" if poster_cols else "generated",
    })
    for k, v in over.items():
        if k not in ("fonts", "transitions"):
            dna[k] = v
    from .audio import mood_bpm
    dna["bpm"] = over.get("bpm") or mood_bpm(dna["music_mood"], seed % 100000)
    sig = dna_signature(dna)
    dna["novelty_vs_last"] = [diff_count(sig, h) for h in history[:5]]
    dna["dna_sig"] = sig
    if poster_cols:
        dna["poster_palette"] = poster_cols
    log(f"style DNA: {dna['palette_family']} · font={dna['hero_font']} · bg={dna['background']} · motif={dna['motif']} · "
        f"motion={dna['motion']} · captions={dna['caption_style']} · open={dna['opening']} · music={dna['music_mood']} · "
        f"novelty vs last videos={dna['novelty_vs_last'] or 'first video'}")
    return dna


# ───────────────────────── taste memory + reference intake ─────────────────────────
def feedback(dna: dict, approve: bool, note: str = "") -> dict:
    t = load_taste()
    w = t.setdefault("weights", {})
    for k in ("background", "motif", "motion", "caption_style", "opening", "card_shape", "music", "hero_font", "tone"):
        v = dna.get("music_mood" if k == "music" else k)
        if v is None:
            continue
        d = w.setdefault(k, {})
        d[v] = round(clamp(d.get(v, 0.0) + (0.35 if approve else -0.45), -0.9, 3.0), 3)
    if note:
        t.setdefault("notes", []).append({"date": datetime.date.today().isoformat(), "approve": approve, "note": note})
    write_json(state_home() / "taste.json", t)
    return t


def analyze_reference(path: Path) -> dict:
    """Reference image/video → palette, brightness, saturation, contrast, detail density, cut pace (videos)."""
    frames = []
    info = {"file": path.name}
    if path.suffix.lower() in (".mp4", ".mov", ".mkv", ".webm"):
        out = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-vf", "fps=1,scale=180:-2", "-f", "image2pipe", "-vcodec", "png", "-"],
                             capture_output=True, timeout=180).stdout
        import io
        sig = b"\x89PNG\r\n\x1a\n"
        for chunk in out.split(sig)[1:40]:
            try:
                frames.append(Image.open(io.BytesIO(sig + chunk)).convert("RGB"))
            except OSError:
                pass
        sc = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-vf", "select='gt(scene,0.28)',showinfo", "-f", "null", "-"],
                            capture_output=True, text=True, timeout=300).stderr
        cuts = sc.count("pts_time")
        from .core import ffprobe_duration
        dur = ffprobe_duration(path)
        info["avg_shot_sec"] = round(dur / max(1, cuts + 1), 2)
    else:
        frames = [Image.open(path).convert("RGB")]
    if not frames:
        return info
    arr = np.concatenate([np.asarray(f.resize((120, 213)), np.float32).reshape(-1, 3) for f in frames])
    lum = arr @ np.array([0.2126, 0.7152, 0.0722], np.float32)
    sat = arr.max(1) - arr.min(1)
    edges = np.mean([np.asarray(f.convert("L").resize((120, 213)).filter(__import__("PIL.ImageFilter", fromlist=["x"]).FIND_EDGES), np.float32).mean() for f in frames])
    big = Image.fromarray(arr[: 120 * 213].reshape(213, 120, 3).astype(np.uint8))
    info.update(brightness=round(float(lum.mean() / 255), 3), saturation=round(float(sat.mean() / 255), 3),
                contrast=round(float(lum.std() / 255), 3), detail=round(float(edges / 255), 3),
                palette=[c["hex"] for c in extract_palette(big, 5)])
    return info


def intake_references(folder: Path) -> dict:
    t = load_taste()
    refs = []
    for p in sorted(folder.iterdir()):
        if p.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp", ".mp4", ".mov", ".webm", ".mkv"):
            try:
                refs.append(analyze_reference(p))
                log(f"reference: {p.name} → {refs[-1]}")
            except (OSError, ValueError, subprocess.SubprocessError) as e:
                log(f"reference skipped {p.name}: {e}")
    t["refs"] = refs
    # translate refs into soft preferences
    if refs:
        b = float(np.mean([r.get("brightness", 0.4) for r in refs]))
        s = float(np.mean([r.get("saturation", 0.3) for r in refs]))
        shots = [r["avg_shot_sec"] for r in refs if "avg_shot_sec" in r]
        w = t.setdefault("weights", {})
        w.setdefault("tone", {})
        w["tone"]["light"] = round(2.0 * clamp((b - 0.45) * 3, -0.9, 2), 3)
        w["tone"]["dark"] = round(2.0 * clamp((0.45 - b) * 3, -0.9, 2), 3)
        w["tone"]["mid"] = round(clamp((s - 0.35) * 4, -0.9, 2), 3)
        if shots:
            pace = float(np.mean(shots))
            w.setdefault("motion", {})
            w["motion"]["snappy"] = round(clamp((2.5 - pace), -0.9, 2), 3)
            w["motion"]["smooth"] = round(clamp((pace - 2.5) * 0.6, -0.9, 2), 3)
    write_json(state_home() / "taste.json", t)
    return t


def describe(dna: dict) -> str:
    p = dna["palette"]
    return (f"Palette {dna['palette_family']} (bg {p['bg0']}, accent {p['accent']}, accent2 {p['accent2']}) · hero font {dna['hero_font']} · "
            f"background {dna['background']} · motif {dna['motif']} · motion {dna['motion']} · transitions {', '.join(dna['transitions'])} · "
            f"captions {dna['caption_style']} · opening {dna['opening']} · cards {dna['card_shape']} · align {dna['layout_align']} · "
            f"music {dna['music_mood']}")
