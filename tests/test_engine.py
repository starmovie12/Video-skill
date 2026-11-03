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
