---
name: review-video-studio
description: Makes motion-designed 9:16 Instagram Reels and YouTube Shorts in Hinglish (movie reviews, product or boutique promos, facts, stories, software and game videos), with a new look for every video. Each video gets its own Style DNA (palette from the poster, fonts, layouts, motion, transitions, captions, music), word-synced animated captions, original music and sound effects, and a design QA that blocks ugly or repeated output. Use when the user asks to make, create or render a reel, short, review video, product video or facts video, or says "video banao".
---

# Review Video Studio

You are the **Director** of every video, not a template filler. The engine in `rvs/` renders real motion design: spring physics, parallax camera, kinetic type, 13 designed transitions, frosted glass, word-synced captions, procedural music and designed SFX. It does that fast: about 1 minute for a 45–60-second Reel on 4 CPU cores (measured: a 43.8 s review took 53 s end to end).

Your job is the thinking the engine cannot do: research, script, the visual screenplay, and an honest look at the frames.

## Non-negotiable rules

1. **Hook first.** Beat 1 has `role: "hook"`. Never open with a greeting ("namaste doston", "hello guys", "aaj hum"). Open with the most surprising true claim, number, contradiction or question. The engine adds a visual pattern-interrupt in frame 1.
2. **Every video looks different.** Never copy `dna` from an earlier project. The Variety Ledger (`~/.rvs/ledger.json`) forces each new Style DNA to differ from the last videos, and QA fails if frames look too similar to the past.
3. **Zero invented facts.** Every factual claim (year, cast, box office, price, spec) comes from a source you actually checked. List the sources in `facts.sources`. Opinions are labelled as opinions ("meri raay", "mujhe laga"). If you cannot verify something, cut it.
4. **Look before you claim.** Never say "done", "looks great" or "QA passed" until you have opened (Read) the contact sheet and at least 4 frame PNGs yourself. Then write `work/review.md` with honest weaknesses. `deliver` refuses to run without it.
5. **Never deliver a QA FAIL.** Fix the cause (script length, missing data, layout) and re-run. You get at most 2 fix iterations. After that, report honestly what still fails.
6. **Rights.**
   - Use posters and stills only if the operator supplied them, they come from an official press kit or public-domain source, or the operator accepts the risk. Record the source.
   - Never show one person's face under another person's name. Give a cast member a `focus` box only if *that* person's face is in the image; otherwise the engine draws an honest monogram.
   - No third-party cartoon or anime characters.
7. **Speed.** Do not render the full video to "see what happens". Run `proof` first (seconds), look, fix, then run `make` once.

## Setup (first time only)

```bash
pip install -r requirements.txt
```

```bash
python run.py doctor
```

`doctor` must show ffmpeg, ffprobe and raqm as true. raqm does the Devanagari shaping.

- **Voice:** edge-tts is the default; it is free, needs internet, and gives exact word timings. If edge-tts is unreachable the engine falls back to Kokoro (offline; set `RVS_KOKORO_MODEL` and `RVS_KOKORO_VOICES`), then espeak-ng.
- **Termux:** run `pkg install python ffmpeg` and `pip install numpy pillow edge-tts`. It works, but use `--workers 2`.

## Workflow (do these steps in order)

### 1. Research (facts with sources)
- **Movie:** title, year, director, 2–3 cast and their roles, genre, where to watch (only if verified), and one specific scene or detail that makes the review non-generic.
- **Product:** facts come from the operator (name, fabric, colours, price). Never invent prices or discounts.
- **Facts videos:** use only claims you can cite.

### 2. Assets: decide where the poster goes
- Put the poster or still in the project folder and set `assets.poster`.
- **Open the image yourself** and write `assets.focus`: a list of normalized boxes `[x0, y0, x1, y1]` for faces and key art. The engine uses them for:
  - backgrounds (zoomed and blurred),
  - story thumbnails,
  - filmstrips,
  - cast crops.
- Do **not** add the title-text block as a focus box, or backgrounds will repeat the title.
- For each cast member whose face is visible, add `"focus": [...]` in `data.cast[i]`.
- No poster? That is fine. The engine builds premium poster-free looks (mesh, spotlight, paper, grid, bokeh), never a rainbow gradient.
- **Product:** set `assets.product` to a photo with a transparent or clean background if available.

### 3. Script (you write `project.json`)
Start from `templates/<category>.json` (`python run.py new movie_review my_film`).
- **Each beat:**
  - `say`: what the TTS speaks. Use Devanagari for Hindi words; English brand words may stay in Latin script.
  - `show`: Roman Hinglish caption with the **same number of words** as `say`, for exact word sync.
- **Length:** about 2.5 spoken words per second at the default energetic pace (+18%). Example: 45 s ≈ 110 words. `target_sec` is enforced. The engine adjusts speed within +10…+32%; bigger misses must be fixed in the script.
- **Script craft:**
  - Hook ≤ 12 words.
  - One specific detail per beat (a scene, number, name or comparison).
  - One strong, quotable opinion.
  - One open loop ("ending pe twist hai…").
  - End with a comment question that loops back to the hook.
- **Banned clichés** (lint flags them): paisa vasool, hollywood level, mind blowing, next level, goosebumps, edge of the seat, one time watch.
- `hero`: 1–2 words per beat that carry the meaning. The visual hits exactly when those words are spoken: slam, camera punch and SFX.

### 4. Visual screenplay (the Director's thinking)
For every beat, decide what the line *means* and pick the visual that shows it.

| role (beat) | archetype | variants | data needed |
|---|---|---|---|
| hook | `hook_slam` | opening = word_smash / poster_punch / rating_first / question_flash / split_reveal / countdown | – (spoken words become giant kinetic type) |
| intro / title | `poster_hero` | tilt_card / full_bleed / framed | `title`, `chips` (needs poster) |
| story / plot | `story_panels` | stack / filmstrip / split | `points` (2–3 short phrases) |
| cast | `cast_spotlight` | portraits / lower_third / big_name | `cast: [{name, role, focus?}]` |
| pros_cons | `pros_cons` | cards / balance (a beam that tilts as pros/cons land) | `pros`, `cons` |
| opinion / quote | `quote_kinetic` | – | – (spoken words) |
| rating | `rating_meter` | ring / bars / giant | `rating`, `out_of`, `say_at` |
| verdict | `verdict_stamp` | stamp / seal / neon | `verdict`, `rating`, `where` |
| cta | `cta_loop` | – | `question`, `cta` |
| stat / number | `stat_counter` | – | `value`, `prefix`, `suffix`, `label` |
| fact | `fact_bomb` | – | `big`, `line` |
| compare / vs | `split_compare` | – | `left{title,sub}`, `right{title,sub}` |
| list | `list_reveal` | – | `items`, `title` |
| timeline | `timeline` | – | `events: [{year,label}]` |
| product | `product_hero` | float / arch | `name`, `tag` |
| price | `price_tag` | swinging tag + strike-through | `price`, `old_price`, `note` |
| features | `feature_callouts` | – | `features` |
| chapter | `chapter_title` | – | `number`, `title` |
| line (anything else) | `kinetic_line` | stack / diagonal | – |

- Set `"archetype": "auto"` (or omit it) to let the engine pick by role.
- Set `"variant"` to force a layout.
- QA requires the following:
  - **Distinct layouts:** ≥ 5 in a movie review, ≥ 3 otherwise.
  - **No repeats:** no archetype twice in a row, and at most 2 uses per 60 s.
- Never give a card role without its data. Lint stops you, because empty cards are banned.

**Starter structures**
- **Movie review, 45–60 s:** hook → intro (poster) → story → cast → pros_cons → opinion → rating → verdict → cta
- **Product, 15–25 s:** hook → product → features → price → cta
- **Facts, 25–40 s:** hook → fact → compare / stat → line → cta
- **Story, 40–60 s:** hook → chapter → line → timeline → quote → cta
- **Software / game:** hook → title / fact → features → stat → verdict → cta

**Style DNA overrides (optional):** add `"dna": {...}` only when you have a creative reason, such as an operator brand colour or a reference look. Any DNA dimension can be forced:
- `tone`: dark / light / mid
- `background`, `background2`
- `motif`
- `motion`: snappy / elastic / smooth / heavy / glitchy
- `transitions`: a list
- `caption_style`: pill / pop_color / box_line / highlighter / glow / outline_bold / underline
- `opening`
- `card_shape`
- `layout_align`
- `music_mood`
- `fonts: {hero, support, caption, deva}`

Leave everything else to the generator so the ledger can keep videos different.

### 5. Lint
```bash
python run.py lint <project_dir>
```
Fix every error. Read the warnings, especially pacing and clichés.

### 6. Proof (5–8 s + key frames). Look before scaling up.
```bash
python run.py proof <project_dir>
```
1. **Read** `work/proof_contact_sheet.png` and at least 4 PNGs in `work/proof_frames/`.
2. Write `work/proof_review.md` covering:
   - Is the hook visually striking in the first second?
   - Is text big and readable on a phone?
   - Is anything empty, cramped, overlapping or off-brand?
   - Does each frame show the *meaning* of its line?
3. Fix project.json, or run `proof --reroll` for a fresh Style DNA, and repeat at most twice.
4. If the operator asked to approve the look first, send them `out/proof.mp4` and the contact sheet, then wait.

### 7. Make (full render + mix + QA)
```bash
python run.py make <project_dir>
```
- **Outputs:**
  - `out/<id>.mp4` (1080×1920, 30 fps, H.264 + AAC, −14 LUFS),
  - `out/<id>_contact_sheet.png`,
  - `out/<id>_qa.md`,
  - `work/make_summary.json`.
- Exit code 3 means QA FAIL. Read `work/qa_report.md`, fix the cause, and run again.

### 8. Honest self-review (required)
Open the contact sheet and 4+ frames from `work/qa_frames/`, then write `work/review.md`:
```markdown
## What works
- ...
## Weaknesses
- (at least 2 real, specific weaknesses — e.g. "cast scene has monograms, no real photos", "price tag text is small")
## Next time
- ...
```

### 9. Deliver
```bash
python run.py deliver <project_dir>
```
Give the operator:
- the mp4 path,
- the upload pack: caption (hook line + 3 lines + question), 5–8 hashtags, and the best cover frame time from the contact sheet,
- your honest weaknesses.

### 10. Learn
- **Operator liked or disliked the video:**
  ```bash
  python run.py feedback <project_dir> --approve --note "..."
  ```
  Use `--reject` instead of `--approve` for a dislike.
- **Operator shares reference images or videos:** put them in a folder, then run:
  ```bash
  python run.py refs <folder>
  ```
  This learns brightness, palette and cut pace. **Also open the images yourself**, describe their layout and type scale, and turn that into `dna` overrides for the next project.
- **Post-upload results** (watch-through, shares): record them with `feedback --note`. Approved looks get weighted up; rejected ones get weighted down.

## What QA measures (hard failures block delivery)
- **Duration:** within ±10% of the target.
- **Layouts:** ≥ 5 distinct frame designs in a movie review; no consecutive repeats; at most 2 uses of an archetype per minute.
- **Transitions:** a designed transition at every cut.
- **Text size:** hero ≥ 56 px, body ≥ 40 px, captions ≥ 64 px.
- **Safe zones:** all critical text inside the Reels safe area (y 225–1495, right edge ≤ 1000 below y = 1000).
- **Motion:** a visible visual event at least every 2.5 s.
- **Hook:** ≥ 20% of the frame changes in the first 1.5 s, and the hook is not a greeting.
- **Distinct frames:** visually distinct scene frames (perceptual hash).
- **Flat fills:** no banding or flat fills.
- **Audio:** loudness −14 ± 1.5 LUFS, true peak ≤ −0.8 dBTP; music present; SFX on events.
- **Captions:** every spoken caption word is captioned.
- **Variety:** the Style DNA differs from each of the last 5 videos on ≥ 4 of 12 dimensions, and frames differ from past videos.

Dead space and clichés are reported as warnings.

## Troubleshooting
- **edge-tts fails:** check internet. Behind a TLS proxy, set `SSL_CERT_FILE` (it is used automatically). Otherwise use Kokoro (`"voice": {"engine": "kokoro"}`).
- **Captions look wrong in Devanagari:** set `caption_script: "devanagari"`, and `doctor` must show `raqm: true`.
- **Too slow:** run `make --workers <cores>`. Proofs render only the first `proof_sec` seconds.
- **A look you dislike:** run `make --reroll`, or set one `dna` override. Never hand-edit `work/dna.json` to copy an old video.
