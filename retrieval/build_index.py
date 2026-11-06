"""Build (or query) the MindBridge vector database.

Usage:
    python retrieval/build_index.py
    python retrieval/build_index.py --query "signs of burnout"
    python retrieval/build_index.py --chunk-size 500
"""
import argparse
import csv
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT / "data" / "raw"
SOURCE_CSVS = (
    ROOT / "data" / "Generalinfo.csv",
    ROOT / "data" / "conditions_and_signs.csv",
)
DB_DIR = ROOT / "chroma_db"
COLLECTION = "mindbridge"
EMBED_MODEL = "all-MiniLM-L6-v2"  # small, free, runs on a laptop


# Website clutter that autopopulate.py copies in with the article text.
# Removed before chunking so it never gets embedded or shown to a student.
BOILERPLATE_PATTERNS = [
    r"Skip (?:directly )?to (?:main |site )?content",
    r"Skip directly to search",
    r"Skip navigation",
    r"Skip to content",
    r"An official website of the United States government",
    r"Here's how you know",
    r"Official websites use \.gov A \.gov website belongs to an official government organization in the United States\.",
    r"Secure \.gov websites use HTTPS A lock \( \) or https:// means you.ve safely connected to the \.gov website\.",
    r"Share sensitive information only on official, secure websites\.",
    r"NIH Websites Are Changing Get the Latest Updates and FAQs on the transition",
    r"Per Executive Order \d+ ?, federal agencies are now using .{0,120}?during this transition\.",
    r"Health Topics Statistics Brochures and Fact Sheets Help for Mental Illnesses Clinical Trials Share Page Menu",
    r"Download PDF",
    r"En español",
    r"Reading time:",
]
_BOILERPLATE_RE = re.compile("|".join(BOILERPLATE_PATTERNS))


def clean_text(text):
    """Strip known site boilerplate and collapse whitespace."""
    text = _BOILERPLATE_RE.sub(" ", text)
    return re.sub(r"[ \t]+", " ", text).strip()


def _split_sentences(text):
    """Split on paragraph breaks and sentence ends. The raw files are one long
    line each, so splitting on paragraphs alone would make one giant chunk per
    document, and the embedding model only reads the first ~256 tokens."""
    pieces = []
    for para in re.split(r"\n\s*\n", text):
        pieces.extend(s.strip() for s in re.split(r"(?<=[.!?])\s+(?=[A-Z0-9\"“(])", para) if s.strip())
    return pieces


def chunk_text(text, chunk_size=800, overlap=100):
    """Split text into overlapping chunks of roughly `chunk_size` characters,
    breaking on sentence boundaries. A single sentence longer than
    `chunk_size` (e.g. a run-on list of links) is cut at word boundaries."""
    sentences = []
    for s in _split_sentences(text):
        while len(s) > chunk_size:
            cut = s.rfind(" ", 0, chunk_size)
            cut = cut if cut > 0 else chunk_size
            sentences.append(s[:cut])
            s = s[cut:].strip()
        if s:
            sentences.append(s)

    chunks, current = [], ""
    for sent in sentences:
        if current and len(current) + 1 + len(sent) > chunk_size:
            chunks.append(current)
            tail = current[-overlap:]
            tail = tail[tail.find(" ") + 1:] if " " in tail else tail  # start the overlap on a whole word
            current = f"{tail} {sent}"
        else:
            current = f"{current} {sent}" if current else sent
    if current:
        chunks.append(current)
    return chunks


def load_source_metadata():
    """Map doc_id -> row from both data source catalogs."""
    metadata = {}
    for csv_path in SOURCE_CSVS:
        if not csv_path.exists():
            continue
        with csv_path.open(newline="", encoding="utf-8") as file:
            metadata.update(
                (row["doc_id"], row)
                for row in csv.DictReader(file)
                if row.get("doc_id")
            )
    return metadata


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
            print(f"  ! {doc_id} has no row in Generalinfo.csv or conditions_and_signs.csv")
        chunks = chunk_text(clean_text(path.read_text(encoding="utf-8")), chunk_size=chunk_size)
        if not chunks:
            print(f"  ! {doc_id} is empty after cleaning, skipped")
            continue
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
