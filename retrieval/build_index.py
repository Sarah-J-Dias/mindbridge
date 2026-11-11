"""Build and query the MindBridge vector databases.

Run ``python retrieval/build_index.py`` to index all five source catalogs, or
pass ``--query`` and ``--route`` to test a particular catalog.
"""

from __future__ import annotations

import argparse
import csv
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
DB_DIR = ROOT / "chroma_db"
COLLECTION_PREFIX = "mindbridge_"
ARTICLE_CATALOGS = {
    "generalinfo": DATA_DIR / "Generalinfo.csv",
    "conditions_and_signs": DATA_DIR / "conditions_and_signs.csv",
}
CSV_CATALOGS = {
    "resources": DATA_DIR / "resources.csv",
    "quotes": DATA_DIR / "quotes.csv",
    "wellness": DATA_DIR / "wellness.csv",
}
ROUTES = (*ARTICLE_CATALOGS, *CSV_CATALOGS)
EMBED_MODEL = "all-MiniLM-L6-v2"


class IndexNotBuiltError(RuntimeError):
    """Raised when a requested route has not been indexed yet."""


def collection_name(route: str) -> str:
    if route not in ROUTES:
        raise ValueError(f"Unknown source route: {route}")
    return f"{COLLECTION_PREFIX}{route}"


def chunk_text(text: str, chunk_size: int = 800, overlap: int = 100) -> list[str]:
    """Split text into bounded, overlapping chunks, preferring paragraph breaks."""
    if chunk_size < 1:
        raise ValueError("chunk_size must be greater than zero")
    if overlap < 0 or overlap >= chunk_size:
        raise ValueError("overlap must be between zero and chunk_size - 1")

    text = "\n\n".join(part.strip() for part in text.splitlines() if part.strip())
    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = min(start + chunk_size, len(text))
        if end < len(text):
            boundary = text.rfind("\n\n", start + chunk_size // 2, end)
            if boundary <= start:
                boundary = text.rfind(" ", start, end)
            if boundary > start:
                end = boundary

        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= len(text):
            break
        start = max(start + 1, end - overlap)
    return chunks


def _read_catalog_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8-sig") as file:
        return [
            {key: (value or "").strip() for key, value in row.items() if key}
            for row in csv.DictReader(file)
        ]


def _article_records(route: str, path: Path, chunk_size: int) -> list[dict[str, str]]:
    records: list[dict[str, str]] = []
    for row in _read_catalog_rows(path):
        doc_id = row.get("doc_id", "")
        raw_path = RAW_DIR / f"{doc_id}.txt"
        if not doc_id or not raw_path.is_file():
            continue
        text = raw_path.read_text(encoding="utf-8")
        for index, chunk in enumerate(chunk_text(text, chunk_size)):
            records.append({
                "id": f"{route}__{doc_id}__{index}",
                "text": chunk,
                "title": row.get("title") or doc_id,
                "url": row.get("url", ""),
                "organization": row.get("organization", ""),
                "category": row.get("category", ""),
            })
    return records


def _csv_records(route: str, path: Path) -> list[dict[str, str]]:
    rows = _read_catalog_rows(path)
    records: list[dict[str, str]] = []
    seen_resources: set[str] = set()

    for index, row in enumerate(rows):
        if any("todo" in value.lower() for value in row.values()):
            continue

        if route == "resources":
            title = row.get("name", "")
            if not title or title.casefold() in seen_resources:
                continue
            seen_resources.add(title.casefold())
            fields = (
                ("Type", row.get("type")),
                ("Phone", row.get("phone")),
                ("Text", row.get("text")),
                ("Hours", row.get("hours")),
                ("Who it serves", row.get("who_it_serves")),
                ("Scope", row.get("scope")),
            )
            text = "\n".join(f"{key}: {value}" for key, value in fields if value)
            category = row.get("type", "")
            organization = "MindBridge resources catalog"
        elif route == "quotes":
            title = row.get("Category") or "Quote"
            quote = row.get("Quote", "")
            if not quote:
                continue
            text = f"Category: {title}\nQuote: {quote}"
            quote_url = row.get("Quote-url", "")
            url = (
                f"https://www.passiton.com{quote_url}"
                if quote_url.startswith("/")
                else quote_url
            )
            category = title
            organization = "Pass It On"
        else:
            title = row.get("title", "")
            if not title:
                continue
            text = "\n".join(
                f"{key}: {row[key]}"
                for key in ("category", "title", "description", "actionable_tip")
                if row.get(key)
            )
            url = ""
            category = row.get("category", "")
            organization = "MindBridge wellness catalog"

        if route == "resources":
            url = row.get("url", "")
        records.append({
            "id": f"{route}__{index}",
            "text": text,
            "title": title,
            "url": url,
            "organization": organization,
            "category": category,
        })
    return records


def load_records(chunk_size: int = 800) -> dict[str, list[dict[str, str]]]:
    """Load curated article chunks and catalog rows for all five routes."""
    records = {
        route: _article_records(route, path, chunk_size)
        for route, path in ARTICLE_CATALOGS.items()
    }
    records.update({
        route: _csv_records(route, path)
        for route, path in CSV_CATALOGS.items()
    })
    return records


def _client():
    import chromadb

    return chromadb.PersistentClient(path=str(DB_DIR))


@lru_cache(maxsize=1)
def _embedding_function():
    from chromadb.utils import embedding_functions

    return embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name=EMBED_MODEL
    )


def build(chunk_size: int = 800) -> int:
    records_by_route = load_records(chunk_size)
    total_records = sum(len(records) for records in records_by_route.values())
    if total_records == 0:
        raise FileNotFoundError(
            "No catalog records were found. Check the CSV files and data/raw/."
        )

    client = _client()
    embedding_function = _embedding_function()
    existing = {
        item if isinstance(item, str) else item.name
        for item in client.list_collections()
    }
    managed_names = {collection_name(route) for route in ROUTES}
    for name in managed_names | {"mindbridge"}:
        if name in existing:
            client.delete_collection(name)

    total_chunks = 0
    for route, records in records_by_route.items():
        if not records:
            print(f"  {route}: no records")
            continue
        collection = client.create_collection(
            name=collection_name(route),
            embedding_function=embedding_function,
            metadata={"hnsw:space": "cosine"},
        )
        collection.add(
            ids=[record["id"] for record in records],
            documents=[record["text"] for record in records],
            metadatas=[
                {
                    key: record[key]
                    for key in ("title", "url", "organization", "category")
                }
                for record in records
            ],
        )
        total_chunks += len(records)
        print(f"  {route}: {len(records)} records")

    print(f"Indexed {total_chunks} records across {len(ROUTES)} routes in {DB_DIR}")
    return total_chunks


def search(query: str, k: int = 4, route: str = "generalinfo") -> list[dict]:
    """Return relevant text nodes from one of the five route collections."""
    name = collection_name(route)
    if not query.strip():
        return []
    if k < 1:
        raise ValueError("k must be greater than zero")

    client = _client()
    existing = {
        item if isinstance(item, str) else item.name
        for item in client.list_collections()
    }
    if name not in existing:
        raise IndexNotBuiltError(
            f"The {route} vector collection is missing. "
            "Build the indexes with `python retrieval/build_index.py`."
        )

    collection = client.get_collection(
        name=name,
        embedding_function=_embedding_function(),
    )
    count = collection.count()
    if not count:
        return []
    result = collection.query(query_texts=[query], n_results=min(k, count))
    return [
        {"id": node_id, "text": text, "distance": distance, **metadata}
        for node_id, text, metadata, distance in zip(
            result["ids"][0],
            result["documents"][0],
            result["metadatas"][0],
            result["distances"][0],
        )
    ]


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--query", help="search a catalog instead of rebuilding")
    parser.add_argument("--route", choices=ROUTES, default="generalinfo")
    parser.add_argument("--chunk-size", type=int, default=800)
    args = parser.parse_args()
    if args.query:
        for index, hit in enumerate(search(args.query, route=args.route), 1):
            print(f"\n[{index}] {hit['title']} ({hit['organization']})")
            print(hit["text"][:300] + ("..." if len(hit["text"]) > 300 else ""))
    else:
        build(args.chunk_size)
