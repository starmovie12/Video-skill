# Scene Samjho: channel playbook

> Machine-readable version: `channel/channel.json` (the engine reads it). This file is the "why" and the "how".
> 30-day growth plan with sources: `channel/GROWTH_PLAN.md`.

## Who we are

| | |
|---|---|
| Name | **Scene Samjho** |
| Instagram | **@scene.samjho1**: Creator account (full music library), category "Reel creator" |
| Bio | 🎬 Trailer, gaane, box office: DECODE in Hindi \| 🔍 Har scene ka asli matlab \| 🕐 Roz 2 reels: 1 PM & 7:30 PM |
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

## Schedule (IST): 2 reels + 3 Stories every day (from 4 Nov 2026)

| Slot | Mon–Fri | Sat–Sun | Topic |
|---|---|---|---|
| **reel_1** | **13:00** | 12:30 | The time-sensitive topic (release tomorrow, trailer just out, box-office headline), so it has more hours to spread |
| **reel_2** | **19:30** | 20:30 | Prime time: the day's pillar or the strongest topic |

**Slot rules:**
- Two different topics a day. Never two reels on the same film the same day.
- Set `"slot": "reel_1"` or `"reel_2"` in project.json. The upload pack then prints the exact time.

**Stories (3 a day, a 4th optional):**

| Time | Story |
|---|---|
| 09:00 | Poll / quiz about today's two topics ("Aaj Ramayana ya Eetha?") |
| 13:15 | Share reel 1 with a "NEW REEL" sticker |
| 19:45 | Share reel 2 |
| 21:30 | Optional: poll result, question box, or tomorrow's teaser |

**Day plan:**

| Time | What |
|---|---|
| 09:00 | Research both topics (last 24–48 h) · morning Story |
| 09:30 | Script MD for reel 1 → operator → **wait for "continue"** |
| 10:00 | Make reel 1 (proof → make → QA → deliver) · script MD for reel 2 |
| 13:00 | Reel 1 live · reply to comments till 14:00 |
| 15:00 | Make reel 2 after "continue" |
| 19:30 | Reel 2 live · reply to comments till 20:30 |
| +24 h | `run.py log … --slot reel_1/reel_2 --status posted --views … --skip-rate … --avg-watch … --sends … --follows …` |

Timing sources:
- Third-party India data puts weekday evenings (7–9 PM) strongest and 11 AM–2 PM second.
- One source suggests 2–3 Stories a day; Mosseri reportedly advises "a couple of Stories per day".
- After 2 weeks, check Insights → "Most active times" and move the slots if needed.

## Reel rules (and why)

| Rule | Why |
|---|---|
| 25–60 s, never over 90 s (test 25–40 s from 4 Nov 2026) | Watch-time %. Ramayan reel (49 s): avg watch 7 s, ~3 % reached the end. Reels over 3 min are reported not to reach non-followers, and new accounts grow from non-followers |
| Hook ≤ 16 words, lands in ~2 s, subject on screen in frame 1 | Skip rate = viewers gone in the first 3 s |
| One topic per reel | People watch to the end |
| Last beat = send line + two-option question | Instagram's top signals: watch time, likes per reach, **sends per reach** (sends weigh more for non-followers) |
| Facts with sources; theories labelled | Trust; no misinformation |
| Original only: our VO + analysis + graphics; Commons CC photos with credits | April 2026 originality policy: repost-heavy accounts lose recommendations |
| Cover always (the skill's `cover_9x16.jpg`) | Grid clicks; a blank thumbnail kills profile visits |
| ≤ 5 hashtags, `#SceneSamjho` first | Reported 5-hashtag limit; no spam look |
| `_no_music.mp4` + a trending Instagram audio at 10–15 % | Creator account has the full music library |

## Look rotation and the face-cam (from 4 Nov 2026)

- **Every reel gets a different look** (Style DNA `look`):
  - `clean` — bright footage, only numbers on screen;
  - `rush` — fast photo cuts;
  - `bar` — series header;
  - `split` — footage on top, face-cam or words below;
  - `poster` — designed text cards.
- QA fails a reel whose look repeats the previous one.
- **The single biggest upgrade is the operator on camera.** Record a selfie video reading the script (phone, front camera, vertical, quiet room) → `media/host.mp4` → `"assets": {"host": "media/host.mp4"}`. Its voice replaces the AI voice.
- See `docs/REFERENCE_ANALYSIS.md` for why: all 5 reference creators show their face.

## Script template (≈35 s, 90–120 words; talk like a person: `reel_rules.voice_style`)

1. **hook** (`hook_slam`): the most surprising fact, ≤ 14 words. No greeting.
2. **context** (`kinetic_line`): why now (release, trailer, number), ≤ 15 words.
3–7. **content beats:** 4–5 beats from the pillar's archetypes, 12–20 words each, one fact per beat, no archetype twice in a row.
8. **cta** (`cta_loop`): "Ye video us dost ko bhejo jo …" + a two-option question ("FDFS ya review ke baad?").

- `say` = Devanagari for the voice; `show` = Roman Hinglish, the same number of words.
- Hero words on the payoff word of each beat.
- Beats where the graphic appears late (story panels, cards, counters) need enough media items that a cut lands within ~2.2 s (see SKILL.md, "Where cuts land").

## Prompts the operator uses

- **A, topic:** "Skill activate karo. Aaj ka topic research karo" or "<film> par reel".
  - Claude runs `run.py channel`, researches the last 24–48 h and picks the topic.
  - Then it runs the three-prompt system (`prompts/ADAPTATION.md`): research brief → script doctor → proof frames → **handover PDF**.
  - The PDF goes to the operator.
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

## Lessons from real numbers

| Date | Reel | Numbers | What we change |
|---|---|---|---|
| 4 Nov 2026 | Drishyam "2 October yaad hai na?" (39 s) | 481 views, skip 52.6 %, avg watch 5 s, 2 likes, 0 shares, 0 follows (at ~4 h) | Frame-1 hook cut the skip rate by 10 points and tripled views, but people left right after it. Compared with 5 top creators (`docs/REFERENCE_ANALYSIS.md`): they show a real person, bright footage, almost no text, and their layout is nothing like ours. Now: a different look every reel (clean / rush / bar / split / poster), talk like a person (`reel_rules.voice_style`), and the operator's face-cam when possible (`assets.host`). |
| 4 Nov 2026 | Ramayan 1987 vs 2026 (49 s) | 158 views, skip 62.7 %, avg watch 7 s, 0 shares, 0 follows (at 2 h) | Half the viewers left in the first second. Frame 1 showed a poster with one word, the payoff came at ~4 s, the send line came at 45 s. Now: whole hook text on frame 1, payoff by 2 s, 25–40 s, send line before ~70 %, share-able topics (a meme people already send, a debate, a missed detail). |
