# Scene Samjho: channel playbook

> Machine-readable version: `channel/channel.json` (the engine reads it). This file is the "why" and the "how".
> 30-day growth plan with sources: `channel/GROWTH_PLAN.md`.

## Who we are

| | |
|---|---|
| Name | **Scene Samjho** |
| Instagram | **@scene.samjho1**: Creator account (full music library), category "Reel creator" |
| Bio | 🎬 Trailer, gaane, box office: DECODE in Hindi \| 🔍 Har scene ka asli matlab \| 🕖 Roz shaam 7:30 baje naya reel |
| Niche | Bollywood + OTT **DECODE** in Hindi. Never mix in other niches (AI tips, call recordings, reposts) |
| Audience | Hindi-speaking movie fans in India, 16–35, on phones, often with sound off |
| Language | Hindi voice-over (written in Devanagari for TTS) + Roman Hinglish captions |
| Started | 3 Nov 2026 (old posts archived; Account Status all green) |

## Pillars and weekly rhythm

| Day | Pillar | What | Typical archetypes |
|---|---|---|---|
| Mon | 📊 numbers | Weekend box office, budget, advance booking: one big number | stat_counter, timeline, split_compare |
| Tue | 🎬 decode | New trailer / song / teaser, scene by scene | story_panels, split_compare, quote_kinetic |
| Wed | 🤯 facts | "N baatein jo koi nahi jaanta" | fact_bomb, cast_spotlight, list_reveal |
| Thu | 🎬 decode | Same as Tue | |
| Fri | 📺 this_week | Theatre + OTT this week, one-line verdict each | list_reveal, verdict_stamp |
| Sat | 🤔 theory | Fan theories or a debate | list_reveal, split_compare, cta_loop |
| Sun | 🤯 facts | Evergreen / throwback facts | fact_bomb, timeline |

**Trend override:** if a big trailer, teaser, song, release or box-office headline broke in the last 24 h, drop the pillar and decode that, the same day.

## Schedule (IST)

| Time | What |
|---|---|
| 09:00 | Research the topic (Prompt A) · Story poll about it |
| 10:00 | Script MD to the operator. **Wait for "continue"** |
| 11:00 | proof → look at the frames → make → QA PASS → review → deliver |
| 13:00 | Second reel (only from 17 Nov, and only if quality holds) |
| **19:30** | **Main reel goes live** · share to Story at 21:00 |
| 19:30–20:30 | Reply to every comment |
| +24 h | `run.py log … --status posted --views … --skip-rate … --avg-watch … --sends … --follows …` |

## Reel rules (and why)

| Rule | Why |
|---|---|
| 45–60 s, never over 90 s | Watch-time %. Reels over 3 min are reported not to reach non-followers, and new accounts grow from non-followers |
| Hook ≤ 16 words, lands in ~2 s, subject on screen in frame 1 | Skip rate = viewers gone in the first 3 s |
| One topic per reel | People watch to the end |
| Last beat = send line + two-option question | Instagram's top signals: watch time, likes per reach, **sends per reach** (sends weigh more for non-followers) |
| Facts with sources; theories labelled | Trust; no misinformation |
| Original only: our VO + analysis + graphics; Commons CC photos with credits | April 2026 originality policy: repost-heavy accounts lose recommendations |
| Cover always (the skill's `cover_9x16.jpg`) | Grid clicks; a blank thumbnail kills profile visits |
| ≤ 5 hashtags, `#SceneSamjho` first | Reported 5-hashtag limit; no spam look |
| `_no_music.mp4` + a trending Instagram audio at 10–15 % | Creator account has the full music library |

## Script template (≈50 s, 130–150 words)

1. **hook** (`hook_slam`): the most surprising fact, ≤ 14 words. No greeting.
2. **context** (`kinetic_line`): why now (release, trailer, number), ≤ 15 words.
3–7. **content beats:** 4–5 beats from the pillar's archetypes, 12–20 words each, one fact per beat, no archetype twice in a row.
8. **cta** (`cta_loop`): "Ye video us dost ko bhejo jo …" + a two-option question ("FDFS ya review ke baad?").

- `say` = Devanagari for the voice; `show` = Roman Hinglish, the same number of words.
- Hero words on the payoff word of each beat.
- Beats where the graphic appears late (story panels, cards, counters) need enough media items that a cut lands within ~2.2 s (see SKILL.md, "Where cuts land").

## Prompts the operator uses

- **A, topic:** "Skill activate karo. Aaj ka topic research karo aur script banao."
  - Claude runs `run.py channel`, researches the last 24–48 h, and proposes the top 3 topics with sources.
  - Then it picks one and writes the script MD.
- **B, make:** "continue". Claude builds the project, renders proof → make → QA → deliver, then logs it.
- **C, weekly review:** "Ye 7 reels ke Insights screenshots hain, review karo."
  - Claude updates `history.jsonl` with the numbers and compares hooks, pillars and lengths.
  - It adjusts the plan in `channel.json` if needed.
- **D, part 2:** "Ye reel chala, iska part 2 / naya hook version banao."

## History and memory

- `channel/history.jsonl`: one row per video (topic, pillar, hook, length, status, Insights numbers).
  - Never repeat a topic that is already there, unless it is a deliberate Part 2.
- `channel/state/ledger.json`: past looks. The next video's Style DNA differs from the last ones.
- Commit + push both after every video, so a new chat remembers.
