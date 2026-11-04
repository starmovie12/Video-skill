"""Reel handover PDF (operator's Prompt 3, adapted to this engine — see prompts/ADAPTATION.md).

Builds `out/reel-handover_<slug>.pdf` from what earlier stages produced:
  pack/research-brief_*.md   (Prompt 1, written by Claude)
  pack/script-pack_*.md      (Prompt 2, written by Claude; 8 sections + YAML handoff)
  project.json, work/plan.json, work/dna.json, work/words.json, work/proof_frames/*.png (engine proof)
  media/credits.json, channel/channel.json
The script's words are never changed here. Rendering: HTML → headless Chromium (Node Playwright) → PDF; every page is
then rasterised to work/handover_pages/ so the Director can LOOK at it before sending (fallback: HTML only).
"""
from __future__ import annotations

import datetime as dt
import html
import re
import shutil
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw

from .core import H, W, RvsError, log, read_json

ROOT = Path(__file__).resolve().parent.parent
FONTS = ROOT / "assets" / "fonts"
ARCH_COLORS = {"hook_slam": "#E4572E", "poster_hero": "#F2A541", "kinetic_line": "#7A6FF0", "stat_counter": "#2BB3A3",
               "cast_spotlight": "#E86A92", "fact_bomb": "#F25C54", "quote_kinetic": "#9B5DE5", "story_panels": "#00A6ED",
               "split_compare": "#F7B32B", "list_reveal": "#4CB944", "timeline": "#3D5A80", "pros_cons": "#8AC926",
               "verdict_stamp": "#FF595E", "cta_loop": "#1982C4", "rating_meter": "#FFCA3A"}
DESCRIBE = {"hook_slam": "Hook: words slam in one by one", "poster_hero": "Poster card + title + chips", "kinetic_line": "Kinetic type",
            "stat_counter": "Number counter", "cast_spotlight": "Cast circles", "fact_bomb": "Big fact slam", "quote_kinetic": "Quote + hero word",
            "story_panels": "Story panels", "split_compare": "VS split", "list_reveal": "Numbered list", "timeline": "Timeline",
            "pros_cons": "Pros / cons cards", "verdict_stamp": "Verdict stamp", "cta_loop": "Question + loop", "rating_meter": "Rating meter"}


# ───────────────────────── tiny Markdown → HTML (enough for our own packs) ─────────────────────────
def _inline(s: str) -> str:
    s = html.escape(s, quote=False)
    codes = []
    s = re.sub(r"`([^`]+)`", lambda m: codes.append(m.group(1)) or f"\x00{len(codes) - 1}\x00", s)
    s = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", s)
    s = re.sub(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])", r"<i>\1</i>", s)
    s = re.sub(r"\[([^\]]+)\]\((https?://[^)\s]+)\)", r'<a href="\2">\1</a>', s)
    s = re.sub(r"(?<![\"'>=])(https?://[^\s<|]+)", r'<a href="\1">\1</a>', s)
    return re.sub(r"\x00(\d+)\x00", lambda m: f"<code>{codes[int(m.group(1))]}</code>", s)


def md_to_html(md: str, h_shift: int = 2) -> str:
    """Headings (shifted down), pipe tables, bullet/numbered lists (one nesting level), fenced code, quotes, hr, paragraphs."""
    out, para, lines, i = [], [], md.replace("\r", "").split("\n"), 0

    def flush():
        if para:
            out.append("<p>" + _inline(" ".join(x.strip() for x in para)) + "</p>")
            para.clear()
    while i < len(lines):
        ln = lines[i]
        st = ln.strip()
        if st.startswith("```"):
            flush()
            lang = st[3:].strip()
            j = i + 1
            buf = []
            while j < len(lines) and not lines[j].strip().startswith("```"):
                buf.append(lines[j])
                j += 1
            out.append(f'<pre class="code {html.escape(lang)}"><code>{html.escape(chr(10).join(buf))}</code></pre>')
            i = j + 1
            continue
        m = re.match(r"^(#{1,6})\s+(.*)$", st)
        if m:
            flush()
            lvl = min(6, len(m.group(1)) + h_shift)
            out.append(f"<h{lvl}>{_inline(m.group(2))}</h{lvl}>")
            i += 1
            continue
        if st.startswith("|") and i + 1 < len(lines) and re.match(r"^\|?\s*:?-{2,}", lines[i + 1].strip()):
            flush()
            rows = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                rows.append(lines[i].strip())
                i += 1
            cells = [[c.strip() for c in r.strip("|").split("|")] for r in rows]
            head, body = cells[0], [r for r in cells[2:]]
            t = ["<table><thead><tr>" + "".join(f"<th>{_inline(c)}</th>" for c in head) + "</tr></thead><tbody>"]
            for r in body:
                t.append("<tr>" + "".join(f"<td>{_inline(c)}</td>" for c in r) + "</tr>")
            out.append("".join(t) + "</tbody></table>")
            continue
        if re.match(r"^\s*([-*•]|\d+[.)])\s+", ln):
            flush()
            items = []
            ordered = bool(re.match(r"^\s*\d+[.)]\s+", ln))
            while i < len(lines) and (re.match(r"^\s*([-*•]|\d+[.)])\s+", lines[i]) or (lines[i].startswith("   ") and lines[i].strip())):
                cur = lines[i]
                indent = len(cur) - len(cur.lstrip())
                if indent < 2 and items and bool(re.match(r"^\s*\d+[.)]\s+", cur)) != ordered:
                    break  # bullets → numbers (or back) starts a new list
                txt = re.sub(r"^\s*([-*•]|\d+[.)])\s+", "", cur).strip()
                txt = re.sub(r"^\[ \]\s*", "☐ ", re.sub(r"^\[x\]\s*", "☑ ", txt, flags=re.I))
                if indent >= 2 and items:
                    items[-1][1].append(txt)
                else:
                    items.append([txt, []])
                i += 1
            tag = "ol" if ordered else "ul"
            out.append(f"<{tag}>" + "".join(f"<li>{_inline(a)}" + (("<ul>" + "".join(f"<li>{_inline(s)}</li>" for s in b) + "</ul>") if b else "")
                                            + "</li>" for a, b in items) + f"</{tag}>")
            continue
        if st.startswith(">"):
            flush()
            buf = []
            while i < len(lines) and lines[i].strip().startswith(">"):
                buf.append(lines[i].strip()[1:].strip())
                i += 1
            out.append('<div class="callout">' + _inline(" ".join(buf)) + "</div>")
            continue
        if re.match(r"^(-{3,}|\*{3,})$", st):
            flush()
            out.append("<hr>")
            i += 1
            continue
        if not st:
            flush()
        else:
            para.append(ln)
        i += 1
    flush()
    return "\n".join(out)


def md_sections(md: str) -> dict[int, tuple[str, str]]:
    """'## 1. Verdict' style sections → {1: (title, body)}. Unnumbered ## headings are kept with key 100+."""
    res, cur, title, body, extra = {}, None, "", [], 100
    for ln in md.split("\n"):
        m = re.match(r"^##\s+(?:(\d+)[.)]\s*)?(.*)$", ln)
        if m and not ln.startswith("###"):
            if cur is not None:
                res[cur] = (title, "\n".join(body).strip())
            if m.group(1):
                cur = int(m.group(1))
            else:
                cur, extra = extra, extra + 1
            title, body = m.group(2).strip(), []
        elif cur is not None:
            body.append(ln)
    if cur is not None:
        res[cur] = (title, "\n".join(body).strip())
    return res


def handoff_yaml(md: str) -> dict:
    blocks = re.findall(r"```ya?ml\s*\n(.*?)```", md, flags=re.S)
    if not blocks:
        return {}
    try:
        import yaml
        d = yaml.safe_load(blocks[-1])
        return d if isinstance(d, dict) else {}
    except Exception:  # simple key: value fallback
        d = {}
        for ln in blocks[-1].splitlines():
            m = re.match(r"^([A-Za-z_]+):\s*(.*)$", ln)
            if m:
                d[m.group(1)] = m.group(2).strip().strip('"')
        return d


# ───────────────────────── images ─────────────────────────
def _thumb(src: Path, dst: Path, w=360) -> Path:
    im = Image.open(src).convert("RGB")
    im = im.resize((w, int(w * im.height / im.width)), Image.Resampling.LANCZOS)
    dst.parent.mkdir(parents=True, exist_ok=True)
    im.save(dst, quality=86)
    return dst


def _crop_guides(src: Path, dst: Path) -> Path:
    """Cover with the profile-grid crop guides (3:4 = centre 1080x1440, and 4:5 = centre 1080x1350)."""
    im = Image.open(src).convert("RGB").resize((W, H))
    ov = Image.new("RGBA", im.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)
    for (hh, col, lab) in ((1440, (255, 214, 10, 255), "3:4 grid crop"), (1350, (0, 200, 255, 255), "4:5")):
        y0 = (H - hh) // 2
        d.rectangle((0, 0, W, y0), fill=(0, 0, 0, 70)) if hh == 1440 else None
        d.rectangle((0, y0 + hh, W, H), fill=(0, 0, 0, 70)) if hh == 1440 else None
        d.rectangle((6, y0, W - 6, y0 + hh), outline=col, width=8)
        d.text((24, y0 + 14), lab, fill=col)
    im = Image.alpha_composite(im.convert("RGBA"), ov).convert("RGB")
    return _thumb_img(im, dst, 420)


def _thumb_img(im: Image.Image, dst: Path, w=360) -> Path:
    im = im.resize((w, int(w * im.height / im.width)), Image.Resampling.LANCZOS)
    dst.parent.mkdir(parents=True, exist_ok=True)
    im.save(dst, quality=88)
    return dst


# ───────────────────────── page CSS ─────────────────────────
def _css(accent: str) -> str:
    f = lambda name: (FONTS / name).as_uri()  # noqa: E731
    return f"""
@font-face {{ font-family: Body; src: url('{f("Montserrat-VF.ttf")}'); font-weight: 100 900; }}
@font-face {{ font-family: Title; src: url('{f("SpaceGrotesk-VF.ttf")}'); font-weight: 300 700; }}
@font-face {{ font-family: Display; src: url('{f("Anton-Regular.ttf")}'); }}
@font-face {{ font-family: Mono; src: url('{f("IBMPlexMono-Bold.ttf")}'); }}
@font-face {{ font-family: Deva; src: url('{f("Mukta-Bold.ttf")}'); }}
@page {{ size: A4; margin: 16mm 0 18mm 0; background: #FAF6EE; }}
html, body {{ background: #FAF6EE; color: #1B1B1B; margin: 0; }}
body {{ font-family: Body, Deva, sans-serif; font-size: 9.6pt; line-height: 1.42; -webkit-print-color-adjust: exact; print-color-adjust: exact; }}
.page {{ padding: 0 18mm; }}
.break {{ break-before: page; }}
h1, h2, h3, h4, h5 {{ font-family: Title, Deva, sans-serif; margin: 0.9em 0 0.35em; break-after: avoid; }}
h1.sec {{ font-size: 20pt; font-weight: 700; margin-top: 0; }}
h1.sec::after {{ content: ""; display: block; width: 46px; height: 4px; background: {accent}; margin-top: 6px; border-radius: 2px; }}
h1.sec .num {{ color: {accent}; margin-right: 8px; }}
h3 {{ font-size: 12.5pt; }} h4 {{ font-size: 11pt; }} h5 {{ font-size: 10pt; }}
p {{ margin: 0.35em 0; }}
a {{ color: #1B1B1B; text-decoration: underline; text-decoration-color: {accent}; overflow-wrap: anywhere; word-break: break-all; }}
table {{ border-collapse: collapse; width: 100%; margin: 0.5em 0 0.9em; font-size: 8.4pt; break-inside: auto; }}
th {{ text-align: left; font-family: Title, sans-serif; font-variant: small-caps; letter-spacing: 0.04em; font-size: 8pt;
     border-bottom: 2px solid #1B1B1B; padding: 4px 5px; }}
td {{ border-bottom: 1px solid #DDD3C2; padding: 4px 5px; vertical-align: top; overflow-wrap: break-word; }}
table.fixed {{ table-layout: fixed; }}
tr {{ break-inside: avoid; }}
code {{ font-family: Mono, monospace; font-size: 8pt; background: #EFE7D8; padding: 0 3px; border-radius: 3px; }}
pre.code {{ background: #14161A; color: #F2EDE4; padding: 9px 11px; border-radius: 8px; font-size: 7.8pt; white-space: pre-wrap;
           word-break: break-word; break-inside: avoid; }}
pre.code code {{ background: none; color: inherit; padding: 0; }}
.callout {{ border-left: 4px solid {accent}; background: #F3EBDD; padding: 7px 10px; margin: 0.6em 0; border-radius: 0 6px 6px 0; }}
.chip {{ display: inline-block; background: #14161A; color: #F2EDE4; border-radius: 99px; padding: 2px 9px; margin: 0 4px 4px 0; font-size: 8pt; }}
.chip.acc {{ background: {accent}; color: #14161A; font-weight: 700; }}
.eyebrow {{ font-family: Title; letter-spacing: 0.32em; font-size: 9pt; color: {accent}; font-weight: 700; }}
.cover-title {{ font-family: Display, Deva, sans-serif; font-size: 44pt; line-height: 1.0; margin: 8px 0 6px; }}
.cover-sub {{ font-size: 12pt; color: #3a3a3a; margin-bottom: 12px; }}
.cover {{ display: flex; gap: 14mm; align-items: flex-start; }}
.cover img {{ width: 56mm; border-radius: 10px; box-shadow: 0 6px 18px rgba(0,0,0,.25); }}
.cards {{ display: grid; grid-template-columns: 1fr 1.3fr 1.3fr; gap: 4mm; margin-top: 7mm; }}
.card {{ border: 1px solid #DDD3C2; border-radius: 10px; padding: 8px 11px; background: #FFFDF8; }}
.card .k {{ font-family: Title; font-weight: 700; font-size: 9pt; }}
.card .big {{ font-family: Display; font-size: 26pt; line-height: 1.05; }}
.card .big span {{ color: {accent}; }}
.strip4 {{ display: grid; grid-template-columns: repeat(6, 1fr); gap: 2.5mm; margin-top: 5mm; }}
section.coverpage {{ height: 258mm; overflow: hidden; break-after: page; }}
.strip4 img {{ width: 100%; border-radius: 6px; }}
.box {{ background: #14161A; color: #F2EDE4; border-radius: 10px; padding: 10px 14px; }}
.box h4 {{ color: {accent}; margin-top: 0; }}
.box li {{ margin: 2px 0; }}
.grid {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 5mm; }}
.frame {{ break-inside: avoid; }}
.frame img {{ width: 100%; border-radius: 6px; display: block; }}
.frame .lab {{ font-size: 7.6pt; line-height: 1.3; margin-top: 3px; }}
.frame .lab b {{ color: {accent}; }}
.strip {{ display: flex; height: 26px; border-radius: 6px; overflow: hidden; margin: 6px 0 2px; }}
.strip div {{ color: #fff; font-size: 6.5pt; padding: 2px 3px; overflow: hidden; white-space: nowrap; border-right: 1px solid #FAF6EE; }}
.swatches {{ display: flex; gap: 6px; flex-wrap: wrap; }}
.sw {{ width: 64px; font-size: 7pt; }} .sw div {{ height: 30px; border-radius: 6px; border: 1px solid #0002; }}
.pipeline {{ display: flex; gap: 4px; margin: 6px 0 10px; flex-wrap: wrap; }}
.pipeline span {{ background: #14161A; color: #F2EDE4; padding: 4px 8px; border-radius: 6px; font-size: 7.6pt; }}
.pipeline span.stop {{ background: {accent}; color: #14161A; font-weight: 700; }}
.prompt {{ background: #14161A; color: #F2EDE4; border-radius: 9px; padding: 9px 12px; margin: 8px 0; break-inside: avoid; }}
.prompt .meta {{ font-size: 7.4pt; color: {accent}; margin-bottom: 4px; font-family: Mono; }}
.prompt pre {{ white-space: pre-wrap; margin: 0; font-family: Mono, Deva, monospace; font-size: 8pt; }}
.two {{ display: grid; grid-template-columns: 1fr 1fr; gap: 6mm; }}
.small {{ font-size: 8pt; color: #555; }}
"""


# ───────────────────────── build ─────────────────────────
def _find(pack: Path, prefix: str) -> Path | None:
    c = sorted(pack.glob(f"{prefix}*.md"))
    return c[-1] if c else None


def _slug(s: str) -> str:
    return re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", s.lower())).strip("-")[:48] or "reel"


def _sec(n, title, body, brk=True) -> str:
    return f'<section class="page{" break" if brk else ""}"><h1 class="sec"><span class="num">{n}</span>{html.escape(title)}</h1>{body}</section>'


def capabilities() -> list[tuple[str, bool, str]]:
    node = shutil.which("node")
    pw = False
    if node:
        try:
            pw = subprocess.run([node, "-e", "require('playwright')"], capture_output=True, timeout=30).returncode == 0
        except Exception:
            pw = False
    return [("Headless Chromium (Node Playwright)", pw, "PDF build; without it the handover falls back to HTML"),
            ("pdftoppm", bool(shutil.which("pdftoppm")), "every page rasterised to PNG for the visual check"),
            ("ffmpeg", bool(shutil.which("ffmpeg")), "engine renders + proof frames"),
            ("Web search / page fetch", True, "research brief + fact checks (Claude's tools in the session)"),
            ("Second reviewer", False, "no blind second scorer; scores are one editor's judgment")]


def build(root: Path, html_only: bool = False) -> dict:
    root = Path(root)
    work, out, pack = root / "work", root / "out", root / "pack"
    p = read_json(root / "project.json", {})
    if not p:
        raise RvsError("NO_PROJECT", f"{root}/project.json missing")
    sp_file, rb_file = _find(pack, "script-pack"), _find(pack, "research-brief")
    if not sp_file:
        raise RvsError("NO_SCRIPT_PACK", f"write {pack}/script-pack_<slug>.md first (prompts/2-script-doctor.md)")
    plan, dna, words = read_json(work / "plan.json", {}), read_json(work / "dna.json", {}), read_json(work / "words.json", {})
    frames = sorted((work / "proof_frames").glob("*.png"))
    if not plan or not frames:
        raise RvsError("NO_PROOF", "run `python run.py proof <project>` first: the frame board uses the engine's real frames")
    from .channel import load as load_channel, slot_time
    ch = load_channel() or {}
    sp_md = sp_file.read_text(encoding="utf-8")
    rb_md = rb_file.read_text(encoding="utf-8") if rb_file else ""
    sp, hy = md_sections(sp_md), handoff_yaml(sp_md)
    title = str(hy.get("title") or p.get("title") or root.name)
    slug = _slug(str(hy.get("slug") or title))
    accent = (dna.get("palette") or {}).get("accent", "#E4572E")
    assets = work / "handover_assets"
    beats = p.get("beats", [])
    scenes = plan.get("scenes", [])
    spans = words.get("spans", [])
    dur = float(words.get("duration") or plan.get("duration") or 0)
    post_date = p.get("post_date") or ""
    when = slot_time(p, ch, dt.date.fromisoformat(post_date) if re.match(r"\d{4}-\d{2}-\d{2}$", str(post_date)) else None) if ch else None

    # images: frame board thumbs, hero, cover preview with grid-crop guides, safe-zone contact sheet
    thumbs = [_thumb(f, assets / f"f_{i:02d}.jpg") for i, f in enumerate(frames)]
    times = [float(re.search(r"_(\d+\.\d+)s", f.name).group(1)) for f in frames]
    hero = thumbs[min(1, len(thumbs) - 1)]
    cover_src = work / "cover_preview.jpg"
    cover_img = _crop_guides(cover_src if cover_src.exists() else frames[min(1, len(frames) - 1)], assets / "cover_guides.jpg")
    safe = work / "proof_contact_sheet.png"
    safe_img = _thumb(safe, assets / "safe_sheet.jpg", 1100) if safe.exists() else None

    # 1 cover
    chips = [f'<span class="chip acc">{html.escape(ch.get("handle", ""))}</span>' if ch else "",
             f'<span class="chip">{html.escape(str(post_date))} · {html.escape(str(when or ""))} IST</span>' if post_date or when else "",
             f'<span class="chip">{dur:.0f} s · {sum(len(str(b.get("say", "")).split()) for b in beats)} words</span>',
             f'<span class="chip">slot {html.escape(str(p.get("slot", "")))}</span>' if p.get("slot") else "",
             '<span class="chip acc">STATUS: script + preview · video after "continue"</span>']
    inside = ["Overview: verdict, scores, assumptions", "Final script + recording-ready voice script", "Video idea and design (Style DNA)",
              "Frame board: real frames from the engine", "How it will be built (exact commands)", "Publish pack: caption, hashtags, time, stories",
              "Background: retention, swipe test, flaws, fact check", "QA, rights, credits", "Appendix A: your next messages to Claude",
              "Appendix B: research brief + log"]
    hook = beats[0].get("show", "") if beats else ""
    sc_m = re.search(r"(\d{2,3})\s*→\s*(\d{2,3})\s*/\s*100", sp.get(1, ("", ""))[1])
    score_html = (f'<div class="big">{sc_m.group(1)} → <span>{sc_m.group(2)}</span></div><div class="small">draft → final, out of 100 '
                  '(editorial judgment)</div>') if sc_m else '<div class="small">n/a: no score in the script pack</div>'
    strip_idx = [i for i in range(len(thumbs)) if i not in (0, 1)][:6]
    cover = (f'<section class="page coverpage"><div class="eyebrow">{html.escape((ch.get("name") or "REEL").upper())} · '
             f'{html.escape(ch.get("handle", ""))} · REEL HANDOVER</div>'
             f'<div class="cover-title">{html.escape(title)}</div><div class="cover-sub">{html.escape(hook)}</div>'
             f'<div>{"".join(chips)}</div><div class="cover" style="margin-top:7mm"><img src="{hero.as_uri()}">'
             f'<div class="box" style="flex:1"><h4>What\'s inside</h4><ol>' + "".join(f"<li>{x}</li>" for x in inside) +
             '</ol><p class="small" style="color:#bbb">Scores and predictions are editorial judgment, not measured data. '
             'No reel is guaranteed to go viral.</p></div></div>'
             f'<div class="cards"><div class="card"><div class="k">Score</div>{score_html}</div>'
             f'<div class="card"><div class="k">Hook (pehle 2 second)</div><div>{html.escape(hook)}</div></div>'
             f'<div class="card"><div class="k">Ab kya karna hai</div><div>1) Section 3 me script padho. 2) Theek lage to Claude ko '
             f'<b>"continue"</b> likho: video ~10 min me. 3) Post: {html.escape(str(post_date))} {html.escape(str(when or ""))} IST.</div></div></div>'
             '<div class="strip4">' + "".join(f'<img src="{thumbs[i].as_uri()}">' for i in strip_idx) + '</div></section>')

    # 2 overview
    glance = [("Hook", hook), ("Length", f"{dur:.1f} s real voice duration (target {p.get('target_sec', '')} s)"),
              ("Post", f"{post_date} {when or ''} IST · {p.get('slot', '')}"), ("Pillar", str(p.get("pillar", ""))),
              ("Voice", f"{(p.get('voice') or {}).get('preset', '')} (edge-tts) · {words.get('rate', '')}"),
              ("Style", f"{dna.get('palette_family', '')} · {(dna.get('fonts') or {}).get('hero', '')} · {dna.get('motion', '')} motion · "
                        f"{dna.get('caption_style', '')} captions · music {dna.get('music_mood', '')}")]
    ov = ("<table><thead><tr><th>At a glance</th><th></th></tr></thead><tbody>" +
          "".join(f"<tr><td><b>{a}</b></td><td>{html.escape(b)}</td></tr>" for a, b in glance) + "</tbody></table>")
    ov += md_to_html(sp.get(1, ("", "n/a: script pack has no Verdict section"))[1])

    # 3 final script
    s3 = md_to_html(sp.get(2, ("", "n/a: script pack has no Final script section"))[1])
    eng = ["<h3>Engine beats (what the renderer was given)</h3><table><thead><tr><th>#</th><th>Time</th><th>On screen / caption (show)</th>"
           "<th>Voice (say)</th><th>Layout</th><th>Media</th></tr></thead><tbody>"]
    for i, b in enumerate(beats):
        t0 = spans[i]["t0"] if i < len(spans) else 0
        med = b.get("media", "auto")
        med = ", ".join((m.get("file", "") if isinstance(m, dict) else str(m)).split("/")[-1] for m in (med if isinstance(med, list) else [med]))
        arch = scenes[i]["archetype"] if i < len(scenes) else b.get("archetype", "")
        eng.append(f"<tr><td>{i + 1}</td><td>{t0:.1f}</td><td>{html.escape(b.get('show', ''))}</td><td style='font-family:Deva'>"
                   f"{html.escape(b.get('say', ''))}</td><td>{html.escape(DESCRIBE.get(arch, arch))}</td><td>{html.escape(med)}</td></tr>")
    s3 += "".join(eng) + "</tbody></table>"

    # 4 video idea and design (from the Style DNA + plan)
    pal = {k: v for k, v in (dna.get("palette") or {}).items() if isinstance(v, str) and v.startswith("#")}
    sw = "".join(f'<div class="sw"><div style="background:{v}"></div>{k}<br>{v}</div>' for k, v in pal.items())
    strip = "".join(f'<div style="flex:{max(0.1, s["t1"] - s["t0"]):.2f};background:{ARCH_COLORS.get(s["archetype"], "#666")}" '
                    f'title="{s["archetype"]}">{i + 1}</div>' for i, s in enumerate(scenes))
    trans = {round(t["t"], 1): t["kind"] for t in plan.get("transitions", [])}
    rows = "".join(f"<tr><td>{i + 1}</td><td>{s['t0']:.1f}-{s['t1']:.1f}</td><td>{html.escape(DESCRIBE.get(s['archetype'], s['archetype']))}"
                   f"</td><td>{html.escape(', '.join(beats[i].get('hero', [])) if i < len(beats) else '')}</td>"
                   f"<td>{html.escape(trans.get(round(s['t0'], 1), 'cut-in' if i == 0 else ''))}</td></tr>" for i, s in enumerate(scenes))
    fonts = dna.get("fonts") or {}
    s4 = (f"<p><b>Concept:</b> {html.escape(str(hy.get('recommended_hook') or hook))}</p>"
          f"<h3>Palette ({html.escape(str(dna.get('palette_family', '')))})</h3><div class='swatches'>{sw}</div>"
          f"<h3>Look</h3><table><tbody>"
          f"<tr><td><b>Fonts</b></td><td>hero {fonts.get('hero')} · support {fonts.get('support')} · captions {fonts.get('caption')} · "
          f"Devanagari {fonts.get('deva')} (all SIL OFL)</td></tr>"
          f"<tr><td><b>Background / motif</b></td><td>{dna.get('background')} · motif {dna.get('motif')} · tone {dna.get('tone')}</td></tr>"
          f"<tr><td><b>Motion</b></td><td>{dna.get('motion')} springs · camera punches on hero words · shots cut on spoken words</td></tr>"
          f"<tr><td><b>Transitions</b></td><td>{', '.join(dna.get('transitions') or [])}</td></tr>"
          f"<tr><td><b>Captions</b></td><td>{dna.get('caption_style')}: word-by-word, active word highlighted, 64 px+, inside the safe zone</td></tr>"
          f"<tr><td><b>Sound</b></td><td>voice {words.get('rate', '')} · procedural {dna.get('music_mood')} music (original, licence-free) · "
          f"SFX on hits, ticks, stamps · −14 LUFS · no song audio</td></tr>"
          f"<tr><td><b>Loop</b></td><td>the last scene reuses the first scene's plate; the on-screen question sits on the final beat</td></tr>"
          f"</tbody></table><h3>Retention map</h3><div class='strip'>{strip}</div>"
          f"<table><thead><tr><th>#</th><th>Time (s)</th><th>Layout</th><th>Hero words (hit + SFX)</th><th>Transition in</th></tr></thead>"
          f"<tbody>{rows}</tbody></table>")

    # 5 frame board
    cells = []
    board = [(th, t) for k, (th, t) in enumerate(zip(thumbs, times)) if not (k == 1 and t < 1.5 and len(thumbs) > 2)]  # drop the near-duplicate hook frame
    for th, t in board:
        idx = next((i for i, s in enumerate(scenes) if s["t0"] <= t < s["t1"] + 1e-3), None)
        b = beats[idx] if idx is not None and idx < len(beats) else {}
        arch = scenes[idx]["archetype"] if idx is not None else ""
        cells.append(f'<div class="frame"><img src="{th.as_uri()}"><div class="lab"><b>{t:.1f}s · scene {"" if idx is None else idx + 1}</b> '
                     f'{html.escape(DESCRIBE.get(arch, arch))}<br>{html.escape(b.get("show", "")[:120])}</div></div>')
    s5 = ("<p class='small'>Real frames rendered by the engine at each scene's key moment (not mock-ups). Text is exactly as it will be "
          "burned in.</p><div class='grid'>" + "".join(cells) + "</div>"
          f"<div class='two break'><div><h3>Cover (grid crop guides)</h3><img src='{cover_img.as_uri()}' style='width:100%;border-radius:8px'>"
          f"<p class='small'>Cover text: {html.escape(str(hy.get('cover_text') or p.get('cover_text') or ''))}. Key text stays inside the "
          "yellow 3:4 box (profile grid).</p></div><div><h3>Safe-zone check</h3>"
          + (f"<img src='{safe_img.as_uri()}' style='width:100%;border-radius:8px'>" if safe_img else "<p>n/a: no contact sheet</p>")
          + "<p class='small'>Red lines = Reels UI zones (top 250 px, bottom ~420 px, right buttons below y=1000).</p></div></div>")

    # 6 how it will be built
    q = lambda c: f'<pre class="code"><code>{html.escape(c)}</code></pre>'  # noqa: E731
    proj = str(root)
    s6 = ('<div class="pipeline"><span>1 Research brief ✓</span><span>2 Script pack ✓</span><span>3 Proof frames ✓</span>'
          '<span class="stop">STOP: read this PDF → "continue"</span><span>4 make</span><span>5 QA PASS + review</span>'
          '<span>6 deliver</span><span>7 post + log</span></div>'
          "<table><thead><tr><th>Step</th><th>What happens</th><th>Command</th></tr></thead><tbody>"
          f"<tr><td>Voice</td><td>edge-tts {html.escape(str((p.get('voice') or {}).get('preset', '')))} with exact word timing (cached). "
          "Own recording instead: put it in media/ and set voice.engine=recording (Whisper alignment)</td><td><code>python run.py voice "
          f"{html.escape(proj)}</code></td></tr>"
          f"<tr><td>Proof</td><td>first 6 s + one frame per scene + contact sheet (done for this PDF)</td><td><code>python run.py proof {html.escape(proj)}</code></td></tr>"
          f"<tr><td>Make</td><td>full render (Pillow + numpy → ffmpeg, 4 workers), music + SFX mix, −14 LUFS, cover, upload pack, QA</td>"
          f"<td><code>python run.py make {html.escape(proj)}</code></td></tr>"
          f"<tr><td>Deliver</td><td>refuses unless QA PASS and an honest review.md exist</td><td><code>python run.py deliver {html.escape(proj)}</code></td></tr>"
          f"<tr><td>Log</td><td>history for the next chat; add Insights after 24 h</td><td><code>python run.py log {html.escape(proj)} --status made</code></td></tr>"
          "</tbody></table><h3>Export spec</h3><p>1080×1920 · 30 fps · H.264 (yuv420p, ≤10 Mbps) · AAC · −14 LUFS integrated, true peak ≤ −0.8 dBTP · "
          "plus a voice+SFX-only version for adding trending audio inside Instagram. Working defaults, not an official Instagram rule.</p>"
          + q(f"cd ~/.claude/skills/review-video-studio   # or the repo folder\npython run.py channel\npython run.py make {proj}\n"
              f"python run.py deliver {proj}\npython run.py log {proj} --status made"))

    # 7 publish pack
    tags = hy.get("hashtags") or []
    tags = tags if isinstance(tags, list) else str(tags).split()
    stories = (ch.get("schedule") or {}).get("stories", [])
    pub = [("Caption, first line", hy.get("caption_first_line", "")), ("Full caption", hy.get("caption_full", "")),
           ("Hashtags", " ".join(map(str, tags))), ("Pinned comment", hy.get("pinned_comment", "")),
           ("Cover text", hy.get("cover_text", "")), ("Post", f"{post_date} {when or ''} IST ({p.get('slot', '')}); reply to every comment for 60 min")]
    s7 = ("<table><tbody>" + "".join(f"<tr><td style='width:28%'><b>{a}</b></td><td>{html.escape(str(b))}</td></tr>" for a, b in pub) +
          "</tbody></table><h3>Stories</h3><table><tbody>" +
          "".join(f"<tr><td>{html.escape(str(s.get('time')))}</td><td>{html.escape(str(s.get('what')))}</td></tr>" for s in stories if isinstance(s, dict)) +
          "</tbody></table><h3>After posting</h3><ul><li>Upload <code>_no_music.mp4</code> if you add a trending Instagram audio (10–15 % volume); "
          "otherwise the main file.</li><li>After 24 h read in Insights: <b>skip rate</b> (first 3 s), <b>average watch time</b>, <b>sends</b>, "
          "follows. High skip rate → the hook (beat 1) failed; low watch time → the middle beats sag; low sends → the send-worthy line is weak.</li>"
          f"<li>Record it: <code>python run.py log {html.escape(proj)} --status posted --views N --skip-rate N --avg-watch N --sends N --follows N</code></li>"
          f"<li>A/B idea: test the runner-up hook from the script pack in a later reel; compare skip rate only.</li></ul>")

    # 8 background (script pack 3–6)
    bg = []
    for n in (3, 4, 5, 6):
        if n in sp:
            bg.append(f"<h2>{html.escape(sp[n][0])}</h2>" + md_to_html(sp[n][1]))
    s8 = "".join(bg) or "<p>n/a: script pack sections 3–6 not supplied</p>"

    # 9 QA, rights, credits, assumptions
    cr = read_json(root / "media" / "credits.json", {}) or {}
    def _nm(k):
        k = re.sub(r"\.(jpe?g|png|webp)$", "", k, flags=re.I).replace("__", " ").replace("_", " ").strip()
        return k if len(k) <= 48 else k[:46] + "…"

    def _src(s):
        s = str(s or "")
        return f'<a href="{html.escape(s)}">Commons page ↗</a>' if s.startswith("http") else html.escape(s)
    crow = "".join(f"<tr><td>{html.escape(_nm(k))}</td><td>{html.escape(str(v.get('author', ''))[:60])}</td><td>{html.escape(str(v.get('license', '')))}</td>"
                   f"<td>{_src(v.get('source'))}</td></tr>" for k, v in cr.items())
    caps = "".join(f"<tr><td>{a}</td><td>{'yes' if b else 'no'}</td><td>{c}</td></tr>" for a, b, c in capabilities())
    s9 = ("<h3>Credits (paste CC BY / BY-SA credits into the caption or first comment)</h3><table class='fixed'><colgroup><col style='width:34%'>"
          "<col style='width:24%'><col style='width:26%'><col style='width:16%'></colgroup><thead><tr><th>File</th><th>Author</th>"
          f"<th>Licence</th><th>Source</th></tr></thead><tbody>{crow or '<tr><td colspan=4>none</td></tr>'}</tbody></table>"
          "<h3>Licences</h3><ul><li>Fonts: SIL OFL 1.1 / Apache 2.0 (assets/fonts/licenses). Stickers: Microsoft Fluent UI Emoji, MIT.</li>"
          "<li>Music: procedural, composed by the engine (original, licence-free). No song audio, no film clips.</li>"
          "<li>Voice: Microsoft edge-tts neural voice (AI voice) unless you record your own.</li></ul>"
          "<h3>QA gates before delivery</h3><ul><li>QA must PASS (length ≤ 90 s, safe zones, text sizes, no static runs, captions cover the speech, "
          "loudness, footage coverage, variety vs. past videos).</li><li>review.md with ≥ 2 honest weaknesses; deliver refuses otherwise.</li></ul>"
          "<h3>If you see this, do this</h3><table><tbody>"
          "<tr><td>Text covers a face</td><td>letterbox the still and move the band (<code>\"y\": 0.64</code>) or crop elsewhere</td></tr>"
          "<tr><td>A photo shows the wrong person</td><td>remove it; a name monogram is used instead (never a wrong face)</td></tr>"
          "<tr><td>QA static run</td><td>give that beat more media items (first cut ≈ beat length ÷ items)</td></tr>"
          "<tr><td>Reel too long</td><td>cut words in the script pack, never speed up the voice past +32 %</td></tr></tbody></table>"
          "<h3>Reuse checklist</h3><ul><li>☐ Every VERIFY BEFORE POSTING item checked</li><li>☐ \"kal / aaj\" still true on the posting date</li>"
          "<li>☐ Cover set (never a blank thumbnail)</li><li>☐ ≤ 5 hashtags, #SceneSamjho first</li><li>☐ Logged in channel history</li></ul>"
          f"<h3>Build tools (this PDF)</h3><table><thead><tr><th>Tool</th><th>Used</th><th>Effect</th></tr></thead><tbody>{caps}</tbody></table>"
          "<h3>Assumptions (script pack)</h3>"
          + (md_to_html(sp[7][1]) if 7 in sp else ""))

    # Appendix A: the operator's next messages
    def card(name, meta, body):
        return f'<div class="prompt"><div class="meta">{html.escape(name)} · {html.escape(meta)}</div><pre>{html.escape(body)}</pre></div>'
    appA = (card("1 · Approve", "renders the video", "continue") +
            card("2 · Change a line", "re-runs voice + proof + this PDF",
                 f"Beat 3 ki line badlo: \"<nayi line>\". Baaki script frozen. Phir proof aur handover dobara banao ({proj}).") +
            card("3 · After posting", "updates channel history", f"Post ho gaya. Log karo: {proj} --status posted") +
            card("4 · 24 h numbers", "learning loop", "Ye reel ke 24 ghante ke Insights: views N, skip rate N%, avg watch N s, sends N, follows N. "
                 "Log karo aur bolo agle reel me kya badlein.") +
            card("5 · Next topic", "starts the whole system again", "Kal ke reel_2 ke liye topic: <film / trailer>. System chalao aur PDF do."))

    # Appendix B: research brief (log at the end)
    appB = md_to_html(rb_md) if rb_md else "<p>n/a: research brief not supplied</p>"

    body = (cover + _sec("2", "Overview (read first)", ov) + _sec("3", "Final script", s3) + _sec("4", "Video idea and design", s4)
            + _sec("5", "Frame board", s5) + _sec("6", "How it will be built", s6) + _sec("7", "Publish pack", s7)
            + _sec("8", "Background: why it will hold, what was wrong", s8) + _sec("9", "QA, rights, credits, assumptions", s9)
            + _sec("A", "Appendix A: your next messages to Claude", appA) + _sec("B", "Appendix B: research brief", appB))
    doc = (f"<!doctype html><html lang='hi'><head><meta charset='utf-8'><title>{html.escape(title)}</title><style>{_css(accent)}</style>"
           f"</head><body>{body}</body></html>")
    out.mkdir(parents=True, exist_ok=True)
    html_path = work / f"reel-handover_{slug}.html"
    html_path.write_text(doc, encoding="utf-8")
    res = {"html": str(html_path), "pdf": None, "pages": [], "fallback": None}
    if html_only:
        res["fallback"] = "html (requested)"
        return res
    pdf = out / f"reel-handover_{slug}.pdf"
    if not render_pdf(html_path, pdf, f"{title} · reel handover"):
        res["fallback"] = "html (no headless Chromium); open the .html file"
        return res
    res["pdf"] = str(pdf)
    res["pages"] = [str(x) for x in rasterise(pdf, work / "handover_pages")]
    return res


_JS = r"""
const { chromium } = require('playwright');
(async () => {
  const [src, dst, foot] = process.argv.slice(2);
  const b = await chromium.launch();
  const pg = await b.newPage();
  await pg.goto('file://' + src, { waitUntil: 'load' });
  await pg.evaluate(() => document.fonts.ready);
  await pg.pdf({ path: dst, format: 'A4', printBackground: true, displayHeaderFooter: true,
    headerTemplate: '<span></span>',
    footerTemplate: `<div style="font-size:7.5px;width:100%;padding:0 18mm;display:flex;justify-content:space-between;color:#666;font-family:sans-serif">
      <span>${foot}</span><span class="pageNumber"></span></div>`,
    margin: { top: '16mm', bottom: '18mm', left: '0', right: '0' } });
  await b.close();
})().catch(e => { console.error(e); process.exit(1); });
"""


def render_pdf(html_path: Path, pdf: Path, footer: str) -> bool:
    node = shutil.which("node")
    if not node:
        return False
    js = html_path.parent / "_render_pdf.js"
    js.write_text(_JS, encoding="utf-8")
    r = subprocess.run([node, str(js), str(html_path.resolve()), str(pdf.resolve()), html.escape(footer)], capture_output=True, text=True, timeout=300)
    if r.returncode != 0:
        log(f"handover: PDF render failed: {r.stderr[-400:]}")
        return False
    return pdf.exists()


def rasterise(pdf: Path, out_dir: Path, dpi=60) -> list[Path]:
    if not shutil.which("pdftoppm"):
        return []
    if out_dir.exists():
        for f in out_dir.glob("page-*.png"):
            f.unlink()
    out_dir.mkdir(parents=True, exist_ok=True)
    subprocess.run(["pdftoppm", "-r", str(dpi), "-png", str(pdf), str(out_dir / "page")], check=True, timeout=300)
    pages = sorted(out_dir.glob("page-*.png"))
    if pages:  # one overview sheet of all pages for a quick look
        ims = [Image.open(x).convert("RGB") for x in pages]
        w, h = ims[0].size
        cols = 4
        rows = (len(ims) + cols - 1) // cols
        sheet = Image.new("RGB", (cols * (w + 8), rows * (h + 8)), "white")
        for i, im in enumerate(ims):
            sheet.paste(im, ((i % cols) * (w + 8), (i // cols) * (h + 8)))
        sheet.save(out_dir / "all_pages.png")
    return pages
