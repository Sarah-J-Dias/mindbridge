"""MindBridge dashboard (interface/streamlit.py).

Run from the repository root:  streamlit run interface/streamlit.py
"""

import html
import os
import random
import re
import sys
from pathlib import Path

# This file is named streamlit.py, so keep its own folder off sys.path.
# Otherwise `import streamlit` can pick up this file instead of the library.
_HERE = Path(__file__).resolve().parent
sys.path = [p for p in sys.path if Path(p or ".").resolve() != _HERE]

import streamlit as st  # noqa: E402

ROOT = _HERE.parent
sys.path.insert(0, str(ROOT))

from agents.pipeline import PipelineError, respond  # noqa: E402
from retrieval.build_index import (  # noqa: E402
    IndexNotBuiltError,
    search,
    warm_embedding_model,
)

DISCLAIMER = (ROOT / "safety" / "disclaimer.md").read_text(encoding="utf-8")

st.set_page_config(page_title="MindBridge", page_icon="🌿", layout="wide")

# ---------------------------------------------------------------------------
# Starry night theme
# ---------------------------------------------------------------------------
def _stars(count: int, seed: int, w: int = 2560, h: int = 1600) -> str:
    rnd = random.Random(seed)
    return ", ".join(
        f"{rnd.randint(0, w)}px {rnd.randint(0, h)}px rgba(255,255,255,{rnd.uniform(.35, .95):.2f})"
        for _ in range(count)
    )


THEME_CSS = """
<style>
.stApp {
  background: radial-gradient(ellipse at 20% 0%, #252d6b 0%, #0d1131 45%, #05060f 100%) !important;
}
[data-testid="stHeader"] {background: transparent !important;}
[data-testid="stSidebar"] {background: rgba(9, 11, 30, .82) !important;}

/* ---- sky ---- */
.sky {position: fixed; inset: 0; pointer-events: none; z-index: 0; overflow: hidden;}
.stars {position: absolute; top: 0; left: 0; background: transparent; border-radius: 50%;
        animation: twinkle 4s ease-in-out infinite alternate;}
.st1 {width: 1px; height: 1px; box-shadow: __S1__;}
.st2 {width: 2px; height: 2px; box-shadow: __S2__; animation-duration: 6s; animation-delay: -2s;}
.st3 {width: 3px; height: 3px; box-shadow: __S3__; animation-duration: 5s; animation-delay: -1s;}
@keyframes twinkle {0% {opacity: .35;} 100% {opacity: 1;}}

.shoot {position: absolute; width: 140px; height: 2px; opacity: 0;
        background: linear-gradient(90deg, rgba(255,255,255,0), #fff);
        border-radius: 2px; transform: rotate(35deg); animation: shoot 11s linear infinite;}
.sh1 {top: 8%;  left: 12%; animation-delay: 1s;}
.sh2 {top: 22%; left: 55%; animation-delay: 5s;  animation-duration: 14s;}
.sh3 {top: 4%;  left: 78%; animation-delay: 9s;  animation-duration: 17s;}
@keyframes shoot {
  0%   {opacity: 0; transform: rotate(35deg) translateX(0);}
  2%   {opacity: 1;}
  9%   {opacity: 0; transform: rotate(35deg) translateX(650px);}
  100% {opacity: 0; transform: rotate(35deg) translateX(650px);}
}

/* ---- header ---- */
.hero h1 {margin: 0; font-size: 2.6rem; font-weight: 800;
          background: linear-gradient(90deg, #b9c6ff, #9ff3e0);
          -webkit-background-clip: text; -webkit-text-fill-color: transparent;}
.hero p {margin: 4px 0 0; opacity: .75;}
.said {display: inline-block; margin: 18px 0 6px; padding: 8px 16px; border-radius: 999px;
       background: rgba(130, 150, 255, .16); border: 1px solid rgba(160, 175, 255, .25);}
.said b {opacity: .7; font-weight: 600; margin-right: 6px;}

/* ---- cards ---- */
div[data-testid="stVerticalBlockBorderWrapper"] {
  background: rgba(18, 22, 54, .62) !important;
  border: 1px solid rgba(160, 175, 255, .18) !important;
  border-radius: 18px !important;
  box-shadow: 0 8px 30px rgba(0, 0, 0, .35);
}
.card-title {font-size: 1.05rem; font-weight: 700; margin-bottom: 8px;}
.section {letter-spacing: .14em; text-transform: uppercase; font-size: .75rem;
          opacity: .65; margin: 26px 0 8px;}
.chip {display: inline-block; padding: 2px 11px; border-radius: 999px; font-size: .75rem;
       background: rgba(120, 140, 255, .2); color: #c9d2ff; margin: 0 6px 6px 0;}
.try {margin-top: 8px; padding: 10px 12px; border-radius: 12px; font-size: .92rem;
      background: rgba(90, 220, 190, .12); border-left: 3px solid #5adcbe;}
.quote {font-size: 1.15rem; font-style: italic; line-height: 1.5; margin: 6px 0 10px;}
.res {margin-bottom: 12px;}
.res .meta {font-size: .82rem; opacity: .75;}

/* ---- breathing orb ---- */
.breathe {display: flex; flex-direction: column; align-items: center;
          justify-content: center; height: 215px;}
.orb {width: 70px; height: 70px; border-radius: 50%;
      background: radial-gradient(circle at 35% 30%, #a8f7e6, #3aa68f);
      box-shadow: 0 0 34px rgba(90, 220, 190, .65);
      animation: orb 16s ease-in-out infinite;}
@keyframes orb {
  0% {transform: scale(1);} 25% {transform: scale(1.9);}
  50% {transform: scale(1.9);} 75% {transform: scale(1);} 100% {transform: scale(1);}
}
.phases {position: relative; width: 100%; height: 22px; margin-top: 62px; text-align: center;}
.phases span {position: absolute; left: 0; right: 0; opacity: 0; color: #bff5e8;
              animation: ph 16s infinite;}
.phases span:nth-child(2) {animation-delay: 4s;}
.phases span:nth-child(3) {animation-delay: 8s;}
.phases span:nth-child(4) {animation-delay: 12s;}
@keyframes ph {0% {opacity: 0;} 3% {opacity: 1;} 22% {opacity: 1;} 25% {opacity: 0;} 100% {opacity: 0;}}
</style>

<div class="sky">
  <div class="stars st1"></div><div class="stars st2"></div><div class="stars st3"></div>
  <span class="shoot sh1"></span><span class="shoot sh2"></span><span class="shoot sh3"></span>
</div>
"""

BREATHE_HTML = """
<div class="breathe">
  <div class="orb"></div>
  <div class="phases"><span>Breathe in</span><span>Hold</span><span>Breathe out</span><span>Hold</span></div>
</div>
"""


def inject_theme() -> None:
    css = (
        THEME_CSS.replace("__S1__", _stars(90, 1))
        .replace("__S2__", _stars(35, 2))
        .replace("__S3__", _stars(10, 3))
    )
    st.markdown(css, unsafe_allow_html=True)


def esc(text) -> str:
    return html.escape(str(text or ""))


def card(height: int | None = None):
    try:
        return st.container(border=True, height=height)
    except TypeError:  # older Streamlit without the height option
        return st.container(border=True)


inject_theme()

# ---------------------------------------------------------------------------
# Text helpers
# ---------------------------------------------------------------------------
# CSV rows are indexed as flat text like "Category: X Quote: Y".
FIELD_KEYS = (
    "category", "title", "description", "actionable_tip", "quote", "author",
    "text", "sentiment", "source", "name", "organization", "url", "phone",
    "hours", "location", "contact", "type",
)
_FIELD_RE = re.compile(r"\b(" + "|".join(FIELD_KEYS) + r"):\s*", re.IGNORECASE)


def parse_fields(text: str) -> dict:
    parts = _FIELD_RE.split(text or "")
    return {parts[i].lower(): parts[i + 1].strip() for i in range(1, len(parts) - 1, 2)}


def clean(text: str) -> str:
    text = re.sub(r"[*_`#>]+", "", text or "")
    return re.sub(r"\s+", " ", text).strip()


HEAVY_TERMS = ("suicide", "lost their lives", "death", "died")


def to_bullets(text: str, n: int = 3, max_chars: int = 130, skip_heavy: bool = False) -> list[str]:
    """Turn a paragraph into up to n short, complete-sentence bullets."""
    text = re.sub(r"^Here are the most relevant passages from the library:\s*", "", text or "")
    text = re.sub(r"\[\d+\]\s*", "", text)      # [1] source markers
    text = re.sub(r"\(\d+\)", "", text)         # (2) citations
    text = re.sub(r"[*_`#>]+", "", text)
    bullets = []
    for p in re.split(r"(?<=[.!?])\s+|\n+", text):
        p = re.sub(r"\s+([.,;])", r"\1", re.sub(r"\s+", " ", p)).strip(" -•")
        if len(p) < 20 or p[0].islower():       # skip fragments cut mid-sentence
            continue
        if skip_heavy and any(t in p.lower() for t in HEAVY_TERMS):
            continue
        if len(p) > max_chars:
            p = p[: max_chars - 1].rsplit(" ", 1)[0] + "…"
        bullets.append(p)
        if len(bullets) == n:
            break
    return bullets


# ---------------------------------------------------------------------------
# Retrieval for the dashboard cards
# ---------------------------------------------------------------------------
def safe_search(query: str, route: str) -> list[dict]:
    try:
        return search(query, route=route) or []
    except (IndexNotBuiltError, Exception):
        return []


def build_dashboard(message: str) -> dict:
    return {
        "tips": safe_search(f"breathing exercise calming relax {message}", "wellness")[:3],
        "quote": (safe_search(message, "quotes") or [None])[0],
        "resources": safe_search(message, "resources")[:3],
    }


@st.cache_resource(show_spinner="Loading the search model...")
def _preload_embedding_model():
    warm_embedding_model()
    return True


if os.getenv("MINDBRIDGE_PRELOAD_EMBEDDINGS", "").strip().lower() in {
    "1", "true", "yes", "on"
}:
    _preload_embedding_model()

# ---------------------------------------------------------------------------
# Sidebar: disclaimer + crisis lines on every screen
# ---------------------------------------------------------------------------
with st.sidebar:
    st.header("MindBridge")
    st.info(DISCLAIMER)
    st.error(
        "**In crisis?**\n\n"
        "- Call or text **988**\n"
        "- Emergency: **911**\n"
        "- UCLA CAPS: see counseling.ucla.edu for the current 24/7 line"
    )
    st.caption("Privacy: nothing is saved after you close this tab.")
    if st.button("Start new session", use_container_width=True):
        st.session_state.history = []
        st.rerun()


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------
def show_sources(sources):
    with st.expander(f"Sources ({len(sources)})"):
        for index, source in enumerate(sources, 1):
            title = source.get("title") or "Source"
            url = source.get("url")
            st.markdown(f"{index}. [{title}]({url})" if url else f"{index}. **{title}**")
            if source.get("organization"):
                st.caption(source["organization"])


def render_dashboard(entry: dict) -> None:
    result, dash = entry["result"], entry["dashboard"]

    # ---- Row 1: breathe | quote | resources ----
    st.markdown('<div class="section">Take a moment</div>', unsafe_allow_html=True)
    c_breathe, c_quote, c_res = st.columns(3)

    with c_breathe:
        with card(330):
            st.markdown('<div class="card-title">🫁 Breathe</div>', unsafe_allow_html=True)
            st.markdown(BREATHE_HTML, unsafe_allow_html=True)
            st.caption("Box breathing: 4 seconds each step. Repeat 4 times.")

    with c_quote:
        with card(330):
            st.markdown('<div class="card-title">💬 A thought for you</div>', unsafe_allow_html=True)
            q = dash["quote"]
            if q:
                f = parse_fields(q.get("text", ""))
                body = f.get("quote") or f.get("text") or clean(q.get("text", ""))
                st.markdown(f'<div class="quote">“{esc(clean(body)[:280])}”</div>', unsafe_allow_html=True)
                label = f.get("author") or f.get("category")
                if label:
                    st.markdown(f'<span class="chip">{esc(clean(label))}</span>', unsafe_allow_html=True)
            else:
                st.caption("No quote available.")

    with c_res:
        with card(330):
            st.markdown('<div class="card-title">📍 Support at UCLA</div>', unsafe_allow_html=True)
            if not dash["resources"]:
                st.caption("None matched. See crisis lines in the sidebar.")
            for r in dash["resources"]:
                f = parse_fields(r.get("text", ""))
                title = clean(f.get("name") or f.get("title") or r.get("title") or "Resource")
                url = r.get("url") or f.get("url")
                name = f'<a href="{esc(url)}" target="_blank">{esc(title)}</a>' if url else esc(title)
                meta = []
                if f.get("type"):
                    meta.append(f'<span class="chip">{esc(clean(f["type"]))}</span>')
                if f.get("phone"):
                    meta.append(f'<span class="meta">📞 {esc(f["phone"])}</span>')
                st.markdown(
                    f'<div class="res"><b>{name}</b><br>{"".join(meta)}</div>',
                    unsafe_allow_html=True,
                )

    # ---- Row 2: what you can do ----
    st.markdown('<div class="section">What you can do right now</div>', unsafe_allow_html=True)
    tips = dash["tips"]
    if tips:
        cols = st.columns(len(tips))
        for col, tip in zip(cols, tips):
            with col:
                with card(300):
                    f = parse_fields(tip.get("text", ""))
                    st.markdown(
                        f'<div class="card-title">{esc(clean(f.get("title") or tip.get("title") or "Tip"))}</div>',
                        unsafe_allow_html=True,
                    )
                    if f.get("category"):
                        st.markdown(f'<span class="chip">{esc(f["category"])}</span>', unsafe_allow_html=True)
                    if f.get("description"):
                        st.write(clean(f["description"]))
                    if f.get("actionable_tip"):
                        st.markdown(
                            f'<div class="try"><b>Try:</b> {esc(clean(f["actionable_tip"]))}</div>',
                            unsafe_allow_html=True,
                        )
                    if not f:
                        for b in to_bullets(tip.get("text", ""), 3, 110):
                            st.markdown(f"- {b}")
    else:
        st.caption("No tips matched this time.")

    # ---- Row 3: key points ----
    st.markdown('<div class="section">Key points</div>', unsafe_allow_html=True)
    with card():
        points = to_bullets(result["answer"], n=3, max_chars=150, skip_heavy=True)
        if points:
            for b in points:
                st.markdown(f"- {b}")
        else:
            st.caption("No short summary available. Open the full answer below.")
        if not os.getenv("ANTHROPIC_API_KEY", "").strip():
            st.caption(
                "Showing excerpts from the library. Add ANTHROPIC_API_KEY to .env "
                "for a short written summary."
            )

    with st.expander("Read the full answer"):
        st.markdown(result["answer"])
    if result.get("sources"):
        show_sources(result["sources"])


# ---------------------------------------------------------------------------
# Page
# ---------------------------------------------------------------------------
st.markdown(
    '<div class="hero"><h1>🌿 MindBridge</h1>'
    "<p>Tell me how you're feeling. You'll get exercises, a quote, and UCLA resources.</p></div>",
    unsafe_allow_html=True,
)
st.caption("⚠️ MindBridge is not a psychiatrist or therapist and is not a replacement for professional care.")

# History is held only in this browser session; it is not persisted.
if "history" not in st.session_state:
    st.session_state.history = []

prompt = st.chat_input("How are you feeling today?")

if prompt:
    try:
        with st.spinner("Putting your dashboard together..."):
            result = respond(prompt)
            if result["route"] == "crisis":
                entry = {"prompt": prompt, "crisis": True, "result": result}
            else:
                entry = {
                    "prompt": prompt,
                    "result": result,
                    "dashboard": build_dashboard(prompt),
                }
        st.session_state.history.append(entry)
    except PipelineError as error:
        st.error(f"MindBridge could not answer this question. {error}")

if not st.session_state.history:
    st.info("✨ Type how you're feeling below to build your dashboard.")
else:
    latest = st.session_state.history[-1]
    st.markdown(
        f'<div class="said"><b>You said</b> {esc(latest["prompt"])}</div>',
        unsafe_allow_html=True,
    )
    if latest.get("crisis"):
        # Fixed message only: no retrieval, no dashboard
        st.error(latest["result"]["answer"])
    else:
        render_dashboard(latest)

    earlier = st.session_state.history[:-1]
    if earlier:
        with st.expander(f"Earlier in this session ({len(earlier)})"):
            for e in reversed(earlier):
                st.markdown(f"**{e['prompt']}**")
                if e.get("crisis"):
                    st.caption("Crisis resources were shown.")
                else:
                    for b in to_bullets(e["result"]["answer"], n=2, skip_heavy=True):
                        st.markdown(f"- {b}")