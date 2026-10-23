"""MindBridge chat screen (Member 6).

Run:  streamlit run app/app.py

Week 1: get this running and change the look.
Week 2: add the crisis banner styling and polish the sources area.
Week 4: deploy to Streamlit Community Cloud.
"""
import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from agents.pipeline import respond  # noqa: E402

DISCLAIMER = (ROOT / "safety" / "disclaimer.md").read_text(encoding="utf-8")

st.set_page_config(page_title="MindBridge", page_icon="💬")
st.title("MindBridge")
st.caption("Ask a general question about mental health. Answers come from trusted public sources.")

with st.sidebar:
    st.subheader("About")
    st.info(DISCLAIMER)
    st.markdown("**In crisis?** Call or text **988**, or call **911**.")

# Chat history lives only in this browser session — nothing is saved.
if "messages" not in st.session_state:
    st.session_state.messages = []

for m in st.session_state.messages:
    with st.chat_message(m["role"]):
        st.markdown(m["content"])

if prompt := st.chat_input("Type your question..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    result = respond(prompt)
    with st.chat_message("assistant"):
        if result["route"] == "crisis":
            st.error(result["answer"])
        else:
            st.markdown(result["answer"])
        if result["sources"]:
            with st.expander("Sources"):
                for s in result["sources"]:
                    st.markdown(f"- [{s['title']}]({s['url']})" if s.get("url") else f"- {s['title']}")
    st.session_state.messages.append({"role": "assistant", "content": result["answer"]})
