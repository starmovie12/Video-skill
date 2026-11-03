"""deliver.py — what the operator uploads: Reel cover (9:16) + profile-grid crop (4:5), and upload_pack.md
(caption draft, hashtags, media credits, cover time, music advice). The Director refines the caption; facts stay as written."""
from __future__ import annotations

import re
from pathlib import Path

from PIL import ImageEnhance

from . import gfx
from .core import W, read_json
from .typo import apply_case, text_sprite

GENRE_TAGS = {"horror": "#horror", "thriller": "#thriller", "action": "#action", "comedy": "#comedy", "romance": "#romance", "drama": "#drama",
              "scifi": "#scifi", "sci-fi": "#scifi", "animation": "#animation", "crime": "#crime", "fantasy": "#fantasy",
              "documentary": "#documentary"}
BASE_TAGS = {"movie_review": ["#moviereview", "#filmreview", "#hindireview", "#reelsindia"], "product": ["#newcollection", "#shopnow", "#reelsindia"],
             "facts": ["#facts", "#didyouknow", "#hindifacts", "#reelsindia"], "story": ["#story", "#hindistory", "#reelsindia"],
             "software": ["#tech", "#apps", "#techhindi", "#reelsindia"], "game": ["#gaming", "#gamereview", "#reelsindia"]}


def best_cover_time(tl) -> float:
    """The title / poster scene if there is one, else the end of the hook (all hook words on screen)."""
    for p in tl.plan:
        if p["archetype"] in ("poster_hero", "product_hero"):
            return round(p["t0"] + (p["t1"] - p["t0"]) * 0.75, 2)
    p = tl.plan[0]
    return round(min(p["t1"] - 0.1, p["t0"] + (p["t1"] - p["t0"]) * 0.9), 2)


def make_cover(tl, project: dict, out_dir: Path) -> dict:
    pal, F = tl.dna["palette"], tl.dna["fonts"]
    t = best_cover_time(tl)
    base = tl.background_frame(t)
    base = ImageEnhance.Brightness(base).enhance(0.62)
    im = base.convert("RGBA")
    text = project.get("cover_text") or project.get("title", "")
    text = re.sub(r"\(.*?\)", "", text).strip()
    tsp = text_sprite(apply_case(text, "upper"), F["hero"], None, deva_fid=F["deva"], color="#FFFFFF", box=(920, 520), max_lines=3,
                      max_px=230, min_px=80, stroke=0.05, stroke_color="#000000", shadow=(0, 10, 18, 0.8, "#000000"),
                      highlight={re.sub(r"\W", "", w.lower()) for w in text.split()[-1:]}, highlight_color=pal["accent"])
    y_mid = 285 + (1635 - 285) * 0.45  # centre of the 4:5 grid-safe box
    im.alpha_composite(tsp.img, (int(W / 2 - tsp.w / 2), int(y_mid - tsp.h / 2)))
    facts = project.get("facts", {})
    if project.get("category") == "movie_review" and facts.get("rating") is not None:
        n = 5
        val = float(facts["rating"]) / float(facts.get("out_of", 5)) * n
        y = int(y_mid + tsp.h / 2 + 10)
        for i in range(n):
            st = gfx.star(110, max(0.0, min(1.0, val - i)), pal["accent"], "#FFFFFF55")
            im.alpha_composite(st, (int(W / 2 + (i - 2) * 124 - 55), y))
    tag = project.get("cover_tag") or {"movie_review": "REVIEW", "product": "NEW", "facts": "FACTS", "story": "STORY",
                                       "software": "TECH", "game": "GAME"}.get(project.get("category", ""), "")
    if tag:
        tg = text_sprite(tag, F["support"], 54, color=pal["ink"], box=(2000, 300), max_lines=1)
        pill = gfx.card(tg.w + 40, tg.h + 10, fill=pal["accent"], kind="pill")
        pill.alpha_composite(tg.img, (20, 5))
        im.alpha_composite(pill, (int(W / 2 - pill.width / 2), int(y_mid - tsp.h / 2 - pill.height - 20)))
    out_dir.mkdir(parents=True, exist_ok=True)
    cov = out_dir / "cover_9x16.jpg"
    im.convert("RGB").save(cov, quality=92)
    grid = out_dir / "cover_grid_4x5.jpg"
    im.convert("RGB").crop((0, 285, 1080, 1635)).save(grid, quality=92)
    return {"cover": str(cov), "grid": str(grid), "frame_time": t}


def upload_pack(project: dict, tl, qa: dict, out: Path, root: Path, cover: dict) -> Path:
    beats = project["beats"]
    hook = beats[0].get("show") or beats[0].get("say", "")
    cta = next((b for b in reversed(beats) if b.get("role") in ("cta", "question")), beats[-1])
    question = (cta.get("data") or {}).get("question") or cta.get("show", "")
    facts = project.get("facts", {})
    title = facts.get("title") or project.get("title", "")
    tags = list(BASE_TAGS.get(project.get("category", ""), ["#reelsindia"]))
    for g in facts.get("genre", []) if isinstance(facts.get("genre"), list) else []:
        if g.lower() in GENRE_TAGS and GENRE_TAGS[g.lower()] not in tags:
            tags.append(GENRE_TAGS[g.lower()])
    t_tag = "#" + re.sub(r"[^A-Za-z0-9]", "", title.title())[:30]
    if len(t_tag) > 2:
        tags.insert(0, t_tag)
    from .channel import hashtags as ch_hashtags, load as load_channel
    ch = load_channel() if project.get("channel") else None
    tags = ch_hashtags(project, ch, tags)
    credits = read_json(root / "media" / "credits.json", {}) or {}
    cred_lines = [f"- {k}: {v.get('author', '?')} — {v.get('license', '?')} ({v.get('source', '')})" for k, v in credits.items()]
    music = qa.get("mix", {}).get("music_source", "")
    ch_lines = []
    if ch:
        from .channel import post_times, slot_time
        import datetime as dt
        sch = ch.get("schedule", {})
        mine = slot_time(project, ch)
        when = (f"**{mine} IST** ({project.get('slot') or 'post_at'})" if mine
                else "slots today: " + ", ".join(post_times(dt.date.today(), ch)) + " IST — set `slot` (reel_1 / reel_2) in project.json")
        stories = "; ".join(f"{s.get('time')} {s.get('what')}" if isinstance(s, dict) else str(s) for s in sch.get("stories", []))
        ch_lines = ["## Channel", f"- **{ch.get('name')}** ({ch.get('handle')}) · {ch.get('platform')} · {ch.get('account_type')} account",
                    f"- Post at {when}",
                    f"- Stories ({sch.get('stories_per_day', '')}/day): {stories}",
                    f"- Stay online {sch.get('reply_window_min', 60)} min after posting and reply to every comment",
                    f"- Then: `python run.py log <project> --status posted`, and after 24 h add Insights numbers "
                    f"(--views --skip-rate --avg-watch --sends --follows)", ""]
    lines = [f"# Upload pack — {project.get('title', '')}", "", *ch_lines,
             "## Caption (draft — Director: rewrite in your own words, keep facts exact)", "",
             f"{hook}", "", f"{question} 👇", "", " ".join(tags), "",
             "## Cover", f"- Reel cover: `{Path(cover['cover']).name}` (frame at {cover['frame_time']}s) · profile grid crop: `{Path(cover['grid']).name}`",
             "", "## Files",
             f"- With music: `{Path(qa['video']).name}`",
             f"- Voice + SFX only (add a trending Instagram audio in-app at 10–15 % volume): `{Path(qa['video']).stem}_no_music.mp4`",
             f"- Music in the main file: {music}", "",
             "## Credits (required for CC BY / CC BY-SA media — paste into the caption or first comment)",
             *(cred_lines or ["- none (only operator-supplied or public-domain/procedural assets)"]), "",
             "## Posting checklist",
             f"- Length {qa.get('duration')} s · 1080×1920 · 30 fps · −14 LUFS",
             "- First line of the caption = the hook; ask the comment question; reply to early comments.",
             "- Posters/trailer clips of new films are copyrighted: use only operator-licensed or official press material."]
    out.write_text("\n".join(lines), encoding="utf-8")
    return out

