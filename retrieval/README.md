# retrieval/ — Vector database (Member 3)

`build_index.py` reads every `.txt` file in `data/raw/`, splits it into chunks, turns each chunk into an embedding, and saves them in a local Chroma database (`chroma_db/`).

## Run it

```bash
python retrieval/build_index.py                     # build the database
python retrieval/build_index.py --query "signs of burnout"   # test a search
```

## Words to know

- **Chunk** — a short passage (a few paragraphs) cut from a document. We search chunks, not whole documents.
- **Embedding** — a list of numbers that captures a chunk's meaning, so similar ideas end up close together.
- **Vector database** — stores the embeddings and finds the chunks closest to a question.

## Your Week 1–3 tasks

- Week 1: run the script on a couple of test files; explain chunks and embeddings in 3 sentences.
- Week 2: load all docs; run 10 test searches; note which return useful chunks in `retrieval/notes.md`.
- Week 3: try `--chunk-size 500` vs `--chunk-size 1000` and compare with Member 5.
