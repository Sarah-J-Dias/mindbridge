# MindBridge — Agentic RAG for Mental Health

> **Educational prototype. Not a substitute for professional care.**
> If you or someone you know is in crisis, call or text **988** (Suicide & Crisis Lifeline) or call **911** for immediate danger.

MindBridge answers general mental health questions using only a curated library of trusted public sources, cites every answer, points students to real support resources, and **checks for crisis language before anything else runs**.

Showcase: **Tuesday, December 1, 2026** · NSDC Healthcare AI Project

---

## How it works

```
Student message
      │
      ▼
 Safety agent ──crisis──► Fixed crisis response (988, 911, campus counseling)
      │ safe
      ▼
 Router agent ──resource──► Resource tool (data/resources.csv)
      │        ──other────► Polite out-of-scope reply
      │ info
      ▼
 Retrieval agent (Chroma) → Answer agent (cites sources) → Self-check agent
      │
      ▼
 Reply in chat (answer + sources + disclaimer)
```

## Repo map — find your folder

| Folder | Owner | What lives here |
| --- | --- | --- |
| `data/` | Members 1 + 2 | Source documents, `sources.csv`, `resources.csv` |
| `retrieval/` | Member 3 | Script that chunks docs and builds the Chroma database |
| `agents/` | Sarah | Safety, router, answer and self-check agents |
| `safety/` | Member 4 | Crisis keywords, crisis message, disclaimer, "never do" rules |
| `eval/` | Member 5 | Test questions and the scorecard |
| `app/` | Member 6 | Streamlit chat interface |
| `showcase/` | Member 7 | Slides, poster, demo video, script |

## Quick start (first time)

**Option A — Google Colab (easiest, nothing to install):** open a new Colab notebook and run
```
!git clone https://github.com/<OWNER>/mindbridge.git
%cd mindbridge
!pip install -r requirements.txt
```

**Option B — your laptop:**
```bash
git clone https://github.com/<OWNER>/mindbridge.git
cd mindbridge
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env               # Sarah shares the API key privately — never commit it
```

Check that it works:
```bash
python agents/safety.py            # runs the crisis-check self-test
streamlit run app/app.py           # opens the chat screen in your browser
```

## How we work

- Read [CONTRIBUTING.md](CONTRIBUTING.md) before your first change — it walks through branches and pull requests step by step.
- One task = one branch = one pull request. Sarah reviews every merge.
- **Definition of done:** it runs on someone else's machine, it's merged, and it has a 3-line note on how to use it.
- Stuck for more than a day? Post in the team chat with "Done / Doing / Stuck".

## Safety rules (non-negotiable)

1. The safety check always runs first.
2. Over-flag, never under-flag.
3. Answers come only from our curated library, with citations.
4. No diagnosis, no medication advice.
5. No real personal data — test questions are written by the team, and chats are not saved.

Full rules: [`safety/README.md`](safety/README.md)

## Team

| Role | Name |
| --- | --- |
| Project lead + Agent engineer | Sarah |
| Knowledge Base Curator A | Member 1 |
| Knowledge Base Curator B | Member 2 |
| Retrieval Assistant | Member 3 |
| Safety & Ethics Lead | Member 4 |
| Evaluation Lead | Member 5 |
| Interface Builder | Member 6 |
| Showcase & Docs Lead | Member 7 |
