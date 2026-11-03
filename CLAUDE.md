# Scene Samjho: read this first

This repo is the video skill for **one channel**:

- **Name:** Scene Samjho
- **Instagram:** [@scene.samjho1](https://instagram.com/scene.samjho1) (Creator account)
- **What we make:** Bollywood + OTT **"DECODE"** reels in Hindi: trailers, songs, box office, OTT releases, film facts.
- **Who it's for:** the operator, who talks in Hinglish (Roman). Reply in Hinglish.

Every script and video made here is for this channel. Its profile, schedule and rules live in `channel/channel.json`. The engine applies them automatically: new projects, lint, QA and the upload pack all read that file.

## Before any script or video

1. Run `python run.py channel`. It shows:
   - today's and tomorrow's pillar
   - the posting time
   - the reel rules
   - recent topics (never repeat one)
2. Read `channel/CHANNEL.md` (how we make videos for this channel) and `SKILL.md` (how the engine works).

## Rules that always apply

- **Script first.** Research the topic on the web, then write the script MD with a source for every fact. Show it to the operator and **wait for "continue"** before rendering.
- **Reel shape:**
  - 45–60 s (hard max 90 s)
  - hook in the first 2 s
  - one topic per reel
  - end with a send line ("ye us dost ko bhejo jo…") and a two-option question
- **Upload:** cover always; ≤5 hashtags, `#SceneSamjho` first.
- **Post** daily at **19:30 IST**. From 17 Nov 2026 add a second post at 13:00. Stories at 09:00 (poll) and 21:00 (share).
- **Original content only:** voice-over + analysis + graphics.
  - No raw movie clips, no reposts.
  - Theories are called theories.
  - Wikimedia Commons photos only with their credits.
- **Where projects live:** outside this repo, in `~/scene_samjho/<YYYY-MM-DD>_<topic>/` (or any folder outside the repo). Never commit copyrighted stills or rendered videos here.

## After making and after posting

1. After making: `python run.py log <project> --status made`.
2. After posting: `--status posted`.
3. After 24 h: add Insights numbers (`--views --skip-rate --avg-watch --sends --follows`).
4. Commit + push `channel/` (history + `state/` style ledger) so the next chat remembers.
5. Every Tuesday: weekly review of `channel/history.jsonl`. Do more of what worked and update `channel/channel.json` if the plan changes.

## Honesty

- No video is guaranteed to go viral. Say so if asked.
- Never invent views, facts or sources.
