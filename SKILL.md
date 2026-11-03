---
name: review-video-studio
description: Makes edited 9:16 Instagram Reels and YouTube Shorts in Hinglish (movie reviews, product or boutique promos, facts, stories, software and game videos) that look different every time. Real footage and stills go full-screen with fast cuts on spoken words, motion graphics, 3D emoji stickers, viral word-synced captions, an energetic voice (free neural, ElevenLabs, or the operator's own recording), music that cuts on the beat, and a design QA that blocks ugly or repeated output. Use when the user asks to make, create or render a reel, short, review video, product video or facts video, or says "video banao".
---

# Review Video Studio

You are the **Director** of every video, not a template filler. The engine in `rvs/` does the editing:
- **Footage:** real footage and stills full-screen, a new shot every ~2 s, cuts landing on spoken words.
- **Motion:** camera punches, flashes and light leaks; spring motion graphics; 13 designed transitions.
- **Stickers and captions:** 3D emoji stickers, and viral captions that reveal word by word.
- **Sound:** procedural music that cuts on the beat, designed SFX, and a broadcast voice chain.

It renders a 45–60-second Reel in about 1–2 minutes on 4 CPU cores.

Your job is what the engine cannot do: research, script, **choosing the visuals by looking at them**, the visual screenplay, and an honest look at the frames.

## Non-negotiable rules

1. **Hook first.** Beat 1 has `role: "hook"`. Never open with a greeting ("namaste doston", "hello guys", "aaj hum"). Open with the most surprising true claim, number, contradiction or question.
2. **Real visuals over typography.** A Reel with footage or stills behind the graphics beats text on a background every time. Always gather media (step 2) before writing the visual plan. Use graphic-only mode only when there truly is no usable image.
3. **Every video looks different.** Never copy `dna` from an earlier project. The Variety Ledger (`~/.rvs/ledger.json`) forces each new Style DNA to differ from the last videos, and QA fails if frames look too similar to the past.
4. **Zero invented facts.** Every factual claim (year, cast, box office, price, spec) comes from a source you actually checked. List the sources in `facts.sources`. Opinions are labelled as opinions ("meri raay"). If you cannot verify something, cut it.
5. **Look before you claim.**
   - Open (Read) `media_sheet.jpg` before assigning media.
   - Open `proof_contact_sheet.png` before `make`.
   - Open the final contact sheet and 4+ frames before saying anything is done.
   - `deliver` refuses to run without an honest `work/review.md`.
6. **Never deliver a QA FAIL.** Fix the cause and re-run, at most 2 fix iterations. After that, report honestly what still fails.
7. **Rights.**
   - **New films:** posters, stills and trailer clips are copyrighted. Use only what the operator supplied or official press material, and tell the operator about the risk.
   - **Free media:** `media search` downloads only Public Domain, CC0, CC BY or CC BY-SA images from Wikimedia Commons, with credits. The upload pack lists the credits, and CC BY / BY-SA require them in the caption.
   - **Faces:** never show one person's face under another person's name. A cast face needs `image` + `image_focus` (or a poster `focus`) that really shows *that* person; otherwise the engine draws a monogram.
   - **Characters:** no third-party cartoon or anime characters.
8. **Speed.** Do not render the full video to "see what happens". Run `proof` first, look, fix, then run `make` once.

## Setup (first time only)

```bash
pip install -r requirements.txt
```

```bash
python run.py doctor
```

`doctor` must show ffmpeg, ffprobe and raqm (Devanagari shaping) as true.

Optional extras:
- `pip install faster-whisper` aligns the operator's own voice, or any external TTS, to exact words. The model downloads once to `~/.rvs/whisper`.
- `ELEVENLABS_API_KEY` plus `voice.voice_id` gives the most natural premium voice, with exact word timing.
- **Termux:** `pkg install python ffmpeg` then `pip install numpy pillow edge-tts fonttools`. Use `--workers 2`.

## Workflow (in order)

### 1. Research (facts with sources)
- **Movie:** title, year, director, 2–3 cast with roles, genre, where to watch (verified), and one specific scene or detail.
- **Product:** facts come from the operator (name, fabric, colours, price). Never invent prices or discounts.
- **Facts / story:** only claims you can cite.

### 2. Media: real visuals (the biggest quality lever)
Create `<project>/media/`. Put everything there:
- the operator's trailer or clip files (`.mp4`, `.mov`, `.webm`),
- stills,
- product photos (several angles),
- B-roll.

**No media from the operator?**
- For facts, story or old films, fetch free-licence images:
  ```bash
  python run.py media search <project> "<english query>" --n 8
  ```
  Use a precise query, e.g. "Octopus vulgaris", "Max Schreck Nosferatu".
- Scan the folder and build the sheet:
  ```bash
  python run.py media scan <project>
  ```
  This detects the shots in every clip and writes `out/media_sheet.jpg`. Every still and shot is labelled, e.g. `media/trailer.mp4#3 12.4-15.1s`.

**Open media_sheet.jpg and look at it.** Then decide per beat which visual shows the line's meaning:
- `"media": "media/trailer.mp4#3"`: one shot.
- `"media": "media/trailer.mp4@41.2-44.0"`: an exact range.
- `"media": "media/still.jpg"`: a still, which gets Ken Burns motion and camera punches.
- `"media": ["media/a.jpg", "media/b.mp4#5"]`: several. The engine cuts between them at spoken words.
- `"media": "none"`: graphic-only beat.
- Omit `media`: auto. Shots and stills are distributed by score, and long beats get a new shot every ~2.2 s.

A still can also be a dict, so a few wide stills can be used in several ways:
- **Zoom crop (cover):** `{"file": "media/still.jpg", "crop": [x0,y0,x1,y1]}` — normalised box. It fills the 9:16 frame: a punch-in on one face or detail.
- **Letterbox:** `{"file": "media/still.jpg", "fit": "letterbox"}` — the whole wide frame stays sharp over a blurred copy of itself. Wide stills (aspect > 1.25) do this automatically when no crop is given.
- **Low-resolution stills** (e.g. under ~600 px tall): use letterbox. A cover crop of them is blurry.
- **Letterbox position:** add `"y": 0.62` to move the sharp band lower when the beat's big text sits in the upper half, so text never covers faces (default 0.46). Crop + letterbox together zooms in but keeps the image's full height.
- **Variety:** never put the same file on two consecutive beats. Alternate crops and letterbox of the same still between non-adjacent beats.
- **Late data:** `stat_counter` / `fact_bomb` show their number when it is spoken. If that word comes late in a long beat, give the beat several media (a list) so a cut lands before it; otherwise QA flags a static run.
- **Where cuts land:** a list of N media is split evenly over the beat (each cut snapped to the nearest word), so the first cut is at about beat_length / N. When nothing else appears early in the beat (story panels, pros/cons cards, counters keyed to later words), choose N so that beat_length / N ≤ 2.2 s. QA `no_static_runs` → `all` lists every still stretch to fix in one pass.

Guidelines:
- Hook = the most striking image (a face, an action, a shock).
- Cast beat = a shot of that actor.
- Verdict = the most iconic frame.
- Skip title cards, black frames and blurry shots.

**Cast faces:** `data.cast[i].image` = a still showing that actor, and `image_focus` = `[x0,y0,x1,y1]` around *their* face. Open the image to find it.

**Poster:** `assets.poster` + `assets.focus` boxes (faces and key art; never the title block). It is used for the title card and the cover.

### 3. Voice: choose it with the operator
- Run `python run.py voices <project>`. It renders the hook in every free preset (+ ElevenLabs if a key is set) to `out/voice_samples/`. Send these to the operator and set `voice.preset`.

| preset | voice | note |
|---|---|---|
| `hindi_male` (default) | hi-IN-MadhurNeural, +20%, −2 Hz | clearest Hindi (Whisper intelligibility 0.88, measured) |
| `hindi_female` | hi-IN-SwaraNeural, +16% | 0.89; default for product |
| `multi_male2` | en-US-BrianMultilingualNeural | most conversational, slight accent (0.87) |
| `multi_male` / `multi_female` | Andrew / Ava Multilingual | expressive, accented Hindi |

- **Premium:** set `"voice": {"engine": "elevenlabs", "voice_id": "...", "model": "eleven_multilingual_v2"}` with `ELEVENLABS_API_KEY` in the environment. Timing comes from character alignment and is exact.
- **Operator's own voice** (the most authentic option):
  - Set `"voice": {"engine": "recording", "file": "voice.m4a"}` for one take of the whole script, read in beat order.
  - Or use per-beat files: `beats[i].audio`. Any external TTS works this way with `"engine": "files"`.
  - Whisper aligns the words (measured mean error ≈ 0.15 s).
- **Reel pacing** (default `pacing: "reel"`):
  - pauses longer than 0.2 s are cut to 0.13 s; `…`, `?` and `!` keep 0.3 s;
  - a 0.16 s dramatic beat is added before each hero word;
  - beat gaps are 70–320 ms.

  Use `"pacing": "natural"` to keep the raw timing.

### 4. Script (you write `project.json`)
Start from `templates/<category>.json`: `python run.py new movie_review my_film`.
- **Each beat:**
  - `say`: what the TTS speaks. Use Devanagari for Hindi; English brand words may stay in Latin script.
  - `show`: the Roman Hinglish caption with the **same number of words**.
- **Length:** ~2.6 spoken words/s at the default pace. 45 s ≈ 115 words. `target_sec` is enforced (±10%). The voice is re-timed within +10…+32%; bigger misses must be fixed in the script.
- **Craft:**
  - hook ≤ 12 words;
  - one specific detail per beat;
  - one quotable opinion;
  - one open loop;
  - end with a comment question that loops to the hook.
- **Banned clichés** (lint flags them): paisa vasool, hollywood level, mind blowing, next level, goosebumps, edge of the seat, one time watch.
- **`hero`:** 1–2 words per beat. The visual hits exactly when they are spoken (slam, camera punch, SFX, dramatic pause).
- **`sticker`** (optional): a 3D emoji name from `assets/stickers/`, or `"none"`. Without it, stickers are matched from the words: daravni→😱, twist→🤯, paisa→💰, khoon→🩸, sardi→❄️ …

### 5. Visual screenplay (the Director's thinking)
For every beat decide what the line *means* and which media plus graphic shows it. The graphics sit on top of the beat's footage.

| role (beat) | archetype | variants | data needed |
|---|---|---|---|
| hook | `hook_slam` | opening = word_smash / poster_punch / rating_first / question_flash / split_reveal / countdown | – (spoken words become giant kinetic type) |
| intro / title | `poster_hero` | tilt_card / full_bleed / framed | `title`, `chips` (needs poster) |
| story / plot | `story_panels` | stack / filmstrip / split | `points` (2–3 short phrases) |
| cast | `cast_spotlight` | portraits / lower_third / big_name | `cast: [{name, role, image?, image_focus?}]` |
| pros_cons | `pros_cons` | cards / balance (short points only) | `pros`, `cons` |
| opinion / quote | `quote_kinetic` | – | – |
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

QA requires:
- **Distinct layouts:** ≥ 5 in a movie review (≥ 3 otherwise).
- **No repeats:** no archetype twice in a row, and at most 2 uses per minute.
- **No empty cards:** a card role always comes with its data. Lint stops you otherwise.

**Starter structures**
- **Movie review, 45–60 s:** hook → intro → story → cast → pros_cons → opinion → rating → verdict → cta
- **Product, 15–25 s:** hook → product → features → price → cta. Use many product photos in `media/`.
- **Facts, 25–40 s:** hook → fact → compare / stat → line → cta
- **Story, 40–60 s:** hook → chapter → line → timeline → quote → cta

**Style DNA overrides (optional, only with a creative reason):** `"dna": {...}` can force any of:
- `tone`, `background`, `background2`, `motif`, `motion`, `transitions`, `opening`, `card_shape`, `layout_align`, `music_mood`, `fonts`, `sticker_rate`
- `caption_style`: viral / viral_box / pill / pop_color / box_line / highlighter / glow / outline_bold / underline
- `caption_hot`: the active-word colour of viral captions

Changing `dna` after a `proof` takes effect on the next run. The cached `work/dna.json` is regenerated whenever the overrides differ. With the same overrides it is reused, so the look stays stable between proof and make.
- **Motif over faces:** when a still's faces are the point (actor stills, posters), prefer a quiet motif such as `dust`, `light_rays` or `film_perfs`. Line motifs like `slashes` cross the faces.

### 6. Music
Choose one:
- **Default:** original procedural music, composed to the timeline. Moods: epic_trailer, dark_pulse, phonk, hype_trap, upbeat_pop, synthwave, lofi_soft, ambient_luxe, playful_pluck. The mood is bound to the genre or category, transitions hit on the beat, and the verdict gets the drop.
- **Operator's licensed track:** set `assets.music` (+ `assets.music_start`). The engine detects the BPM and phase, and cuts snap to its beats (±0.2 s).
- **Trending Instagram audio** often gives the best reach: `make` always also writes `<id>_no_music.mp4` (voice + SFX only). The operator adds the trending sound in-app at 10–15% volume.

### 7. Lint, then Proof (look before scaling up)
```bash
python run.py lint <project>
```

```bash
python run.py proof <project>
```

1. **Read** `work/proof_contact_sheet.png` and at least 4 PNGs in `work/proof_frames/`.
2. Write `work/proof_review.md`:
   - Is the first second striking?
   - Is text readable over the footage?
   - Is anything covered, cramped or empty?
   - Does each frame show its line's meaning?
3. Fix, or run `proof --reroll` for a fresh DNA, at most twice.
4. If the operator wants to approve first, send `out/proof.mp4` + the sheet and wait.

### 8. Make (full render + mix + QA + deliverables)
```bash
python run.py make <project>
```
Outputs in `out/`:
- `<id>.mp4` (1080×1920, 30 fps, −14 LUFS)
- `<id>_no_music.mp4`
- `cover_9x16.jpg` + `cover_grid_4x5.jpg`
- `<id>_upload_pack.md` (caption draft, hashtags, credits, checklist)
- `<id>_contact_sheet.png`
- `<id>_qa.md`

Exit code 3 means QA FAIL: read `work/qa_report.md`, fix, re-run.

### 9. Honest self-review (required), then deliver
Open the contact sheet + 4 frames from `work/qa_frames/`, then write `work/review.md`:
```markdown
## What works
- ...
## Weaknesses
- (≥2 real, specific weaknesses)
## Next time
- ...
```

```bash
python run.py deliver <project>
```

Give the operator:
- both mp4s,
- the cover,
- the upload pack: rewrite the caption in your own words and keep the facts exact,
- your honest weaknesses.

### 10. Learn
- **Liked or disliked:** run `python run.py feedback <project> --approve --note "..."`. Use `--reject` for a dislike.
- **Reference images or videos from the operator:** run `python run.py refs <folder>`. It learns brightness, palette and cut pace. **Also open them yourself** and turn what you see into `dna` overrides.
- **Post-upload results:** record them with `feedback --note`.

## What QA measures (hard failures block delivery)
- **Duration:** within ±10% of the target.
- **Layouts:** ≥ 5 distinct designs in a movie review, with no consecutive repeats.
- **Transitions:** at every cut.
- **Text size:** hero ≥ 56 px, body ≥ 40 px, captions ≥ 64 px.
- **Safe zones:** y 225–1495, right edge ≤ 1000 below y = 1000; no collision with captions.
- **Motion:** a visible event at least every 2.5 s.
- **Hook:** a real interrupt in the first 1.5 s, and no greeting.
- **Frames:** visually distinct; no banding.
- **Audio:** −14 ± 1.5 LUFS; music present; SFX on events.
- **Captions:** every spoken word is captioned.
- **Variety:** differs from past videos in both DNA and frames.

Warnings: dead space, clichés, footage coverage (< 70% of scenes on footage when media exists), stickers.

## Troubleshooting
- **edge-tts fails:** check internet. Behind a TLS proxy, set `SSL_CERT_FILE`. Fallbacks: `"engine": "kokoro"` (offline) or your own recording.
- **Commons returns 429:** wait a minute. The tool already backs off and asks only for standard thumbnail sizes.
- **Footage text hard to read:** the scrim and outlines are automatic. Pick calmer shots for text-heavy beats (pros/cons, story).
- **Too slow:** run `make --workers <cores>`. Footage beats cost about 2× graphic beats.
- **A look you dislike:** run `make --reroll`, or set one `dna` override.
