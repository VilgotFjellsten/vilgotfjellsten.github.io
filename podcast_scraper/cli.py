"""CLI entrypoint: ``podcast-scraper`` / ``python -m podcast_scraper``."""

from __future__ import annotations

import argparse
import logging
import sys

from podcast_scraper import __version__
from podcast_scraper.niches import PARTITIONS
from podcast_scraper.pipeline import JobConfig, run_job


def build_parser() -> argparse.ArgumentParser:
    known = ", ".join(sorted(PARTITIONS))
    p = argparse.ArgumentParser(
        prog="podcast-scraper",
        description=(
            "Discover niche podcasts with contact info for clipping outreach. "
            "v1: health niche via Podcast Index + Apple + RSS (+ website when thin)."
        ),
    )
    p.add_argument(
        "--job",
        default="health",
        help=f"Niche partition to run. Known: {known} (default: health)",
    )
    p.add_argument(
        "--title-slice",
        default=None,
        help="Optional title prefix slice, e.g. A-F",
    )
    p.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Max candidates to enrich (useful for smoke tests)",
    )
    p.add_argument(
        "--max-per-term",
        type=int,
        default=30,
        help="Max search results per query term (default: 30)",
    )
    p.add_argument(
        "--dump",
        default=None,
        dest="dump_path",
        help="Path to Podcast Index dump (.jsonl / .json / .csv) for offline enum",
    )
    p.add_argument(
        "--sample",
        action="store_true",
        help="Offline sample mode using packaged fixtures (no API keys needed)",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Use fixtures for candidates; skip Apple charts; good for pipeline verify",
    )
    p.add_argument("--skip-apple", action="store_true", help="Skip Apple gap-fill")
    p.add_argument(
        "--skip-podcast-index",
        action="store_true",
        help="Skip Podcast Index enumeration",
    )
    p.add_argument(
        "--skip-website",
        action="store_true",
        help="Skip website contact scrape when RSS email is missing",
    )
    p.add_argument(
        "--skip-charts",
        action="store_true",
        help="Skip Apple genre chart pulls",
    )
    p.add_argument(
        "--output-dir",
        default="output",
        help="Directory for CSV/XLSX exports (default: ./output)",
    )
    p.add_argument(
        "--format",
        dest="formats",
        action="append",
        choices=["csv", "xlsx"],
        default=None,
        help="Export format (repeatable). Default: csv and xlsx",
    )
    p.add_argument(
        "--rss-interval",
        type=float,
        default=0.75,
        help="Seconds between RSS/website requests (default: 0.75)",
    )
    p.add_argument(
        "--dormant-years",
        type=int,
        default=3,
        help="Flag shows with no episode newer than N years (default: 3)",
    )
    p.add_argument(
        "--apple-country",
        default="us",
        help="Apple storefront country code (default: us)",
    )
    p.add_argument("-v", "--verbose", action="store_true", help="Debug logging")
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    formats = tuple(args.formats) if args.formats else ("csv", "xlsx")
    config = JobConfig(
        job=args.job,
        title_slice=args.title_slice,
        limit=args.limit,
        max_per_term=args.max_per_term,
        skip_apple=args.skip_apple,
        skip_podcast_index=args.skip_podcast_index,
        skip_website=args.skip_website,
        skip_charts=args.skip_charts,
        dump_path=args.dump_path,
        sample=args.sample,
        dry_run=args.dry_run,
        dormant_years=args.dormant_years,
        rss_interval=args.rss_interval,
        output_dir=args.output_dir,
        formats=formats,
        apple_country=args.apple_country,
    )

    try:
        result = run_job(config)
    except ValueError as exc:
        logging.error("%s", exc)
        return 2
    except Exception as exc:  # noqa: BLE001
        logging.exception("Job failed: %s", exc)
        return 1

    print(
        f"Job {result.partition.job_id}: {result.candidates} candidates → "
        f"{len(result.rows)} rows after dedupe"
    )
    for path in result.output_paths:
        print(f"  wrote {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
