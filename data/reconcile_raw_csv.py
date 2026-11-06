#!/usr/bin/env python3
"""Reconcile raw documents against the Generalinfo and conditions catalogs."""

from __future__ import annotations

import csv
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
RAW_DIR = ROOT / "raw"
CSV_PATHS = (ROOT / "Generalinfo.csv", ROOT / "conditions_and_signs.csv")
DEFAULT_FIELDS = ["doc_id", "title", "url", "organization", "category", "source", "added_on"]


def read_csv_rows(csv_path: Path) -> tuple[list[str], list[dict[str, str]]]:
    if not csv_path.exists():
        return DEFAULT_FIELDS, []

    with csv_path.open("r", newline="", encoding="utf-8") as file:
        reader = csv.DictReader(file)
        fieldnames = reader.fieldnames or DEFAULT_FIELDS
        rows = [
            row for row in reader
            if (row.get("doc_id") or "").strip()
        ]
    return fieldnames, rows


def reconcile() -> tuple[int, int]:
    if not RAW_DIR.exists():
        raise FileNotFoundError(f"Missing raw directory: {RAW_DIR}")
    missing_catalogs = [path for path in CSV_PATHS if not path.exists()]
    if missing_catalogs:
        raise FileNotFoundError(f"Missing source catalogs: {', '.join(map(str, missing_catalogs))}")

    catalog_rows = {path: read_csv_rows(path) for path in CSV_PATHS}
    tracked_ids = {
        (row.get("doc_id") or "").strip()
        for _, rows in catalog_rows.values()
        for row in rows
    }

    raw_files = [path for path in RAW_DIR.iterdir() if path.is_file()]
    raw_stems = {path.stem for path in raw_files if path.suffix.lower() == ".txt"}
    if not tracked_ids and raw_stems:
        raise ValueError("Both source catalogs are empty; refusing to remove all raw documents.")

    orphaned_raw = [
        path for path in raw_files
        if path.suffix.lower() == ".txt" and path.stem not in tracked_ids
    ]
    for path in orphaned_raw:
        path.unlink()

    removed_csv = 0
    for csv_path, (fieldnames, rows) in catalog_rows.items():
        kept_rows = [
            row for row in rows
            if (row.get("doc_id") or "").strip() in raw_stems
        ]
        removed_csv += len(rows) - len(kept_rows)
        if len(kept_rows) != len(rows):
            with csv_path.open("w", newline="", encoding="utf-8") as file:
                writer = csv.DictWriter(file, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(kept_rows)

    return len(orphaned_raw), removed_csv


if __name__ == "__main__":
    try:
        removed_raw, removed_csv = reconcile()
        print(f"Deleted {removed_raw} orphaned .txt file(s) from {RAW_DIR}")
        print(f"Removed {removed_csv} orphaned row(s) from the source catalogs")
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(1)
