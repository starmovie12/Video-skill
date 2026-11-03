# QA report — PASS

Video: `nosferatu-1922-review.mp4` · 31.5s · voice timing: exact (edge-tts WordBoundary)

| check | result | value | rule |
|---|---|---|---|
| duration_vs_target | PASS | 31.53 | |31.5s − 33s| ≤ 3.3s (fix the SCRIPT, not the speed) |
| distinct_frame_designs | PASS | 8 | ≥ 5 distinct archetype layouts |
| no_repeat_consecutive_layout | PASS | [] | no archetype twice in a row |
| archetype_reuse_limit | PASS | {} | no archetype more than 2× per video |
| designed_transitions | PASS | 7 | every scene boundary has a designed transition (no hard cuts) |
| text_min_size | PASS | [] | hero ≥56px, body ≥40px, label ≥30px |
| caption_size | PASS | 72 | captions ≥ 64px on a 1080px-wide frame |
| caption_collision | PASS | [] | scene text ends above the caption band when captions are on |
| safe_zones | PASS | [] | critical text inside Reels safe area (top 225, bottom 1495, right 1000 below y=1000) |
| no_static_runs | PASS | {"longest_s": 0.1, "at_s": 24.4} | a visible visual event (≥0.4 % of pixels change) at least every 2.5 s |
| hook_pattern_interrupt | PASS | 100.0 | ≥ 20 % of the frame changes inside the first 1.5 s |
| hook_not_greeting | PASS | "Court ne ise nasht karne ko kaha… phir b" | first line is a hook, never a greeting |
| hook_layout | PASS | "hook_slam" | opening beat uses a designed hook |
| visually_distinct_frames | PASS | 7 | ≥ 5 visually different scene frames (dHash > 10 bits) |
| no_banding_or_flat_fills | PASS | 0.176 | flat 4×4 plateaus < 25 % of mid-tone area |
| dead_space | PASS | {"max": 0.439, "per_scene": [0.183, 0.439, 0.078, 0.19, 0.26, 0.209, 0.206, 0.39 | featureless area ≤ 55 % of the safe area |
| loudness | PASS | {"I": -14.18, "TP": -1.43, "LRA": 2.3} | −14 LUFS ±1.5, true peak ≤ −0.8 dBTP |
| music_present | PASS | -36.9 | music bed present by default |
| sfx_on_events | PASS | 35 | SFX on transitions + in-scene events |
| captions_cover_speech | PASS | "69/69" | every spoken word in caption beats is captioned (word-synced) |
| script_cliches | PASS | [] | ≤ 1 cliché per script (specific > generic) |
| dna_differs_from_past | PASS | [11] | ≥ 4 of 12 style dimensions differ from each of the last 5 videos |
| frames_differ_from_past | PASS | [13.8] | avg nearest-frame dHash distance to past videos ≥ 9 bits |

Self-review is still required: open the contact sheet + frames, then write review.md (see SKILL.md).