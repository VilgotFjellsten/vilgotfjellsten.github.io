"""Podcast Index API + optional local dump enumeration."""

from __future__ import annotations

import csv
import hashlib
import json
import logging
import os
import time
from pathlib import Path
from typing import Iterable, Iterator
from urllib.parse import quote

from podcast_scraper.http_client import HttpClient, USER_AGENT
from podcast_scraper.models import Candidate
from podcast_scraper.niches import NichePartition, title_in_slice

logger = logging.getLogger(__name__)

API_BASE = "https://api.podcastindex.org/api/1.0"


class PodcastIndexSource:
    """Enumerate niche feeds via Podcast Index API and/or a local dump file."""

    def __init__(
        self,
        http: HttpClient | None = None,
        *,
        api_key: str | None = None,
        api_secret: str | None = None,
        dump_path: str | Path | None = None,
    ) -> None:
        self.api_key = api_key or os.environ.get("PODCAST_INDEX_API_KEY", "")
        self.api_secret = api_secret or os.environ.get("PODCAST_INDEX_API_SECRET", "")
        self.dump_path = Path(dump_path) if dump_path else None
        # Podcast Index soft limit is generous; be polite anyway (~2 rps)
        self.http = http or HttpClient(min_interval_seconds=0.5)
        self._owns_http = http is None

    def close(self) -> None:
        if self._owns_http:
            self.http.close()

    @property
    def has_credentials(self) -> bool:
        return bool(self.api_key and self.api_secret)

    def _auth_headers(self) -> dict[str, str]:
        if not self.has_credentials:
            raise RuntimeError(
                "Podcast Index API credentials missing. Set PODCAST_INDEX_API_KEY "
                "and PODCAST_INDEX_API_SECRET (free at https://api.podcastindex.org)."
            )
        epoch = str(int(time.time()))
        token = hashlib.sha1(
            (self.api_key + self.api_secret + epoch).encode("utf-8")
        ).hexdigest()
        return {
            "User-Agent": USER_AGENT,
            "X-Auth-Date": epoch,
            "X-Auth-Key": self.api_key,
            "Authorization": token,
        }

    def _api_get(self, path: str, params: dict[str, str] | None = None) -> dict:
        url = f"{API_BASE}{path}"
        if params:
            qs = "&".join(f"{k}={quote(str(v))}" for k, v in params.items())
            url = f"{url}?{qs}"
        resp = self.http.get(url, headers=self._auth_headers())
        return resp.json()

    def search_by_term(self, term: str, *, max_results: int = 50) -> list[dict]:
        data = self._api_get(
            "/search/byterm",
            {"q": term, "max": str(max_results), "clean": "1"},
        )
        return list(data.get("feeds") or [])

    def feeds_by_category_term(self, term: str, *, max_results: int = 50) -> list[dict]:
        """Use search as category proxy; Podcast Index has no perfect category dump API."""
        return self.search_by_term(term, max_results=max_results)

    def enumerate(
        self,
        partition: NichePartition,
        *,
        max_per_term: int = 40,
        limit: int | None = None,
    ) -> list[Candidate]:
        """Pull candidates for a niche partition.

        Prefers local dump when ``dump_path`` is set; otherwise uses the API.
        """
        if self.dump_path and self.dump_path.exists():
            logger.info("Enumerating Podcast Index from dump %s", self.dump_path)
            return list(
                self._from_dump(partition, limit=limit)
            )

        if not self.has_credentials:
            logger.warning(
                "No Podcast Index credentials and no dump; skipping PI enumeration"
            )
            return []

        logger.info("Enumerating Podcast Index via API for job %s", partition.job_id)
        seen: dict[str, Candidate] = {}
        terms = partition.search_terms or ("health",)
        for term in terms:
            try:
                feeds = self.search_by_term(term, max_results=max_per_term)
            except Exception as exc:  # noqa: BLE001 — continue other terms
                logger.error("Podcast Index search failed for %r: %s", term, exc)
                continue
            for feed in feeds:
                cand = self._feed_to_candidate(feed, partition)
                if not cand.rss_url:
                    continue
                if not title_in_slice(cand.title, partition.title_slice):
                    continue
                if not self._matches_categories(cand, partition):
                    # Keep search hits even if category labels are thin — search term
                    # already scoped the niche; category filter only drops clear mismatches
                    # when categories are present and none overlap.
                    if cand.categories and not self._category_overlap(cand, partition):
                        continue
                key = cand.identity_key()
                if key not in seen:
                    seen[key] = cand
                if limit and len(seen) >= limit:
                    return list(seen.values())
        return list(seen.values())

    def _matches_categories(self, cand: Candidate, partition: NichePartition) -> bool:
        if not partition.podcast_index_categories:
            return True
        if not cand.categories:
            return True
        return self._category_overlap(cand, partition)

    def _category_overlap(self, cand: Candidate, partition: NichePartition) -> bool:
        wanted = {c.lower() for c in partition.podcast_index_categories}
        have = {c.lower() for c in cand.categories}
        return bool(wanted & have)

    def _feed_to_candidate(self, feed: dict, partition: NichePartition) -> Candidate:
        cats: list[str] = []
        raw_cats = feed.get("categories") or {}
        if isinstance(raw_cats, dict):
            cats = [str(v) for v in raw_cats.values()]
        elif isinstance(raw_cats, list):
            cats = [str(c) for c in raw_cats]

        rss = (feed.get("url") or feed.get("originalUrl") or "").strip()
        itunes_id = feed.get("itunesId") or feed.get("itunes_id")
        pi_id = feed.get("id")
        title = (feed.get("title") or "").strip()
        author = (feed.get("author") or feed.get("ownerName") or "").strip()
        website = (feed.get("link") or "").strip()
        desc = (feed.get("description") or "").strip()

        platforms = ["Podcast Index"]
        if itunes_id:
            platforms.append("Apple")

        source_urls = [f"podcastindex:feed:{pi_id}"] if pi_id else ["podcastindex:api"]
        if itunes_id:
            source_urls.append(f"https://podcasts.apple.com/podcast/id{itunes_id}")

        return Candidate(
            title=title,
            rss_url=rss,
            apple_id=str(itunes_id) if itunes_id else None,
            podcast_index_id=int(pi_id) if pi_id is not None else None,
            podcast_index_guid=str(feed.get("podcastGuid") or "") or None,
            categories=cats,
            author=author,
            website=website,
            description=desc[:500],
            source="podcast_index",
            source_urls=source_urls,
            platforms=platforms,
            niche=partition.niche,
            sub_niche=partition.sub_niche or "",
        )

    def _from_dump(
        self, partition: NichePartition, *, limit: int | None = None
    ) -> Iterator[Candidate]:
        """Read a Podcast Index dump.

        Supports:
        - JSONL (one feed object per line)
        - JSON array of feeds
        - CSV with at least title,url columns (optional: itunesId,id,categories,author,link)
        """
        path = self.dump_path
        assert path is not None
        suffix = path.suffix.lower()
        count = 0

        if suffix == ".jsonl":
            with path.open("r", encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    feed = json.loads(line)
                    cand = self._feed_to_candidate(feed, partition)
                    if self._dump_keep(cand, partition):
                        yield cand
                        count += 1
                        if limit and count >= limit:
                            return
        elif suffix == ".json":
            data = json.loads(path.read_text(encoding="utf-8"))
            feeds: Iterable[dict]
            if isinstance(data, dict) and "feeds" in data:
                feeds = data["feeds"]
            elif isinstance(data, list):
                feeds = data
            else:
                raise ValueError(f"Unrecognized dump JSON shape in {path}")
            for feed in feeds:
                cand = self._feed_to_candidate(feed, partition)
                if self._dump_keep(cand, partition):
                    yield cand
                    count += 1
                    if limit and count >= limit:
                        return
        elif suffix == ".csv":
            with path.open("r", encoding="utf-8", newline="") as fh:
                reader = csv.DictReader(fh)
                for row in reader:
                    feed = {
                        "title": row.get("title") or row.get("Title") or "",
                        "url": row.get("url") or row.get("rss") or row.get("feedUrl") or "",
                        "itunesId": row.get("itunesId") or row.get("apple_id") or "",
                        "id": row.get("id") or row.get("podcast_index_id") or None,
                        "author": row.get("author") or "",
                        "link": row.get("link") or row.get("website") or "",
                        "description": row.get("description") or "",
                        "categories": _parse_cats(row.get("categories") or ""),
                    }
                    if feed["id"] in ("", None):
                        feed["id"] = None
                    cand = self._feed_to_candidate(feed, partition)
                    if self._dump_keep(cand, partition):
                        yield cand
                        count += 1
                        if limit and count >= limit:
                            return
        else:
            raise ValueError(f"Unsupported dump format: {path} (use .jsonl, .json, or .csv)")

    def _dump_keep(self, cand: Candidate, partition: NichePartition) -> bool:
        if not cand.rss_url:
            return False
        if not title_in_slice(cand.title, partition.title_slice):
            return False
        # For dump enumeration, require category overlap when categories exist
        if cand.categories:
            return self._category_overlap(cand, partition)
        # If no categories on record, fall back to title keyword hint from search terms
        title_l = cand.title.lower()
        return any(t.lower() in title_l for t in partition.search_terms)


def _parse_cats(raw: str) -> dict[str, str]:
    if not raw:
        return {}
    if raw.strip().startswith("{"):
        try:
            data = json.loads(raw)
            if isinstance(data, dict):
                return {str(k): str(v) for k, v in data.items()}
        except json.JSONDecodeError:
            pass
    parts = [p.strip() for p in raw.replace("|", ",").split(",") if p.strip()]
    return {str(i): p for i, p in enumerate(parts)}
