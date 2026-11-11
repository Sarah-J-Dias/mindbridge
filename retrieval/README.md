# retrieval/ — Vector databases

`build_index.py` converts the curated article catalogs and three CSV catalogs
into five local Chroma collections in `chroma_db/`:

| Route | Catalog |
| --- | --- |
| `generalinfo` | `data/Generalinfo.csv` and matching files in `data/raw/` |
| `conditions_and_signs` | `data/conditions_and_signs.csv` and matching raw files |
| `resources` | `data/resources.csv` |
| `quotes` | `data/quotes.csv` |
| `wellness` | `data/wellness.csv` |

Build or rebuild all collections from the repository root:

```powershell
python retrieval\build_index.py
```

Test a route after building:

```powershell
python retrieval\build_index.py --query "signs of burnout" --route conditions_and_signs
python retrieval\build_index.py --query "campus counseling" --route resources
```

The first build downloads the `all-MiniLM-L6-v2` embedding model if it is not
already cached. `chroma_db/` is local and can be rebuilt from the catalogs.

- **Chunk** — a bounded passage from an article; CSV entries are indexed as individual records.
- **Embedding** — numbers representing text meaning, used to find similar passages.
- **Vector database** — stores embeddings and returns the passages closest to a query.
