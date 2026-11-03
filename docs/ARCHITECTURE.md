# Architecture

## 1. Decision: which engine renders the motion?

| Option | Visual ceiling | Variety | Speed (60 s Reel) | Cost | Reliability | Runs on the operator's setup (cloud Claude Code / PC / Termux) |
|---|---|---|---|---|---|---|
| **A. Remotion (React + headless Chromium)** | Very high (CSS, SVG, any web animation) | High | Medium. A browser screenshot per frame; needs a warm Chromium | Free for individuals and small teams; company licence above that (Remotion's own licence — verify before commercial use) | Good, but a heavy toolchain (Node, npm, Chromium) | Cloud/PC yes, **Termux no** |
| **B. Python procedural motion engine (Pillow + numpy → ffmpeg pipe)** ✅ | High for kinetic type, cards, particles and camera; no GPU shaders | High. Every parameter is data (Style DNA) | **Fast**: forked workers render frame ranges straight into x264; a 43.8 s Reel takes 53 s end to end on 4 cores (measured) | Free (MIT / HPND / BSD stack) | Deterministic, pure function of time | **Everywhere** (cloud, PC, Termux) |
| **C. Per-scene AI-generated artwork + draw-on animation** | Unique art | Very high | Slow (image API per scene) | Paid API per video | Inconsistent style, text artefacts | Needs a paid key; rights of generated art unclear |
| **D. Hybrid** | B + any operator-supplied stills or AI art as assets | – | – | – | – | – |

**Chosen: B as the engine, D as the policy.** The engine is the Python procedural renderer. Any image the operator supplies (licensed stills, product photos, AI mockups they own) enters as an asset the engine lays out and animates.

Reasons:
- It runs where the operator works, including Termux (P-46).
- It is fast (the operator's main complaint was 30+ minutes per video).
- It is deterministic, so QA can reason about every frame.
- Option A was rejected as the default because of the Chromium requirement and the licence terms. It stays a possible future backend: the Style DNA and plan JSON are engine-agnostic.

## 2. Pipeline

```
project.json (Director: research, script, visual screenplay)
  → lint (hook rules, empty-card prevention, pacing, clichés)
  → voice: edge-tts per beat (exact WordBoundary timings) → Kokoro → espeak-ng; duration control
  → Style DNA (poster palette + genre/category profile + taste memory + Variety Ledger novelty)
  → Timeline: archetype per beat (role → archetype, no repeats), variants, transitions, captions, SFX cues, music sections
  → proof: first 6 s + key frames + contact sheet → Director looks and fixes
  → mix: voice chain + procedural music composed to the timeline + designed SFX → two-pass loudnorm −14 LUFS
  → render: forked workers → x264 segments → lossless concat → mux
  → design QA (hard gates) → ledger entry → honest review.md → deliver
```

## 3. Modules

| File | What it does |
|---|---|
| `rvs/core.py` | Spring physics (damped oscillator), easing, OKLab colour science, WCAG contrast, k-means poster palette |
| `rvs/typo.py` | Font registry (41 OFL / Apache fonts), RAQM shaping, per-word script and glyph fallback, fit-to-box hero type |
| `rvs/gfx.py` | Dithered gradients, mesh gradients, real frosted glass, AA shapes, stroke-draw icons, perspective tilt, duotone, halftone, light rays, bokeh, film perfs, stamps |
| `rvs/engine.py` | Layers with spring enter/idle/exit, dynamic layers, particles, parallax camera (push/drift/orbit/dolly/handheld + punches + shake), backgrounds, 13 transitions |
| `rvs/scenes.py` | 19 archetypes, backgrounds per DNA, motifs, kinetic typography core |
| `rvs/captions.py` | Word-synced captions, 7 styles |
| `rvs/dna.py` | Style DNA, Variety Ledger, taste memory, reference intake |
| `rvs/audio.py` | TTS, procedural composer (8 moods), designed SFX, mix |
| `rvs/timeline.py` | Turns the plan into a frame(t) function |
| `rvs/render.py` | Parallel render and encode |
| `rvs/qa.py` | Design QA |
| `rvs/lint.py` | Script lint |
| `rvs/cli.py` | Commands |

## 4. Variety guarantee (and how it is measured)

1. **Per-video Style DNA** has 12 dimensions:
   - `palette_family`, `tone`
   - `hero_font`
   - `background`, `motif`
   - `motion`, `transitions`
   - `caption_style`, `opening`
   - `card_shape`, `layout_align`
   - `music_mood`

   Generation samples 160 candidates from the genre or category profile, weighted by taste memory. It scores fit + novelty against the ledger and keeps the best. Any candidate that differs from one of the last 3 videos on fewer than 5 dimensions is heavily penalised. Tone and music are *bound* to the genre: novelty never puts playful music on a horror film.
2. **Inside a video:**
   - Every beat gets a different archetype or variant (no repeats in a row, ≤ 2 uses per minute).
   - Backgrounds alternate between two DNA treatments, with a different poster focus crop per scene.
   - Transitions cycle round-robin through the DNA vocabulary.
3. **Measured by QA:**
   - `distinct_frame_designs`: ≥ 5 distinct archetype layouts in a movie review.
   - `visually_distinct_frames`: dHash > 10 bits between scene frames.
   - `dna_differs_from_past`: ≥ 4 of 12 dimensions differ from each of the last 5 videos.
   - `frames_differ_from_past`: average nearest-frame dHash distance to past videos ≥ 9 bits.

## 5. Instagram Reels safe zones (what the numbers are based on)

Meta has not published an official safe-zone spec for organic Reels. Public guides disagree:
- Meta's Reels-*ads* guidance, as reported by checker sites, is ≈ 14% top, 35% bottom and 6% sides.
- Several creator guides use a centred 1080×1420 area, or 250 px top / 350–440 px bottom / ~120 px right.

The engine uses a **conservative organic profile (ESTIMATE)**:
- Text is kept between y = 250 and y = 1480. QA tolerance is 225–1495.
- Text stays at x ≥ 70.
- The right edge is ≤ 1010, and ≤ 940 for captions below y = 1000, which clears the like/comment/share buttons.
- Captions sit at y ≈ 1240–1330.

Re-check against the current app before relying on it for ads. Sources (searched 2026-11-02):
- https://www.hopperhq.com/blog/instagram-reel-size/
- https://admanage.ai/instagram-reels-safe-zone
- https://www.socialync.io/tools/safe-zones/instagram-reels

## 6. Research notes: what was taken, what was rejected

| Project / technique | Licence (as stated by the project; verify for commercial use) | Taken | Rejected |
|---|---|---|---|
| Remotion | Remotion Licence (free for individuals and small companies) | The idea of a pure `frame(t)` composition, spring-based motion primitives, and an engine-agnostic plan | Node/Chromium dependency as the default |
| MoviePy | MIT | Clip-as-function-of-time thinking | Its per-frame Python compositing is slower than our cached-sprite approach |
| libass karaoke | ISC | Word-level highlight concept | ASS styling can't do pills, highlighter swipes, or springs on our scale; captions are drawn by the engine instead |
| Pillow + RAQM (HarfBuzz) | HPND (Pillow) | Correct Devanagari shaping, whole-cluster rendering | – |
| edge-tts | LGPL-3.0 (checked in the earlier audit) | Free neural Hindi voices with WordBoundary events, which give **exact** word timings | – |
| kokoro-onnx + Kokoro-82M | MIT / Apache-2.0 weights (checked in the earlier audit) | Offline voice fallback | No word events, so timing is estimated |
| ffmpeg (loudnorm, x264) | LGPL/GPL build | Two-pass loudnorm, x264 encode, concat | – |
| Google Fonts (41 families) | SIL OFL 1.1 / Apache 2.0 (licence files in `assets/fonts/licenses/`) | Bundled so it works offline | – |
| Stock music / SFX sites | Varies, often unclear for redistribution | – | Bundling third-party audio. Instead the music and SFX are synthesised (original). The operator can supply licensed tracks. |

Spring maths: closed-form step response of a damped harmonic oscillator, `x(t) = 1 − e^{−ζωt}(cos ω_d t + ζω/ω_d sin ω_d t)`. The five motion personalities are (ω, ζ) pairs.

## 7. Known limits (honest)

- **Procedural music** is good enough as a bed, not a studio production. Licensed tracks give better results.
- **Saliency crops** (without Director focus boxes) are heuristic: edge density × colourfulness, not a face detector.
- **Speed figures** are measured on a 4-vCPU container. Phones are slower.
- **The dead-space metric** is an advisory heuristic; the other QA metrics are hard gates.

## 8. v2 — footage-first editing, voice v2, stickers, music v2 (operator feedback: "awaaz bakwas, editing boring")

**Footage-first.** `rvs/media.py`
- **Catalogue:** stills + video clips are catalogued; clips are split into shots with ffmpeg scene detection (`select=gt(scene,0.3)`).
- **Media sheet:** every still and shot gets a thumbnail in `media_sheet.jpg` with a reference label (`media/x.mp4#3`).
- **Assignment:** the Director assigns media per beat, or auto-assignment picks by detail + length (title cards and black frames are filtered out).
- **Cut rhythm:** beats longer than ~2.2 s get several shots, with cut points snapped to word starts.
- **`FootageBackground`:**
  - It is a dynamic background with `t`.
  - Stills are cover-fitted with a baked legibility scrim.
  - Clips are decoded sequentially by a per-worker ffmpeg (`-ss` seek, `setpts` slow-mo down to 0.5× when a shot is shorter than the beat, last frame held, re-opened after fork).
  - The camera (push / punch / shake) moves the footage like any other layer.
  - Every cut adds a camera kick, a 2-frame flash, a warm light-leak sweep and a swish SFX.

**Free media.** `media search` queries the Wikimedia Commons API:
- Licences are filtered to PD / CC0 / CC BY / CC BY-SA.
- Only standard thumbnail steps are requested (1280 px; non-standard sizes return 429 per https://www.mediawiki.org/wiki/Common_thumbnail_sizes).
- The tool backs off on 429.
- Credits go to `media/credits.json` → the upload pack.

**Voice v2.** `rvs/voice.py`
- Engines:
  - edge (exact WordBoundary);
  - ElevenLabs `/v1/text-to-speech/{voice_id}/with-timestamps` (character alignment → words; doc-verified, not live-tested without a key);
  - recording / files (any audio → faster-whisper word timestamps → monotonic DTW alignment to the script on a Devanagari-skeleton similarity);
  - Kokoro and espeak.
- Measured on a 43 s Hindi take: mean word-start error 0.145 s, p90 0.32 s vs exact edge timings.
- Reel pacing:
  - inner pauses > 0.2 s cut to 0.13 s (0.3 s after `… ? !`);
  - 0.16 s dramatic beat before hero words;
  - word timings shifted consistently (start/end-aware).
- Broadcast chain: HPF → mud cut → compressor 6:1 → presence + air → de-esser → glue compressor → limiter.
- Whisper intelligibility of the presets (hook + fact, Hindi), MEASURED:

  | Preset | Voice | Intelligibility |
  |---|---|---|
  | `hindi_female` | Swara | 0.889 |
  | `hindi_male` | Madhur | 0.878 |
  | `multi_male2` | Brian | 0.871 |
  | `multi_male` | Andrew | 0.812 |
  | `multi_female` | Ava | 0.714 |

**Stickers.**
- Source: 89 Microsoft Fluent UI 3D emoji (MIT, 256 px).
- Selection: keyword map in Hinglish / English / Devanagari, hero words first.
- Placement: the first spot that does not overlap any text block at that moment; no free spot → no sticker.

**Captions v2.** `viral` (progressive word reveal, heavy outline, yellow active word with overshoot bounce, short groups up to +30% bigger) and `viral_box`. Both get a strong prior in every Style DNA profile.

**Music v2.**
- Instruments: layered kick, 808 metallic hats (six square oscillators), 808 cowbell.
- New `phonk` mood; sidechain pumping on upbeat_pop / synthwave / hype_trap / phonk.
- The beat grid starts at 0 with the DNA BPM, and scene cuts snap to it (±0.2 s).
- Operator tracks: spectral-flux onset → autocorrelation tempo (70–180 BPM, log-normal prior) → best phase. Cuts snap to that grid.
- A voice + SFX-only mix is always exported for in-app trending audio.

**Deliverables.** `rvs/deliver.py`
- Cover from a clean background frame (no text) + title + stars + tag.
- 4:5 grid crop.
- `upload_pack.md` with caption draft, hashtags, credits and checklist.

**Speed.**
- Big sprites rotate in 1° steps (bilinear); camera-shake jitter below 0.5° is not rotated; scale is quantised to 0.5% for cache hits.
- Clips decode with `-threads 1`, bilinear, on a 1.06× plate.
- Footage frames cost ~70–170 ms vs ~35 ms for graphic frames.
