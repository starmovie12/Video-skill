# Video-skill — Review Video Studio (v2)

Claude Code skill jo **edited 9:16 Reels/Shorts** banata hai (Hinglish): movie review, boutique/product promo, facts, story, software, game.
v2 me focus: **asli footage + tez editing + modern awaaz** — slideshow nahi, edit kiya hua Reel.

## v2 me kya badla (operator feedback: "awaaz bakwas, editing boring")

| Pehle (v1) | Ab (v2) |
|---|---|
| Video sirf text + background graphics (slideshow jaisa) | **Footage-first editing**: trailer clips / stills / product photos / B-roll poore screen par, har ~2 s naya shot, cut bolte hue word par, camera punch + flash + light leak har cut par |
| Images nahi to kuch nahi | `media search` — Wikimedia Commons se **free-licence images** (Public Domain / CC0 / CC BY / BY-SA) credits ke saath; `media scan` — clips ke shots detect karke `media_sheet.jpg` (Director dekh ke har beat ke liye visual chunta hai) |
| Robotic, slow, flat awaaz | **Reel pacing** (lambe pause kaate, hero word se pehle dramatic beat), broadcast voice chain (EQ + double compression + de-ess), **voice audition** (`voices` → 5 awaazein sun ke chuno), **ElevenLabs premium** (exact word timing), **apni awaaz recording** (Whisper alignment, ~0.15 s accuracy) |
| Chhote captions | **Viral captions**: heavy uppercase, thick outline, word-by-word reveal, active word yellow + bounce (aur 8 aur styles) |
| Koi stickers/emoji nahi | **89 Fluent 3D emoji stickers** (MIT) — words se auto match (daravni→😱, twist→🤯, paisa→💰), khali jagah dhoond ke pop |
| Music synthetic/chiptune | Music v2: naya **phonk** mood, 808 metallic hats + cowbell, **sidechain pumping**; cuts **beat par snap**; apna track do to BPM detect; **no-music version** (Instagram trending audio in-app daalne ke liye) |
| Sirf mp4 | **Cover** (9:16 + grid 4:5), **upload pack** (caption draft, hashtags, credits, checklist), no-music mp4 |

v1 ki sab cheezein bani hain: Style DNA (har video alag), Variety Ledger, 19 scene archetypes, design QA, proof, honest review gate.

## Scene Samjho channel mode (v2.2)

Ye skill ab **ek hi channel** ke liye set hai: **Scene Samjho**, Instagram [@scene.samjho1](https://instagram.com/scene.samjho1), Bollywood + OTT ka DECODE Hindi me.

- **Repo me kya hai:** `channel/channel.json` me channel ka naam, niche, pillars, roz ka schedule (**2 reels: 1:00 PM + 7:30 PM IST**, 3 stories) aur reel rules hain. `CLAUDE.md` har nayi chat me apne aap padha jaata hai.
- **`python run.py channel`:** aaj aur kal ka pillar, posting time, rules, aur pichhle topics (repeat nahi karne).
- **Har naya project:** apne aap 50 s reel, viral captions, end card par @scene.samjho1. Lint/QA 90 s se lamba reel rokte hain. Upload pack me posting time aur `#SceneSamjho` ke saath max 5 hashtags.
- **Flow:** research → script MD (operator ko dikhao) → **"continue"** → video → `python run.py log <project> --status made/posted` → `channel/` commit.
- **Yaad kahan rehti hai:** har video `channel/history.jsonl` aur `channel/state/` me rehta hai, isliye nayi chat ko bhi pichhli videos yaad rehti hain.
- **Docs:** playbook `channel/CHANNEL.md`, 30 din ka plan `channel/GROWTH_PLAN.md`.

## Install

```bash
git clone https://github.com/starmovie12/Video-skill ~/.claude/skills/review-video-studio
cd ~/.claude/skills/review-video-studio
pip install -r requirements.txt          # + ffmpeg (apt install ffmpeg | pkg install ffmpeg)
pip install faster-whisper               # optional: apni awaaz / kisi bhi TTS ka word-sync
python run.py doctor
```

## Use (Claude Code ke saath)

Claude ko bolo: *"Is skill se <film> ka review reel banao, ye rahi script"*. Claude `SKILL.md` follow karega:
research → media (aapke clips/stills ya free images) → voice → script → visual screenplay → `proof` (khud frames dekhega) → `make` → honest review → `deliver`.

Manual:
```bash
python run.py new movie_review my_film                 # template
python run.py media search my_film "Nosferatu 1922"    # free-licence images (ya apne clips my_film/media/ me daalo)
python run.py media scan my_film                       # shots + media_sheet.jpg
python run.py voices my_film                           # 5 awaazon me hook → out/voice_samples/
python run.py proof my_film                            # 6 s proof + key frames
python run.py make my_film                             # video + no-music video + cover + upload pack + QA
python run.py deliver my_film                          # QA PASS + review.md ho tabhi
python run.py feedback my_film --approve --note "ye look pasand aaya"
python run.py refs my_references/
```

Awaaz options (`project.json → voice`):
```jsonc
{"preset": "hindi_male"}                                         // free, default (sabse saaf Hindi)
{"preset": "multi_male2"}                                        // free, zyada conversational
{"engine": "elevenlabs", "voice_id": "<id>"}                     // premium, ELEVENLABS_API_KEY env me
{"engine": "recording", "file": "media/meri_awaaz.m4a"}          // apni awaaz (best authentic)
```

## Examples (is code se render)

Har example folder: `preview_720p.mp4`, `contact_sheet.jpg`, `cover_9x16.jpg`, `qa_report.md`, `review.md`, `media/credits.json`.

| Example | Kya dikhata hai |
|---|---|
| `examples/caligari` | Movie review — public-domain film stills (1920) full-screen, asli cast faces (Krauss, Veidt), poster title card |
| `examples/nosferatu` | Movie review — public-domain Orlok stills, alag look |
| `examples/octopus_facts` | Facts — Wikimedia Commons CC images, stickers 🩸🧠, viral captions |
| `examples/winter_shawl` | Boutique product (DEMO data, graphic-only mode — asli use me product photos `media/` me daalo) |

## Speed (MEASURED, 4 vCPU container)

Graphic-only beats ~50 fps render; footage beats ~15–20 fps. 25–45 s Reel ka poora pipeline (voice + media + mix + render + QA + cover)
≈ 1–2 min. Exact numbers: `examples/*/qa_report.md`, `work/make_summary.json → stage_seconds`.

## Honest limits

- Free Microsoft voices (edge-tts) ki ek ceiling hai. Sabse natural: **ElevenLabs** (paid) ya **apni recording**.
- Procedural music original hai par studio track nahi; best reach ke liye `_no_music.mp4` + Instagram trending audio, ya apna licensed track.
- Naye films ke posters/trailers copyrighted hain — sirf operator-licensed / official press material.
- Instagram safe-zone numbers public guides se (Meta ka official organic spec nahi) — `docs/ARCHITECTURE.md`.

## Licences

Code: MIT. Fonts: SIL OFL 1.1 / Apache 2.0 (`assets/fonts/licenses/`). Stickers: Microsoft Fluent UI Emoji, MIT
(`assets/stickers/LICENSE-fluentui-emoji-MIT.txt`). Example media: public domain / CC (see each `media/credits.json`).
