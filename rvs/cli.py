"""cli.py — one command per stage, plus `make` (everything). Run from anywhere:  python /path/to/skill/run.py make <project_dir>"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

from .core import FPS, RvsError, log, read_json, write_json

CATS = ("movie_review", "product", "facts", "story", "software", "game")


def _paths(project_dir: str):
    root = Path(project_dir).resolve()
    pj = root / "project.json" if root.is_dir() else root
    root = pj.parent
    work, out = root / "work", root / "out"
    work.mkdir(exist_ok=True)
    out.mkdir(exist_ok=True)
    return root, pj, work, out


def load_project(pj: Path) -> dict:
    from .lint import lint
    p = json.loads(pj.read_text(encoding="utf-8"))
    errs, warns = lint(p)
    for w in warns:
        log(f"lint WARN: {w}")
    if errs:
        for e in errs:
            log(f"lint ERROR: {e}")
        raise RvsError("LINT", f"{len(errs)} script/plan error(s) — fix project.json")
    return p


def stage_voice(p, work):
    from .audio import voice_with_duration_control
    return voice_with_duration_control(p, work)


def stage_dna(p, root, work, reroll=False):
    from .dna import generate
    from .timeline import load_assets
    f = work / "dna.json"
    if f.exists() and not reroll:
        return read_json(f)
    assets = load_assets(p, root)
    d = generate(p, assets.get("poster"), seed_extra=str(time.time()) if reroll else "")
    write_json(f, d)
    return d


def build_timeline(p, root, voice, dna):
    from .timeline import Timeline, load_assets
    return Timeline(p, voice, dna, load_assets(p, root)).build_all()


def key_times(tl, n_extra=3):
    ts = [0.35, 1.0]
    for s in tl.scenes:
        ts.append(round(min(s.t1 - 0.15, s.t0 + (s.t1 - s.t0) * 0.8), 2))
    return ts


def cmd_proof(a):
    from .qa import contact_sheet
    from .render import render_video, save_frames
    root, pj, work, out = _paths(a.project)
    p = load_project(pj)
    voice = stage_voice(p, work)
    dna = stage_dna(p, root, work, a.reroll)
    tl = build_timeline(p, root, voice, dna)
    write_json(work / "plan.json", tl.summary())
    times = key_times(tl)
    frames = save_frames(tl, times, work / "proof_frames", "proof")
    contact_sheet(frames, work / "proof_contact_sheet.png", [f"{t:.1f}s" for t in times])
    sec = float(p.get("proof_sec", 6.0))
    render_video(tl, work / "proof_video.mp4", 0, sec, workers=a.workers, label="proof")
    from .audio import build_mix
    stats = build_mix(work, voice, tl.duration, dna, tl.cues, tl.music_sections(), [t["t"] for t in tl.trans], p.get("assets", {}).get("music"))
    from .render import mux
    mux(work / "proof_video.mp4", work / "mix.wav", out / "proof.mp4", 0, sec)
    print(json.dumps({"proof_video": str(out / "proof.mp4"), "contact_sheet": str(work / "proof_contact_sheet.png"),
                      "frames": [str(f) for f in frames], "style_dna": dna["dna_sig"], "music": stats["music_source"],
                      "next": "OPEN the contact sheet + frames, list weaknesses in work/proof_review.md, fix, then run make"}, indent=1, ensure_ascii=False))


def cmd_make(a):
    from .audio import build_mix
    from .dna import save_ledger_entry
    from .qa import contact_sheet, run_qa
    from .render import mux, render_video
    t_start = time.time()
    root, pj, work, out = _paths(a.project)
    p = load_project(pj)
    voice = stage_voice(p, work)
    dna = stage_dna(p, root, work, a.reroll)
    tl = build_timeline(p, root, voice, dna)
    write_json(work / "plan.json", tl.summary())
    stats = build_mix(work, voice, tl.duration, dna, tl.cues, tl.music_sections(), [t["t"] for t in tl.trans], p.get("assets", {}).get("music"))
    rinfo = render_video(tl, work / "video.mp4", workers=a.workers, preset=a.preset)
    slug = p.get("id") or pj.parent.name
    final = out / f"{slug}.mp4"
    mux(work / "video.mp4", work / "mix.wav", final)
    times = key_times(tl)
    qdir = work / "qa_frames"
    qdir.mkdir(exist_ok=True)
    for f in qdir.glob("*.png"):
        f.unlink()
    frames = []
    for k, t in enumerate(times):
        fp = qdir / f"qa_{k:02d}_{t:05.2f}s.png"
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", f"{t:.3f}", "-i", str(final), "-frames:v", "1", str(fp)], check=True, timeout=60)
        frames.append(fp)
    sheet = contact_sheet(frames, out / f"{slug}_contact_sheet.png",
                          [f"{t:.1f}s" if k < 2 else f"{t:.1f}s {tl.plan[k - 2]['archetype']}" for k, t in enumerate(times)])
    rep = run_qa(work, p, tl, final, voice, stats, frames[2:])
    shutil.copy(work / "qa_report.md", out / f"{slug}_qa.md")
    save_ledger_entry({"id": slug, "title": p.get("title"), "category": p.get("category"), "date": time.strftime("%Y-%m-%d %H:%M"),
                       "dna_sig": dna["dna_sig"], "frame_hashes": rep["frame_hashes"], "qa_passed": rep["passed"],
                       "plan": [(x["archetype"], x["variant"]) for x in tl.plan]})
    total = time.time() - t_start
    summary = {"video": str(final), "contact_sheet": str(sheet), "qa": "PASS" if rep["passed"] else "FAIL", "hard_failures": rep["hard_failures"],
               "duration_sec": rep["duration"], "render": {"seconds": rinfo["seconds"], "fps": rinfo["fps"], "workers": rinfo["workers"]},
               "total_pipeline_sec": round(total, 1), "voice": f"{voice['engine']} · {voice['timing']}", "music": stats["music_source"],
               "style": dna["dna_sig"], "frames_for_self_review": [str(f) for f in frames],
               "next": "OPEN contact sheet + frames, write work/review.md (## Weaknesses), then `deliver`"}
    write_json(work / "make_summary.json", summary)
    print(json.dumps(summary, indent=1, ensure_ascii=False))
    if not rep["passed"] and not a.allow_fail:
        sys.exit(3)


def cmd_deliver(a):
    root, pj, work, out = _paths(a.project)
    rep = read_json(work / "qa_report.json")
    rv = work / "review.md"
    if not rep:
        raise RvsError("NO_QA", "run make first")
    if not rep["passed"]:
        raise RvsError("QA_FAIL", f"QA failed: {rep['hard_failures']} — fix and re-render; never deliver a failing video")
    if not rv.exists() or rv.stat().st_mtime < Path(rep["video"]).stat().st_mtime:
        raise RvsError("NO_REVIEW", "write work/review.md AFTER looking at the frames (honest self-review gate)")
    txt = rv.read_text(encoding="utf-8")
    sec = txt.split("## Weaknesses", 1)[-1].split("\n## ", 1)[0] if "## Weaknesses" in txt else ""
    weak = [ln for ln in sec.splitlines() if ln.strip().startswith("- ")]
    if len(weak) < 2:
        raise RvsError("REVIEW_SHALLOW", "review.md needs a '## Weaknesses' section with ≥2 honest bullet points")
    print(json.dumps({"deliver": rep["video"], "review": str(rv), "weaknesses_listed": len(weak)}, indent=1))


def cmd_dna(a):
    from .dna import describe
    root, pj, work, out = _paths(a.project)
    p = load_project(pj)
    d = stage_dna(p, root, work, a.reroll)
    print(describe(d))


def cmd_voice(a):
    root, pj, work, out = _paths(a.project)
    v = stage_voice(load_project(pj), work)
    print(json.dumps({k: v[k] for k in ("engine", "voice", "rate", "timing", "duration")}, indent=1))


def cmd_lint(a):
    from .lint import lint
    root, pj, work, out = _paths(a.project)
    errs, warns = lint(json.loads(pj.read_text(encoding="utf-8")))
    print(json.dumps({"errors": errs, "warnings": warns}, indent=1, ensure_ascii=False))
    sys.exit(1 if errs else 0)


def cmd_refs(a):
    from .dna import intake_references
    t = intake_references(Path(a.folder))
    print(json.dumps({"refs": len(t.get("refs", [])), "weights": t.get("weights", {})}, indent=1))


def cmd_feedback(a):
    from .dna import feedback
    root, pj, work, out = _paths(a.project)
    d = read_json(work / "dna.json")
    feedback(d, a.approve, a.note or "")
    print("taste memory updated")


def cmd_doctor(a):
    import shutil as sh
    from PIL import features
    rep = {"ffmpeg": bool(sh.which("ffmpeg")), "ffprobe": bool(sh.which("ffprobe")), "raqm (Devanagari shaping)": features.check("raqm")}
    for m in ("numpy", "edge_tts", "kokoro_onnx", "aiohttp"):
        try:
            __import__(m)
            rep[m] = True
        except ImportError:
            rep[m] = False
    import os
    rep["cpu"] = os.cpu_count()
    print(json.dumps(rep, indent=1))


def cmd_new(a):
    src = Path(__file__).resolve().parent.parent / "templates" / f"{a.category}.json"
    dst = Path(a.dir)
    dst.mkdir(parents=True, exist_ok=True)
    shutil.copy(src, dst / "project.json")
    print(f"created {dst / 'project.json'} — fill facts, script beats and assets")


def main(argv=None):
    ap = argparse.ArgumentParser(prog="rvs", description="Review Video Studio — motion-designed Reels with a unique look per video")
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name, fn in (("make", cmd_make), ("proof", cmd_proof), ("dna", cmd_dna), ("voice", cmd_voice), ("lint", cmd_lint),
                     ("deliver", cmd_deliver), ("feedback", cmd_feedback)):
        s = sub.add_parser(name)
        s.add_argument("project")
        s.set_defaults(fn=fn)
        if name in ("make", "proof", "dna"):
            s.add_argument("--reroll", action="store_true", help="generate a fresh Style DNA")
        if name in ("make", "proof"):
            s.add_argument("--workers", type=int, default=None)
        if name == "make":
            s.add_argument("--preset", default="veryfast")
            s.add_argument("--allow-fail", action="store_true")
        if name == "feedback":
            g = s.add_mutually_exclusive_group(required=True)
            g.add_argument("--approve", action="store_true")
            g.add_argument("--reject", dest="approve", action="store_false")
            s.add_argument("--note", default="")
    s = sub.add_parser("refs")
    s.add_argument("folder")
    s.set_defaults(fn=cmd_refs)
    s = sub.add_parser("doctor")
    s.set_defaults(fn=cmd_doctor)
    s = sub.add_parser("new")
    s.add_argument("category", choices=CATS)
    s.add_argument("dir")
    s.set_defaults(fn=cmd_new)
    a = ap.parse_args(argv)
    try:
        a.fn(a)
    except RvsError as e:
        log(f"ERROR {e}")
        sys.exit(2)


__all__ = ["main", "FPS"]
