#!/usr/bin/env python3
"""Populate data/raw and data/sources.csv from trusted mental-health sources.

This script intentionally uses only known public sources approved by the project:
NIMH, SAMHSA, WHO, NAMI, MedlinePlus, and official campus counseling pages.
It fetches each URL, extracts readable text, saves the plaintext in data/raw,
and records metadata in data/sources.csv for the vector database.
"""

from __future__ import annotations

import argparse
import base64
import csv
import html
import re
import ssl
import sys
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Iterable, List, Optional
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, quote, urlparse
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
SOURCES_CSV = DATA_DIR / "sources.csv"
args_overwrite_for_build = False

ALLOWED_DOMAINS = {
    "nimh.nih.gov",
    "www.nimh.nih.gov",
    "samhsa.gov",
    "www.samhsa.gov",
    "who.int",
    "www.who.int",
    "nami.org",
    "www.nami.org",
    "medlineplus.gov",
    "www.medlineplus.gov",
    "uhs.berkeley.edu",
    "www.uhs.berkeley.edu",
    "caps.umich.edu",
    "www.caps.umich.edu",
    "counseling.ucla.edu",
    "www.counseling.ucla.edu",
    "studenthealth.ucla.edu",
    "www.studenthealth.ucla.edu",
    "wellbeing.utexas.edu",
    "www.wellbeing.utexas.edu",
}

SEARCH_ORGANIZATIONS = [
    {
        "name": "National Institute of Mental Health",
        "domain": "nimh.nih.gov",
        "topics": [
            "anxiety",
            "depression",
            "stress",
            "sleep",
            "ptsd",
            "burnout",
            "suicide prevention",
            "eating disorders",
            "mental health disorders",
        ],
    },
    {
        "name": "Substance Abuse and Mental Health Services Administration",
        "domain": "samhsa.gov",
        "topics": [
            "mental health",
            "anxiety",
            "depression",
            "stress",
            "support",
            "find treatment",
            "crisis help",
            "mental health resources",
        ],
    },
    {
        "name": "World Health Organization",
        "domain": "who.int",
        "topics": [
            "mental health",
            "depression",
            "stress",
            "anxiety",
            "mental disorders",
            "wellbeing",
        ],
    },
    {
        "name": "National Alliance on Mental Illness",
        "domain": "nami.org",
        "topics": [
            "mental health conditions",
            "anxiety",
            "depression",
            "stress",
            "support",
            "therapy",
        ],
    },
    {
        "name": "MedlinePlus",
        "domain": "medlineplus.gov",
        "topics": [
            "anxiety",
            "depression",
            "stress",
            "sleep disorders",
            "mental health",
            "substance abuse",
        ],
    },
]


class TextExtractor(HTMLParser):
    """A small HTML parser that keeps readable body text and strips boilerplate."""

    def __init__(self):
        super().__init__()
        self._text_parts: List[str] = []
        self._skip_depth = 0
        self._block_tags = {"p", "div", "article", "section", "li", "h1", "h2", "h3", "h4"}

    def handle_starttag(self, tag: str, attrs):
        tag = tag.lower()
        if tag in {"script", "style", "noscript", "svg", "header", "footer", "nav"}:
            self._skip_depth += 1
            return
        if tag in self._block_tags and self._skip_depth == 0:
            self._text_parts.append("\n\n")

    def handle_endtag(self, tag: str):
        tag = tag.lower()
        if tag in {"script", "style", "noscript", "svg", "header", "footer", "nav"}:
            if self._skip_depth > 0:
                self._skip_depth -= 1
            return
        if tag in self._block_tags and self._skip_depth == 0:
            self._text_parts.append("\n\n")

    def handle_data(self, data: str):
        if self._skip_depth == 0 and data.strip():
            self._text_parts.append(data.strip())

    def get_text(self) -> str:
        return " ".join(self._text_parts)


def slugify(value: str) -> str:
    value = html.unescape(value)
    value = value.lower()
    value = re.sub(r"[^a-z0-9]+", "_", value)
    value = value.strip("_")
    return value or "document"


def is_allowed_domain(url: str) -> bool:
    try:
        netloc = urlparse(url).netloc.lower()
    except Exception:
        return False
    if not netloc:
        return False
    domain = netloc.replace("www.", "")
    return domain in ALLOWED_DOMAINS or any(netloc.endswith(f".{allowed}") for allowed in ALLOWED_DOMAINS)


def ddg_search(domain: str, query: str) -> list[str]:
    """Use Bing's search page to find documents within a single approved domain.

    Bing encodes the final URL in its `u` parameter; we decode that instead of relying on a
    hard-coded article list.
    """
    encoded_query = "site:" + domain + " " + query
    search_url = "https://www.bing.com/search?q=" + quote(encoded_query)
    request = Request(
        search_url,
        headers={
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        },
    )
    context = ssl._create_unverified_context()
    with urlopen(request, context=context, timeout=30) as response:
        page = response.read().decode(response.headers.get_content_charset() or "utf-8", errors="replace")

    results: list[str] = []
    seen = set()
    for href in re.findall(r'href="([^"]+)"', page, flags=re.I):
        if "bing.com/ck/a" not in href:
            continue
        try:
            href = html.unescape(href)
            parsed = urlparse(href)
            params = parse_qs(parsed.query)
            raw_u = params.get("u", [""])[0]
            if not raw_u:
                continue
            decoded = base64.b64decode(raw_u[2:] + "=" * (-len(raw_u[2:]) % 4)).decode("utf-8", errors="replace")
            final_url = decoded.replace("https://https://", "https://")
        except Exception:
            continue
        parsed_final = urlparse(final_url)
        if not parsed_final.scheme or not parsed_final.netloc:
            continue
        netloc = parsed_final.netloc.lower()
        if netloc not in {domain, "www." + domain} and not netloc.endswith("." + domain):
            continue
        clean = final_url.rstrip("/")
        if clean not in seen:
            seen.add(clean)
            results.append(clean)
    return results


def discover_articles(limit: int = 15) -> list[dict]:
    """Search approved organizations dynamically and return a diverse, deduplicated article set."""
    by_org: dict[str, list[dict]] = {org["name"]: [] for org in SEARCH_ORGANIZATIONS}
    seen_urls: set[str] = set()

    for org in SEARCH_ORGANIZATIONS:
        for term in org["topics"]:
            for result in ddg_search(org["domain"], term):
                if result in seen_urls or not is_allowed_domain(result):
                    continue
                result_title = result.split("/")[-1].replace(".html", "").replace("-", " ").replace("_", " ")
                title = result_title.title() if result_title.strip() else org["name"]
                record = {
                    "title": title,
                    "url": result,
                    "organization": org["name"],
                    "category": term.lower().replace(" ", "-"),
                }
                by_org[org["name"]].append(record)
                seen_urls.add(result)

    if not any(by_org.values()):
        raise RuntimeError("No approved-domain articles were discovered from search results.")

    selected: list[dict] = []
    selected_urls: set[str] = set()
    org_names = list(by_org.keys())
    index = 0

    while len(selected) < limit and sum(len(items) for items in by_org.values()) > 0:
        org_name = org_names[index % len(org_names)]
        items = by_org[org_name]
        if not items:
            index += 1
            continue

        item = items.pop(0)
        if item["url"] in selected_urls:
            index += 1
            continue

        selected.append(item)
        selected_urls.add(item["url"])
        index += 1

    if len(selected) < limit:
        for org_name, items in by_org.items():
            for item in items:
                if item["url"] in selected_urls:
                    continue
                selected.append(item)
                selected_urls.add(item["url"])
                if len(selected) >= limit:
                    break
            if len(selected) >= limit:
                break

    return selected[:limit]


def fetch_html(url: str) -> Optional[str]:
    if not is_allowed_domain(url):
        raise ValueError(f"URL is not from an approved source: {url}")

    request = Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (compatible; MindBridgeAutopopulate/1.0)",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        },
    )
    context = ssl._create_unverified_context()
    with urlopen(request, context=context, timeout=25) as response:
        charset = response.headers.get_content_charset() or "utf-8"
        return response.read().decode(charset, errors="replace")


def extract_readable_text(html_text: str) -> str:
    parser = TextExtractor()
    parser.feed(html_text)
    text = parser.get_text()
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"\s*\n\s*", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = text.strip()
    return text


def load_existing_rows() -> dict:
    rows: dict = {}
    if not SOURCES_CSV.exists():
        return rows
    with SOURCES_CSV.open("r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            doc_id = (row.get("doc_id") or "").strip()
            if doc_id:
                rows[doc_id] = row
    return rows


def reset_library(overwrite: bool):
    if not overwrite:
        return
    for path in RAW_DIR.glob("*.txt"):
        path.unlink()
    if SOURCES_CSV.exists():
        SOURCES_CSV.unlink()


def write_sources_csv(rows: Iterable[dict]):
    fieldnames = ["doc_id", "title", "url", "organization", "category", "source", "added_on"]
    rows = list(rows)
    RAW_DIR.mkdir(parents=True, exist_ok=True)

    merged = {}
    if SOURCES_CSV.exists():
        with SOURCES_CSV.open("r", newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                key = (row.get("doc_id") or "").strip()
                if key:
                    merged[key] = row

    for row in rows:
        merged[row["doc_id"]] = row

    with SOURCES_CSV.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in merged.values():
            writer.writerow(row)


def doc_id_for_record(record: dict) -> str:
    title = record["title"].strip()
    path_slug = slugify(urlparse(record["url"]).path.strip("/"))
    return slugify(f"{path_slug} {title} {record['organization']}")


def build_document(record: dict) -> tuple[str, str, dict]:
    title = record["title"].strip()
    doc_id = doc_id_for_record(record)
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    html_text = fetch_html(record["url"])
    if html_text is None:
        raise RuntimeError(f"No HTML returned for {record['url']}")

    text = extract_readable_text(html_text)
    if not text or len(text) < 200:
        raise RuntimeError(f"Fetched page looks empty or blocked: {record['url']}")

    target = RAW_DIR / f"{doc_id}.txt"
    if target.exists() and not args_overwrite_for_build:
        raise RuntimeError(f"File already exists: {target.name}")
    target.write_text(text, encoding="utf-8")

    row = {
        "doc_id": doc_id,
        "title": title,
        "url": record["url"],
        "organization": record["organization"],
        "category": record["category"],
        "source": record["organization"],
        "added_on": timestamp,
    }
    return doc_id, target.name, row


def populate(count: int = 15, overwrite: bool = False) -> list[str]:
    global args_overwrite_for_build
    args_overwrite_for_build = overwrite

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    if overwrite:
        reset_library(overwrite=True)

    rows: List[dict] = []
    saved: List[str] = []
    seen = set()
    existing_ids = {p.stem for p in RAW_DIR.glob("*.txt")}
    if SOURCES_CSV.exists():
        with SOURCES_CSV.open("r", newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                doc_id = (row.get("doc_id") or "").strip()
                if doc_id:
                    existing_ids.add(doc_id)

    candidate_pool = discover_articles(limit=max(count * 5, 50))
    for record in candidate_pool:
        doc_id = doc_id_for_record(record)

        if not overwrite and doc_id in existing_ids:
            continue

        try:
            doc_id, filename, row = build_document(record)
        except Exception as exc:
            print(f"[skip] {record['title']} -> {exc}", file=sys.stderr)
            continue

        if not overwrite and doc_id in seen:
            continue
        seen.add(doc_id)
        existing_ids.add(doc_id)
        rows.append(row)
        saved.append(filename)

        if len(saved) >= count:
            break

    if rows:
        write_sources_csv(rows)
    else:
        print("No valid articles were saved.", file=sys.stderr)

    return saved


def main() -> int:
    parser = argparse.ArgumentParser(description="Fetch and save trusted mental-health articles into the project data library.")
    parser.add_argument("--count", type=int, default=15, help="How many approved articles to fetch (default: 15)")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite any existing raw files and CSV rows for the selected documents")
    args = parser.parse_args()

    if args.count < 1:
        raise SystemExit("--count must be at least 1")

    saved = populate(count=args.count, overwrite=args.overwrite)
    print(f"Saved {len(saved)} documents to {RAW_DIR}.")
    print(f"Updated {SOURCES_CSV}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
