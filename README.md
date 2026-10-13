# Podcast outreach scraper (v1)

Discover **health-niche podcasts** with official contact info for clipping outreach.  
One row per podcast → CSV / Excel. **No mass-email sending. No Spotify contact scraping. No host-social enrichment (v2).**

Design: see project `docs/scraper-design.md` (Podcast Index + Apple gap-fill + RSS + website when thin).

## Install

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
# optional editable install for the CLI entrypoint:
pip install -e .
```

Requires Python 3.10+.

## Environment variables

| Variable | Required? | Purpose |
|----------|-----------|---------|
| `PODCAST_INDEX_API_KEY` | For live Podcast Index API runs | Free key from [api.podcastindex.org](https://api.podcastindex.org) |
| `PODCAST_INDEX_API_SECRET` | For live Podcast Index API runs | Pair with the key |

Apple Search / genre charts need **no key**.  
If you have a Podcast Index **database dump**, pass `--dump path/to/feeds.jsonl` and skip the API entirely.

## Quick start (offline sample)

Verifies the full pipeline without downloading millions of feeds:

```bash
python -m podcast_scraper --sample --output-dir output
```

Writes:

- `output/health_podcasts.csv`
- `output/health_podcasts.xlsx`

## Run a health niche scrape (live)

```bash
export PODCAST_INDEX_API_KEY=...
export PODCAST_INDEX_API_SECRET=...

# Full health partition (Podcast Index API + Apple gap-fill + RSS + website)
python -m podcast_scraper --job health --limit 50 --output-dir output

# Sub-slices
python -m podcast_scraper --job health_sleep --limit 30
python -m podcast_scraper --job health_food --limit 30
python -m podcast_scraper --job health_training --limit 30

# Title prefix slice (A–F)
python -m podcast_scraper --job health --title-slice A-F --limit 40

# Offline dump enumeration (no API key)
python -m podcast_scraper --job health --dump ./data/feeds.jsonl --skip-apple --limit 100
```

### Useful flags

| Flag | Meaning |
|------|---------|
| `--sample` | Packaged fixtures only (offline) |
| `--dry-run` | Fixture candidates; skips Apple charts |
| `--limit N` | Cap candidates enriched |
| `--skip-apple` / `--skip-podcast-index` / `--skip-website` | Turn off stages |
| `--skip-charts` | Skip Apple genre chart pulls (~rate-limit friendly) |
| `--rss-interval 0.75` | Polite delay between RSS/website requests |
| `--format csv` / `--format xlsx` | Choose export formats |
| `-v` | Debug logging |

## Output schema

Columns match the design sheet: podcast name, niche/sub-niche, description, official email, host-derived email (empty in v1), contact form URL, website, socials (empty in v1), host names, platforms, source URLs, RSS URL, Apple ID, Podcast Index ID, confidence/notes, do-not-contact.

**Dedupe:** same normalized email first, then same show (RSS URL → Apple ID / Podcast Index ID → fuzzy title+author).

## Package layout

```
podcast_scraper/
  cli.py            # CLI
  pipeline.py       # job orchestration
  sources/          # Podcast Index + Apple
  rss.py            # feed parse (itunes:owner)
  website.py        # mailto / contact-page scrape
  dedupe.py         # contact then show merge
  export.py         # CSV + XLSX
  fixtures/         # sample mode data
```

CLI entrypoint after `pip install -e .`: `podcast-scraper ...`

## Rate limits & etiquette

- Identified `User-Agent` on all HTTP calls
- Apple paced (~17 req/min soft limit)
- Podcast Index ~2 req/s unless using a dump
- RSS/website throttled via `--rss-interval`
- **Spotify is never scraped for contacts**

## License note

Use contact data only for relevant B2B clipping outreach; respect opt-out / suppression (`Do not contact` column reserved).
