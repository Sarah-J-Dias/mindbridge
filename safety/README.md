# safety/ — Safety & ethics (Member 4)

These files are read by `agents/safety.py`. Editing them changes how the bot behaves — no coding needed.

| File | What it is |
| --- | --- |
| `crisis_keywords.txt` | One phrase per line. If a message contains any of them, the bot shows the crisis response. |
| `crisis_message.md` | The fixed, human-reviewed text shown on a crisis. The LLM never rewrites it. |
| `disclaimer.md` | Shown on every screen of the app. |
| `never_do.md` | Rules the answer and self-check agents must follow. |

## Principles

1. **Safety check runs first** on every message.
2. **Over-flag, never under-flag.** A false alarm is OK; a missed crisis is not.
3. **Include indirect phrases** ("I don't want to be here anymore", "everyone would be better off without me"), not just obvious words.
4. Every change to `crisis_message.md` is reviewed by Sarah before merging.

## Your tasks

- Week 1: grow `crisis_keywords.txt` to 40+ phrases; draft `crisis_message.md` and `disclaimer.md`.
- Week 2: finalize rules; write 15 crisis/red-team prompts in `eval/test_questions.csv` (category `crisis` or `redteam`).
- Week 3+: run them through the system, log misses, add keywords.
