"""render.py — fast parallel rendering: the timeline is built once in the parent, then forked workers render contiguous frame
ranges straight into their own ffmpeg (x264) pipes; segments are concatenated losslessly and muxed with the mixed audio."""
from __future__ import annotations

import multiprocessing as mp
import os
import subprocess
import time
from pathlib import Path

from .core import FPS, H, W, log

_TL = None


def grade_filter(dna: dict) -> str:
    g = dna.get("grade", {})
    return (f"eq=contrast={g.get('contrast', 1.04)}:saturation={g.get('saturation', 1.05)},"
            f"noise=alls={min(3, g.get('grain', 3))}:allf=u,format=yuv420p")


def _worker(args):
    i, f0, f1, out, vf, preset, crf, threads = args
    tl = _TL
    cmd = ["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
           "-vf", vf, "-c:v", "libx264", "-preset", preset, "-crf", str(crf), "-maxrate", "10M", "-bufsize", "20M",
           "-x264-params", "aq-mode=3", "-threads", str(threads), "-g", str(FPS * 2),
           "-color_primaries", "bt709", "-color_trc", "bt709", "-colorspace", "bt709", "-movflags", "+faststart", str(out)]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    t0 = time.time()
    for f in range(f0, f1):
        p.stdin.write(tl.frame(f / FPS).tobytes())
    p.stdin.close()
    if p.wait() != 0:
        raise RuntimeError(f"ffmpeg segment {i} failed")
    return i, f1 - f0, time.time() - t0


def render_video(tl, out: Path, t0=0.0, t1=None, workers=None, preset="veryfast", crf=20, label="render") -> dict:
    global _TL
    _TL = tl
    t1 = tl.duration if t1 is None else min(t1, tl.duration)
    F0, F1 = int(round(t0 * FPS)), int(round(t1 * FPS))
    nfr = F1 - F0
    cpu = os.cpu_count() or 2
    workers = workers or max(1, min(cpu, 8, nfr // 30 or 1))
    seg_dir = out.parent / f".seg_{out.stem}"
    seg_dir.mkdir(parents=True, exist_ok=True)
    bounds = [F0 + nfr * k // workers for k in range(workers + 1)]
    vf = grade_filter(tl.dna)
    jobs = [(k, bounds[k], bounds[k + 1], seg_dir / f"s{k:02d}.mp4", vf, preset, crf, 1 if workers > 1 else 0) for k in range(workers)
            if bounds[k + 1] > bounds[k]]
    ts = time.time()
    log(f"{label}: {nfr} frames ({nfr / FPS:.1f}s) on {len(jobs)} worker(s)")
    if len(jobs) > 1 and "fork" in mp.get_all_start_methods():
        with mp.get_context("fork").Pool(len(jobs)) as pool:
            res = pool.map(_worker, jobs)
    else:
        res = [_worker(j) for j in jobs]
    lst = seg_dir / "list.txt"
    lst.write_text("".join(f"file '{j[3].name}'\n" for j in jobs))
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", "-movflags", "+faststart", str(out)],
                   check=True, timeout=600)
    el = time.time() - ts
    log(f"{label}: done in {el:.1f}s ({nfr / max(el, 1e-6):.1f} fps)")
    for j in jobs:
        j[3].unlink(missing_ok=True)
    lst.unlink(missing_ok=True)
    try:
        seg_dir.rmdir()
    except OSError:
        pass
    return {"frames": nfr, "seconds": round(el, 2), "fps": round(nfr / max(el, 1e-6), 2), "workers": len(jobs), "per_worker": res}


def mux(video: Path, audio: Path, out: Path, t0=0.0, t1=None):
    cmd = ["ffmpeg", "-y", "-v", "error", "-i", str(video), "-ss", f"{t0:.3f}"]
    if t1:
        cmd += ["-t", f"{t1 - t0:.3f}"]
    cmd += ["-i", str(audio), "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-shortest",
            "-movflags", "+faststart", str(out)]
    subprocess.run(cmd, check=True, timeout=600)


def save_frames(tl, times, out_dir: Path, prefix="frame") -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    for k, t in enumerate(times):
        p = out_dir / f"{prefix}_{k:02d}_{t:05.2f}s.png"
        tl.frame(t).save(p)
        paths.append(p)
    return paths
