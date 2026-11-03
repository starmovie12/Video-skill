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
