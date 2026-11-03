"""stickers.py — Fluent 3D emoji stickers (Microsoft fluentui-emoji, MIT) that pop onto the frame on the word they illustrate."""
from __future__ import annotations

import re

from PIL import Image

from .core import ASSETS

DIR = ASSETS / "stickers"
# keyword (Roman Hinglish / English / Devanagari) → sticker. First match in hero words wins, then any spoken word.
KEYWORDS = {
    "fire": "fire aag zabardast jabardast dhamakedar kamaal blockbuster hit lit best",
    "scream": "daravni darawni darr dar horror scary khaufnaak khatarnak",
    "mindblown": "twist shock pagal mind unbelievable dimaag-hila",
    "eyes": "dekho dekhna dekhiye notice nazar",
    "hundred": "100 perfect sau",
    "star": "rating star stars",
    "clapper": "film movie cinema picture scene",
    "popcorn": "entertainment maza popcorn weekend",
    "thumbs_up": "accha acchi badhiya pros taakat worth recommend",
    "thumbs_down": "bura kamzori cons bakwas bekar skip flop",
    "heart": "pyaar love romance",
    "joy": "comedy funny mazedaar",
    "crying": "emotional rona sad dukh",
    "thinking": "kyun sawaal socho sochiye",
    "check": "sahi right must haan",
    "cross": "galat wrong",
    "zap": "energy tez action bijli fast",
    "boom": "boom dhamaka blast explosion climax",
    "money": "paisa budget crore keemat price rupaye box-office",
    "cart": "buy kharido order shop",
    "snowflake": "sardi winter thand barf",
    "brain": "dimaag neurons smart brain",
    "ghost": "bhoot ghost atma",
    "skull": "maut death qatl murder",
    "crown": "king raja legend",
    "trophy": "award jeet winner oscar",
    "rocket": "growth launch rocket space",
    "sparkles": "naya nayi new special khaas premium",
    "gem": "gem heera classic",
    "bulb": "idea fact tip",
    "warning": "warning savdhaan spoiler",
    "megaphone": "announce news breaking",
    "camera": "director shoot cinematography camera",
    "tv": "ott netflix series show tv",
    "game": "game gaming khel console",
    "phone": "app phone mobile",
    "laptop": "software laptop code",
    "robot": "ai robot",
    "alien": "alien sci-fi",
    "detective": "mystery jasoos detective raaz",
    "magnifier": "khoj detail",
    "hourglass": "time samay slow dheemi lamba",
    "gift": "offer gift free tohfa",
    "label": "sale discount daam",
    "scarf": "shawl scarf dupatta stole",
    "dress": "dress kurti suit collection fashion",
    "coat": "jacket coat",
    "shocked": "wow hairaan",
    "nerd": "science padhai",
    "monocle": "review analysis",
    "shush": "secret",
    "cold": "cold",
    "hot": "garam hot garmi",
    "point_down": "neeche below link",
    "bell": "follow subscribe",
    "speech": "comment batao bolo likho",
    "question": "kaun kya kaise",
    "octopus": "octopus ऑक्टोपस",
    "drop_blood": "khoon blood खून",
    "microphone": "gaana song awaaz",
    "notes": "music bgm",
    "crystal_ball": "future bhavishya prediction",
    "bomb": "bomb",
    "ticket": "ticket theatre release",
    "projector": "silent purani",
    "masks": "acting performance actor drama",
    "calendar": "date saal year",
    "key": "chaabi",
    "sleeping": "boring neend",
    "devil": "villain shaitaan evil",
    "clown": "joker clown",
    "moon": "raat night",
    "lightning": "toofan storm thunder",
    "dna": "dna डीएनए",
    "microscope": "research",
}
_KW = {}
for k, words in KEYWORDS.items():
    for w in words.split():
        _KW.setdefault(re.sub(r"[^\wऀ-ॿ-]", "", w.lower()), k)
_CACHE = {}


def available() -> list[str]:
    return sorted(p.stem for p in DIR.glob("*.png"))


def load(name: str, size: int) -> Image.Image | None:
    key = (name, size)
    if key not in _CACHE:
        p = DIR / f"{name}.png"
        if not p.exists():
            return None
        _CACHE[key] = Image.open(p).convert("RGBA").resize((size, size), Image.Resampling.LANCZOS)
    return _CACHE[key]


def match(words: list[dict], hero: set) -> tuple[str, float] | None:
    """→ (sticker, local time of the word that triggered it). Hero words first."""
    def norm(s):
        return re.sub(r"[^\wऀ-ॿ-]", "", (s or "").lower())
    order = [w for w in words if norm(w.get("show")) in hero] + words
    for w in order:
        for cand in (norm(w.get("show")), norm(w.get("say"))):
            if cand in _KW:
                return _KW[cand], w["t0"]
    return None
