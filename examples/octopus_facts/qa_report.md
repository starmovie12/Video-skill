# QA report — PASS

Video: `octopus-facts.mp4` · 24.1s · voice timing: exact (edge-tts WordBoundary)

| check | result | value | rule |
|---|---|---|---|
| duration_vs_target | PASS | 24.1 | |24.1s − 26s| ≤ 3.0s (fix the SCRIPT, not the speed) |
| distinct_frame_designs | PASS | 6 | ≥ 3 distinct archetype layouts |
| no_repeat_consecutive_layout | PASS | [] | no archetype twice in a row |
| archetype_reuse_limit | PASS | {} | no archetype more than 2× per video |
| designed_transitions | PASS | 5 | every scene boundary has a designed transition (no hard cuts) |
| text_min_size | PASS | [] | hero ≥56px, body ≥40px, label ≥30px |
| caption_size | PASS | 84 | captions ≥ 64px on a 1080px-wide frame |
| caption_collision | PASS | [] | scene text ends above the caption band when captions are on |
| safe_zones | PASS | [] | critical text inside Reels safe area (top 225, bottom 1495, right 1000 below y=1000) |
| no_static_runs | PASS | {"longest_s": 0.4, "at_s": 7.5} | a visible visual event (≥0.4 % of pixels change) at least every 2.5 s |
| hook_pattern_interrupt | PASS | 98.8 | ≥ 20 % of the frame changes inside the first 1.5 s |
| hook_not_greeting | PASS | "Is janwar ke teen dil hain… aur khoon ne" | first line is a hook, never a greeting |
| hook_layout | PASS | "hook_slam" | opening beat uses a designed hook |
| visually_distinct_frames | PASS | 6 | ≥ 3 visually different scene frames (dHash > 10 bits) |
| no_banding_or_flat_fills | PASS | 0.032 | flat 4×4 plateaus < 25 % of mid-tone area |
| dead_space | PASS | {"max": 0.003, "per_scene": [0.001, 0.003, 0.002, 0.001, 0.001, 0.0]} | featureless area ≤ 55 % of the safe area |
| loudness | PASS | {"I": -14.15, "TP": -1.48, "LRA": 3.0} | −14 LUFS ±1.5, true peak ≤ −0.8 dBTP |
| music_present | PASS | -34.7 | music bed present by default |
| sfx_on_events | PASS | 33 | SFX on transitions + in-scene events |
| captions_cover_speech | PASS | "44/44" | every spoken word in caption beats is captioned (word-synced) |
| footage_coverage | PASS | "6/6 scenes on real footage" | with media supplied, ≥70 % of scenes sit on real footage/stills |
| stickers | PASS | 2 | ≥1 emoji sticker accent (unless the DNA chose none) |
| script_cliches | PASS | [] | ≤ 1 cliché per script (specific > generic) |
| dna_differs_from_past | PASS | [11, 12, 12] | ≥ 4 of 12 style dimensions differ from each of the last 5 videos |
| frames_differ_from_past | PASS | [25.8, 32.0, 25.0] | avg nearest-frame dHash distance to past videos ≥ 9 bits |

Self-review is still required: open the contact sheet + frames, then write review.md (see SKILL.md).