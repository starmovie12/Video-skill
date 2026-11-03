"""lint.py — script & plan lint BEFORE any rendering: hook rules, empty-card prevention, pacing vs target duration, clichés."""
from __future__ import annotations

import json
import re

from .qa import CLICHES, GREETINGS

NEEDS = {"pros_cons": ("pros", "cons"), "cast": ("cast",), "rating": ("rating",), "verdict": ("verdict",), "stat": ("value",),
         "timeline": ("events",), "price": ("price",), "list": ("items",), "compare": ("left", "right"), "fact": ("big",),
         "features": ("features",)}
WPS = 2.55  # MEASURED: hi-IN-MadhurNeural at +18 % ≈ 2.55 spoken tokens / s incl. pauses (Caligari sample, 103 tokens / 40.4 s)


def lint(p: dict, root=None):
    errs, warns = [], []
    from .channel import apply_defaults, lint as channel_lint
    ce, cw = channel_lint(apply_defaults(p))
    errs += ce
    warns += cw
    beats = p.get("beats") or []
    if not beats:
        return ["no beats"], warns
    if not p.get("target_sec"):
        warns.append("target_sec missing → duration is not controlled")
    for i, b in enumerate(beats):
        bid = b.get("id", f"#{i + 1}")
        if not (b.get("say") or b.get("show")):
            errs.append(f"{bid}: empty line")
            continue
        say, show = (b.get("say") or b.get("show")).split(), (b.get("show") or b.get("say")).split()
        if len(say) != len(show):
            warns.append(f"{bid}: say/show word counts differ ({len(say)} vs {len(show)}) → caption timing is interpolated")
        role = b.get("role", "line")
        need = NEEDS.get(role)
        data = b.get("data") or {}
        if need and not any(data.get(k) not in (None, "", []) for k in need) and role not in ("fact",):
            errs.append(f"{bid}: role '{role}' needs data.{' or data.'.join(need)} (prevents empty cards)")
    for i, b in enumerate(beats):  # media references must exist (the Director picks them from media_sheet.jpg)
        refs = b.get("media")
        for r in (refs if isinstance(refs, list) else [refs] if refs and refs not in ("auto", "none") else []):
            f = (r["file"] if isinstance(r, dict) else str(r)).split("#")[0].split("@")[0]
            if root is not None and not (root / f).exists():
                errs.append(f"{b.get('id', i)}: media '{f}' not found (run `media scan` and copy a label from media_sheet.jpg)")
        for c in (b.get("data") or {}).get("cast", []) or []:
            if c.get("image") and root is not None and not (root / c["image"]).exists():
                errs.append(f"{b.get('id', i)}: cast image '{c['image']}' not found")
    first = beats[0]
    if first.get("role") != "hook":
        errs.append("first beat must have role 'hook' (designed pattern-interrupt)")
    ftxt = first.get("show") or first.get("say") or ""
    if GREETINGS.search(ftxt):
        errs.append(f"hook starts with a greeting: '{ftxt[:30]}' — start with the most surprising claim instead")
    if len(ftxt.split()) > 14:
        warns.append("hook is long (>14 words) — keep it under ~3 s")
    total = sum(len((b.get("say") or b.get("show") or "").split()) for b in beats)
    if p.get("target_sec"):
        est = total / WPS
        if abs(est / p["target_sec"] - 1) > 0.15:
            warns.append(f"script ≈ {est:.0f}s at energetic pace vs target {p['target_sec']}s → {'cut' if est > p['target_sec'] else 'add'} "
                         f"~{abs(est - p['target_sec']) * WPS:.0f} words")
    text = " ".join((b.get("show") or b.get("say") or "") for b in beats).lower()
    cl = [c for c in CLICHES if c in text]
    if cl:
        warns.append(f"clichés: {cl} → replace with a specific scene, number or comparison")
    if not re.search(r"\d", text + json.dumps([b.get("data") for b in beats], ensure_ascii=False)):
        warns.append("no numbers/specifics in the script — specific beats generic")
    last = beats[-1]
    if "?" not in (last.get("show") or last.get("say") or "") and last.get("role") not in ("cta",):
        warns.append("ending has no question/CTA → weaker comments + loop")
    return errs, warns
