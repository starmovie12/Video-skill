"""Fast offline tests (no network): physics, colour, DNA variety, lint, typography fallback, captions, transitions, a real render."""
import json
import os
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("RVS_HOME", str(Path("/tmp") / "rvs_test_home"))

from rvs import dna as D  # noqa: E402
from rvs.core import H, W, Rng, contrast, spring  # noqa: E402


def test_spring_settles_and_overshoots():
    assert spring(0) == 0
    assert abs(spring(3.0, 16, 0.5) - 1) < 1e-3
    assert max(spring(t / 100, 16, 0.3) for t in range(100)) > 1.05  # elastic overshoot
    assert max(spring(t / 100, 10, 1.0) for t in range(300)) <= 1.0 + 1e-9  # critically damped: no overshoot


@pytest.mark.parametrize("tone", ["dark", "light", "mid"])
def test_palette_is_readable(tone):
    for s in range(20):
        p = D.build_palette(tone, Rng(s), None)
        assert contrast(p["text"], p["bg0"]) >= (7.0 if tone != "mid" else 4.5)
        assert contrast(p["accent"], p["bg0"]) >= 3.0


def _proj(title, genre="horror", cat="movie_review"):
    return {"title": title, "id": title, "category": cat, "facts": {"genre": [genre]}, "beats": [{"role": "hook", "say": "x"}]}


def test_dna_novelty_against_ledger(tmp_path, monkeypatch):
    monkeypatch.setenv("RVS_HOME", str(tmp_path))
    sigs = []
    for i in range(5):
        d = D.generate(_proj(f"film{i}"), None)
        D.save_ledger_entry({"id": f"film{i}", "dna_sig": d["dna_sig"]})
        sigs.append(d["dna_sig"])
    for i in range(1, 5):
        assert D.diff_count(sigs[i], sigs[i - 1]) >= 4, (sigs[i], sigs[i - 1])


def test_genre_binds_music_and_tone(tmp_path, monkeypatch):
    monkeypatch.setenv("RVS_HOME", str(tmp_path))
    for i in range(6):
        d = D.generate(_proj(f"h{i}", "horror"), None)
        D.save_ledger_entry({"id": f"h{i}", "dna_sig": d["dna_sig"]})
        assert d["music_mood"] in ("dark_pulse", "epic_trailer")
        assert d["tone"] == "dark"


def test_lint_blocks_greeting_and_empty_cards():
    from rvs.lint import lint
    errs, _ = lint({"target_sec": 20, "beats": [{"role": "hook", "say": "Namaste doston aaj hum"},
                                                {"role": "pros_cons", "say": "accha bura"}]})
    assert any("greeting" in e for e in errs)
    assert any("pros_cons" in e for e in errs)


def test_rupee_and_devanagari_fallback():
    from rvs.typo import supports, text_sprite
    assert not supports("tenor", "₹1,499")
    s = text_sprite("₹1,499", "tenor", 120, box=(4000, 400), max_lines=1)
    assert s.w > 200
    d = text_sprite("ज़बरदस्त फिल्म", "anton", 120, deva_fid="mukta-xb", box=(4000, 400), max_lines=1)
    a = np.asarray(d.img)[..., 3]
    assert (a > 0).mean() > 0.05  # Devanagari actually drawn (fallback font)


def test_transitions_shapes():
    from PIL import Image
    from rvs.engine import TRANSITIONS, transition
    A, B = Image.new("RGB", (W, H), (255, 0, 0)), Image.new("RGB", (W, H), (0, 0, 255))
    for k in TRANSITIONS:
        for p in (0.0, 0.5, 1.0):
            out = transition(k, A, B, p)
            assert out.size == (W, H)
        end = np.asarray(transition(k, A, B, 1.0))
        assert end[..., 2].mean() > end[..., 0].mean(), k  # ends on B


def _fake_voice(beats, wps=2.6):
    words, spans, t = [], [], 0.1
    for i, b in enumerate(beats):
        st = t
        for w in b["show"].split():
            words.append({"say": w, "show": w, "t0": round(t, 3), "t1": round(t + 0.3, 3), "beat": i})
            t += 1 / wps
        spans.append({"beat": i, "t0": round(st, 3), "t1": round(t, 3)})
        t += 0.2
    return {"engine": "fake", "voice": "-", "rate": "+18%", "timing": "fake", "duration": t, "words": words, "spans": spans}


def test_render_smoke(tmp_path, monkeypatch):
    monkeypatch.setenv("RVS_HOME", str(tmp_path))
    from rvs.render import render_video
    from rvs.timeline import Timeline
    proj = json.loads((ROOT / "examples/octopus_facts/project.json").read_text(encoding="utf-8"))
    voice = _fake_voice(proj["beats"])
    d = D.generate(proj, None)
    tl = Timeline(proj, voice, d, {}).build_all()
    assert len({p["archetype"] for p in tl.plan}) >= 4
    assert len(tl.trans) == len(tl.scenes) - 1
    fr = tl.frame(1.0)
    assert fr.size == (W, H)
    out = tmp_path / "smoke.mp4"
    info = render_video(tl, out, 0, 1.0, workers=2)
    assert out.exists() and out.stat().st_size > 10_000 and info["frames"] == 30
    from rvs.captions import Captioner
    cap = Captioner(voice["words"], d)
    assert sum(len(g["words"]) for g in cap.groups) == len(voice["words"])
    assert all(len(g["words"]) <= 3 for g in cap.groups)


# ───────────────────────── v2 features ─────────────────────────
def test_dtw_alignment_handles_numbers_and_spelling():
    from rvs.voice import align_tokens
    toks = "106 साल पुरानी फिल्म और आज भी डरावनी".split()
    words = [("एक", 0.0, 0.3), ("सो", 0.36, 0.5), ("छे", 0.56, 0.75), ("साल", 0.8, 1.0), ("पुरानी", 1.08, 1.5), ("फ़िल्म", 1.56, 1.9),
             ("और", 2.58, 2.8), ("आजज", 2.92, 3.2), ("भी", 3.28, 3.4), ("दरावनी", 3.42, 3.9)]
    al = align_tokens(toks, words)
    assert abs(al[1][0] - 0.8) < 0.05 and abs(al[2][0] - 1.08) < 0.05 and abs(al[7][0] - 3.42) < 0.05
    assert all(al[i][0] <= al[i + 1][0] for i in range(len(al) - 1))  # monotonic


def test_elevenlabs_alignment_mapping():
    from rvs.voice import eleven_chars_to_words
    text = "हाँ ये ज़बरदस्त है"
    chars = list(text)
    st = [i * 0.1 for i in range(len(chars))]
    en = [i * 0.1 + 0.09 for i in range(len(chars))]
    w = eleven_chars_to_words(text, {"characters": chars, "character_start_times_seconds": st, "character_end_times_seconds": en})
    assert len(w) == 4 and w[0][0] == 0.0 and w[1][0] == pytest.approx(0.4) and w[3][1] == pytest.approx(en[-1])


def test_reel_pacing_edits_keep_timing_consistent():
    from rvs.voice import SR, hero_pauses, tighten
    x = np.zeros(int(3.0 * SR), np.float32)
    tw = [(0.1, 0.5), (1.2, 1.6), (1.6, 2.0)]
    x2, tw2 = tighten(x, tw, ["ek", "do", "teen"])
    assert tw2[1][0] - tw2[0][1] == pytest.approx(0.13, abs=0.01) and len(x2) < len(x)
    x3, tw3 = hero_pauses(x2, tw2, ["ek", "do", "teen"], {"teen"})
    assert tw3[2][0] - tw3[1][1] == pytest.approx(0.16, abs=0.01) and tw3[1][1] == pytest.approx(tw2[1][1])


def test_beat_grid_detects_tempo():
    from rvs.audio import SR, beat_grid, kick, place
    bpm = 120
    x = np.zeros((SR * 12, 2), np.float32)
    for k in range(24):
        place(x, kick(0), 0.25 + k * 60 / bpm, 0.9)
    b, off = beat_grid(x)
    assert abs(b - bpm) < 2 or abs(b - bpm / 2) < 1 or abs(b - bpm * 2) < 2
    assert abs(((off - 0.25) % 0.5)) < 0.06 or abs(((off - 0.25) % 0.5) - 0.5) < 0.06


def test_sticker_matching_and_assets():
    from rvs import stickers as ST
    assert len(ST.available()) >= 80
    words = [{"show": "aaj", "t0": 0.1}, {"show": "bhi", "t0": 0.3}, {"show": "daravni!", "t0": 0.6}]
    assert ST.match(words, set()) == ("scream", 0.6)
    assert ST.load("fire", 120).size == (120, 120)


def test_media_scan_assign_and_footage_frame(tmp_path):
    import subprocess
    from PIL import Image
    from rvs.media import assign, build_background, scan
    from rvs.engine import Camera
    md = tmp_path / "media"
    md.mkdir()
    Image.new("RGB", (900, 1400), (40, 90, 160)).save(md / "a.jpg")
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "testsrc2=size=640x360:rate=30:duration=2", "-f", "lavfi", "-i",
                    "mandelbrot=size=640x360:rate=30", "-filter_complex", "[1]trim=duration=2[m];[0][m]concat=n=2:v=1[v]", "-map", "[v]",
                    "-pix_fmt", "yuv420p", str(md / "clip.mp4")], check=True, timeout=120)
    proj = {"beats": [{"role": "hook", "say": "a b c d"}, {"role": "line", "say": "e f g h"}]}
    cat = scan(proj, tmp_path, tmp_path / "work")
    assert cat["items"]["media/clip.mp4"]["kind"] == "video" and len(cat["items"]["media/clip.mp4"]["shots"]) >= 1
    voice = {"duration": 6.0, "spans": [{"beat": 0, "t0": 0.1, "t1": 2.9}, {"beat": 1, "t0": 3.0, "t1": 5.9}],
             "words": [{"show": c, "t0": 0.1 + i * 0.7, "t1": 0.6 + i * 0.7, "beat": 0 if i < 4 else 1} for i, c in enumerate("abcdefgh")]}
    plan = assign(proj, cat, voice)
    assert set(plan) == {0, 1}
    d = D.generate({"title": "m", "category": "facts", "beats": []}, None)
    fb = build_background(plan[0], tmp_path, d)
    cam = Camera("push", 0.05, 3.0).bind(0.5)
    fr = fb.render(cam, 0.5)
    assert fr.size == (W, H)


def test_viral_captions_progressive_reveal():
    from PIL import Image
    from rvs.captions import Captioner
    d = D.generate({"title": "c", "category": "facts", "beats": [], "dna": {"caption_style": "viral"}}, None)
    words = [{"show": w, "say": w, "t0": 0.2 + i * 0.4, "t1": 0.5 + i * 0.4, "beat": 0} for i, w in enumerate(["ek", "do", "teen"])]
    cap = Captioner(words, d)
    assert cap.style == "viral" and cap.px >= 88
    f1, f2 = Image.new("RGBA", (W, H), (0, 0, 0, 255)), Image.new("RGBA", (W, H), (0, 0, 0, 255))
    cap.render(f1, 0.3)
    cap.render(f2, 1.1)
    a1, a2 = (np.asarray(f)[1000:1600, :, :3].astype(int).sum() for f in (f1, f2))
    assert a2 > a1 * 1.5  # more words visible later


def test_cli_new_feedback_refs(tmp_path, monkeypatch):
    monkeypatch.setenv("RVS_HOME", str(tmp_path / "home"))
    from PIL import Image
    from rvs.cli import main
    main(["new", "product", str(tmp_path / "p")])
    pj = json.loads((tmp_path / "p" / "project.json").read_text(encoding="utf-8"))
    assert pj["category"] == "product"
    refs = tmp_path / "refs"
    refs.mkdir()
    Image.new("RGB", (540, 960), (240, 230, 220)).save(refs / "light.png")
    main(["refs", str(refs)])
    t = json.loads((tmp_path / "home" / "taste.json").read_text())
    assert t["refs"] and t["weights"]["tone"]["light"] > 0
    work = tmp_path / "p" / "work"
    work.mkdir()
    (work / "dna.json").write_text(json.dumps(D.generate(pj, None)))
    main(["feedback", str(tmp_path / "p"), "--approve", "--note", "nice"])
    t = json.loads((tmp_path / "home" / "taste.json").read_text())
    assert t["notes"][-1]["note"] == "nice"


def test_still_crop_letterbox_and_band_position(tmp_path):
    """Dict media refs carry crop / fit / y; letterbox keeps the whole wide frame sharp and `y` moves the band."""
    from PIL import Image
    from rvs.media import MARGIN, StillSource, parse_ref
    md = tmp_path / "media"
    md.mkdir()
    im = Image.new("RGB", (1600, 600), (20, 20, 20))
    im.paste((250, 250, 250), (0, 250, 1600, 350))  # bright stripe across the middle of the wide still
    im.save(md / "wide.jpg")
    cat = {"items": {"media/wide.jpg": {"kind": "image"}}}
    ref = parse_ref({"file": "media/wide.jpg", "fit": "letterbox", "y": 0.7, "crop": [0, 0, 1, 1]}, cat)
    assert ref["fit"] == "letterbox" and ref["y"] == 0.7 and ref["crop"] == [0, 0, 1, 1]
    bh = int(H * MARGIN)

    def band_row(y):
        a = np.asarray(StillSource(md / "wide.jpg", fit="letterbox", y=y).img.convert("L"), np.float32)
        return int(np.argmax(a.mean(axis=1))) / bh
    lo, hi = band_row(0.3), band_row(0.7)
    assert abs(lo - 0.3) < 0.05 and abs(hi - 0.7) < 0.05
    assert abs(band_row(None) - 0.46) < 0.05  # default position unchanged
    # wide stills letterbox automatically; a crop switches to cover (punch-in)
    assert StillSource(md / "wide.jpg").fit == "letterbox"
    assert StillSource(md / "wide.jpg", crop=[0.4, 0, 0.6, 1]).fit == "cover"


def test_dna_overrides_invalidate_cached_dna(tmp_path, monkeypatch):
    """Changing project.json `dna` overrides after a proof must not be ignored because work/dna.json exists."""
    monkeypatch.setenv("RVS_HOME", str(tmp_path / "home"))
    from rvs.cli import stage_dna
    proj = {"title": "m", "category": "facts", "beats": []}
    d1 = stage_dna(proj, tmp_path, tmp_path)
    other = next(m for m in D.MOTIFS if m != d1["motif"])
    d2 = stage_dna(dict(proj, dna={"motif": other, "caption_style": "viral"}), tmp_path, tmp_path)
    assert d2["motif"] == other and d2["caption_style"] == "viral"
    d3 = stage_dna(dict(proj, dna={"motif": other, "caption_style": "viral"}), tmp_path, tmp_path)
    assert d3 == d2  # same overrides → cache reused


def test_qa_lists_every_static_run():
    """QA reports ALL static runs > 2.5 s (not just the longest), so the Director fixes them in one re-render."""
    from rvs.qa import longest_static, static_runs
    d = np.array([1.0] * 10 + [0.0] * 30 + [1.0] * 5 + [0.0] * 20 + [0.1] * 26)
    assert static_runs(d, 10) == [(1.0, 3.0), (4.5, 4.6)]
    assert longest_static(d, 10)[0] == 4.6
    assert static_runs(np.ones(50), 10) == []


def _channel_dir(tmp_path, monkeypatch):
    ch = {"name": "Test Channel", "handle": "@test.ch", "platform": "instagram", "account_type": "creator",
          "weekly_rhythm": {"mon": "numbers", "tue": "decode", "wed": "facts", "thu": "decode", "fri": "this_week", "sat": "theory", "sun": "facts"},
          "schedule": {"post_main": "19:30", "post_second": "13:00", "post_second_from": "2099-01-01", "stories": []},
          "reel_rules": {"target_sec": 50, "max_sec": 60, "hard_max_sec": 90, "hook_max_words": 16, "script_words": [110, 160],
                         "send_cta_words": ["bhejo"], "hashtags_max": 5, "base_hashtags": ["#TestCh"]},
          "defaults": {"category": "movie_review", "format": "reel", "target_sec": 50, "caption_script": "roman",
                       "voice": {"preset": "hindi_male"}, "dna": {"caption_style": "viral", "motif": "dust"}}}
    d = tmp_path / "channel"
    d.mkdir()
    (d / "channel.json").write_text(json.dumps(ch), encoding="utf-8")
    monkeypatch.setenv("RVS_CHANNEL", str(d))
    return d


def test_channel_defaults_lint_hashtags(tmp_path, monkeypatch):
    """Channel defaults fill a project (project values win); lint enforces the reel rules; hashtags follow the policy."""
    _channel_dir(tmp_path, monkeypatch)
    from rvs import channel as C
    p = C.apply_defaults({"title": "x", "target_sec": 45, "dna": {"motif": "slashes"}, "beats": []})
    assert p["target_sec"] == 45 and p["dna"] == {"caption_style": "viral", "motif": "slashes"}
    assert p["format"] == "reel" and p["channel"]["handle"] == "@test.ch"
    long_reel = {"target_sec": 200, "beats": [{"say": " ".join(["शब्द"] * 30), "show": "x"}, {"say": "a", "show": "Comment karo"}]}
    errs, warns = C.lint(long_reel)
    assert any("CHANNEL_LENGTH" in e for e in errs)
    assert any("CHANNEL_HOOK" in w for w in warns) and any("CHANNEL_SEND_CTA" in w for w in warns)
    assert any("CHANNEL_QUESTION" in w for w in warns)
    ok = {"target_sec": 50, "beats": [{"say": "छोटा हुक", "show": "Chhota hook"},
                                       {"say": "भेजो", "show": "Ye us dost ko bhejo. Hit ya flop?"}]}
    assert C.lint(ok) == ([], [])
    assert C.lint(dict(long_reel, format="long"))[0] == []
    tags = C.hashtags({"hashtags": ["#Ramayana"]}, C.load(), ["#King", "#moviereview", "#a", "#b", "#c", "#d"])
    assert tags[0] == "#TestCh" and "#Ramayana" in tags and len(tags) == 5


def test_channel_log_and_brief(tmp_path, monkeypatch):
    """`log` appends a video and later updates the same project's row; the brief shows the pillar and recent topics."""
    import datetime as dt
    _channel_dir(tmp_path, monkeypatch)
    from rvs import channel as C
    C.log({"project": "p1", "topic": "Ramayana facts", "status": "made"})
    C.log({"project": "p1", "status": "posted", "views": 1234, "notes": None})
    rows = C.history()
    assert len(rows) == 1 and rows[0]["status"] == "posted" and rows[0]["views"] == 1234 and rows[0]["topic"] == "Ramayana facts"
    b = C.brief(dt.date(2026, 11, 4))
    assert "wed" in b["today"] and "facts" in b["today"] and "decode" in b["tomorrow"]
    assert b["post_at_ist"] == ["19:30"] and "Ramayana facts" in b["recent_topics_do_not_repeat"][0]
