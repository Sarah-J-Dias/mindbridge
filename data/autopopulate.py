#!/usr/bin/env python3
"""Populate the mental-health source catalogs using live search results.

This script intentionally uses only known public sources approved by the project:
NIMH, SAMHSA, WHO, NAMI, MedlinePlus, and official campus counseling pages.
It discovers article URLs at runtime, fetches each page, saves readable text in
data/raw, and records metadata in either Generalinfo.csv or
conditions_and_signs.csv. No article URLs are stored in the script.
"""

from __future__ import annotations

import argparse
import base64
import csv
import html
import re
import sys
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Iterable, List, Optional
from urllib.parse import parse_qs, quote, urlparse
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
CATALOGS = {
    "generalinfo": DATA_DIR / "Generalinfo.csv",
    "conditions_and_signs": DATA_DIR / "conditions_and_signs.csv",
}

ALLOWED_DOMAINS = {
    "nimh.nih.gov",
    "www.nimh.nih.gov",
    "cdc.gov",
    "www.cdc.gov",
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
        "name": "Centers for Disease Control and Prevention",
        "domain": "cdc.gov",
        "topics": [
            "mental health",
            "anxiety",
            "depression",
            "suicide prevention",
            "substance use",
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

CONDITION_SEARCH_TERMS = [
    ("anxiety", "anxiety disorders signs symptoms"),
    ("depression", "depression warning signs symptoms"),
    ("ptsd", "PTSD symptoms post-traumatic stress disorder"),
    ("eating-disorders", "eating disorders warning signs symptoms"),
    ("bipolar-disorder", "bipolar disorder signs symptoms"),
    ("schizophrenia", "schizophrenia early warning signs symptoms"),
    ("ocd", "obsessive compulsive disorder signs symptoms"),
    ("adhd", "ADHD signs symptoms adults children"),
    ("substance-use", "substance use disorder warning signs symptoms"),
    ("suicide-prevention", "suicide warning signs"),
]

CONDITION_TITLE_PATTERNS = {
    "anxiety": r"\banxiety\b",
    "depression": r"\bdepress(?:ion|ive)\b",
    "ptsd": r"\bptsd\b|post[\s-]traumatic stress disorder",
    "eating-disorders": r"eating disorder|anorexia|bulimia",
    "bipolar-disorder": r"\bbipolar\b",
    "schizophrenia": r"\bschizophrenia\b|\bpsychosis\b",
    "ocd": r"\bocd\b|obsessive.compulsive disorder",
    "adhd": r"\badhd\b|attention.deficit hyperactivity disorder",
    "substance-use": r"substance use|alcohol use disorder|drug use disorder",
    "suicide-prevention": r"suicid",
}
WARNING_SIGN_PATTERN = re.compile(
    r"\b(signs?|symptoms?|warning|recogniz\w*|early signs|criteria)\b",
    flags=re.IGNORECASE,
)


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
    with urlopen(request, timeout=30) as response:
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


def extract_page_title(html_text: str, fallback: str) -> str:
    match = re.search(r"<title[^>]*>(.*?)</title>", html_text, flags=re.IGNORECASE | re.DOTALL)
    if not match:
        return fallback
    title = html.unescape(re.sub(r"<[^>]+>", "", match.group(1)))
    title = re.sub(r"\s*[|–—]\s*.*$", "", title)
    title = re.sub(
        r"\s+-\s+(?:National Institute|Centers for Disease Control|World Health|"
        r"Substance Abuse|National Alliance|MedlinePlus).*$",
        "",
        title,
        flags=re.IGNORECASE,
    )
    return re.sub(r"\s+", " ", title).strip() or fallback


def discover_articles(limit: int = 15, catalog: str = "conditions_and_signs") -> list[dict]:
    """Search approved organizations dynamically and return relevant article URLs."""
    if catalog not in CATALOGS:
        raise ValueError(f"Unknown source catalog: {catalog}")

    seen_urls: set[str] = set()
    selected: list[dict] = []
    if catalog == "conditions_and_signs":
        topics = CONDITION_SEARCH_TERMS
        per_topic_limit = max(1, (limit + len(topics) - 1) // len(topics))
        found_by_topic = {category: 0 for category, _ in topics}
        for round_index in range(per_topic_limit):
            for category, term in topics:
                if found_by_topic[category] >= per_topic_limit:
                    continue
                for org in SEARCH_ORGANIZATIONS:
                    try:
                        results = ddg_search(org["domain"], term)
                    except Exception as exc:
                        print(f"[search skip] {org['name']} ({category}) -> {exc}", file=sys.stderr)
                        continue
                    for result in results:
                        if (
                            result in seen_urls
                            or not is_allowed_domain(result)
                            or urlparse(result).path.lower().endswith((".pdf", ".doc", ".docx"))
                        ):
                            continue
                        fallback_title = result.rstrip("/").split("/")[-1].replace(".html", "").replace("-", " ").replace("_", " ")
                        title = fallback_title.title() if fallback_title.strip() else org["name"]
                        selected.append({
                            "title": title,
                            "url": result,
                            "organization": org["name"],
                            "category": category,
                        })
                        seen_urls.add(result)
                        found_by_topic[category] += 1
                        break
                    if found_by_topic[category] >= round_index + 1:
                        break
                if len(selected) >= limit:
                    return selected[:limit]
        return selected[:limit]

    for org in SEARCH_ORGANIZATIONS:
        for term in org["topics"]:
            try:
                results = ddg_search(org["domain"], term)
            except Exception as exc:
                print(f"[search skip] {org['name']} ({term}) -> {exc}", file=sys.stderr)
                continue
            for result in results:
                if (
                    result in seen_urls
                    or not is_allowed_domain(result)
                    or urlparse(result).path.lower().endswith((".pdf", ".doc", ".docx"))
                ):
                    continue
                fallback_title = result.rstrip("/").split("/")[-1].replace(".html", "").replace("-", " ").replace("_", " ")
                title = fallback_title.title() if fallback_title.strip() else org["name"]
                selected.append({
                    "title": title,
                    "url": result,
                    "organization": org["name"],
                    "category": term.lower().replace(" ", "-"),
                })
                seen_urls.add(result)
                if len(selected) >= limit:
                    return selected[:limit]

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
    with urlopen(request, timeout=25) as response:
        if not is_allowed_domain(response.geturl()):
            raise ValueError(f"Redirected outside approved source domains: {response.geturl()}")
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


def is_condition_warning_source(record: dict, text: str) -> bool:
    category = record.get("category", "")
    title_pattern = CONDITION_TITLE_PATTERNS.get(category)
    if not title_pattern:
        return True
    title_matches = re.search(title_pattern, record.get("title", ""), flags=re.IGNORECASE)
    discusses_signs = WARNING_SIGN_PATTERN.search(text) or WARNING_SIGN_PATTERN.search(record.get("title", ""))
    return bool(title_matches and discusses_signs)


def load_existing_rows(csv_path: Path) -> dict:
    rows: dict = {}
    if not csv_path.exists():
        return rows
    with csv_path.open("r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            doc_id = (row.get("doc_id") or "").strip()
            if doc_id:
                rows[doc_id] = row
    return rows


def write_catalog_csv(csv_path: Path, rows: Iterable[dict]):
    fieldnames = ["doc_id", "title", "url", "organization", "category", "source", "added_on"]
    rows = list(rows)
    RAW_DIR.mkdir(parents=True, exist_ok=True)

    merged = load_existing_rows(csv_path)

    for row in rows:
        merged[row["doc_id"]] = row

    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in merged.values():
            writer.writerow(row)


def doc_id_for_record(record: dict) -> str:
    title = record["title"].strip()
    path_slug = slugify(urlparse(record["url"]).path.strip("/"))
    return slugify(f"{path_slug} {title} {record['organization']}")


def build_document(record: dict, overwrite: bool = False) -> tuple[str, str, dict]:
    title = record["title"].strip()
    doc_id = doc_id_for_record(record)
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    html_text = fetch_html(record["url"])
    if html_text is None:
        raise RuntimeError(f"No HTML returned for {record['url']}")

    title = extract_page_title(html_text, title)
    text = extract_readable_text(html_text)
    if not text or len(text) < 200:
        raise RuntimeError(f"Fetched page looks empty or blocked: {record['url']}")
    validation_record = {**record, "title": title}
    if record.get("category") in CONDITION_TITLE_PATTERNS:
        if not is_condition_warning_source(validation_record, text):
            if not re.search(CONDITION_TITLE_PATTERNS[record["category"]], title, flags=re.IGNORECASE):
                raise RuntimeError(f"Page title does not match condition {record['category']}: {title}")
            raise RuntimeError(f"Page does not discuss symptoms or warning signs: {record['url']}")

    target = RAW_DIR / f"{doc_id}.txt"
    if overwrite or not target.exists():
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


def populate(
    count: int = 15,
    overwrite: bool = False,
    catalog: str = "conditions_and_signs",
) -> list[str]:
    if catalog not in CATALOGS:
        raise ValueError(f"Unknown source catalog: {catalog}")
    csv_path = CATALOGS[catalog]
    RAW_DIR.mkdir(parents=True, exist_ok=True)

    rows: List[dict] = []
    saved: List[str] = []
    seen = set()
    existing_rows = load_existing_rows(csv_path)
    existing_ids = set(existing_rows)

    candidate_pool = discover_articles(limit=max(count * 3, 30), catalog=catalog)
    for record in candidate_pool:
        doc_id = doc_id_for_record(record)

        if not overwrite and doc_id in existing_ids:
            continue

        try:
            doc_id, filename, row = build_document(record, overwrite=overwrite)
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
        write_catalog_csv(csv_path, rows)
    else:
        print(f"No new sources were added to {csv_path.name}.")

    return saved


def main() -> int:
    parser = argparse.ArgumentParser(description="Fetch and save trusted mental-health articles into the project data library.")
    parser.add_argument("--count", type=int, default=15, help="How many approved articles to fetch (default: 15)")
    parser.add_argument(
        "--catalog",
        choices=sorted(CATALOGS),
        default="conditions_and_signs",
        help="Which CSV catalog to update (default: conditions_and_signs)",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Refresh discovered documents already in the selected catalog without deleting other files",
    )
    args = parser.parse_args()

    if args.count < 1:
        raise SystemExit("--count must be at least 1")

    saved = populate(count=args.count, overwrite=args.overwrite, catalog=args.catalog)
    print(f"Saved {len(saved)} documents to {RAW_DIR}.")
    print(f"Updated {CATALOGS[args.catalog]}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
