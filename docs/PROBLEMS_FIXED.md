# Problems → fixes (traceability)

The operator's problem list (P-01…P-49) and requirements (R-01…R-12) are mapped to where this skill fixes each one.

Status values:
- **FIXED**: implemented and measured by QA or the demos.
- **PARTIAL**: improved, but with a stated limit.
- **OUT-OF-SCOPE**: needs data or tools the skill cannot have.

## Group A — sameness & creative direction
| # | Status | Where / how |
|---|---|---|
| P-01 same look every video | FIXED | `rvs/dna.py` Style DNA (12 dims) + Variety Ledger. QA `dna_differs_from_past`, `frames_differ_from_past`. 4 demos = 4 different looks |
| P-02 only 5 card modes in one function | FIXED | `rvs/scenes.py`: 19 archetypes, 1–3 layout variants each |
| P-03 no Creative Director stage | FIXED | `SKILL.md` steps 3–4 (Director writes the visual screenplay: role, archetype, variant, hero words, focus boxes) + `proof` look-and-fix loop |
| P-04 closed schema, no creative fields | FIXED | `project.json` has `dna` overrides, `archetype`, `variant`, `hero`, `data`, `transition_in`, `assets.focus` |
| P-05 style packs = 4 numbers | FIXED | DNA picks palette (OKLab, poster-derived), fonts, background, motif, motion, transitions, captions, opening, shapes, alignment, music |
| P-06 movie review needs ≥5 frames | FIXED | QA `distinct_frame_designs` ≥ 5 + `visually_distinct_frames` (dHash) |
| P-07 no memory of earlier videos | FIXED | `~/.rvs/ledger.json` (DNA signature + frame hashes per video) |
| P-08 category-blind look | FIXED | Category/genre profiles in `dna.py` (movie genres, product/boutique, facts, story, software, game). Tone and music are bound to genre |
| P-09 meaning ignored | FIXED | `hero` words: the visual (slam, punch, SFX) fires on the exact spoken word. Archetype chosen by the line's role. Data elements appear when spoken (`Ctx.t_word`) |

## Group B — visual design
| # | Status | Where / how |
|---|---|---|
| P-10 empty cards | FIXED | Lint blocks card roles without data. Timeline falls back to kinetic type. Never an empty card |
| P-11 tiny auto-shrunk text | FIXED | Fit-to-box hero type (fills its box), justified kinetic stacks. QA `text_min_size` (hero ≥ 56 px, body ≥ 40 px) |
| P-12 fake glass, no proof of promises | FIXED | `gfx.frosted_glass` blurs the real background plate. QA measures frames, not promises |
| P-13 dirty glow, banding | FIXED | Glow only via blurred alpha. Dithered float gradients. QA `no_banding_or_flat_fills` |
| P-14 rainbow fallback | FIXED | Palette-bound poster-free plates (mesh, spotlight, paper, grid, bokeh, split tone, fabric) |
| P-15 16:9 master, empty right side | FIXED | Native 1080×1920 only. No 16:9 derivation |
| P-16 tiny stars | FIXED | `rating_meter` ring / bars / giant number with count-up + popping stars. Verdict stamp / seal / neon |
| P-17 tiny host, third-party characters | FIXED (by removal) | No anime/third-party characters. Cast uses the actor's own face crop only when given, otherwise an honest monogram |
| P-18 no imagery strategy | FIXED | Poster used 6 ways (tilt / full-bleed / framed / backgrounds / filmstrip / thumbnails) via Director focus boxes + saliency fallback |

## Group C — motion
| # | Status | Where / how |
|---|---|---|
| P-19 still + slow zoom | FIXED | Spring-driven layers, parallax camera with punches/shake. QA `no_static_runs` ≤ 2.5 s |
| P-20 hard cuts only | FIXED | 13 transitions, one at every boundary. QA `designed_transitions` |
| P-21 cards cut-to-cut | FIXED | 13 enter behaviours (slam, slide, drop, wipe, flip, spin, stretch…) with stagger |
| P-22 no camera/parallax/stroke-draw/particles/continuity | FIXED | `engine.Camera`, depth `z`, stroke-draw icons/rings/lines, particles, DNA motif persists across scenes |
| P-23 no rhythm | FIXED | Events keyed to word timings. QA static-run gate |
| P-24 architecture ceiling | PARTIAL | Python motion engine chosen for speed + Termux (see ARCHITECTURE §1). Ceiling below a browser engine; plan JSON is engine-agnostic |

## Group D — captions & type
| # | Status | Where / how |
|---|---|---|
| P-25 small dead captions | FIXED | 72–82 px, pop-in, active-word pill / highlighter / underline / pop / glow, stroke + shadow |
| P-26 highlight not synced | FIXED | edge-tts WordBoundary = exact word timing. Fallback engines are flagged "estimated" |
| P-27 captions ≠ speech | FIXED | Captions built from the spoken words (`show` aligned 1:1 to `say`). QA `captions_cover_speech` |
| P-28 two fonts, no Devanagari tests | FIXED | 41 OFL fonts with vibe tags. RAQM shaping. Per-word script + glyph fallback (₹ etc.). Font coverage measured with fontTools |

## Group E — audio
| # | Status | Where / how |
|---|---|---|
| P-29 robotic slow voice | PARTIAL | +18% default, per-beat energy, designed pauses. Voice quality is bounded by free TTS |
| P-30 no music | FIXED | Procedural music by default (8 moods, composed to the timeline). Operator track supported with ducking |
| P-31 cheap SFX at beat start only | FIXED | Designed SFX library on in-scene events (slams, ticks, stamps, swishes) + transitions |
| P-32 no beat/onset analysis | PARTIAL | Music is composed *to* the timeline (hits on transitions, drop on the verdict), not cut to music. No onset sync for operator tracks yet |

## Group F — hook, retention, virality
| # | Status | Where / how |
|---|---|---|
| P-33 greeting opening | FIXED | Lint + QA block greetings. 6 designed opening moves. QA `hook_pattern_interrupt` |
| P-34 no retention engineering | PARTIAL | SKILL.md script craft (open loop, quotable opinion, comment question, loop ending `cta_loop`). Platform research is limited to public guides |
| P-35 duration drift | FIXED | Duration control re-times the voice. QA `duration_vs_target` ±10% is a hard gate |
| P-36 generic script | PARTIAL | Cliché lint + specificity rules in SKILL.md. Script quality still depends on the Director's research |
| P-37 no success metrics / learn loop | PARTIAL | `feedback` + taste weights. Post-upload metrics are recorded by note; no API pull from Instagram |

## Group G — QA & honesty
| # | Status | Where / how |
|---|---|---|
| P-38 technical-only QA | FIXED | Design checks are HARD: size, safe zones, static runs, distinct frames, banding, hook, variety |
| P-39 evals don't look at frames | FIXED | QA decodes the real mp4 (motion, banding, dHash). `tests/` render real frames |
| P-40 AI says done without looking | FIXED | SKILL.md rule 4 + `deliver` refuses without a fresh `review.md` with ≥ 2 weaknesses |
| P-41 no hero proof | FIXED | `proof`: first 6 s + key frames + contact sheet before `make` |
| P-42 contact sheet only for completeness | FIXED | Contact sheet with safe-zone guides and per-scene labels for design review |

## Group H — process, environment, rights
| # | Status | Where / how |
|---|---|---|
| P-43 bureaucracy | FIXED | One command per stage, `make` does everything in ~1–1.5 min. No copy-paste between AIs |
| P-44 dangling references | FIXED | SKILL.md references only files that exist |
| P-45 4K/8K/HDR priorities | FIXED | 1080×1920 30 fps H.264 only (what Reels uses). Bitrate capped at 10 Mbps |
| P-46 environment conflict | FIXED | Pure Python + ffmpeg: cloud, PC and Termux |
| P-47 no reference intake | PARTIAL | `refs` learns brightness/saturation/palette/cut pace. The Director must look at the images to copy layout/type scale |
| P-48 imagery rights | PARTIAL | Rights rules in SKILL.md, poster-free premium fallback, honest monograms. Legal judgement stays with the operator |
| P-49 safe zones unverified | PARTIAL | Conservative profile from public guides (no official Meta organic spec). See ARCHITECTURE §5 |

## Requirements
| # | Status |
|---|---|
| R-01 ≥5 distinct frames, unique per film | FIXED (QA + DNA) |
| R-02 theme per video type | FIXED (category/genre profiles) |
| R-03 9:16 1080×1920, zones as hints | FIXED |
| R-04 hook in 3 s, never greeting | FIXED |
| R-05 big captions 65–80 px, active word, pop, outline + shadow | FIXED (72–82 px) |
| R-06 animated cards | FIXED |
| R-07 music + SFX by default, energetic voice | FIXED (+18%) |
| R-08 cinematic backgrounds from the poster, no dirty glow | FIXED |
| R-09 reference intake | PARTIAL (see P-47) |
| R-10 skill thinks for itself | FIXED (DNA + Director role + auto archetypes) |
| R-11 viral-ready, visibly impressive | PARTIAL: designed for it. Real virality can only be measured after upload |
| R-12 hero proof + self-inspection before full render | FIXED (`proof`, review gate) |

## Extra flaws found and fixed while building
| # | Fix |
|---|---|
| P-50 | A Latin display font was missing ₹ → per-glyph fallback via fontTools cmap |
| P-51 | Backgrounds repeated the poster's title block → zoomed focus-box plates |
| P-52 | One face shown under two actors' names → honest monograms unless per-actor focus is given |
| P-53 | Novelty pushed playful music onto horror → tone and music bound to genre |
| P-54 | Film-grain noise made 211 MB files (38 Mbps) → static light grain + 10 Mbps cap |
| P-55 | QA "static" metric fooled by grain → % of pixels changing > 6 levels, caption band excluded |

## v2 — operator feedback after the first demos

| # | Operator said | Status | Fix |
|---|---|---|---|
| V-01 | "Awaaz bahut bakwas, aajkal ki videos jaisi nahi" | PARTIAL → much better | Reel pacing (pause trimming, hero-word dramatic beats), broadcast voice chain, `voices` audition of 5 presets (intelligibility measured), ElevenLabs premium with exact timing, operator's own recording with Whisper alignment. **Limit:** free TTS has a ceiling; the most natural options need ElevenLabs or a human voice. |
| V-02 | "Editing aur graphics bakwas, attractive nahi" | FIXED (design) | Footage-first editing (real stills/clips full-screen, shot every ~2 s, cuts on words, punch + flash + light leak), Commons free-licence media search, 3D emoji stickers, viral captions, stronger outlines + scrim for legibility |
| V-03 | "Boring, maza nahi aa raha" | FIXED (design) | Faster cut rhythm, stickers + SFX on events, beat-snapped cuts, sidechain-pumped music, phonk mood |
| V-04 | "Kuch missing / code adhura" | FIXED | Added: voice audition, own-voice + any-TTS alignment, ElevenLabs, media scan/search, shot detection, cover + grid crop, upload pack with credits, no-music export, beat sync for operator music, lint for media/cast refs, CI, 18 tests (v1 had 10) |
| P-56 | Cover showed hook text behind the title | FIXED | Cover is built from a clean background frame |
| P-57 | Stickers covered titles | FIXED | Free-spot placement against every text block |
| P-58 | Pros/cons balance chips overflowed the frame with long points | FIXED | Balance only for short points; chips width-bounded and clamped |
| P-59 | Story cards clipped two-line text | FIXED | Thumbnail left, text vertically centred over the full card height |
| P-60 | Camera-shake rotation made every frame re-rotate big sprites (slow) | FIXED | Rotation threshold + quantisation, bilinear for big sprites |

## v2.1 — found while making the first real long-form Reel (KING, 3:18)

| # | Problem seen in the proof frames | Fix |
|---|---|---|
| P-61 | Only 5 wide film stills for a 27-beat, 3-minute video, so the same image would repeat | Dict media refs: `crop` (zoom cover), `fit: letterbox` (whole frame sharp over a blurred copy), `y` (band position). One still yields 3–4 different shots |
| P-62 | In letterbox mode the big kinetic text covered faces in the sharp band | `y` places the band lower (e.g. 0.62–0.64) when the text sits on top |
| P-63 | `dna` overrides in project.json were ignored after the first proof (cached `work/dna.json`) | The cache is keyed by the overrides and regenerated when they change |
| P-64 | Poster-card chips with a long name ran off the right edge | Chips wrap into rows inside the safe width |
| P-65 | `words.json` / `voice` reported the preset rate instead of the rate actually used after duration control | The effective rate is recorded |
| P-66 | The line motif (`slashes`) crossed actors' faces on footage beats | SKILL.md: choose a quiet motif (`dust`, `light_rays`, `film_perfs`) for face-heavy stills |
| P-67 | VS split: the upper side's sub-label sat on the divider and the VS badge covered it | Each side's block is centred in its own zone, kept clear of the badge + divider |
| P-68 | Cast portraits with 3 people: a 2-line name + role chip ran into the next row's circle | Circle size follows the row slot; name + chip block is centred on its row and fits between neighbouring rings |
| P-69 | List items low on the screen reached x≈1050 (Reels buttons zone) | Items below y=1000 use the low safe width |
| P-70 | A stat beat whose number is spoken late showed one still for 4 s (QA static run) | SKILL.md: give such beats two media so a cut lands before the counter |
| P-71 | QA reported only the longest static run, so each fix needed another full render to find the next one | `no_static_runs` also lists `all` runs > 2.5 s as [start, length] |

Tests: 18 → 21 (`test_still_crop_letterbox_and_band_position`, `test_dna_overrides_invalidate_cached_dna`, `test_qa_lists_every_static_run`).

## v2.2 — channel mode (Scene Samjho)

| # | Operator asked | Fix |
|---|---|---|
| C-01 | "Skill ko yaad rahe ki channel kaunsa hai, har nayi chat mein" | `CLAUDE.md` (auto-loaded every session) + `channel/channel.json` (name, handle, niche, pillars, rhythm, schedule, reel rules) + `run.py channel` brief |
| C-02 | "Har video channel ke hisaab se bane" | `apply_defaults` on every project load and on `new` (50 s reel, viral captions, quiet motif, voice, handle on the end card); project values win |
| C-03 | "Video viral jaaye" rules | Lint: length/word count (hard), hook ≤ 16 words, send line, two-option question. QA `channel_reel_length` ≤ 90 s (hard). Upload pack: posting time, ≤ 5 hashtags with `#SceneSamjho` first |
| C-04 | "Pichhli videos yaad rahein" | `channel/history.jsonl` + `run.py log` (made → posted → Insights numbers); variety ledger moved to committed `channel/state/` so a new cloud session keeps it |
| C-05 | "Pehle script dikhao, phir banao" | Workflow in CLAUDE.md, SKILL.md §0 and CHANNEL.md: script MD with sources → wait for "continue" → render |

Tests: 21 → 23 (`test_channel_defaults_lint_hashtags`, `test_channel_log_and_brief`).

## v2.3 — the operator's script system (topic → PDF → "continue" → video)

| # | Operator asked / found | Fix |
|---|---|---|
| S-01 | "Topic do to pehle poori PDF do, phir continue par video" | `prompts/` (Research Brief v3, Script Doctor v4, PDF Handover v3) + `prompts/ADAPTATION.md`; `run.py handover` builds the PDF from the brief, the script pack and the engine's real proof frames, and rasterises every page for a visual check |
| S-02 | Script Doctor v4 engagement rule (one CTA, voice ends on the loop line) | Channel lint accepts the on-screen question (`data.question`) and checks for a send-worthy line; `cta_loop` can drop the second chip (`comment_cta: ""`); kill-list phrases added to the cliché check |
| S-03 | India IT Rules 2026 (synthetic content labels) | `disclosure` field (channel default "AI voice") printed with the handle on the end card |
| S-04 | Stale proof frames from earlier runs leaked into reviews | `proof` clears `work/proof_frames/` first |
| S-05 | A 5-item save card was cut to 4 | `list_reveal` shows up to 5 items |
| S-06 | Poster card in the "poster_punch" opening covered the face on a poster background | Director note: use `word_smash` + letterbox `y` when the hook still is a poster |

## v2.4: real numbers + 5 top creators (4 Nov 2026)

| # | Operator found / data showed | Fix |
|---|---|---|
| R-01 | Ramayan reel: skip 62.7 %, half the viewers gone in the first second. Frame 1 was a white flash, then one word | `hook_slam` `data.frame1`: the whole hook text is on screen at t = 0 with no flash. The Drishyam reel's skip fell to 52.6 % and its views tripled |
| R-02 | "Har video ek jaisi dikhti hai, bas script badalti hai" | Style DNA **look** (`poster` / `clean` / `rush` / `bar` / `split`) that never repeats the previous video (QA `look_differs_from_last`). Channel defaults no longer pin `caption_style` / `motif` |
| R-03 | Top creators: bright footage, almost no text on screen | `footage_clean` archetype; light scrim (floor 0.05 instead of 0.42) in clean looks; one graphic card max |
| R-04 | Top creators: footage band on top, host below | `split_top` + `SplitBackground` (band + face-cam or word panel + seam label) |
| R-05 | Top creators: a real person on camera | `assets.host`: the operator's selfie video becomes the voice (recording engine, synced for trimmed lead silence) and the `host_cam` / split panel picture. No "AI voice" label then |
| R-06 | 16:9 trailers lost ~70 % of the picture in a 9:16 crop | `fit: "rotate"` for clips and stills; `fit: "letterbox"` for clips |
| R-07 | Recurring series identity ("MOST WATCHED SERIES", "1 MIN REVIEW") | `bar` look: persistent series header (`series`, default from the pillar) |
| R-08 | Our AI voice: 2.7 words/s; the references: 3.3–4.2 | Channel voice rate +28 %; `reel_rules.voice_style` (talk like a person, claim + number first, curiosity gap, callback ending) |

Analysis: `docs/REFERENCE_ANALYSIS.md`. Tests: 25 → 27 (`test_looks_map_beats_and_never_repeat`, `test_rotate_fit_and_split_background_with_host`).

| # | Operator asked | Fix |
|---|---|---|
| R-09 | "Meri photo har video mein aaye, mera look" | `channel/host/` (photo + background-removed cut-out, `channel.json` → `host`); presenter on the hook, `footage_clean`, `split_top` panel, `host_cam` and the cover; `idle: "talk"` (moves on every spoken word); per-scene caption line `cap_y` above his head; stickers never land on him; openings that would cover frame 1 (`split_reveal`, `countdown`, `rating_first`) are swapped when `frame1` is set |

Tests: 27 → 28 (`test_presenter_on_hook_and_footage_scenes`).
