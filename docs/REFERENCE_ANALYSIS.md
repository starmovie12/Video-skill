# Reference analysis: 5 top Hindi film shorts vs our first reels

**Date:** 4 Nov 2026.

**What:** 5 shorts the operator downloaded from top Indian film creators (described by the operator as "1 billion+ views" channels). They were analysed with ffmpeg (cuts, loudness, frames) and Whisper `medium` (Hindi transcripts with word times).

**Copyright:** the videos and full transcripts are **not** in this repo, because they are other creators' work. This file keeps only measurements, short quotes and the patterns we turned into rules.

| # | Video (file title) | Length |
|---|---|---|
| v1 | "1300 crore ke PRABHAS" (#yogiboltahai) | 46 s |
| v2 | "3 Best Netflix Webseries" | 60 s |
| v3 | "Koreans ki sabse khatarnak movie: Hope" | 57 s |
| v4 | "Sara Arjun: Dhurandhar actress, underrated film" (#FilmiIndian) | 63 s |
| v5 | "Spider-Man: Brand New Day review in Hindi" | 60 s |

## 1. What we measured

| | v1 | v2 | v3 | v4 | v5 | **our Ramayan** | **our Drishyam** |
|---|---|---|---|---|---|---|---|
| Length | 46 s | 60 s | 57 s | 63 s | 60 s | 50 s | 39 s |
| Median shot | 1.9 s | 1.3 s | ~2 s in the footage band* | 1.2 s | 0.8 s | ~2.2 s | ~2.2 s |
| Real person on screen | host on green screen over footage | host to camera, cuts to footage | host bottom ~60 %, footage top | host intro, then photo montage | host bottom half + poster, full-screen footage | **no** | **no** |
| Voice | own, fast, energetic | own, very fast | own, very personal | own, calm | own | AI | AI |
| Speech rate | 3.3 words/s | 4.2 words/s | 2.5 words/s (with long pauses for effect) | 3.9 words/s | not measured (music under the voice; Whisper caught only part of it) | 2.6 words/s | 2.7 words/s |
| On-screen text | only the numbers ("₹1300 Crores!!!", "₹600 Crores") | series header + one stat line ("1.71 BILLION HOURS") | **none** | **none** | "1 MIN REVIEW" label | big kinetic type on every beat + captions | big kinetic type on every beat + captions |
| Word-by-word captions | no | no | no | no | no | yes | yes |
| Footage brightness | full colour | full colour | full colour | full colour | full colour | darkened by a scrim | darkened by a scrim |
| Loudness | −11 LUFS | −18 LUFS | −11 LUFS | −20 LUFS | −15 LUFS | −14 LUFS | −14 LUFS |

\* The whole-frame cut detector under-counts split layouts: the host half does not change, so cuts in the footage band score low. Counted by eye, the band cuts every ~2 s.

## 2. Patterns all five share (and we did not)

1. **A real person.** 5/5 show the creator's face and use their own voice. Viewers stay for a person they recognise, not for a slideshow. Our reels: AI voice + Commons photos.
2. **Footage is the picture; text is rare.** No reference uses word-by-word captions or big kinetic typography. Text appears only for the number or name that matters, or as a series label. Ours put a designed text card over darkened footage on every beat. That is why every reel looked the same, whatever the script.
3. **Bright, full-colour footage.** No dark scrim. Ours darkened every shot so the text would read.
4. **A layout per creator, the same every video (their "brand").**
   - Green-screen host over footage (v1).
   - Host full frame, cutting to footage (v2, v4).
   - Footage band on top, host below (v3, v5).
   - A recurring label ("MOST WATCHED SERIES", "1 MIN REVIEW").
5. **16:9 footage handled without losing the picture:**
   - rotated 90° to fill the frame (v2, v4);
   - placed in a top band (v3, v5);
   - cropped to vertical only for close action (v5).
6. **Hook = the claim + the number or name, in under 2 s, said by the person:**
   - "Terah sau crore ke Prabhas." (v1)
   - "Netflix ke 3 sabse zyada dekhe jaane wale shows…" (v2)
   - "Bhai believe nahi hoga, ye Koreans ki sabse mehngi film hai." (v3)
   - The first frame is either the host mid-sentence or the most violent action shot (v3, v5).
7. **Fast cuts:** a new picture every 0.8–2 s.
8. **Thumbnail ≠ first frame:**
   - The custom cover shows the host's face, one short claim and an emoji (🔥 🤯).
   - Or a series badge ("1 MIN REVIEW").

## 3. How they talk (from the transcripts)

- **No greeting, no "dosto".** The first words are the claim.
- **Casual spoken Hindi with English film words:** budget, flop, record, trend, experience, chase sequence.
- **Personal and emotional:**
  - "bhai", "kasam se", "maine isko dekh liya hai", "believe nahi hoga";
  - affectionate fan terms ("apne Prabhas bhai");
  - direct address with "tum" / "aap".
- **One fact or number per sentence, numbers early** (v1: every sentence carries a budget).
- **Comparisons the audience already knows:**
  - "S.S. Rajamouli ki RRR yaad aa jayegi" (v3);
  - Baahubali and Salaar as the reference points (v1).
- **Verdict first in a review** (v5): "agar main quickly review karun to itna hi bolunga ki… ye winning Spider-Man movie hai", then the reasons, then a personal pick ("Punisher ka role mujhe personally kaafi badhiya laga").
- **Ride a trending debate into your own topic** (v4):
  - opens on the week's talking point ("Dhurandhar mein 40 ke Ranveer ke saamne 20 ki heroine… har koi hil gaya");
  - then pivots with "lekin kya aapko pata hai…" to an older film of the same actress.
- **Curiosity gap:**
  - v3 says the film's name only at ~48 s, after "ab aage kya hoga? kaun bachega?";
  - v4: "naam sirf ek shart pe bataungi… agar aaj raat 12 baje dekhoge", and the name comes in the last 5 s;
  - v2 counts down 3 → 1.
- **Ending:**
  - a callback to the hook ("To hue na apne Prabhas bhai terah sau crore wale", v1);
  - a verdict ("isko miss mat karna", v3, v4);
  - or a fun clip (v5).
  - No "like / share / subscribe".
- **Pace:** 3.3–4.2 words/s when listing facts (v1, v2). Slower with dramatic pauses when building suspense (v3). Our AI voice ran at 2.7 words/s, flat.

## 4. Our numbers next to this

| Reel | Views (time) | Skip rate | Avg watch | Likes | Shares |
|---|---|---|---|---|---|
| Ramayan 1987 vs 2026 (49.8 s) | 158 (2 h) | 62.7 % | 7 s | 2 | 0 |
| Drishyam "2 October" (39 s), first reel with the frame-1 hook | 481 (4 h) | 52.6 % | 5 s | 2 | 0 |

- The frame-1 hook lowered the skip rate by 10 points.
- Viewers still left right after the hook. Nothing after it looked or sounded like a person talking to them.

## 5. What changed in the skill (4 Nov 2026)

| Finding | Skill change |
|---|---|
| Every reel looked the same | New **look** dimension in the Style DNA: `poster` / `clean` / `rush` / `bar` / `split`. It never repeats the previous video's look (QA `look_differs_from_last`), and channel defaults no longer pin caption style or motif. |
| Footage is the picture, text is rare | `footage_clean` archetype: bright full-bleed footage plus only the number or name (`data.tag`). Clean looks keep one graphic card max. |
| Footage band + host below | `split_top` archetype + `SplitBackground` (band ~44 %, host or word panel below, label on the seam). |
| A real person | `assets.host` = the operator's selfie recording. Its audio becomes the voice (Whisper-aligned), and `host_cam` cuts back to the face. |
| 16:9 trailers lose most of the picture | `fit: "rotate"` (clips + stills) and `fit: "letterbox"` for clips. |
| Recurring series label | `bar` look: persistent header (`series` in project.json, default from the pillar). |
| Faster speech | Channel voice rate +28 % (was +18 %). |
| Talk like a person | Script rules in `channel/channel.json` → `reel_rules.voice_style`, applied by Script Doctor. |

## 6. What we cannot copy, and should not

- **Their faces and years of audience trust.** The closest we can get is the operator recording himself (`assets.host`). Until then, the AI voice is the biggest gap.
- **Raw film footage in bulk.** These creators use long stretches of trailer and film clips. Our rule stays: short cuts from official trailers with our own voice and analysis on top, never a clip as the content. Rights Manager can still match trailer footage.
- **No layout guarantees views.** The looks give variety and a cleaner picture. The topic, the hook and a human voice decide the rest.
