"""Build (or query) the MindBridge vector database.

Usage:
    python retrieval/build_index.py
    python retrieval/build_index.py --query "signs of burnout"
    python retrieval/build_index.py --chunk-size 500
"""
import argparse
import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT / "data" / "raw"
SOURCES_CSV = ROOT / "data" / "sources.csv"
DB_DIR = ROOT / "chroma_db"
COLLECTION = "mindbridge"
EMBED_MODEL = "all-MiniLM-L6-v2"  # small, free, runs on a laptop


def chunk_text(text, chunk_size=800, overlap=100):
    """Split text into overlapping chunks of roughly `chunk_size` characters,
    breaking on paragraph boundaries where possible."""
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    chunks, current = [], ""
    for para in paragraphs:
        if current and len(current) + len(para) > chunk_size:
            chunks.append(current)
            current = current[-overlap:] + "\n\n" + para  # carry a little context over
        else:
            current = f"{current}\n\n{para}" if current else para
    if current:
        chunks.append(current)
    return chunks


def load_source_metadata():
    """Map doc_id -> row from data/sources.csv (title, url, organization...)."""
    if not SOURCES_CSV.exists():
        return {}
    with open(SOURCES_CSV, newline="", encoding="utf-8") as f:
        return {row["doc_id"]: row for row in csv.DictReader(f) if row.get("doc_id")}


def get_collection():
    import chromadb
    from chromadb.utils import embedding_functions

    client = chromadb.PersistentClient(path=str(DB_DIR))
    embed_fn = embedding_functions.SentenceTransformerEmbeddingFunction(model_name=EMBED_MODEL)
    return client, client.get_or_create_collection(COLLECTION, embedding_function=embed_fn)


def build(chunk_size):
    files = sorted(RAW_DIR.glob("*.txt"))
    if not files:
        print(f"No .txt files in {RAW_DIR}. Add documents first (see data/README.md).")
        return
    meta = load_source_metadata()
    client, _ = get_collection()
    client.delete_collection(COLLECTION)  # rebuild from scratch each time
    _, collection = get_collection()

    total = 0
    for path in files:
        doc_id = path.stem
        info = meta.get(doc_id, {})
        if not info:
            print(f"  ! {doc_id} has no row in sources.csv — add one so answers can cite it")
        chunks = chunk_text(path.read_text(encoding="utf-8"), chunk_size=chunk_size)
        collection.add(
            ids=[f"{doc_id}__{i}" for i in range(len(chunks))],
            documents=chunks,
            metadatas=[{
                "doc_id": doc_id,
                "title": info.get("title", doc_id),
                "url": info.get("url", ""),
                "organization": info.get("organization", ""),
            } for _ in chunks],
        )
        total += len(chunks)
        print(f"  {doc_id}: {len(chunks)} chunks")
    print(f"Done: {len(files)} documents, {total} chunks saved to {DB_DIR}")


def search(query, k=4):
    """Return the k most relevant chunks as a list of dicts. Used by the agents."""
    _, collection = get_collection()
    res = collection.query(query_texts=[query], n_results=k)
    return [
        {"text": doc, "distance": dist, **meta}
        for doc, meta, dist in zip(res["documents"][0], res["metadatas"][0], res["distances"][0])
    ]


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--query", help="test a search instead of building")
    parser.add_argument("--chunk-size", type=int, default=800)
    args = parser.parse_args()
    if args.query:
        for i, hit in enumerate(search(args.query), 1):
            print(f"\n[{i}] {hit['title']} ({hit['organization']}) distance={hit['distance']:.3f}")
            print(hit["text"][:300] + "...")
    else:
        build(args.chunk_size)
