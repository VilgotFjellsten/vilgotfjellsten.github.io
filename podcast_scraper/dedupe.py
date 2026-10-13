"""Two-layer dedupe: same contact first, then same show."""

from __future__ import annotations

import logging
from collections import defaultdict

from rapidfuzz import fuzz

from podcast_scraper.models import PodcastRow
from podcast_scraper.normalize import canonicalize_url, normalize_email

logger = logging.getLogger(__name__)

TITLE_FUZZ_THRESHOLD = 92


def _merge_field(a: str, b: str) -> str:
    """Prefer non-empty; if both set and differ, keep a and note later."""
    if not a:
        return b
    if not b:
        return a
    return a


def _merge_csv_field(a: str, b: str) -> str:
    parts: list[str] = []
    for raw in (a, b):
        for p in (raw or "").split(","):
            p = p.strip()
            if p and p not in parts:
                parts.append(p)
    return ", ".join(parts)


def merge_rows(primary: PodcastRow, other: PodcastRow) -> PodcastRow:
    """Merge ``other`` into ``primary``, keeping best contact + all platform links."""
    notes = [n for n in (primary.confidence_notes, other.confidence_notes) if n]
    if other.podcast_name and other.podcast_name != primary.podcast_name:
        notes.append(f"merged with '{other.podcast_name}'")

    return PodcastRow(
        podcast_name=primary.podcast_name or other.podcast_name,
        niche=primary.niche or other.niche,
        sub_niche=primary.sub_niche or other.sub_niche,
        description=_merge_field(primary.description, other.description),
        email_official=_merge_field(primary.email_official, other.email_official),
        email_host_derived=_merge_field(
            primary.email_host_derived, other.email_host_derived
        ),
        contact_form_url=_merge_field(primary.contact_form_url, other.contact_form_url),
        website=_merge_field(primary.website, other.website),
        socials=_merge_csv_field(primary.socials, other.socials),
        host_names=_merge_csv_field(primary.host_names, other.host_names),
        platforms_found_on=_merge_csv_field(
            primary.platforms_found_on, other.platforms_found_on
        ),
        source_urls=_merge_csv_field(primary.source_urls, other.source_urls),
        rss_url=_merge_field(primary.rss_url, other.rss_url),
        apple_id=_merge_field(primary.apple_id, other.apple_id),
        podcast_index_id=_merge_field(primary.podcast_index_id, other.podcast_index_id),
        confidence_notes="; ".join(notes),
        do_not_contact=_merge_field(primary.do_not_contact, other.do_not_contact),
    )


def _contact_key(row: PodcastRow) -> str | None:
    email = normalize_email(row.email_official)
    if email:
        return f"email:{email}"
    return None


def _show_keys(row: PodcastRow) -> list[str]:
    keys: list[str] = []
    rss = canonicalize_url(row.rss_url)
    if rss:
        keys.append(f"rss:{rss}")
    if row.apple_id:
        keys.append(f"apple:{row.apple_id.strip()}")
    if row.podcast_index_id:
        keys.append(f"pi:{row.podcast_index_id.strip()}")
    return keys


def _fuzzy_same_show(a: PodcastRow, b: PodcastRow) -> bool:
    """Secondary fuzzy: title + author/host must both be strong."""
    ta = (a.podcast_name or "").strip().lower()
    tb = (b.podcast_name or "").strip().lower()
    if not ta or not tb:
        return False
    if fuzz.token_sort_ratio(ta, tb) < TITLE_FUZZ_THRESHOLD:
        return False
    ha = (a.host_names or "").strip().lower()
    hb = (b.host_names or "").strip().lower()
    if ha and hb:
        return fuzz.token_sort_ratio(ha, hb) >= 90
    # Without author, refuse fuzzy merge (title alone is never enough)
    return False


def dedupe(rows: list[PodcastRow]) -> list[PodcastRow]:
    """Dedupe: same contact → same show (RSS/Apple/PI/fuzzy)."""
    if not rows:
        return []

    # Pass 1: collapse by contact key
    by_contact: dict[str, PodcastRow] = {}
    no_contact: list[PodcastRow] = []
    for row in rows:
        key = _contact_key(row)
        if not key:
            no_contact.append(row)
            continue
        if key in by_contact:
            by_contact[key] = merge_rows(by_contact[key], row)
        else:
            by_contact[key] = row

    pool = list(by_contact.values()) + no_contact

    # Pass 2: collapse by show identity
    show_index: dict[str, int] = {}
    merged: list[PodcastRow] = []

    for row in pool:
        keys = _show_keys(row)
        hit: int | None = None
        for k in keys:
            if k in show_index:
                hit = show_index[k]
                break
        if hit is None:
            # Fuzzy against existing (bounded — O(n^2) ok for niche-sized jobs)
            for idx, existing in enumerate(merged):
                if _fuzzy_same_show(existing, row):
                    hit = idx
                    break

        if hit is None:
            idx = len(merged)
            merged.append(row)
            for k in keys:
                show_index[k] = idx
        else:
            merged[hit] = merge_rows(merged[hit], row)
            for k in _show_keys(merged[hit]):
                show_index[k] = hit

    # Pass 3: if two remaining rows share an email after merges, collapse again
    email_groups: dict[str, list[int]] = defaultdict(list)
    for i, row in enumerate(merged):
        ek = _contact_key(row)
        if ek:
            email_groups[ek].append(i)

    drop: set[int] = set()
    for indices in email_groups.values():
        if len(indices) < 2:
            continue
        primary = indices[0]
        for other in indices[1:]:
            if other in drop:
                continue
            merged[primary] = merge_rows(merged[primary], merged[other])
            drop.add(other)

    result = [r for i, r in enumerate(merged) if i not in drop]
    logger.info("Dedupe: %d → %d rows", len(rows), len(result))
    return result
