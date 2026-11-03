"""Channel memory: the ONE Instagram channel this skill makes videos for.

`channel/channel.json` (committed in the skill repo) holds who the channel is, its niche, schedule and reel rules;
`channel/history.jsonl` logs every video (topic, status, Insights numbers). A new chat reads both through
`run.py channel`, new projects inherit the defaults, lint/QA enforce the reel rules, and the upload pack carries the
handle, posting time and hashtag policy — so every script and video is made for this channel without re-explaining it.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DAYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")


def channel_dir() -> Path:
    return Path(os.environ.get("RVS_CHANNEL", ROOT / "channel"))


def load() -> dict | None:
    f = channel_dir() / "channel.json"
    if not f.exists():
        return None
    return json.loads(f.read_text(encoding="utf-8"))


def _merge(base, over):
    if isinstance(base, dict) and isinstance(over, dict):
        out = dict(base)
        for k, v in over.items():
            out[k] = _merge(base.get(k), v) if k in base else v
        return out
    return over


def apply_defaults(project: dict, ch: dict | None = None) -> dict:
    """Fill channel defaults into a project. Anything the project already sets wins."""
    ch = ch if ch is not None else load()
    if not ch:
        return project
    d = ch.get("defaults", {})
    out = dict(project)
    for k, v in d.items():
        if k in ("voice", "dna"):
            out[k] = _merge(v, out.get(k) or {})
        elif k not in out or out[k] in (None, "", 0):
            out[k] = v
    out.setdefault("channel", {"name": ch.get("name"), "handle": ch.get("handle")})
    return out


def pillar_for(day: dt.date, ch: dict) -> str:
    return ch.get("weekly_rhythm", {}).get(DAYS[day.weekday()], "")


def history(limit: int | None = None) -> list[dict]:
    f = channel_dir() / "history.jsonl"
    if not f.exists():
        return []
    rows = [json.loads(ln) for ln in f.read_text(encoding="utf-8").splitlines() if ln.strip()]
    return rows[-limit:] if limit else rows


def log(entry: dict) -> dict:
    """Append a history row, or update the existing row of the same project (made → posted → Insights numbers)."""
    f = channel_dir() / "history.jsonl"
    rows = history()
    key = entry.get("project")
    for r in rows:
        if key and r.get("project") == key:
            r.update({k: v for k, v in entry.items() if v is not None})
            break
    else:
        rows.append({k: v for k, v in entry.items() if v is not None})
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    return next((r for r in rows if key and r.get("project") == key), rows[-1])


def _words(text: str) -> int:
    return len([w for w in re.split(r"\s+", text or "") if re.search(r"\w", w)])


def lint(project: dict, ch: dict | None = None) -> tuple[list[str], list[str]]:
    """Channel reel rules → (errors, warnings). Long-form projects (`"format": "long"`) skip the length rules."""
    ch = ch if ch is not None else load()
    if not ch:
        return [], []
    r = ch.get("reel_rules", {})
    errs, warns = [], []
    beats = project.get("beats", [])
    if project.get("format", "reel") == "reel":
        tgt = float(project.get("target_sec") or 0)
        if tgt > r.get("hard_max_sec", 90):
            errs.append(f"CHANNEL_LENGTH: target_sec {tgt:.0f} > {r.get('hard_max_sec', 90)} s — reels over 90 s are not pushed to "
                        f"non-followers. Cut the script, or set \"format\": \"long\" for a deliberate long video")
        elif tgt > r.get("max_sec", 60):
            warns.append(f"CHANNEL_LENGTH: target_sec {tgt:.0f} > {r.get('max_sec', 60)} s — channel reels aim for "
                         f"{r.get('min_sec', 30)}–{r.get('max_sec', 60)} s")
        n = sum(_words(b.get("say", "")) for b in beats)
        lo, hi = r.get("script_words", [110, 160])
        if n > hi + 40:
            errs.append(f"CHANNEL_WORDS: {n} spoken words ≈ {n / 2.8:.0f} s — too long for a reel (aim {lo}–{hi})")
        elif n > hi:
            warns.append(f"CHANNEL_WORDS: {n} spoken words — a bit long for a {r.get('max_sec', 60)} s reel (aim {lo}–{hi})")
    if beats:
        hw = _words(beats[0].get("say", ""))
        if hw > r.get("hook_max_words", 16):
            warns.append(f"CHANNEL_HOOK: the hook has {hw} words — keep it ≤ {r.get('hook_max_words', 16)} so it lands in ~2 s")
        text = " ".join(str(b.get("show") or b.get("say") or "") for b in beats).lower()
        if not any(w in text for w in r.get("send_cta_words", [])):
            warns.append("CHANNEL_SEND_LINE: add one send-worthy line that names a kind of person ('wo dost jo hamesha…') — sends drive "
                         "reach to non-followers (no 'share/like/follow karo')")
        tail = " ".join(str(b.get("show") or b.get("say") or "") + " " + str((b.get("data") or {}).get("question", "")) for b in beats[-2:])
        if "?" not in tail:
            warns.append("CHANNEL_QUESTION: the last beat needs a two-option comment question (on screen via data.question, or spoken)")
    return errs, warns


def hashtags(project: dict, ch: dict | None, candidates: list[str]) -> list[str]:
    """Channel hashtag policy: base tags first, then the project's own, capped at hashtags_max (no duplicates)."""
    if not ch:
        return candidates[:9]
    r = ch.get("reel_rules", {})
    tags = []
    for t in list(project.get("hashtags") or []) + list(r.get("base_hashtags", [])) + candidates:
        t = t if t.startswith("#") else "#" + t
        if t.lower() not in [x.lower() for x in tags]:
            tags.append(t)
    own = [t for t in tags if t.lower() not in [b.lower() for b in r.get("base_hashtags", [])]]
    base = [t for t in tags if t not in own]
    return (base + own)[: r.get("hashtags_max", 5)]


def post_times(day: dt.date, ch: dict) -> list[str]:
    """Reel slots for that day, e.g. ['reel_1 13:00', 'reel_2 19:30'] (weekend times on Sat/Sun)."""
    sch = ch.get("schedule", {})
    key = "weekend" if day.weekday() >= 5 else "weekday"
    return [f"{p.get('slot')} {p.get(key) or p.get('weekday')}" for p in sch.get("posts", [])]


def slot_time(project: dict, ch: dict, day: dt.date | None = None) -> str | None:
    """Posting time for this project: `post_at` wins, else its `slot` (reel_1 / reel_2) on that day."""
    if project.get("post_at"):
        return str(project["post_at"])
    day = day or dt.date.today()
    key = "weekend" if day.weekday() >= 5 else "weekday"
    for p in ch.get("schedule", {}).get("posts", []):
        if p.get("slot") == project.get("slot"):
            return p.get(key) or p.get("weekday")
    return None


def brief(today: dt.date | None = None) -> dict:
    ch = load()
    if not ch:
        return {"channel": None, "note": "no channel/channel.json — generic mode"}
    today = today or dt.datetime.now(dt.timezone(dt.timedelta(hours=5, minutes=30))).date()
    tomorrow = today + dt.timedelta(days=1)
    sch = ch.get("schedule", {})
    recent = history(12)
    return {
        "channel": f"{ch.get('name')} ({ch.get('handle')}) · {ch.get('platform')} · {ch.get('account_type')} account",
        "niche": ch.get("niche"),
        "today": f"{today.isoformat()} ({DAYS[today.weekday()]}) → pillar: {pillar_for(today, ch)}",
        "tomorrow": f"{tomorrow.isoformat()} ({DAYS[tomorrow.weekday()]}) → pillar: {pillar_for(tomorrow, ch)}",
        "trend_override": ch.get("trend_override"),
        "reels_today_ist": post_times(today, ch),
        "reels_tomorrow_ist": post_times(tomorrow, ch),
        "slots": sch.get("posts"),
        "slot_rule": sch.get("slot_rule"),
        "stories_per_day": sch.get("stories_per_day"),
        "stories": sch.get("stories"),
        "day_plan": sch.get("day_plan"),
        "reel_rules": ch.get("reel_rules"),
        "workflow": ch.get("workflow"),
        "never": ch.get("never"),
        "recent_topics_do_not_repeat": [f"{r.get('date')} · {r.get('topic')} · {r.get('status')}"
                                       + (f" · {r['views']} views" if r.get("views") is not None else "") for r in recent],
        "pillars": ch.get("pillars"),
    }
