"""timeline.py — project.json + voice timing + Style DNA → a deterministic Timeline (scenes, transitions, captions, SFX cues,
music sections). frame(t) is a pure function, so frames can be rendered in parallel worker processes."""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

from . import scenes as S
from .captions import Captioner
from .core import FPS, H, MOTION, W, Rng, RvsError, log, rgba
from .engine import TRANSITION_SFX, Scene, transition

ROLE_ALIASES = S.ROLE_DEFAULTS


def load_assets(project: dict, root: Path) -> dict:
    # end-card line: channel handle + any disclosure (India IT Rules 2026: synthetic/AI voice must be labelled)
    a = {"root": root, "handle": " · ".join(x for x in ((project.get("channel") or {}).get("handle"), project.get("disclosure")) if x) or None}
    asd = project.get("assets", {}) or {}
    if asd.get("poster"):
        pth = (root / asd["poster"]) if not Path(asd["poster"]).is_absolute() else Path(asd["poster"])
        if not pth.exists():
            raise RvsError("ASSET_MISSING", f"poster not found: {pth}")
        a["poster"] = Image.open(pth).convert("RGB")
    if asd.get("focus"):
        a["focus"] = [tuple(b) for b in asd["focus"]]
    if asd.get("product"):
        a["product"] = Image.open(root / asd["product"]).convert("RGBA")
    if asd.get("host"):  # the operator's own face-cam recording (vertical video); its audio is the voice-over
        hp = (root / asd["host"]) if not Path(asd["host"]).is_absolute() else Path(asd["host"])
        if not hp.exists():
            raise RvsError("ASSET_MISSING", f"host video not found: {hp}")
        a["host"] = {"path": hp, "offset": float(asd.get("host_offset", 0.0))}
    a["series"] = project.get("series") or S.SERIES_DEFAULT.get(project.get("pillar", ""), "SCENE SAMJHO")
    return a


GRAPHIC = ("stat_counter", "list_reveal", "split_compare", "timeline", "rating_meter", "verdict_stamp")


def apply_look(look: str, arch: str, i: int, n: int, has_media: bool, host: bool, kept: list) -> str:
    """Map a beat's archetype onto the video's LOOK (the edit format). poster = designed kinetic-type cards (the old default);
    clean / rush / bar = full-bleed bright footage with only the number or name on screen, at most ONE graphic card;
    split = footage band on top + the operator's face-cam (or a word panel) below."""
    if look in (None, "", "poster") or arch in ("hook_slam", "cta_loop"):
        return arch
    if look == "split":
        return "split_top" if has_media else ("host_cam" if host else arch)
    if host and i % 3 == 1:  # back to the host between cutaways (top creators' rhythm)
        return "host_cam"
    if not has_media:
        return arch
    if arch in GRAPHIC and not kept:
        kept.append(arch)
        return arch
    return "footage_clean"


def _build(ctx, scn):
    S.ARCH[ctx.beat["archetype"]]["fn"](ctx, scn)
    S.add_stickers(ctx, scn)
    if getattr(scn.bg, "dynamic", False):  # footage cuts land on words → camera kick + swish
        for tc in scn.bg.cut_times():
            scn.cam.punch(tc + 0.02, 0.07)
            scn.cue(tc - 0.06, "swish", 0.6)
        S.add_grade_fx(ctx, scn)


class Timeline:
    def __init__(self, project: dict, voice: dict, dna: dict, assets: dict):
        self.project, self.voice, self.dna, self.assets = project, voice, dna, assets
        beats = project["beats"]
        spans = voice["spans"]
        self.duration = round(spans[-1]["t1"] + float(project.get("tail_sec", 0.9)), 3)
        rng = Rng(dna["seed"] + 77)
        has_poster = assets.get("poster") is not None
        used = []
        facts = dict(project.get("facts", {}))
        facts.setdefault("title", project.get("title", ""))
        variants = dna.setdefault("variants", {})
        variants.setdefault("hook_slam", dna["opening"])
        self.scenes = []
        self.plan = []
        kept_graphic = []
        if dna.get("look") == "bar":
            variants["footage_clean"] = "news"  # the label variant would sit under the series bar
        # scene boundaries = voice beat starts, snapped onto the music beat grid (±0.2 s) → cuts land on the beat
        bpm, off = assets.get("beat_grid") or (dna.get("bpm") or 0, 0.0)
        bounds = [0.0] + [sp["t0"] for sp in spans[1:]]
        self.snapped = 0
        if bpm:
            per = 60.0 / bpm
            for k in range(1, len(bounds)):
                cand = off + round((bounds[k] - off) / per) * per
                lo = bounds[k - 1] + 0.8
                hi = (bounds[k + 1] - 0.8) if k + 1 < len(bounds) else self.duration - 0.8
                if abs(cand - bounds[k]) <= 0.2 and lo < cand < hi:
                    bounds[k] = round(cand, 3)
                    self.snapped += 1
        bounds.append(self.duration)
        for i, (b, sp) in enumerate(zip(beats, spans)):
            arch = b.get("archetype", "auto")
            if arch in ("auto", None, "") or arch not in S.ARCH:
                if arch not in ("auto", None, "") and arch not in S.ARCH:
                    log(f"beat {b.get('id', i)}: unknown archetype '{arch}' → Director picks by role")
                role = b.get("role", "line")
                arch = ROLE_ALIASES.get(role) if ROLE_ALIASES.get(role) in S.ARCH else None
                if arch is None or (used and used[-1] == arch) or used.count(arch) >= 2:
                    arch = S.choose_archetype(role, dna["category"], used, rng, has_poster)
            spec = S.ARCH[arch]
            if "poster" in spec["needs"] and not has_poster:
                arch = "kinetic_line" if arch != "poster_hero" else "fact_bomb" if b.get("data", {}).get("big") else "kinetic_line"
            if arch == "pros_cons" and not (b.get("data", {}).get("pros") or b.get("data", {}).get("cons")):
                log(f"beat {b.get('id', i)}: pros_cons without data → kinetic_line (never an empty card)")
                arch = "kinetic_line"
            if arch not in variants:
                variants[arch] = rng.choice(list(S.ARCH[arch]["variants"]))
            if not b.get("keep_archetype"):
                arch = apply_look(dna.get("look"), arch, i, len(beats), i in (assets.get("media_segments") or {}), bool(assets.get("host")),
                                  kept_graphic)
                if arch not in variants:
                    variants[arch] = rng.choice(list(S.ARCH[arch]["variants"]))
            used.append(arch)
            t0, t1 = bounds[i], bounds[i + 1]
            beat = dict(b, archetype=arch, _t0=t0)
            if arch == "split_top" and not assets.get("host"):
                beat["captions"] = False  # the lower panel already shows the words
            if i == 0 and arch != "hook_slam" and b.get("role") == "hook":
                beat["archetype"] = "hook_slam"
            words = [dict(w, t0=round(w["t0"] - t0, 3), t1=round(w["t1"] - t0, 3)) for w in voice["words"] if w["beat"] == i]
            ctx = S.Ctx(dna, beat, words, t1 - t0, i, len(beats), assets, facts)
            sc = Scene(i, t0, t1, beat["archetype"], (lambda c: (lambda scn: _build(c, scn)))(ctx),
                         {"variant": ctx.variant, "role": b.get("role"), "id": b.get("id", f"b{i + 1}"), "captions": ctx.cap_on})
            self.scenes.append(sc)
            self.plan.append({"id": sc.meta["id"], "role": b.get("role"), "archetype": beat["archetype"],
                              "variant": variants.get(beat["archetype"]) if not b.get("variant") else b["variant"],
                              "t0": round(t0, 3), "t1": round(t1, 3), "captions": ctx.cap_on})
        # transitions at every boundary — never a plain hard cut
        tr_dur = {"snappy": 0.32, "elastic": 0.4, "smooth": 0.55, "heavy": 0.36, "glitchy": 0.26}[dna["motion"]]
        vocab = list(dna["transitions"])
        rng.shuffle(vocab)
        self.trans = []
        uses = {v: 0 for v in vocab}
        last = None
        for i in range(1, len(self.scenes)):
            b = self.scenes[i].t0
            k = beats[i].get("transition_in")
            if not k:  # round-robin: least-used first, never twice in a row
                k = min([v for v in vocab if v != last] or vocab, key=lambda v: (uses[v], vocab.index(v)))
            uses[k] = uses.get(k, 0) + 1
            last = k
            d = tr_dur * (1.25 if k in ("ink", "luma_fade", "iris") else 1.0)
            self.trans.append({"t": b, "kind": k, "dur": d, "a": i - 1, "b": i, "dir": rng.choice([-1, 1]), "seed": rng.randint(0, 99)})
        # captions: only for words whose beat shows captions
        cap_beats = {i for i, s in enumerate(self.scenes) if s.meta["captions"]}
        cwords = [dict(w, caption=w["beat"] in cap_beats) for w in voice["words"]]
        self.captions = Captioner(cwords, dna)
        self.progress = dna.get("progress_bar", (dna["seed"] % 3) == 0)
        self.series_bar = self._series_bar() if dna.get("look") == "bar" else None

    def _series_bar(self):
        """Persistent series header (top creators keep one: "NETFLIX · MOST WATCHED SERIES", "1 MIN REVIEW")."""
        from .typo import text_sprite
        p, F = self.dna["palette"], self.dna["fonts"]
        title = text_sprite(str(self.assets.get("series", "SCENE SAMJHO")).upper(), F["hero"], 92, color=p["accent"], box=(1000, 130),
                            max_lines=1, max_px=96, role="label", stroke=0.05)
        bar = Image.new("RGBA", (W, title.h + 36), (8, 8, 12, 225))
        bar.alpha_composite(title.img, ((W - title.w) // 2, 18))
        return bar

    # ── build everything in the parent (cues for the mix, text boxes for QA); workers inherit via fork ──
    def build_all(self):
        for s in self.scenes:
            s.ensure()
        cues = [c for s in self.scenes for c in s.cues]
        for tr in self.trans:
            cues.append({"t": round(tr["t"] - tr["dur"] * 0.45, 3), "kind": TRANSITION_SFX.get(tr["kind"], "whoosh"), "gain": 0.75,
                         "pan": 0.3 * tr["dir"], "scene": tr["b"]})
        cues.sort(key=lambda c: c["t"])
        # de-clutter: max one SFX per 90 ms of the same kind
        out, last = [], {}
        for c in cues:
            if c["t"] - last.get(c["kind"], -9) >= 0.09:
                out.append(c)
                last[c["kind"]] = c["t"]
        self.cues = out
        return self

    def music_sections(self):
        secs = []
        verdict_i = next((i for i, p in enumerate(self.plan) if p["role"] in ("verdict", "final")), None)
        for i, p in enumerate(self.plan):
            kind = "hook" if i == 0 else "body"
            if verdict_i is not None and i == verdict_i:
                kind = "drop"
            if verdict_i is not None and i == verdict_i - 1:
                kind = "build"
            if p["role"] in ("cta", "outro") and i == len(self.plan) - 1:
                kind = "outro" if verdict_i is not None else "drop"
            secs.append((p["t0"], p["t1"], kind))
        secs[-1] = (secs[-1][0], self.duration + 2, secs[-1][2])
        return secs

    def scene_at(self, t):
        for i, s in enumerate(self.scenes):
            if s.t0 <= t < s.t1:
                return i
        return len(self.scenes) - 1

    def frame(self, t: float) -> Image.Image:
        tr = next((x for x in self.trans if abs(t - x["t"]) < x["dur"] / 2), None)
        if tr:
            p = (t - (tr["t"] - tr["dur"] / 2)) / tr["dur"]
            A = self.scenes[tr["a"]].frame(t)
            B = self.scenes[tr["b"]].frame(max(t, self.scenes[tr["b"]].t0))
            fr = transition(tr["kind"], A, B, p, self.dna["palette"]["accent"], tr["seed"], tr["dir"]).convert("RGBA")
        else:
            fr = self.scenes[self.scene_at(t)].frame(t)
        if self.series_bar is not None:
            fr.alpha_composite(self.series_bar, (0, 232))
        self.captions.render(fr, t)
        if self.progress:
            q = min(1.0, t / self.duration)
            d = ImageDraw.Draw(fr)
            d.rectangle([0, 0, int(W * q), 7], fill=rgba(self.dna["palette"]["accent"], 230))
        return fr.convert("RGB")

    def background_frame(self, t: float):
        """The scene's footage/plate only (camera applied, no text) — clean base for covers."""
        sc = self.scenes[self.scene_at(t)].ensure()
        sc.cam.bind(t - sc.t0)
        bg = sc.bg
        fr = bg.render(sc.cam, t - sc.t0) if getattr(bg, "dynamic", False) else bg.render(sc.cam)
        for ly in sc.layers:  # keep pictures (poster cards, product shots), drop text/decoration
            if getattr(ly, "role", "") == "image":
                ly.render(fr, t - sc.t0, sc.cam)
        return fr.convert("RGB")

    def summary(self):
        return {"duration": self.duration, "fps": FPS, "size": [W, H], "scenes": self.plan, "transitions": [{k: v for k, v in t.items()} for t in self.trans],
                "motion": MOTION[self.dna["motion"]]}
