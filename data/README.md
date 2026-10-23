# data/ — Knowledge base (Members 1 + 2)

## What goes here

```
data/
├── raw/             # one plain-text .txt file per source document
├── sources.csv      # one row per document in raw/
└── resources.csv    # support resources the bot can point students to
```

## Approved sources

NIMH, SAMHSA, CDC, WHO, NAMI, MedlinePlus, and official campus counseling pages.
Skip anything paywalled, unclear about reuse, or written as personal opinion (blogs, forums).

## Adding a document — checklist

1. Copy the page's main text into a new file in `raw/`, named like `nimh_anxiety_overview.txt`.
2. Delete menus, ads, footers, "related articles" links — keep only the article.
3. Add a row to `sources.csv` with the same `doc_id` (the file name without `.txt`).
4. Note the terms of use (most U.S. government pages are public domain; check others).

## Topic split

| Member 1 | Member 2 |
| --- | --- |
| Anxiety, depression, stress, sleep, burnout | Coping skills, therapy types, substance use, student life |

## resources.csv

Member 2 owns this. **Verify every phone number and link on the official site before adding it**, and fill `last_verified`.
