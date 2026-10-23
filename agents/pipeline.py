"""MindBridge agent pipeline (Sarah owns this file).

    message -> Safety -> Router -> {Retrieval -> Answer -> Self-check | Resource tool | Out-of-scope}

The app calls `respond(message)` and gets back a dict:
    {"route": str, "answer": str, "sources": [{"title", "url"}]}

Week 1 status: safety + a placeholder router work end to end so the UI can be
built in parallel. Replace each TODO in Weeks 2-3.
"""
import csv
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from agents.safety import is_crisis, load_crisis_message  # noqa: E402

RESOURCES_CSV = ROOT / "data" / "resources.csv"
RESOURCE_WORDS = ("talk to someone", "counsel", "therap", "hotline", "where can i", "help line", "support group")


def route(message):
    """Pick 'resource', 'info' or 'other'.
    TODO (Week 2): replace this keyword placeholder with an LLM router."""
    msg = message.lower()
    if any(w in msg for w in RESOURCE_WORDS):
        return "resource"
    return "info"


def resource_tool(message):
    with open(RESOURCES_CSV, newline="", encoding="utf-8") as f:
        rows = [r for r in csv.DictReader(f) if "TODO" not in r.get("phone", "")]
    lines = [f"- **{r['name']}** ({r['type']}): {r['phone'] or r['url']} — {r['hours']}" for r in rows]
    return {"answer": "Here are some places you can reach out to:\n\n" + "\n".join(lines),
            "sources": [{"title": r["name"], "url": r["url"]} for r in rows if r["url"]]}


def answer_from_library(message):
    """Retrieval -> Answer -> Self-check.
    TODO (Week 2): retrieval.build_index.search(message), then prompt the LLM
    to answer ONLY from those chunks and cite them.
    TODO (Week 3): self-check that the answer is grounded and follows safety/never_do.md."""
    if not os.getenv("ANTHROPIC_API_KEY"):
        return {"answer": "(Placeholder) The library answer will appear here once retrieval is connected.",
                "sources": []}
    return {"answer": "(Placeholder) LLM answer not wired up yet.", "sources": []}


def respond(message):
    if is_crisis(message):
        return {"route": "crisis", "answer": load_crisis_message(), "sources": []}
    r = route(message)
    if r == "resource":
        return {"route": r, **resource_tool(message)}
    if r == "other":
        return {"route": r, "answer": "I can only help with general mental health information. "
                                      "For anything else, please try another resource.", "sources": []}
    return {"route": r, **answer_from_library(message)}


if __name__ == "__main__":
    for q in ["What's the difference between stress and anxiety?",
              "Where can I talk to someone on campus?",
              "I don't want to be here anymore"]:
        out = respond(q)
        print(f"\nQ: {q}\n-> route={out['route']}\n{out['answer'][:200]}")
