"""qa.py — DESIGN QA that blocks ugly / repetitive / dishonest output. Every check is measured on the real render or the real
plan; HARD failures make `make` exit non-zero and the video is NOT delivered. Results: qa_report.json + qa_report.md + contact sheet."""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

from .audio import measure_loudness
from .core import FPS, H, W, ffprobe_duration, log
from .dna import DIMS, diff_count, load_ledger

GREETINGS = re.compile(r"^\s*(namaste|namaskar|hello|hi+|hey|kaise ho|welcome|aaj hum|doston|dosto|guys|नमस्ते|नमस्कार|दोस्तों|आज हम)", re.I)
CLICHES = ["paisa vasool", "hollywood level", "hollywood-level", "must watch film hai", "edge of the seat", "mind blowing", "mind-blowing",
           "next level", "goosebumps", "slow second half", "one time watch", "blockbuster"]


def dhash(img: Image.Image, n=8) -> int:
    g = np.asarray(img.convert("L").resize((n + 1, n), Image.Resampling.BILINEAR), np.int16)
    bits = (g[:, 1:] > g[:, :-1]).flatten()
    return int("".join("1" if b else "0" for b in bits), 2)


def ham(a: int, b: int) -> int:
    return bin(a ^ b).count("1")


def decode_gray(video: Path, fps=10, w=108, h=192) -> np.ndarray:
    out = subprocess.run(["ffmpeg", "-v", "error", "-i", str(video), "-vf", f"fps={fps},scale={w}:{h},format=gray", "-f", "rawvideo", "-"],
                         capture_output=True, timeout=600).stdout
    return np.frombuffer(out, np.uint8).reshape(-1, h, w).astype(np.float32)


def motion_profile(video: Path, fps=10):
    g = decode_gray(video, fps)
    cap0, cap1 = int(1190 / H * g.shape[1]), int(1470 / H * g.shape[1])
    mask = np.ones(g.shape[1:], bool)
    mask[cap0:cap1] = False  # ignore captions: a caption change alone is not a "visual event"
    diff = np.abs(np.diff(g, axis=0))[:, mask]
    d = (diff > 6).mean(1) * 100  # % of pixels that visibly changed (film grain alone stays ≈ 0)
    return d, fps


def longest_static(d, fps, thr=0.4):
    run = best = 0
    at = 0
    for i, v in enumerate(d):
        run = run + 1 if v < thr else 0
        if run > best:
            best, at = run, i - run + 1
    return best / fps, at / fps


def static_runs(d, fps, thr=0.4, limit=2.5):
    """Every run of near-static frames longer than `limit` s as (start_s, length_s), so all of them can be fixed in one pass."""
    out, run = [], 0
    for i, v in enumerate(list(d) + [thr]):  # sentinel closes a run at the end
        if v < thr:
            run += 1
            continue
        if run / fps > limit:
            out.append((round((i - run) / fps, 1), round(run / fps, 1)))
        run = 0
    return out


def banding_score(img: Image.Image) -> float:
    """Share of 4×4 blocks in mid-tones that are perfectly flat (0 variance) — flat plateaus = 8-bit banding / dead fills."""
    a = np.asarray(img.convert("L"), np.int16)[250:1480]
    h, w = (a.shape[0] // 4) * 4, (a.shape[1] // 4) * 4
    b = a[:h, :w].reshape(h // 4, 4, w // 4, 4).swapaxes(1, 2).reshape(h // 4, w // 4, 16)
    flat = (b.max(-1) - b.min(-1)) == 0
    mid = (b.mean(-1) > 18) & (b.mean(-1) < 235)
    return float((flat & mid).sum() / max(1, mid.sum()))


def dead_space(img: Image.Image) -> float:
    """Share of the safe area made of large, featureless cells (low local detail AND close to the frame's median tone)."""
    a = np.asarray(img.convert("L").resize((54, 96)), np.float32)[13:74]
    med = np.median(a)
    loc = np.abs(a - med) < 10
    gy, gx = np.gradient(a)
    flat = (np.abs(gx) + np.abs(gy)) < 1.2
    return float((loc & flat).mean())


def run_qa(work: Path, project: dict, tl, final: Path, voice: dict, mix_stats: dict, frames: list[Path]) -> dict:
    checks = []

    def chk(name, ok, value, rule, hard=True):
        checks.append({"check": name, "ok": bool(ok), "value": value, "rule": rule, "hard": hard})
    dur = ffprobe_duration(final)
    tgt = project.get("target_sec")
    if tgt:
        tol = max(3.0, 0.10 * tgt)
        chk("duration_vs_target", abs(dur - tgt) <= tol, round(dur, 2), f"|{dur:.1f}s − {tgt}s| ≤ {tol:.1f}s (fix the SCRIPT, not the speed)")
    if project.get("channel") and project.get("format", "reel") == "reel":
        from .channel import load as load_channel
        hard_max = ((load_channel() or {}).get("reel_rules") or {}).get("hard_max_sec", 90)
        chk("channel_reel_length", dur <= hard_max, round(dur, 2),
            f"{project['channel'].get('handle')} reels ≤ {hard_max}s (longer reels are not pushed to non-followers); "
            f"\"format\": \"long\" for a deliberate long video")
    # structure
    plan = tl.plan
    designs = {(p["archetype"], p["variant"]) for p in plan}
    need = 5 if project.get("category", "movie_review") == "movie_review" and dur >= 30 else 3
    chk("distinct_frame_designs", len(designs) >= need, len(designs), f"≥ {need} distinct archetype layouts")
    consec = [plan[i]["archetype"] for i in range(1, len(plan)) if plan[i]["archetype"] == plan[i - 1]["archetype"]]
    chk("no_repeat_consecutive_layout", not consec, consec, "no archetype twice in a row")
    from collections import Counter
    cnt = Counter(p["archetype"] for p in plan)
    lim = max(2, int(round(2 * dur / 60)))
    over = {k: v for k, v in cnt.items() if v > lim}
    chk("archetype_reuse_limit", not over, over, f"no archetype more than {lim}× per video")
    chk("designed_transitions", len(tl.trans) == len(tl.scenes) - 1, len(tl.trans), "every scene boundary has a designed transition (no hard cuts)")
    # text size + safe zones
    small, unsafe, collide = [], [], []
    mins = {"hero": 56, "body": 40, "label": 30, "kinetic": 52}
    for s in tl.scenes:
        for role, px, (x0, y0, x1, y1), text in s.text_boxes():
            if role in mins and px < mins[role]:
                small.append(f"{s.archetype}:{role}:{int(px)}px:{text[:24]}")
            if role in ("hero", "body", "label", "kinetic"):
                right_lim = 1000 if y1 > 1000 else 1045
                if x0 < 35 or x1 > right_lim or y0 < 225 or y1 > 1495:
                    unsafe.append(f"{s.archetype}:{role}:{text[:20]}:({int(x0)},{int(y0)},{int(x1)},{int(y1)})")
                if s.meta.get("captions") and y1 > tl.captions.y - tl.captions.px * 0.75:
                    collide.append(f"{s.archetype}:{role}:{text[:20]}:bottom={int(y1)}")
    for gi in range(len(tl.captions.groups)):
        tl.captions._sprites(gi)
    cap_px = min(tl.captions.sizes) if tl.captions.sizes else None
    chk("text_min_size", not small, small[:6], "hero ≥56px, body ≥40px, label ≥30px")
    chk("caption_size", cap_px is None or cap_px >= 64, cap_px, "captions ≥ 64px on a 1080px-wide frame")
    chk("caption_collision", not collide, collide[:6], "scene text ends above the caption band when captions are on")
    chk("safe_zones", not unsafe, unsafe[:6], "critical text inside Reels safe area (top 225, bottom 1495, right 1000 below y=1000)")
    # motion / static runs / hook
    d, fps = motion_profile(final)
    longest, at = longest_static(d, fps)
    chk("no_static_runs", longest <= 2.5, {"longest_s": round(longest, 2), "at_s": round(at, 2), "all": static_runs(d, fps)[:12]},
        "a visible visual event (≥0.4 % of pixels change) at least every 2.5 s; `all` = every run > 2.5 s as [start, length]")
    hook_energy = float(d[: int(1.5 * fps)].max()) if len(d) else 0
    chk("hook_pattern_interrupt", hook_energy > 20.0, round(hook_energy, 1), "≥ 20 % of the frame changes inside the first 1.5 s")
    first = (project["beats"][0].get("show") or project["beats"][0].get("say") or "")
    chk("hook_not_greeting", not GREETINGS.search(first), first[:40], "first line is a hook, never a greeting")
    chk("hook_layout", plan[0]["archetype"] == "hook_slam", plan[0]["archetype"], "opening beat uses a designed hook")
    # visual distinctness of scenes (rendered frames)
    hashes = [dhash(Image.open(f)) for f in frames]
    distinct = []
    for h_ in hashes:
        if all(ham(h_, o) > 10 for o in distinct):
            distinct.append(h_)
    chk("visually_distinct_frames", len(distinct) >= min(need, len(frames)), len(distinct), f"≥ {need} visually different scene frames (dHash > 10 bits)")
    band = [round(banding_score(Image.open(f)), 3) for f in frames]
    chk("no_banding_or_flat_fills", max(band) < 0.25, max(band), "flat 4×4 plateaus < 25 % of mid-tone area")
    dead = [round(dead_space(Image.open(f)), 3) for f in frames]
    chk("dead_space", max(dead) <= 0.55, {"max": max(dead), "per_scene": dead}, "featureless area ≤ 55 % of the safe area", hard=False)
    # audio
    loud = measure_loudness(final)
    chk("loudness", abs(loud["I"] + 14) <= 1.5 and loud["TP"] <= -0.8, loud, "−14 LUFS ±1.5, true peak ≤ −0.8 dBTP")
    mus = mix_stats.get("music_rms_db")
    chk("music_present", mus is not None and mus > -40, round(mus, 1) if mus else None, "music bed present by default")
    chk("sfx_on_events", mix_stats.get("sfx_count", 0) >= len(tl.trans), mix_stats.get("sfx_count"), "SFX on transitions + in-scene events")
    # captions coverage
    cap_words = sum(len(g["words"]) for g in tl.captions.groups)
    spoken_cap = sum(1 for w in voice["words"] if tl.scenes[w["beat"]].meta["captions"])
    chk("captions_cover_speech", cap_words == spoken_cap, f"{cap_words}/{spoken_cap}", "every spoken word in caption beats is captioned (word-synced)")
    # footage + stickers (advisory): real visuals and emoji accents are what make Reels feel edited, not slideshow-like
    foot = sum(1 for sc in tl.scenes if getattr(sc.bg, "dynamic", False))
    n_media = len(getattr(tl, "assets", {}).get("media_segments") or {}) if hasattr(tl, "assets") else foot
    chk("footage_coverage", foot >= 0.7 * len(tl.scenes) or not n_media, f"{foot}/{len(tl.scenes)} scenes on real footage",
        "with media supplied, ≥70 % of scenes sit on real footage/stills", hard=False)
    stick = sum(1 for sc in tl.scenes for ly in sc.layers if getattr(ly, "role", "") == "sticker")
    chk("stickers", stick >= 1 or tl.dna.get("sticker_rate", 0) < 0.2, stick, "≥1 emoji sticker accent (unless the DNA chose none)", hard=False)
    # script quality (advisory but reported)
    text = " ".join((b.get("show") or b.get("say") or "") for b in project["beats"]).lower()
    cl = [c for c in CLICHES if c in text]
    chk("script_cliches", len(cl) <= 1, cl, "≤ 1 cliché per script (specific > generic)", hard=False)
    # variety vs past videos
    hist = [v for v in reversed(load_ledger()) if v.get("id") != project.get("id")][:8]
    sig = tl.dna["dna_sig"]
    dims = [diff_count(sig, v["dna_sig"]) for v in hist if v.get("dna_sig")]
    chk("dna_differs_from_past", not dims or min(dims[:5]) >= 4, dims[:5], f"≥ 4 of {len(DIMS)} style dimensions differ from each of the last 5 videos")
    if hist:
        sims = []
        for v in hist:
            if v.get("frame_hashes"):
                sims.append(np.mean([min(ham(h_, int(o, 16)) for o in v["frame_hashes"]) for h_ in hashes]))
        chk("frames_differ_from_past", not sims or min(sims) >= 9, [round(x, 1) for x in sims[:5]], "avg nearest-frame dHash distance to past videos ≥ 9 bits")
    hard_fail = [c for c in checks if c["hard"] and not c["ok"]]
    rep = {"video": str(final), "duration": round(dur, 2), "passed": not hard_fail, "hard_failures": [c["check"] for c in hard_fail],
           "checks": checks, "frame_hashes": [f"{h_:016x}" for h_ in hashes], "voice_timing": voice["timing"],
           "mix": mix_stats, "plan": plan}
    (work / "qa_report.json").write_text(json.dumps(rep, indent=1, ensure_ascii=False, default=str), encoding="utf-8")
    md = [f"# QA report — {'PASS' if rep['passed'] else 'FAIL'}", "", f"Video: `{final.name}` · {dur:.1f}s · voice timing: {voice['timing']}", "",
          "| check | result | value | rule |", "|---|---|---|---|"]
    for c in checks:
        md.append(f"| {c['check']} | {'PASS' if c['ok'] else ('FAIL' if c['hard'] else 'WARN')} | {json.dumps(c['value'], ensure_ascii=False, default=str)[:80]} | {c['rule']} |")
    md += ["", "Self-review is still required: open the contact sheet + frames, then write review.md (see SKILL.md)."]
    (work / "qa_report.md").write_text("\n".join(md), encoding="utf-8")
    log(f"QA: {'PASS' if rep['passed'] else 'FAIL'} · hard failures: {rep['hard_failures'] or 'none'}")
    return rep


def contact_sheet(frames: list[Path], out: Path, labels: list[str] | None = None, cols=5) -> Path:
    ims = [Image.open(f).convert("RGB").resize((270, 480)) for f in frames]
    rows = (len(ims) + cols - 1) // cols
    sheet = Image.new("RGB", (270 * cols, 520 * rows), (12, 12, 14))
    d = ImageDraw.Draw(sheet)
    for i, im in enumerate(ims):
        x, y = (i % cols) * 270, (i // cols) * 520
        sheet.paste(im, (x, y))
        d.line([(x, y + 1480 / 4), (x + 269, y + 1480 / 4)], fill=(255, 60, 60), width=1)
        d.line([(x, y + 250 / 4), (x + 269, y + 250 / 4)], fill=(255, 60, 60), width=1)
        if labels:
            d.text((x + 6, y + 486), labels[i][:42], fill=(230, 230, 230))
    sheet.save(out)
    return out


__all__ = ["run_qa", "contact_sheet", "dhash", "ham", "FPS", "W"]
