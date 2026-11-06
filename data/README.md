# data/ — Knowledge base (Members 1 + 2)

## What goes here

```
data/
├── raw/                        # one plain-text .txt file per source document
├── Generalinfo.csv             # general mental-health information sources
├── conditions_and_signs.csv    # conditions, symptoms, and warning-sign sources
└── resources.csv    # support resources the bot can point students to
```

The source catalogs use the same columns (`doc_id`, `title`, `url`,
`organization`, `category`, `source`, `added_on`). Each `doc_id` points to a
text file in `raw/`; retrieval reads metadata from the general-information and
conditions catalogs.

## Approved sources

NIMH, SAMHSA, CDC, WHO, NAMI, MedlinePlus, and official campus counseling pages.
Skip anything paywalled, unclear about reuse, or written as personal opinion (blogs, forums).

## Populating and reconciling sources

Run these commands from the repository root.

Discover sources at runtime, fetch their text into `data/raw/`, and add metadata
to `conditions_and_signs.csv` (the default):

```powershell
python data\autopopulate.py
```

To populate the general-information catalog instead, or to change the number
of sources fetched:

```powershell
python data\autopopulate.py --catalog generalinfo --count 10
```

`--catalog` accepts `generalinfo` or `conditions_and_signs`; `--count` must be
at least 1. Add `--overwrite` to refresh matching documents in the selected
catalog. It does not clear the other catalog or unrelated raw files.

After manually changing catalog entries or raw files, reconcile them with:

```powershell
python data\reconcile_raw_csv.py
```

Reconciliation discovers every CSV in `data/` with a `doc_id` column, removes
`.txt` files not listed in those catalogs, and removes catalog rows whose
matching `.txt` file is missing. CSVs without a `doc_id` column and non-text
files in `raw/` are left untouched.

## Adding a document manually — checklist

1. Copy the page's main text into a new file in `raw/`, named like `nimh_anxiety_overview.txt`.
2. Delete menus, ads, footers, "related articles" links — keep only the article.
3. Add a row to `Generalinfo.csv` or `conditions_and_signs.csv` with the same `doc_id` (the file name without `.txt`).
4. Note the terms of use (most U.S. government pages are public domain; check others).

## Topic split

| Member 1 | Member 2 |
| --- | --- |
| Anxiety, depression, stress, sleep, burnout | Conditions, symptoms, warning signs, coping skills, support |

## resources.csv

Member 2 owns this. **Verify every phone number and link on the official site before adding it**, and fill `last_verified`.
