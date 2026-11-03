# QA report — PASS

Video: `caligari-1920-review.mp4` · 41.4s · voice timing: exact (edge-tts WordBoundary)

| check | result | value | rule |
|---|---|---|---|
| duration_vs_target | PASS | 41.43 | |41.4s − 45s| ≤ 4.5s (fix the SCRIPT, not the speed) |
| distinct_frame_designs | PASS | 9 | ≥ 5 distinct archetype layouts |
| no_repeat_consecutive_layout | PASS | [] | no archetype twice in a row |
| archetype_reuse_limit | PASS | {} | no archetype more than 2× per video |
| designed_transitions | PASS | 8 | every scene boundary has a designed transition (no hard cuts) |
| text_min_size | PASS | [] | hero ≥56px, body ≥40px, label ≥30px |
| caption_size | PASS | 80 | captions ≥ 64px on a 1080px-wide frame |
| caption_collision | PASS | [] | scene text ends above the caption band when captions are on |
| safe_zones | PASS | [] | critical text inside Reels safe area (top 225, bottom 1495, right 1000 below y=1000) |
| no_static_runs | PASS | {"longest_s": 0.1, "at_s": 30.3} | a visible visual event (≥0.4 % of pixels change) at least every 2.5 s |
| hook_pattern_interrupt | PASS | 100.0 | ≥ 20 % of the frame changes inside the first 1.5 s |
| hook_not_greeting | PASS | "106 saal purani film… aur aaj bhi daravn" | first line is a hook, never a greeting |
| hook_layout | PASS | "hook_slam" | opening beat uses a designed hook |
| visually_distinct_frames | PASS | 8 | ≥ 5 visually different scene frames (dHash > 10 bits) |
| no_banding_or_flat_fills | PASS | 0.064 | flat 4×4 plateaus < 25 % of mid-tone area |
| dead_space | PASS | {"max": 0.359, "per_scene": [0.019, 0.0, 0.007, 0.359, 0.0, 0.0, 0.0, 0.0, 0.0]} | featureless area ≤ 55 % of the safe area |
| loudness | PASS | {"I": -14.07, "TP": -1.5, "LRA": 1.6} | −14 LUFS ±1.5, true peak ≤ −0.8 dBTP |
| music_present | PASS | -37.3 | music bed present by default |
| sfx_on_events | PASS | 48 | SFX on transitions + in-scene events |
| captions_cover_speech | PASS | "75/75" | every spoken word in caption beats is captioned (word-synced) |
| footage_coverage | PASS | "9/9 scenes on real footage" | with media supplied, ≥70 % of scenes sit on real footage/stills |
| stickers | PASS | 4 | ≥1 emoji sticker accent (unless the DNA chose none) |
| script_cliches | PASS | [] | ≤ 1 cliché per script (specific > generic) |
| dna_differs_from_past | PASS | [12, 11, 11] | ≥ 4 of 12 style dimensions differ from each of the last 5 videos |
| frames_differ_from_past | PASS | [30.2, 25.7, 27.0] | avg nearest-frame dHash distance to past videos ≥ 9 bits |

Self-review is still required: open the contact sheet + frames, then write review.md (see SKILL.md).