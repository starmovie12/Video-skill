# channel/state

The skill's memory of past videos for **this channel**, committed so a new chat (or a fresh cloud session) still has it:

- `ledger.json` — Style DNA + frame hashes of every made video. The next video's look is chosen to differ from the last ones (QA `dna_differs_from_past`, `frames_differ_from_past`).
- `taste.json` — what the operator liked/disliked (`run.py feedback`). Appears after the first feedback.

Used automatically unless `RVS_HOME` is set. Commit + push it after every `make`.
