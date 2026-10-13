"""End-to-end discovery pipeline for a niche partition job."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from podcast_scraper.dedupe import dedupe
from podcast_scraper.export import export
from podcast_scraper.http_client import HttpClient
from podcast_scraper.models import Candidate, PodcastRow
from podcast_scraper.niches import NichePartition, get_partition
from podcast_scraper.normalize import (
    canonicalize_url,
    map_sub_niche,
    normalize_email,
)
from podcast_scraper.rss import RssMeta, fetch_and_parse, parse_rss_bytes
from podcast_scraper.sources.apple import AppleSource
from podcast_scraper.sources.podcast_index import PodcastIndexSource
from podcast_scraper.website import scrape_contacts

logger = logging.getLogger(__name__)

PACKAGE_DIR = Path(__file__).resolve().parent
FIXTURES_DIR = PACKAGE_DIR / "fixtures"


@dataclass
class JobConfig:
    job: str = "health"
    title_slice: str | None = None
    limit: int | None = None
    max_per_term: int = 30
    skip_apple: bool = False
    skip_podcast_index: bool = False
    skip_website: bool = False
    skip_charts: bool = False
    dump_path: str | None = None
    sample: bool = False  # use packaged fixtures only
    dry_run: bool = False  # enumerate + parse fixtures / limit; no website if sample
    dormant_years: int = 3
    rss_interval: float = 0.75
    output_dir: str = "output"
    formats: tuple[str, ...] = ("csv", "xlsx")
    apple_country: str = "us"


@dataclass
class JobResult:
    partition: NichePartition
    candidates: int = 0
    rows: list[PodcastRow] = field(default_factory=list)
    output_paths: list[Path] = field(default_factory=list)


def merge_candidates(candidates: list[Candidate]) -> list[Candidate]:
    """Merge enumeration hits that share RSS / Apple / PI identity."""
    by_key: dict[str, Candidate] = {}
    for cand in candidates:
        key = cand.identity_key()
        if key not in by_key:
            by_key[key] = cand
            continue
        existing = by_key[key]
        # Prefer richer record
        if not existing.rss_url and cand.rss_url:
            existing.rss_url = cand.rss_url
        if not existing.apple_id and cand.apple_id:
            existing.apple_id = cand.apple_id
        if existing.podcast_index_id is None and cand.podcast_index_id is not None:
            existing.podcast_index_id = cand.podcast_index_id
        for p in cand.platforms:
            if p not in existing.platforms:
                existing.platforms.append(p)
        for u in cand.source_urls:
            if u not in existing.source_urls:
                existing.source_urls.append(u)
        if not existing.description and cand.description:
            existing.description = cand.description
        if not existing.author and cand.author:
            existing.author = cand.author
        if not existing.website and cand.website:
            existing.website = cand.website
        for c in cand.categories:
            if c not in existing.categories:
                existing.categories.append(c)
    return list(by_key.values())


def load_sample_candidates(partition: NichePartition) -> list[Candidate]:
    """Load packaged fixture candidates for dry-run / sample mode."""
    path = FIXTURES_DIR / "sample_candidates.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    out: list[Candidate] = []
    for item in data:
        out.append(
            Candidate(
                title=item.get("title", ""),
                rss_url=item.get("rss_url", ""),
                apple_id=item.get("apple_id"),
                podcast_index_id=item.get("podcast_index_id"),
                categories=list(item.get("categories") or []),
                author=item.get("author", ""),
                website=item.get("website", ""),
                description=item.get("description", ""),
                source=item.get("source", "fixture"),
                source_urls=list(item.get("source_urls") or ["fixture"]),
                platforms=list(item.get("platforms") or ["fixture"]),
                niche=partition.niche,
                sub_niche=partition.sub_niche or item.get("sub_niche", ""),
            )
        )
    return out


def _dormant_note(meta: RssMeta, dormant_years: int) -> str:
    if not meta.last_published:
        return ""
    age = datetime.now(timezone.utc) - meta.last_published
    if age.days > dormant_years * 365:
        return f"dormant since {meta.last_published.date().isoformat()}"
    return ""


def enrich_candidate(
    cand: Candidate,
    *,
    http: HttpClient,
    partition: NichePartition,
    skip_website: bool,
    dormant_years: int,
    fixture_rss: dict[str, Path] | None = None,
) -> PodcastRow:
    notes: list[str] = []
    meta: RssMeta

    rss_url = canonicalize_url(cand.rss_url)
    if fixture_rss and rss_url in fixture_rss:
        meta = parse_rss_bytes(fixture_rss[rss_url].read_bytes(), source_url=rss_url)
        notes.append("rss from fixture")
    elif fixture_rss and cand.rss_url in fixture_rss:
        meta = parse_rss_bytes(
            fixture_rss[cand.rss_url].read_bytes(), source_url=cand.rss_url
        )
        notes.append("rss from fixture")
    elif rss_url:
        meta = fetch_and_parse(http, rss_url)
        if meta.error:
            notes.append(f"rss error: {meta.error}")
    else:
        meta = RssMeta(error="no rss url")
        notes.append("missing rss url")

    title = meta.title or cand.title
    description = meta.description or cand.description
    website = canonicalize_url(meta.website or cand.website)
    host = meta.owner_name or meta.author or cand.author
    email = normalize_email(meta.owner_email)
    contact_form = ""

    if email:
        notes.append("official email from itunes:owner / RSS")
    elif not skip_website and website:
        contact = scrape_contacts(http, website)
        notes.extend(contact.notes)
        if contact.emails:
            email = normalize_email(contact.emails[0])
            notes.append("official email from website")
        contact_form = contact.contact_form_url
        if not email and contact_form:
            notes.append("no email; contact form/page found")
        elif not email:
            notes.append("thin contact; no email found (v1: no social enrichment)")
    else:
        if not email:
            notes.append("thin contact; website scrape skipped or unavailable")

    dormant = _dormant_note(meta, dormant_years)
    if dormant:
        notes.append(dormant)

    cats = list(dict.fromkeys((meta.categories or []) + cand.categories))
    sub = map_sub_niche(cats, partition.sub_niche or cand.sub_niche, description)

    platforms = list(dict.fromkeys(cand.platforms))
    # Presence markers only — never scrape Spotify for contacts
    if cand.apple_id and "Apple" not in platforms:
        platforms.append("Apple")

    return PodcastRow(
        podcast_name=title,
        niche=partition.niche,
        sub_niche=sub,
        description=description,
        email_official=email,
        email_host_derived="",  # v2
        contact_form_url=contact_form,
        website=website,
        socials="",  # v2
        host_names=host,
        platforms_found_on=", ".join(platforms),
        source_urls=", ".join(cand.source_urls),
        rss_url=rss_url or cand.rss_url,
        apple_id=cand.apple_id or "",
        podcast_index_id=str(cand.podcast_index_id) if cand.podcast_index_id else "",
        confidence_notes="; ".join(n for n in notes if n),
    )


def _fixture_rss_map() -> dict[str, Path]:
    """Map fixture RSS URLs (and local keys) to files."""
    mapping_path = FIXTURES_DIR / "rss_map.json"
    if not mapping_path.exists():
        return {}
    raw = json.loads(mapping_path.read_text(encoding="utf-8"))
    out: dict[str, Path] = {}
    for url, rel in raw.items():
        out[url] = FIXTURES_DIR / rel
        out[canonicalize_url(url)] = FIXTURES_DIR / rel
    return out


def run_job(config: JobConfig) -> JobResult:
    partition = get_partition(config.job, config.title_slice)
    logger.info("Starting job %s", partition.job_id)

    candidates: list[Candidate] = []
    fixture_rss: dict[str, Path] | None = None

    if config.sample or config.dry_run:
        logger.info("Sample/dry-run mode — using packaged fixtures")
        candidates.extend(load_sample_candidates(partition))
        fixture_rss = _fixture_rss_map()
        # dry_run may still hit live Apple/PI if explicitly requested; sample stays offline
        if config.sample:
            config.skip_apple = True
            config.skip_podcast_index = True

    http = HttpClient(min_interval_seconds=config.rss_interval)
    try:
        if not config.skip_podcast_index and not config.sample:
            pi = PodcastIndexSource(http=http, dump_path=config.dump_path)
            try:
                pi_limit = config.limit
                candidates.extend(
                    pi.enumerate(
                        partition,
                        max_per_term=config.max_per_term,
                        limit=pi_limit,
                    )
                )
            finally:
                # shared http — don't close
                pass

        if not config.skip_apple and not config.sample:
            remaining = None
            if config.limit is not None:
                remaining = max(0, config.limit - len(candidates))
            apple = AppleSource(country=config.apple_country)
            try:
                candidates.extend(
                    apple.enumerate(
                        partition,
                        max_per_term=min(config.max_per_term, 25),
                        chart_limit=min(50, config.max_per_term * 2),
                        limit=remaining if remaining is not None else config.limit,
                        skip_charts=config.skip_charts or config.dry_run,
                    )
                )
            finally:
                apple.close()

        candidates = merge_candidates(candidates)
        if config.limit is not None:
            candidates = candidates[: config.limit]

        logger.info("Enriching %d candidates", len(candidates))
        rows: list[PodcastRow] = []
        website_fixtures = FIXTURES_DIR / "websites"
        # Sample mode never hits the network for websites — fixtures only.
        skip_website = config.skip_website or config.sample
        for cand in candidates:
            row = enrich_candidate(
                cand,
                http=http,
                partition=partition,
                skip_website=skip_website,
                dormant_years=config.dormant_years,
                fixture_rss=fixture_rss,
            )
            if (
                config.sample
                and not row.email_official
                and cand.website
                and website_fixtures.exists()
            ):
                from podcast_scraper.website import extract_from_html

                slug = cand.website.rstrip("/").split("/")[-1] or "site"
                html_path = website_fixtures / f"{slug}.html"
                if html_path.exists():
                    contact = extract_from_html(
                        html_path.read_text(encoding="utf-8"), cand.website
                    )
                    if contact.emails:
                        row.email_official = normalize_email(contact.emails[0])
                        note = "official email from website fixture"
                        row.confidence_notes = (
                            f"{row.confidence_notes}; {note}"
                            if row.confidence_notes
                            else note
                        )
                    if contact.contact_form_url:
                        row.contact_form_url = contact.contact_form_url
            rows.append(row)

        rows = dedupe(rows)
        out_dir = Path(config.output_dir)
        paths = export(rows, out_dir, job_id=partition.job_id, formats=config.formats)
        return JobResult(
            partition=partition,
            candidates=len(candidates),
            rows=rows,
            output_paths=paths,
        )
    finally:
        http.close()
