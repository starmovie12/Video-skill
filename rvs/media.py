"""media.py — footage-first editing.

Real visuals beat typography: trailers, clips, stills, product shots and B-roll go full-screen under the graphics, cut fast
(new shot every ~2 s on long beats, cuts land on spoken words), with camera punches and a legibility scrim.

  scan      project media (assets.media + ./media/ folder) → shots (ffmpeg scene detection) + thumbnails + media_sheet.jpg
  assign    per beat: Director-chosen media ("trailer.mp4#3", "trailer.mp4@12.5-15", "still.jpg", list, or "none") or auto
  sources   StillSource (cover-fit, focus) and ClipSource (sequential ffmpeg decode, slow-mo to fit, hold last frame)
  FootageBackground   switches sources inside a beat, camera-aware, dynamic (needs t)
  commons_search      free-licence images from Wikimedia Commons with author/licence credits
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageOps

from .core import FPS, H, W, RvsError, log, read_json, write_json

IMG_EXT = {".jpg", ".jpeg", ".png", ".webp"}
VID_EXT = {".mp4", ".mov", ".mkv", ".webm", ".m4v"}
MARGIN = 1.12       # stills: room for Ken Burns + camera moves
CLIP_MARGIN = 1.06  # clips: they already move; smaller plate = faster decode
UA = "ReviewVideoStudio/2.0 (https://github.com/starmovie12/Video-skill)"
FREE_LICENSES = re.compile(r"^(public domain|pd|cc0|cc[- ]by(-sa)?[- ]?\d|cc[- ]by(-sa)?$)", re.I)


def _probe(path: Path) -> dict:
    out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height,r_frame_rate:format=duration",
                          "-of", "json", str(path)], capture_output=True, text=True, timeout=60).stdout
    j = json.loads(out or "{}")
    st = (j.get("streams") or [{}])[0]
    num, den = (st.get("r_frame_rate") or "30/1").split("/")
    return {"w": st.get("width"), "h": st.get("height"), "fps": float(num) / float(den or 1), "duration": float(j.get("format", {}).get("duration", 0))}


def _shots(path: Path, dur: float, thr=0.3) -> list[tuple]:
    r = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(path), "-an", "-vf", f"scale=320:-2,select='gt(scene,{thr})',showinfo",
                        "-f", "null", "-"], capture_output=True, text=True, timeout=900).stderr
    cuts = sorted({round(float(m), 3) for m in re.findall(r"pts_time:([\d.]+)", r)})
    bounds = [0.0] + [c for c in cuts if 0.3 < c < dur - 0.3] + [dur]
    return [(a, b) for a, b in zip(bounds, bounds[1:]) if b - a >= 0.7]


def _frame_at(path: Path, t: float, w=270) -> Image.Image | None:
    out = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{t:.3f}", "-i", str(path), "-frames:v", "1", "-vf", f"scale={w}:-2", "-f", "image2pipe",
                          "-vcodec", "png", "-"], capture_output=True, timeout=60).stdout
    if not out:
        return None
    import io
    return Image.open(io.BytesIO(out)).convert("RGB")


def _stats(img: Image.Image) -> tuple[float, float]:
    a = np.asarray(img.convert("L"), np.float32) / 255
    detail = float(np.abs(np.diff(a, axis=1)).mean() + np.abs(np.diff(a, axis=0)).mean())
    return float(a.mean()), detail


def scan(project: dict, root: Path, work: Path) -> dict:
    """Catalogue every still and every shot of every clip. Cached by file size+mtime."""
    files = []
    for pat in (project.get("assets", {}) or {}).get("media", []) or []:
        p = root / pat
        files += sorted(root.glob(pat)) if any(ch in pat for ch in "*?[") else ([p] if p.exists() else [])
    md = root / "media"
    if md.is_dir():
        files += [p for p in sorted(md.iterdir()) if p.suffix.lower() in IMG_EXT | VID_EXT]
    files = list(dict.fromkeys(files))
    cache = read_json(work / "media_catalog.json", {"items": {}})
    credits = read_json(md / "credits.json", {}) if md.is_dir() else {}
    tdir = work / "media_thumbs"
    tdir.mkdir(parents=True, exist_ok=True)
    items = {}
    for f in files:
        key = str(f.relative_to(root))
        sig = f"{f.stat().st_size}-{int(f.stat().st_mtime)}"
        if key in cache["items"] and cache["items"][key].get("sig") == sig:
            items[key] = cache["items"][key]
            continue
        ext = f.suffix.lower()
        if ext in IMG_EXT:
            im = Image.open(f).convert("RGB")
            lum, det = _stats(im.resize((160, int(160 * im.height / im.width))))
            th = tdir / (re.sub(r"\W", "_", key) + ".jpg")
            ImageOps.fit(im, (270, 480), Image.Resampling.LANCZOS).save(th, quality=80)
            items[key] = {"kind": "image", "sig": sig, "w": im.width, "h": im.height, "lum": lum, "detail": det, "thumb": str(th),
                          "credit": credits.get(f.name)}
        elif ext in VID_EXT:
            info = _probe(f)
            shots = []
            for k, (a, b) in enumerate(_shots(f, info["duration"])):
                mid = (a + b) / 2
                fr = _frame_at(f, mid)
                if fr is None:
                    continue
                lum, det = _stats(fr)
                th = tdir / (re.sub(r"\W", "_", key) + f"_{k:03d}.jpg")
                ImageOps.fit(fr, (270, 480), Image.Resampling.LANCZOS).save(th, quality=80)
                shots.append({"id": k, "start": round(a, 3), "end": round(b, 3), "len": round(b - a, 3), "lum": lum, "detail": det, "thumb": str(th)})
            items[key] = {"kind": "video", "sig": sig, **info, "shots": shots, "credit": credits.get(f.name)}
            log(f"media: {key} → {len(shots)} shots")
    cat = {"items": items}
    write_json(work / "media_catalog.json", cat)
    return cat


def media_sheet(cat: dict, out: Path) -> Path | None:
    """Contact sheet of every still/shot with its reference label — the Director LOOKS at this to pick visuals per beat."""
    cells = []
    for key, it in cat["items"].items():
        if it["kind"] == "image":
            cells.append((key, it["thumb"]))
        else:
            for s in it["shots"]:
                cells.append((f"{key}#{s['id']} {s['start']:.1f}-{s['end']:.1f}s", s["thumb"]))
    if not cells:
        return None
    cols = 6
    rows = (len(cells) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * 180, rows * 350), (14, 14, 16))
    d = ImageDraw.Draw(sheet)
    for i, (lab, th) in enumerate(cells):
        x, y = (i % cols) * 180, (i // cols) * 350
        sheet.paste(Image.open(th).resize((180, 320)), (x, y))
        d.text((x + 4, y + 324), lab[:30], fill=(235, 235, 235))
    sheet.save(out, quality=85)
    return out


# ───────────────────────── assignment ─────────────────────────
REF = re.compile(r"^(?P<file>.+?)(?:#(?P<shot>\d+)|@(?P<a>[\d.]+)-(?P<b>[\d.]+))?$")


def parse_ref(ref, cat: dict) -> dict | None:
    """'media/x.mp4#3' | 'media/x.mp4@12-15' | 'media/x.jpg' |
    {"file": ..., "crop": [x0,y0,x1,y1], "fit": "cover"|"letterbox"|"rotate", "y": band centre}.
    fit "rotate" turns a landscape still/clip 90° so it fills the whole 9:16 frame (big top-creator trick for 16:9 footage)."""
    if isinstance(ref, dict):
        base = parse_ref(ref["file"], cat)
        if base is None:
            return None
        return dict(base, **{k: ref[k] for k in ("crop", "fit", "y") if k in ref})
    m = REF.match(ref.strip())
    if not m or m.group("file") not in cat["items"]:
        return None
    it = cat["items"][m.group("file")]
    if it["kind"] == "image":
        return {"file": m.group("file"), "kind": "image"}
    if m.group("shot") is not None:
        s = next((s for s in it["shots"] if s["id"] == int(m.group("shot"))), None)
        if s is None:
            return None
        return {"file": m.group("file"), "kind": "video", "start": s["start"], "end": s["end"]}
    if m.group("a"):
        return {"file": m.group("file"), "kind": "video", "start": float(m.group("a")), "end": float(m.group("b"))}
    return {"file": m.group("file"), "kind": "video", "start": 0.0, "end": it["duration"]}


def _pool(cat: dict) -> list[dict]:
    pool = []
    for key, it in cat["items"].items():
        if it["kind"] == "image":
            pool.append({"file": key, "kind": "image", "score": 1.0 + it["detail"] * 3})
        else:
            for s in it["shots"]:
                if s["lum"] < 0.06 or s["lum"] > 0.93 or s["len"] < 0.8:
                    continue  # black/white title cards, flashes, micro-shots
                pool.append({"file": key, "kind": "video", "start": s["start"] + 0.12, "end": s["end"] - 0.12,
                             "score": 1.2 + min(s["len"], 4) * 0.2 + s["detail"] * 3})
    return sorted(pool, key=lambda p: -p["score"])


def assign(project: dict, cat: dict, voice: dict, seg_target=2.2) -> dict[int, list]:
    """Per beat: [(t_local_start, source_dict)] segments. Long beats get several shots, cuts snapped to word starts."""
    if not cat["items"]:
        return {}
    pool = _pool(cat)
    used, out = 0, {}
    spans = voice["spans"]
    for i, b in enumerate(project["beats"]):
        ref = b.get("media", "auto")
        if ref == "none":
            continue
        t0 = 0.0 if i == 0 else spans[i]["t0"]
        t1 = spans[i + 1]["t0"] if i + 1 < len(spans) else voice["duration"] + 1
        dur = t1 - t0
        if ref != "auto":
            refs = ref if isinstance(ref, list) else [ref]
            srcs = [s for s in (parse_ref(r, cat) for r in refs) if s]
            if not srcs:
                raise RvsError("MEDIA_REF", f"beat {b.get('id', i)}: media {ref!r} not found — run `media scan` and use a label from media_sheet.jpg")
        else:
            if not pool:
                continue
            n = max(1, int(round(dur / seg_target))) if b.get("role") not in ("rating", "verdict") else 1
            srcs = []
            for _ in range(n):
                srcs.append(pool[used % len(pool)])
                used += 1
        # cut points at word starts nearest to equal splits
        wstarts = [w["t0"] - t0 for w in voice["words"] if w["beat"] == i]
        cuts = [0.0]
        for k in range(1, len(srcs)):
            target = dur * k / len(srcs)
            cuts.append(min(wstarts, key=lambda s: abs(s - target)) if wstarts else target)
        cuts = sorted(set(round(c, 3) for c in cuts))
        out[i] = [(c, dict(s, need=(cuts[k + 1] if k + 1 < len(cuts) else dur) - c)) for k, (c, s) in enumerate(zip(cuts, srcs))]
    return out


# ───────────────────────── sources ─────────────────────────
class StillSource:
    """A still on the 9:16 plate.
    cover     — fill the frame (optionally from a `crop` region [x0,y0,x1,y1], normalised) — punch-in on a face/detail.
    letterbox — keep the WHOLE wide shot sharp across the frame, over a blurred, darkened copy of itself (the standard way to
                show 16:9 / 2.39:1 film frames in a vertical Reel). Auto for very wide images unless a crop is given.
                `y` = vertical centre of the sharp band (0…1, default 0.46); push it down (≈0.62) when the scene's big
                text sits in the upper half, so the text never covers faces."""
    baked = True  # the legibility scrim is baked into the plate once (saves a full-frame composite per frame)

    def __init__(self, path: Path, focus=(0.5, 0.4), scrim: Image.Image | None = None, crop=None, fit=None, y=None, size=None):
        from PIL import ImageEnhance, ImageFilter
        bw, bh = size or (int(W * MARGIN), int(H * MARGIN))
        src = Image.open(path).convert("RGB")
        if crop:
            x0, y0, x1, y1 = crop
            src = src.crop((int(x0 * src.width), int(y0 * src.height), int(x1 * src.width), int(y1 * src.height)))
        if fit == "rotate":
            if src.width > src.height:
                src = src.rotate(-90, expand=True)
            fit = "cover"
        fit = fit or ("letterbox" if (not crop and src.width / src.height > 1.25 and bh > bw) else "cover")
        if fit == "letterbox":
            back = ImageOps.fit(src, (bw // 4, bh // 4), Image.Resampling.BILINEAR, centering=focus).filter(ImageFilter.GaussianBlur(9))
            back = ImageEnhance.Brightness(ImageEnhance.Color(back).enhance(1.25)).enhance(0.5).resize((bw, bh), Image.Resampling.BICUBIC)
            fw = int(bw * 1.0)
            fh = int(fw * src.height / src.width)
            if fh > bh * 0.62:  # very tall: limit height
                fh = int(bh * 0.62)
                fw = int(fh * src.width / src.height)
            fg = src.resize((fw, fh), Image.Resampling.LANCZOS)
            cy = min(1 - fh / 2 / bh, max(fh / 2 / bh, float(y) if y is not None else 0.46))  # keep the band inside the plate
            back.paste(fg, ((bw - fw) // 2, int(bh * cy - fh / 2)))
            self.img = back
        else:
            self.img = ImageOps.fit(src, (bw, bh), Image.Resampling.LANCZOS, centering=focus)
        self.fit = fit
        if scrim is not None:
            im = self.img.convert("RGBA")
            sc = scrim.resize((bw, bh), Image.Resampling.BILINEAR)
            if fit == "letterbox":  # lighter scrim: the sharp band must stay bright
                sc.putalpha(sc.getchannel("A").point(lambda v: int(v * 0.7)))
            im.alpha_composite(sc)
            self.img = im.convert("RGB")

    def frame(self, tau):
        return self.img


class ClipSource:
    baked = False

    """Sequential decoder of one shot: cover-cropped to the 9:16 plate, slow-mo (≥0.5×) if the shot is shorter than the beat,
    holds the last frame after the shot ends. Re-opens itself after fork (each worker owns its own ffmpeg)."""

    def __init__(self, path: Path, start: float, end: float, need: float, grade="", fit="cover", size=None, y=None):
        self.path, self.start, self.end = path, start, end
        L = max(0.2, end - start)
        self.rate = max(0.5, min(1.0, L / max(0.1, need)))  # <1 → slow motion
        bw, bh = size or (int(W * CLIP_MARGIN), int(H * CLIP_MARGIN))
        self.bw, self.bh = int(bw) // 2 * 2, int(bh) // 2 * 2
        self.grade, self.fit, self.y = grade, fit or "cover", (0.46 if y is None else float(y))
        self.proc, self.next_i, self.pid, self.last = None, None, None, None

    def _open(self, i):
        if self.proc:
            self.proc.kill()
        src_t = self.start + i / FPS * self.rate
        head = f"setpts=(PTS-STARTPTS)/{self.rate:.4f},fps={FPS}," + ("transpose=1," if self.fit == "rotate" else "")
        cover = f"scale={self.bw}:{self.bh}:force_original_aspect_ratio=increase:flags=bilinear,crop={self.bw}:{self.bh}"
        if self.fit == "letterbox":  # whole wide frame sharp in a band, over a blurred darker copy of itself
            vf = (head + f"split[a][b];[a]{cover},boxblur=20:2,eq=brightness=-0.16:saturation=1.2[bg];"
                  f"[b]scale={self.bw}:-2:flags=bilinear[fg];[bg][fg]overlay=0:(H-h)*{self.y:.3f}")
        else:
            vf = head + cover
        vf += (f",{self.grade}" if self.grade else "")
        self.proc = subprocess.Popen(["ffmpeg", "-v", "quiet", "-threads", "1", "-ss", f"{src_t:.3f}", "-i", str(self.path), "-an", "-vf", vf,
                                      "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        self.next_i, self.pid = i, os.getpid()

    def frame(self, tau):
        i = max(0, int(round(tau * FPS)))
        if (self.start + i / FPS * self.rate) >= self.end and self.last is not None:
            return self.last  # hold
        if self.proc is None or self.pid != os.getpid() or i != self.next_i:
            if self.last is not None and i == (self.next_i or 0) - 1 and self.pid == os.getpid():
                return self.last
            self._open(i)
        n = self.bw * self.bh * 3
        buf = self.proc.stdout.read(n)
        if len(buf) < n:
            if self.last is None:
                self.last = Image.new("RGB", (self.bw, self.bh), (0, 0, 0))
            return self.last
        self.next_i = i + 1
        self.last = Image.frombuffer("RGB", (self.bw, self.bh), buf, "raw", "RGB", 0, 1).copy()
        return self.last


class FootageBackground:
    """Dynamic background: list of (t_local, source). Camera-aware like Background; adds a legibility scrim."""
    dynamic = True

    def __init__(self, segments, scrim=0.55, depth=0.9, dark=True, floor=0.42):
        self.segments, self.depth, self.ps, self.margin = segments, depth, 1.0, MARGIN
        g = np.linspace(0, 1, H, dtype=np.float32)
        # top band (status bar/badges), bottom band (captions + IG UI) and a uniform floor so mid-screen text reads on busy footage.
        # Clean looks (little text on screen) use a low floor: the footage stays bright and full-colour like top creators' shorts.
        a = (np.clip(1 - g / 0.28, 0, 1) ** 1.6 * 0.55 + np.clip((g - 0.45) / 0.55, 0, 1) ** 1.3 * 0.75) * scrim + floor * scrim
        col = (8, 8, 12) if dark else (250, 248, 244)
        self.scrim = Image.new("RGBA", (W, H), col + (0,))
        self.scrim.putalpha(Image.fromarray((np.clip(a, 0, 1)[:, None].repeat(W, 1) * 255).astype(np.uint8)))
        self._img = None

    @property
    def img(self):  # representative plate (for frosted glass)
        if self._img is None:
            self._img = self.segments[0][1].frame(0.4).copy()
        return self._img

    def cut_times(self):
        return [t for t, _ in self.segments[1:]]

    def render(self, cam, t=0.0):
        k = max(i for i, (ts, _) in enumerate(self.segments) if ts <= max(0.0, t) or i == 0)
        ts, src = self.segments[k]
        im = src.frame(max(0.0, t - ts))
        zoom, px, py, rot = cam._st
        z = 1 + (zoom - 1) * self.depth
        bw, bh = im.size
        mg = bw / W
        w, h = bw / mg / z, bh / mg / z
        cx = bw / 2 - px * self.depth * 0.5
        cy = bh / 2 - py * self.depth * 0.5
        box = (max(0.0, cx - w / 2), max(0.0, cy - h / 2), min(bw, cx + w / 2), min(bh, cy + h / 2))
        fr = im.resize((W, H), Image.Resampling.BILINEAR, box=box).convert("RGBA")
        if not getattr(src, "baked", False):
            fr.alpha_composite(self.scrim)
        return fr


CLEAN_LOOKS = ("clean", "rush", "bar")


def build_background(segs, root: Path, dna: dict, dark=True, focus=(0.5, 0.4), heavy_text=True):
    """heavy_text=False (clean looks, footage_clean scenes): a light scrim so the footage stays bright, full-colour."""
    g = dna.get("grade", {})
    grade = f"eq=contrast={g.get('contrast', 1.06) + 0.04:.3f}:saturation={g.get('saturation', 1.08) + 0.07:.3f}"
    if heavy_text:
        fb = FootageBackground([], scrim=0.62 if dark else 0.35, dark=dark)
    else:
        fb = FootageBackground([], scrim=0.42, dark=dark, floor=0.05)
    for t, s in segs:
        fb.segments.append((t, make_source(root, s, grade, focus, fb.scrim)))
    return fb


def make_source(root: Path, s: dict, grade="", focus=(0.5, 0.4), scrim=None, size=None):
    p = root / s["file"]
    if s["kind"] == "image":
        return StillSource(p, focus, scrim, crop=s.get("crop"), fit=s.get("fit"), y=s.get("y"), size=size)
    return ClipSource(p, s["start"], s["end"], s.get("need", 2.0), grade, fit=s.get("fit") or "cover", size=size, y=s.get("y"))


class SplitBackground:
    """Top-creator split layout: footage in a band at the top (16:9 fits with almost no crop), and below it either the
    operator's own face-cam (host video, time-synced to the voice) or a solid panel for the beat's words."""
    dynamic = True

    def __init__(self, band_segments, band_h, panel, host=None, host_t0=0.0):
        self.band, self.band_h, self.panel, self.host, self.host_t0 = band_segments, int(band_h), panel, host, host_t0
        self._img = None

    @property
    def img(self):
        if self._img is None:
            self._img = self.render(None, 0.4).convert("RGB")
        return self._img

    def cut_times(self):
        return [t for t, _ in self.band[1:]]

    def render(self, cam, t=0.0):
        fr = self.panel.copy()
        if self.band:
            k = max(i for i, (ts, _) in enumerate(self.band) if ts <= max(0.0, t) or i == 0)
            ts, src = self.band[k]
            im = src.frame(max(0.0, t - ts))
            if im.size != (W, self.band_h):
                im = ImageOps.fit(im, (W, self.band_h), Image.Resampling.BILINEAR)
            fr.paste(im.convert("RGBA"), (0, 0))
        if self.host is not None:
            hi = self.host.frame(max(0.0, t))
            hh = H - self.band_h
            if hi.size != (W, hh):
                hi = ImageOps.fit(hi, (W, hh), Image.Resampling.BILINEAR)
            fr.paste(hi.convert("RGBA"), (0, self.band_h))
        return fr


# ───────────────────────── Wikimedia Commons (free licences) ─────────────────────────
def _get_json(url: str, tries=6):
    for k in range(tries):
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        try:
            with urllib.request.urlopen(req, timeout=40) as r:
                j = json.loads(r.read())
            if "error" in j and k + 1 < tries:  # e.g. maxlag / ratelimited returned as JSON
                time.sleep(5)
                continue
            return j
        except urllib.error.HTTPError as e:
            if e.code == 429 and k + 1 < tries:
                wait = max(5, int(e.headers.get("Retry-After", "5") or 5)) * (k + 1)
                log(f"commons: rate-limited, waiting {wait}s")
                time.sleep(min(wait, 60))
                continue
            raise
    raise RvsError("COMMONS", "rate-limited")


def _download(url: str, out: Path, tries=4) -> bool:
    for k in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA}), timeout=60) as r:
                out.write_bytes(r.read())
            return True
        except urllib.error.HTTPError as e:
            if e.code == 429 and k + 1 < tries:
                time.sleep(min(30, int(e.headers.get("Retry-After", "5") or 5)))
                continue
            log(f"commons: download failed {e.code} {url[:80]}")
            return False
    return False


def commons_search(query: str, dest: Path, n=8, min_width=900) -> list[dict]:
    """Download up to n freely licensed images (PD / CC0 / CC BY / CC BY-SA) for `query` into dest, recording credits."""
    dest.mkdir(parents=True, exist_ok=True)
    api = ("https://commons.wikimedia.org/w/api.php?action=query&format=json&generator=search&gsrnamespace=6&gsrlimit=40"
           f"&gsrsearch={urllib.parse.quote(query + ' filetype:bitmap')}&prop=imageinfo&iiprop=url|size|mime|extmetadata&iiurlwidth=1280"
           "&iiextmetadatafilter=LicenseShortName|Artist|LicenseUrl|ImageDescription")
    res = _get_json(api)
    credits = read_json(dest / "credits.json", {})
    got = []
    for p in sorted(res.get("query", {}).get("pages", {}).values(), key=lambda p: p.get("index", 0)):
        ii = (p.get("imageinfo") or [{}])[0]
        meta = ii.get("extmetadata", {})
        lic = re.sub("<[^>]+>", "", meta.get("LicenseShortName", {}).get("value", "")).strip()
        if not FREE_LICENSES.search(lic) or ii.get("width", 0) < min_width or "image/" not in ii.get("mime", ""):
            continue
        name = re.sub(r"[^\w.-]", "_", p["title"].split(":", 1)[1])[:80]
        if not name.lower().endswith((".jpg", ".jpeg", ".png", ".webp")):
            name += ".jpg"
        url = ii.get("thumburl") or ii["url"]  # 1280 px = a standard Wikimedia thumbnail step (non-standard sizes get 429)
        if not _download(url, dest / name):
            continue
        artist = re.sub("<[^>]+>", "", meta.get("Artist", {}).get("value", "")).strip()[:120]
        credits[name] = {"title": p["title"], "author": artist or "unknown", "license": lic,
                         "license_url": meta.get("LicenseUrl", {}).get("value", ""), "source": ii.get("descriptionurl", "")}
        got.append({"file": name, **credits[name]})
        log(f"commons: {name} · {lic} · {artist[:40]}")
        time.sleep(1.0)  # be polite (Wikimedia API etiquette)
        if len(got) >= n:
            break
    write_json(dest / "credits.json", credits)
    return got


__all__ = ["scan", "assign", "media_sheet", "build_background", "commons_search", "StillSource", "ClipSource", "FootageBackground"]
