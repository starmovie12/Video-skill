# Script system: topic → PDF → "continue" → video

The operator's three prompts run in a fixed order for every reel:

| File | Version | Output |
|---|---|---|
| `1-research-brief.md` | v3.0 | research brief |
| `2-script-doctor.md` | v4.0 | script pack |
| `3-pdf-handover-builder.md` | v3.0 | handover PDF |

The skill runs them **in that order** and adapts them to this engine and to the channel in `channel/channel.json`. Older copies the operator shared (Script Doctor v2/v3) are superseded by v4 and not used.

**Trigger:** the operator names a topic or a film, for example:
- "Ramayana par reel"
- "Eetha trailer decode"
- "kal ki dono reels"

The operator gets **one PDF** to read. The video is rendered only after they write **"continue"**.

## Stages

| # | Stage | Done by | Output (inside the project folder) |
|---|---|---|---|
| 0 | Set up | `python run.py channel`; `python run.py new movie_review ~/scene_samjho/<date>_<slug>`; set `slot`, `post_date`, `title` | `project.json` with channel defaults |
| 1 | Research Brief (prompt 1) | Claude: web search + page fetch | `pack/research-brief_<slug>.md` |
| 2 | Script Doctor (prompt 2) | Claude: Draft-0, then score → flaws → tournament → swipe test → re-audit | `pack/script-pack_<slug>.md` |
| 3 | Preview build | Claude writes the beats into `project.json` → `lint` → `voice` → `proof` → look at the frames and fix layout | `work/proof_frames/`, `work/plan.json`, `work/dna.json` |
| 4 | Handover PDF (prompt 3) | `python run.py handover <project>`, then look at **every** page PNG and fix | `out/reel-handover_<slug>.pdf`, `work/handover_pages/` |
| 5 | **STOP** | Send the PDF and wait for "continue" | none |
| 6 | Video | `make` → QA PASS → `review.md` → `deliver` → send files → `run.py log --status made` → commit `channel/` | mp4, no-music mp4, cover, upload pack |

If the operator asks for a change after reading the PDF:
1. Edit `script-pack` and `project.json`.
2. Re-run `voice` → `proof` → `handover`.
3. Send the new PDF (`-v2`).

## How each prompt is adapted (prompt says → in this skill)

### Prompt 1: Research Brief

| Prompt says | Here |
|---|---|
| Input is a script | There is no script yet. The **topic + today's pillar + the channel's angle** is the input. Track A researches the topic itself |
| Track C: watch 8–12 reference Reels | This environment cannot watch Instagram. Use web search (YouTube titles, news and creator articles) and **say so: lower confidence**. Never scrape or download reels |
| Track E: platform rules | Reuse the dated findings in `channel/GROWTH_PLAN.md`; re-check only what is older than ~30 days or likely to have changed |
| Posting date | Taken from the project's `post_date` + `slot` time. "kal / aaj / release se pehle" are checked against it |

### Prompt 2: Script Doctor v4

| Prompt says | Here |
|---|---|
| Input is the creator's script | Claude first writes **Draft-0** from the brief, using the channel template (hook · context · 4–5 beats · ending). Draft-0 is scored **before** any rewrite, honestly, as the "original" |
| Creator profile | From `channel.json`: Scene Samjho (@scene.samjho1), target 50 s (45–60, hard max 90), AI voice (edge-tts `hindi_male`, or the operator's recording), posting date + slot, niche, MUST AVOID = the channel's `never` list, not sponsored, Part 2 = no unless planned |
| Tools: FFmpeg, Whisper, Remotion, HyperFrames | This skill's engine (`rvs`: Python + ffmpeg, edge-tts word timing, Whisper alignment for own voice). Production feasibility = buildable with its archetypes (SKILL.md) and licensable media (own or Commons CC) |
| One CTA: the comment question; voice ends on the loop line | Followed exactly. The last beat's **on-screen** question (`data.question` of `cta_loop`) + caption + pinned comment. One **send-worthy line** names a kind of person ("wo dost jo…"). No "share / like / follow karo" |
| Language | Script lines in Roman Hinglish (`show`). The engine needs a Devanagari `say` with the same word count for the TTS. The spelling lock covers both |
| Deliverable | `pack/script-pack_<slug>.md` with the 8 strict sections and the YAML handoff (`run.py handover` reads it) |

### Prompt 3: PDF Handover Builder

| Prompt says | Here |
|---|---|
| Frame board made in HTML / CSS | **Real frames from this engine's proof render** (better than mock-ups). Plus the cover preview with the 3:4 grid-crop guide and the safe-zone contact sheet |
| Build plan with Remotion / HyperFrames / whisper.cpp stages and commands | This engine's stages and exact `run.py` commands for this project; the Claude Code prompts are the operator's real next messages ("continue", "line badlo", "post ho gaya", "24 h numbers") |
| Video idea and design | Generated from the Style DNA: palette hex, fonts, motion, transitions, captions, music mood, and a retention strip from the plan |
| Words are frozen | Yes. `handover` never edits the script |
| Build from HTML with headless Chrome, rasterise every page, look and fix | `run.py handover` does the build + rasterise; **Claude must open the page PNGs** before sending |
| Fallback ladder | PDF → HTML (if no Chromium) → Markdown parts in chat |

## Channel rules always win on

- **Length:** reel ≤ 90 s, aim 45–60 s.
- **Upload:** ≤ 5 hashtags with `#SceneSamjho` first; cover always.
- **Slot:** times from `channel.json`.
- **Content:** original content only; facts with sources; theories labelled.
- **Honesty:** never promise virality.
