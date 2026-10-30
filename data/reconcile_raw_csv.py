#!/usr/bin/env python3
"""Remove orphaned raw files and orphaned CSV rows.

This script ensures the raw text library and the CSV metadata stay in sync:
- deletes any file in data/raw that is not represented by a row in data/sources.csv
- deletes any CSV row whose doc_id does not have a matching .txt file in data/raw

It is intentionally conservative: only files in data/raw and rows in the CSV are touched.
"""

from __future__ import annotations

import csv
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
RAW_DIR = ROOT / "raw"
CSV_PATH = ROOT / "sources.csv"


def read_csv_doc_ids(csv_path: Path) -> tuple[set[str], list[dict]]:
    if not csv_path.exists():
        return set(), []

    rows: list[dict] = []
    doc_ids: set[str] = set()
    with csv_path.open("r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            doc_id = (row.get("doc_id") or "").strip()
            if not doc_id:
                continue
            rows.append(row)
            doc_ids.add(doc_id)
    return doc_ids, rows


def reconcile() -> tuple[int, int]:
    if not RAW_DIR.exists():
        raise FileNotFoundError(f"Missing raw directory: {RAW_DIR}")

    csv_doc_ids, csv_rows = read_csv_doc_ids(CSV_PATH)
    raw_files = [p for p in RAW_DIR.iterdir() if p.is_file()]

    raw_stems = {p.stem for p in raw_files if p.suffix.lower() == ".txt"}

    removed_raw = []
    for path in raw_files:
        if path.name == ".gitkeep":
            removed_raw.append(path)
            continue
        if path.suffix.lower() == ".txt" and path.stem in csv_doc_ids:
            continue
        if path.suffix.lower() != ".txt" or path.stem not in csv_doc_ids:
            removed_raw.append(path)

    for path in removed_raw:
        path.unlink()

    kept_rows = [row for row in csv_rows if (row.get("doc_id") or "").strip() in raw_stems]
    removed_csv = len(csv_rows) - len(kept_rows)

    if CSV_PATH.exists() and removed_csv > 0:
        with CSV_PATH.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(csv_rows[0].keys()) if csv_rows else ["doc_id", "title", "url", "organization", "category", "source", "added_on"])
            writer.writeheader()
            writer.writerows(kept_rows)

    return len(removed_raw), removed_csv


if __name__ == "__main__":
    try:
        removed_raw, removed_csv = reconcile()
        print(f"Deleted {removed_raw} orphaned file(s) from {RAW_DIR}")
        print(f"Removed {removed_csv} orphaned row(s) from {CSV_PATH}")
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(1)
