# retrieval/ — Vector database (Member 3)

`build_index.py` reads every `.txt` file in `data/raw/`, removes website clutter (menus, .gov banners), splits it into chunks on sentence boundaries, turns each chunk into an embedding, and saves them in a local Chroma database (`chroma_db/`).

The raw files are one long line each, so the chunker splits on sentences rather than blank lines. Chunks stay under ~900 characters because the embedding model (`all-MiniLM-L6-v2`) only reads the first ~256 tokens of each chunk. If you see new clutter in search results, add a pattern to `BOILERPLATE_PATTERNS`.

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
