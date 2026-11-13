"""MindBridge chat + dashboard.

Save as interface/streamlit_app.py (NOT streamlit.py, which shadows the library).
Run from the repo root:  streamlit run interface/streamlit_app.py
"""
import os
import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from agents.pipeline import PipelineError, respond  # noqa: E402
from retrieval.build_index import IndexNotBuiltError, search, warm_embedding_model  # noqa: E402

DISCLAIMER = (ROOT / "safety" / "disclaimer.md").read_text(encoding="utf-8")

DEFAULT_EXERCISE = (
    "**Box breathing:** breathe in for 4 seconds, hold for 4, breathe out for 4, "
    "hold for 4. Repeat 4 times."
)

st.set_page_config(page_title="MindBridge", page_icon="🌿", layout="wide")


# ---------------------------------------------------------------------------
# Sidebar: disclaimer + crisis lines on every screen
# ---------------------------------------------------------------------------
with st.sidebar:
    st.header("MindBridge")
    st.info(DISCLAIMER)
    st.error(
        "**In crisis?**\n\n"
        "- Call or text **988**\n"
        "- UCLA CAPS: check counseling.ucla.edu for the current 24/7 line\n"
        "- Emergency: **911**"
    )
    st.caption("Privacy: this chat exists only in this browser tab. Nothing is saved.")
    if st.button("Start new session", use_container_width=True):
        st.session_state.messages = []
        st.rerun()


@st.cache_resource(show_spinner="Loading the search model...")
def _preload_embedding_model():
    warm_embedding_model()
    return True


if os.getenv("MINDBRIDGE_PRELOAD_EMBEDDINGS", "").strip().lower() in {"1", "true", "yes", "on"}:
    _preload_embedding_model()


# ---------------------------------------------------------------------------
# Dashboard data: pull extra cards from the CSV-backed catalogs
# ---------------------------------------------------------------------------
def _safe_search(query: str, route: str) -> list[dict]:
    try:
        return search(query, route=route) or []
    except IndexNotBuiltError:
        return []
    except Exception:
        return []


def build_dashboard(message: str) -> dict:
    return {
        "exercises": _safe_search(f"breathing exercise calming {message}", "wellness")[:3],
        "quote": (_safe_search(message, "quotes") or [None])[0],
        "resources": _safe_search(message, "resources")[:3],
    }


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------
def show_sources(sources):
    with st.expander(f"Sources ({len(sources)})"):
        for i, s in enumerate(sources, 1):
            title = s.get("title") or "Source"
            url = s.get("url")
            st.markdown(f"{i}. [{title}]({url})" if url else f"{i}. **{title}**")
            if s.get("organization"):
                st.caption(s["organization"])
            st.text(s.get("text", ""))


def show_dashboard(d: dict):
    tab_ex, tab_quote, tab_res = st.tabs(
        ["Breathing & what you can do", "Quote for you", "UCLA resources"]
    )
    with tab_ex:
        if d["exercises"]:
            cols = st.columns(len(d["exercises"]))
            for col, ex in zip(cols, d["exercises"]):
                with col.container(border=True):
                    st.markdown(f"**{ex.get('title') or 'Tip'}**")
                    st.write(ex.get("text", ""))
        else:
            st.markdown(DEFAULT_EXERCISE)
    with tab_quote:
        q = d["quote"]
        if q:
            st.markdown(f"> *{q.get('text', '')}*")
            attribution = q.get("title") or q.get("organization")
            if attribution:
                st.caption(f"— {attribution}")
        else:
            st.caption("No quote available.")
    with tab_res:
        if not d["resources"]:
            st.caption("No resources matched. See the sidebar for crisis lines.")
        for r in d["resources"]:
            with st.container(border=True):
                title = r.get("title") or "Resource"
                url = r.get("url")
                st.markdown(f"**[{title}]({url})**" if url else f"**{title}**")
                st.write(r.get("text", ""))


# ---------------------------------------------------------------------------
# Chat
# ---------------------------------------------------------------------------
st.title("🌿 MindBridge")
st.caption("Tell me what's on your mind. Answers come from trusted public sources.")
st.warning("MindBridge is not a psychiatrist or therapist and is not a replacement for professional care.")

if "messages" not in st.session_state:
    st.session_state.messages = []

for m in st.session_state.messages:
    with st.chat_message(m["role"]):
        if m.get("crisis"):
            st.error(m["content"])
        else:
            st.markdown(m["content"])
        if m.get("dashboard"):
            show_dashboard(m["dashboard"])
        if m.get("sources"):
            show_sources(m["sources"])

if prompt := st.chat_input("How are you feeling today?"):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        try:
            with st.spinner("Thinking..."):
                result = respond(prompt)
        except PipelineError as error:
            answer = f"MindBridge could not answer this question. {error}"
            st.error(answer)
            st.session_state.messages.append({"role": "assistant", "content": answer})
        else:
            if result["route"] == "crisis":
                # Fixed message only: no retrieval, no dashboard
                st.error(result["answer"])
                st.session_state.messages.append(
                    {"role": "assistant", "content": result["answer"], "crisis": True}
                )
            else:
                dashboard = build_dashboard(prompt)
                st.markdown(result["answer"])
                show_dashboard(dashboard)
                if result["sources"]:
                    show_sources(result["sources"])
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": result["answer"],
                    "sources": result["sources"],
                    "dashboard": dashboard,
                })