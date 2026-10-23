"""Safety agent — runs FIRST on every message.

Step 1 (now): keyword check against safety/crisis_keywords.txt.
Step 2 (Week 2, Sarah): add an LLM classifier; escalate if EITHER check fires.

Run `python agents/safety.py` for a quick self-test.
"""
import re
from pathlib import Path

SAFETY_DIR = Path(__file__).resolve().parent.parent / "safety"


def load_keywords():
    lines = (SAFETY_DIR / "crisis_keywords.txt").read_text(encoding="utf-8").splitlines()
    return [l.strip().lower() for l in lines if l.strip() and not l.startswith("#")]


def load_crisis_message():
    return (SAFETY_DIR / "crisis_message.md").read_text(encoding="utf-8")


def _normalize(text):
    text = text.lower().replace("’", "'")  # curly apostrophes -> straight
    return re.sub(r"\s+", " ", text)


def keyword_check(message):
    """Return the list of crisis phrases found in the message (empty = none)."""
    msg = _normalize(message)
    return [kw for kw in load_keywords() if _normalize(kw) in msg]


def llm_check(message):
    """TODO (Week 2, Sarah): ask the LLM whether the message signals risk of harm.
    Return True if it does. Until then, return False so only keywords decide."""
    return False


def is_crisis(message):
    """True if EITHER check fires. Over-flag, never under-flag."""
    return bool(keyword_check(message)) or llm_check(message)


if __name__ == "__main__":
    tests = [
        ("What are signs of burnout?", False),
        ("How does CBT work?", False),
        ("I want to die", True),
        ("Honestly everyone would be better off without me", True),
        ("I don’t want to be here anymore", True),
    ]
    failures = 0
    for text, expected in tests:
        got = is_crisis(text)
        status = "ok  " if got == expected else "FAIL"
        failures += got != expected
        print(f"[{status}] crisis={got!s:5}  {text}")
    print("All tests passed." if not failures else f"{failures} test(s) failed.")
