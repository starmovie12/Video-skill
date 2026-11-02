# Video-skill — Review Video Studio

Claude Code skill jo **motion-designed 9:16 Reels/Shorts** banata hai (Hinglish): movie review, boutique/product promo, facts, story,
software, game. **Har video alag dikhega** — har video ka apna **Style DNA** banta hai, aur ek **Variety Ledger** pichhli videos yaad
rakhta hai aur agli video ko alag hone pe majboor karta hai. **Design QA** ghatiya/khaali/repeat output ko deliver hone se rokta hai.

## Pehle kya galat tha → ab kya hai

| Problem (purana skill) | Ab (ye skill) |
|---|---|
| Har video ek jaisa, same dark-navy card, same layout | Har video ka **Style DNA**: poster se palette, 41 fonts, 10 backgrounds, 12 motifs, 5 motion personalities, 13 transitions, 7 caption styles, 6 opening moves, 8 music moods. Ledger last 5 videos se ≥4/12 dimensions alag karwata hai |
| Sirf ~5 card modes, ek hi function | **19 scene archetypes**, har ek ke 1–3 layout variants (rating ring, pros/cons balance beam, cast portraits, filmstrip, stamp/seal/neon verdict, price tag swing…). Movie review me ≥5 alag designs (QA enforce karta hai) |
| Still image + halka zoom = PowerPoint | Asli motion: spring physics, parallax camera + punches/shake, kinetic typography, stroke-draw icons, count-ups, particles, 13 designed transitions (whip, zoom-through, ink, iris, glitch, shutter…) |
| Chhote captions, highlight word sync nahi | **Bade (72–82 px) word-synced captions** (edge-tts ke exact word timings), active word pe pill / highlighter / pop, Reels safe-zone ke andar |
| Poster kahan lagana hai AI nahi sochta | Poster ke kai designed use: 3D tilt card, full-bleed, framed, zoomed+blurred backgrounds, filmstrip, story thumbnails — Director (Claude) poster dekh ke faces/key-art ke focus boxes deta hai |
| Poster nahi → rainbow gradient | Premium poster-free looks: mesh gradient, spotlight + light rays, paper texture, tech grid, bokeh, split tone, procedural fabric (products). Dithered gradients — no banding |
| Music off, SFX = sine beep | **Original procedural music** (8 moods) jo video ke timeline pe compose hoti hai (transitions pe hits, verdict pe drop) — licence-free. **Designed SFX** (whoosh, impact, stamp, tick, ding, glitch…) in-scene events pe. −14 LUFS |
| Robotic slow voice | +18% energetic pace, per-beat energy (hook tez, verdict thoda slow), designed pauses; target duration control (voice re-time) |
| 1 min video = 30+ min | Parallel renderer: **~25–55 s** full pipeline for 19–44 s Reels (4 cores) — measured below |
| QA "pass" par video ugly | **Design QA hard checks**: text size, safe zones, static runs, hook interrupt, distinct frames, banding, duration, loudness, music/SFX, variety vs past videos + honest `review.md` gate before delivery |

## Demo videos (is exact code se render)

Har example folder me: `preview_720p.mp4` (chhota preview), `contact_sheet.jpg`, `qa_report.md`, `review.md` (honest self-review).
Full 1080×1920 videos `python run.py make examples/<name>` se dobara ban jaate hain (~30–50 s each).

| Example | Category | Look (Style DNA) |
|---|---|---|
| `examples/caligari` | Movie review — *The Cabinet of Dr. Caligari* (1920, public-domain poster) | poster se bani dark magenta-orange palette, Playfair serif, poster-punch opening, epic trailer music |
| `examples/nosferatu` | Movie review — *Nosferatu* (1922), **bina poster** | green spotlight horror, Creepster type, scanlines, dark pulse music |
| `examples/octopus_facts` | Facts | mid-tone blue pop, Archivo, pill captions, upbeat music |
| `examples/winter_shawl` | Boutique product (DEMO data) | light paper boutique, Marcellus serif, sparkles, ambient luxe music |

## Install

Claude Code skill ki tarah (recommended):
```bash
git clone https://github.com/starmovie12/Video-skill ~/.claude/skills/review-video-studio
cd ~/.claude/skills/review-video-studio
pip install -r requirements.txt          # + ffmpeg (apt install ffmpeg | pkg install ffmpeg)
python run.py doctor                     # ffmpeg, ffprobe, raqm = true hone chahiye
```

## Use (Claude Code ke saath)

Claude ko bolo: *"Is skill se <film> ka review reel banao"*. Claude `SKILL.md` follow karega: research → script → visual screenplay →
`proof` (khud frames dekhega) → `make` → honest review → `deliver`.

Manual:
```bash
python run.py new movie_review my_film     # template
# my_film/project.json edit karo + poster daalo
python run.py proof my_film                # 6 s proof + key frames + contact sheet
python run.py make my_film                 # full render + mix + QA  → my_film/out/
python run.py deliver my_film              # QA PASS + review.md ho tabhi
python run.py feedback my_film --approve --note "ye look pasand aaya"   # taste memory
python run.py refs my_references/          # reference images/videos se taste seekhna
```

## Speed (MEASURED, is container me: 4 vCPU, Python 3.13, ffmpeg 6.1.1)

| Video | Length | Full pipeline (voice+mix+render+QA) |
|---|---|---|
| Caligari review | 43.8 s | 53 s |
| Nosferatu review | 31.5 s | 48 s |
| Octopus facts | 25.5 s | 31 s |
| Shawl product | 18.8 s | 26 s |

Termux (phone) pe slow hoga — `--workers 2` use karo.

## Honest limits

- Music procedural hai (numpy synth) — original + licence-free, par studio track jaisi nahi. Best result: apna licensed track `assets.music` me do (auto-ducking hota hai).
- Edge-TTS ko internet chahiye. Offline fallback (Kokoro / espeak-ng) me word timing estimated hoti hai, exact nahi.
- Instagram safe-zone numbers public guides se banaya conservative profile hai (Meta ka official organic-Reels spec published nahi) — `docs/ARCHITECTURE.md` dekho.
- Naye films ke posters copyrighted hote hain — `SKILL.md` ke rights rules padho.

## Licences

Code: MIT (`LICENSE`). Fonts: SIL OFL 1.1 / Apache 2.0 (`assets/fonts/licenses/`). Demo posters: public domain (sources `project.json` me).
