"""Apple Podcasts Search API + genre chart gap-fill.

Soft limit ~20 req/min — we pace at ~1 req / 3.5s by default.
Does not scrape Spotify.
"""

from __future__ import annotations

import logging
from typing import Any
from urllib.parse import quote

from podcast_scraper.http_client import HttpClient
from podcast_scraper.models import Candidate
from podcast_scraper.niches import NichePartition, title_in_slice

logger = logging.getLogger(__name__)

ITUNES_SEARCH = "https://itunes.apple.com/search"
ITUNES_LOOKUP = "https://itunes.apple.com/lookup"
# Genre RSS charts (public)
GENRE_CHART = (
    "https://itunes.apple.com/{country}/rss/toppodcasts/limit={limit}/genre={genre}/json"
)


class AppleSource:
    def __init__(
        self,
        http: HttpClient | None = None,
        *,
        country: str = "us",
        min_interval_seconds: float = 3.5,  # ~17/min under Apple's soft limit
    ) -> None:
        self.country = country
        self.http = http or HttpClient(min_interval_seconds=min_interval_seconds)
        self._owns_http = http is None

    def close(self) -> None:
        if self._owns_http:
            self.http.close()

    def search(self, term: str, *, genre_id: int | None = None, limit: int = 50) -> list[dict]:
        params = {
            "term": term,
            "media": "podcast",
            "entity": "podcast",
            "limit": str(min(limit, 200)),
            "country": self.country,
        }
        if genre_id is not None:
            params["genreId"] = str(genre_id)
        qs = "&".join(f"{k}={quote(str(v))}" for k, v in params.items())
        url = f"{ITUNES_SEARCH}?{qs}"
        data = self.http.get_json(url)
        return list(data.get("results") or [])

    def genre_chart(self, genre_id: int, *, limit: int = 50) -> list[dict]:
        url = GENRE_CHART.format(
            country=self.country, limit=min(limit, 200), genre=genre_id
        )
        try:
            data = self.http.get_json(url)
        except Exception as exc:  # noqa: BLE001
            logger.error("Apple genre chart failed for %s: %s", genre_id, exc)
            return []
        entries = (
            data.get("feed", {}).get("entry")
            if isinstance(data, dict)
            else None
        )
        if not entries:
            return []
        if isinstance(entries, dict):
            entries = [entries]
        # Charts don't include feedUrl; resolve via lookup
        ids = []
        for entry in entries:
            raw_id = (
                entry.get("id", {}).get("attributes", {}).get("im:id")
                if isinstance(entry, dict)
                else None
            )
            if raw_id:
                ids.append(str(raw_id))
        return self.lookup_ids(ids)

    def lookup_ids(self, apple_ids: list[str]) -> list[dict]:
        if not apple_ids:
            return []
        results: list[dict] = []
        # lookup allows comma-separated batches of ~20
        for i in range(0, len(apple_ids), 20):
            batch = apple_ids[i : i + 20]
            url = f"{ITUNES_LOOKUP}?id={','.join(batch)}&entity=podcast"
            try:
                data = self.http.get_json(url)
            except Exception as exc:  # noqa: BLE001
                logger.error("Apple lookup failed: %s", exc)
                continue
            for item in data.get("results") or []:
                if item.get("kind") == "podcast" or item.get("wrapperType") == "track":
                    if item.get("feedUrl") or item.get("collectionId"):
                        results.append(item)
        return results

    def enumerate(
        self,
        partition: NichePartition,
        *,
        max_per_term: int = 30,
        chart_limit: int = 50,
        limit: int | None = None,
        skip_charts: bool = False,
    ) -> list[Candidate]:
        logger.info("Enumerating Apple Podcasts for job %s", partition.job_id)
        seen: dict[str, Candidate] = {}

        genre_ids = partition.apple_genre_ids or (1512,)

        # Gap-fill via search terms scoped to health genres
        for term in partition.search_terms or ("health",):
            primary_genre = genre_ids[0]
            try:
                results = self.search(term, genre_id=primary_genre, limit=max_per_term)
            except Exception as exc:  # noqa: BLE001
                logger.error("Apple search failed for %r: %s", term, exc)
                continue
            for item in results:
                cand = self._item_to_candidate(item, partition)
                if not cand.rss_url:
                    continue
                if not title_in_slice(cand.title, partition.title_slice):
                    continue
                key = cand.identity_key()
                if key not in seen:
                    seen[key] = cand
                if limit and len(seen) >= limit:
                    return list(seen.values())

        if not skip_charts:
            for gid in genre_ids[:4]:  # cap chart pulls to stay polite
                if limit and len(seen) >= limit:
                    break
                items = self.genre_chart(gid, limit=chart_limit)
                for item in items:
                    cand = self._item_to_candidate(item, partition, source_note=f"chart:{gid}")
                    if not cand.rss_url:
                        continue
                    if not title_in_slice(cand.title, partition.title_slice):
                        continue
                    key = cand.identity_key()
                    if key not in seen:
                        seen[key] = cand
                    if limit and len(seen) >= limit:
                        return list(seen.values())

        return list(seen.values())

    def _item_to_candidate(
        self,
        item: dict[str, Any],
        partition: NichePartition,
        *,
        source_note: str = "search",
    ) -> Candidate:
        apple_id = item.get("collectionId") or item.get("trackId")
        rss = (item.get("feedUrl") or "").strip()
        title = (item.get("collectionName") or item.get("trackName") or "").strip()
        author = (item.get("artistName") or "").strip()
        website = ""  # Apple search rarely has show website
        genres = [str(g) for g in (item.get("genres") or []) if g]
        desc = ""

        source_urls = [f"apple:{source_note}"]
        if apple_id:
            source_urls.append(f"https://podcasts.apple.com/podcast/id{apple_id}")

        return Candidate(
            title=title,
            rss_url=rss,
            apple_id=str(apple_id) if apple_id else None,
            categories=genres,
            author=author,
            website=website,
            description=desc,
            source="apple",
            source_urls=source_urls,
            platforms=["Apple"],
            niche=partition.niche,
            sub_niche=partition.sub_niche or "",
        )
