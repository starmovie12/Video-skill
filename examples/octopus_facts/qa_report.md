# QA report — PASS

Video: `octopus-facts.mp4` · 25.5s · voice timing: exact (edge-tts WordBoundary)

| check | result | value | rule |
|---|---|---|---|
| duration_vs_target | PASS | 25.5 | |25.5s − 26s| ≤ 3.0s (fix the SCRIPT, not the speed) |
| distinct_frame_designs | PASS | 6 | ≥ 3 distinct archetype layouts |
| no_repeat_consecutive_layout | PASS | [] | no archetype twice in a row |
| archetype_reuse_limit | PASS | {} | no archetype more than 2× per video |
| designed_transitions | PASS | 5 | every scene boundary has a designed transition (no hard cuts) |
| text_min_size | PASS | [] | hero ≥56px, body ≥40px, label ≥30px |
| caption_size | PASS | 64 | captions ≥ 64px on a 1080px-wide frame |
| caption_collision | PASS | [] | scene text ends above the caption band when captions are on |
| safe_zones | PASS | [] | critical text inside Reels safe area (top 225, bottom 1495, right 1000 below y=1000) |
| no_static_runs | PASS | {"longest_s": 0.2, "at_s": 2.5} | a visible visual event (≥0.4 % of pixels change) at least every 2.5 s |
| hook_pattern_interrupt | PASS | 99.6 | ≥ 20 % of the frame changes inside the first 1.5 s |
| hook_not_greeting | PASS | "Is janwar ke teen dil hain… aur khoon ne" | first line is a hook, never a greeting |
| hook_layout | PASS | "hook_slam" | opening beat uses a designed hook |
| visually_distinct_frames | PASS | 5 | ≥ 3 visually different scene frames (dHash > 10 bits) |
| no_banding_or_flat_fills | PASS | 0.161 | flat 4×4 plateaus < 25 % of mid-tone area |
| dead_space | WARN | {"max": 0.638, "per_scene": [0.638, 0.24, 0.208, 0.253, 0.523, 0.471]} | featureless area ≤ 55 % of the safe area |
| loudness | PASS | {"I": -14.26, "TP": -1.4, "LRA": 3.5} | −14 LUFS ±1.5, true peak ≤ −0.8 dBTP |
| music_present | PASS | -33.3 | music bed present by default |
| sfx_on_events | PASS | 22 | SFX on transitions + in-scene events |
| captions_cover_speech | PASS | "44/44" | every spoken word in caption beats is captioned (word-synced) |
| script_cliches | PASS | [] | ≤ 1 cliché per script (specific > generic) |
| dna_differs_from_past | PASS | [11, 11] | ≥ 4 of 12 style dimensions differ from each of the last 5 videos |
| frames_differ_from_past | PASS | [14.0, 14.8] | avg nearest-frame dHash distance to past videos ≥ 9 bits |

Self-review is still required: open the contact sheet + frames, then write review.md (see SKILL.md).