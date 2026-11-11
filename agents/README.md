# agents/ — Safety-first RAG pipeline

| File | Responsibility |
| --- | --- |
| `safety.py` | Checks crisis phrases before routing or retrieval and loads the fixed response. |
| `pipeline.py` | Routes to one of five catalogs, retrieves source nodes, and prompts Anthropic when configured. |

`respond(message)` returns `route`, `answer`, and retrieved `sources`. Without an
Anthropic API key, it returns the retrieved passages directly. The Streamlit UI
keeps source nodes behind a **Sources** expander.

Run the local smoke test from the repository root:

```powershell
python agents\pipeline.py
```
