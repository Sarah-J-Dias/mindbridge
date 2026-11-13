"""
MindBridge Streamlit app.

Put this at interface/streamlit_app.py (rename the old interface/streamlit.py,
a file named streamlit.py can shadow the real package).
Run from the repo root:  streamlit run interface/streamlit_app.py
"""
import sys
from pathlib import Path

import streamlit as st

# Make `agents` and `retrieval` importable when running from anywhere
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
DISCLAIMER = (
    "MindBridge is an educational tool. It is **not** a psychiatrist, "
    "therapist, or replacement for professional care."
)

CRISIS_LINES = """
**If you are in crisis or need to talk to someone now:**
- **988** Suicide & Crisis Lifeline (call or text, 24/7)
- **UCLA CAPS:** 310-825-0768 (24/7 counseling line)
- **Emergency:** 911
"""

CRISIS_MESSAGE = (
    "I'm really glad you reached out, and I'm concerned about what you're "
    "going through. I can't help with this in a chat, but people can right now. "
    "Please call or text **988**, or call UCLA CAPS at **310-825-0768** (24/7). "
    "If you are in immediate danger, call **911**."
)

# Used only if the pipeline returns no exercises
DEFAULT_EXERCISES = [
    {
        "title": "Box breathing (4-4-4-4)",
        "steps": [
            "Breathe in through your nose for 4 seconds",
            "Hold for 4 seconds",
            "Breathe out slowly for 4 seconds",
            "Hold for 4 seconds, then repeat 4 times",
        ],
    },
    {
        "title": "4-7-8 breathing",
        "steps": [
            "Breathe in quietly through your nose for 4 seconds",
            "Hold your breath for 7 seconds",
            "Exhale through your mouth for 8 seconds",
            "Repeat 3 to 4 times",
        ],
    },
]

# ---------------------------------------------------------------------------
# Pipeline adapter. This is the ONLY part that touches your backend.
# ---------------------------------------------------------------------------
# Expected return shape of run_pipeline():
# {
#   "reply": str,
#   "sentiment": str,
#   "exercises": [{"title": str, "steps": [str, ...]}],
#   "quote": {"text": str, "author": str} | None,
#   "resources": [{"name": str, "description": str, "url": str}],
#   "sources": [str],   # from .source_nodes, for debugging
# }

try:
    # TODO: adjust these names to match agents/pipeline.py and agents/safety.py
    from agents.pipeline import run_pipeline as _real_pipeline  # type: ignore
    from agents.safety import is_crisis as _real_is_crisis  # type: ignore

    BACKEND_READY = True
except Exception:  # missing module or different function names
    BACKEND_READY = False

_FALLBACK_CRISIS_WORDS = [
    "kill myself", "suicide", "end my life", "want to die",
    "hurt myself", "self harm", "self-harm", "don't want to live",
]


def check_crisis(message: str) -> bool:
    if BACKEND_READY:
        return bool(_real_is_crisis(message))
    text = message.lower()
    return any(w in text for w in _FALLBACK_CRISIS_WORDS)


def run_pipeline(message: str, history: list[dict]) -> dict:
    if BACKEND_READY:
        return _real_pipeline(message, history)  # TODO: map output to the shape above

    # Demo stub so the UI works before the backend is wired in
    return {
        "reply": (
            "(Demo mode: backend not connected.) That sounds like a lot to "
            "carry. Here are a few things that might help right now."
        ),
        "sentiment": "overwhelmed",
        "exercises": DEFAULT_EXERCISES,
        "quote": {
            "text": "You don't have to see the whole staircase, just take the first step.",
            "author": "Martin Luther King Jr.",
        },
        "resources": [
            {
                "name": "UCLA CAPS",
                "description": "Free, confidential counseling for UCLA students.",
                "url": "https://www.counseling.ucla.edu/",
            }
        ],
        "sources": [],
    }


# ---------------------------------------------------------------------------
# UI helpers
# ---------------------------------------------------------------------------
def render_cards(result: dict) -> None:
    """Dashboard under an assistant reply."""
    tab_ex, tab_quote, tab_res = st.tabs(
        ["Breathing & exercises", "Quote", "UCLA resources"]
    )

    with tab_ex:
        exercises = result.get("exercises") or DEFAULT_EXERCISES
        cols = st.columns(len(exercises))
        for col, ex in zip(cols, exercises):
            with col.container(border=True):
                st.markdown(f"**{ex['title']}**")
                for i, step in enumerate(ex["steps"], 1):
                    st.markdown(f"{i}. {step}")

    with tab_quote:
        quote = result.get("quote")
        if quote:
            st.markdown(f"> *{quote['text']}*")
            if quote.get("author"):
                st.caption(f"— {quote['author']}")
        else:
            st.caption("No quote for this one.")

    with tab_res:
        resources = result.get("resources") or []
        if not resources:
            st.caption("No specific resources matched. See the sidebar for crisis lines.")
        for r in resources:
            with st.container(border=True):
                name = f"[{r['name']}]({r['url']})" if r.get("url") else r["name"]
                st.markdown(f"**{name}**")
                if r.get("description"):
                    st.write(r["description"])

    if result.get("sources"):
        with st.expander("Sources (debug)"):
            for s in result["sources"]:
                st.write(s)


def render_sidebar() -> None:
    with st.sidebar:
        st.header("MindBridge")
        st.warning(DISCLAIMER)
        st.error(CRISIS_LINES)
        st.caption(
            "Privacy: this chat lives only in this browser tab. Nothing is "
            "saved after you close it."
        )
        if st.button("Start new session", use_container_width=True):
            st.session_state.messages = []
            st.rerun()


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------
st.set_page_config(page_title="MindBridge", page_icon="🌿", layout="wide")
render_sidebar()

st.title("🌿 MindBridge")
st.caption("Tell me what's on your mind. I'll share some info, exercises, and UCLA resources.")
st.info(DISCLAIMER + " Crisis lines are always in the sidebar.")

if not BACKEND_READY:
    st.caption("⚠️ Running in demo mode (agents.pipeline not connected).")

if "messages" not in st.session_state:
    st.session_state.messages = []

# Replay history
for m in st.session_state.messages:
    with st.chat_message(m["role"]):
        st.markdown(m["content"])
        if m.get("result"):
            render_cards(m["result"])

# New input
if prompt := st.chat_input("How are you feeling today?"):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        if check_crisis(prompt):
            # No retrieval, no generation: fixed message only
            st.error(CRISIS_MESSAGE)
            st.session_state.messages.append(
                {"role": "assistant", "content": CRISIS_MESSAGE}
            )
        else:
            with st.spinner("Thinking..."):
                history = [
                    {"role": m["role"], "content": m["content"]}
                    for m in st.session_state.messages[:-1]
                ]
                result = run_pipeline(prompt, history)
            st.markdown(result["reply"])
            render_cards(result)
            st.session_state.messages.append(
                {"role": "assistant", "content": result["reply"], "result": result}
            )