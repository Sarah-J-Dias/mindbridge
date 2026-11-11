"""MindBridge chat screen.

Run with ``streamlit run app/app.py`` from the repository root.
"""

import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from agents.pipeline import PipelineError, respond  # noqa: E402

DISCLAIMER = (ROOT / "safety" / "disclaimer.md").read_text(encoding="utf-8")

st.set_page_config(page_title="MindBridge", page_icon="💬")
st.title("MindBridge")
st.caption("Ask a general question about mental health. Answers come from trusted public sources.")

with st.sidebar:
    st.subheader("About")
    st.info(DISCLAIMER)
    st.markdown("**In crisis?** Call or text **988**, or call **911**.")


def show_sources(sources):
    with st.expander(f"Sources ({len(sources)})"):
        for index, source in enumerate(sources, 1):
            title = source.get("title") or "Source"
            url = source.get("url")
            if url:
                st.markdown(f"{index}. [{title}]({url})")
            else:
                st.markdown(f"{index}. **{title}**")
            organization = source.get("organization")
            if organization:
                st.caption(organization)
            st.text(source.get("text", ""))


# Chat history is held only in this browser session; it is not persisted.
if "messages" not in st.session_state:
    st.session_state.messages = []

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        if message["role"] == "assistant" and message.get("sources"):
            show_sources(message["sources"])

if prompt := st.chat_input("Type your question..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    try:
        result = respond(prompt)
    except PipelineError as error:
        answer = f"MindBridge could not answer this question. {error}"
        with st.chat_message("assistant"):
            st.error(answer)
        st.session_state.messages.append({"role": "assistant", "content": answer})
    else:
        with st.chat_message("assistant"):
            if result["route"] == "crisis":
                st.error(result["answer"])
            else:
                st.markdown(result["answer"])
            if result["sources"]:
                show_sources(result["sources"])
        st.session_state.messages.append({
            "role": "assistant",
            "content": result["answer"],
            "sources": result["sources"],
        })
