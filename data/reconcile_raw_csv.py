#!/usr/bin/env python3
"""Reconcile raw documents against CSV catalogs in the data directory."""

from __future__ import annotations

import csv
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
RAW_DIR = ROOT / "raw"


def read_csv_rows(csv_path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with csv_path.open("r", newline="", encoding="utf-8") as file:
        reader = csv.DictReader(file)
        fieldnames = reader.fieldnames or []
        if "doc_id" not in fieldnames:
            return fieldnames, []

        rows = [
            row for row in reader
            if (row.get("doc_id") or "").strip()
        ]
    return fieldnames, rows


def reconcile() -> tuple[int, int]:
    if not RAW_DIR.exists():
        raise FileNotFoundError(f"Missing raw directory: {RAW_DIR}")

    catalog_rows: dict[Path, tuple[list[str], list[dict[str, str]]]] = {}
    for csv_path in sorted(ROOT.iterdir()):
        if not csv_path.is_file() or csv_path.suffix.lower() != ".csv":
            continue
        fieldnames, rows = read_csv_rows(csv_path)
        if "doc_id" in fieldnames:
            catalog_rows[csv_path] = fieldnames, rows

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
