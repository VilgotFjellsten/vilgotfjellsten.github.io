"""Shared HTTP client: polite User-Agent, rate limiting, retries."""

from __future__ import annotations

import logging
import time
from typing import Any

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

logger = logging.getLogger(__name__)

USER_AGENT = (
    "PodcastOutreachScraper/0.1 (+https://github.com/VilgotFjellsten/"
    "vilgotfjellsten.github.io; research/clipping-outreach; polite bot)"
)


class RateLimiter:
    """Simple token-bucket style minimum-interval limiter."""

    def __init__(self, min_interval_seconds: float) -> None:
        self.min_interval = max(0.0, min_interval_seconds)
        self._last = 0.0

    def wait(self) -> None:
        if self.min_interval <= 0:
            return
        now = time.monotonic()
        elapsed = now - self._last
        if elapsed < self.min_interval:
            time.sleep(self.min_interval - elapsed)
        self._last = time.monotonic()


class HttpClient:
    def __init__(
        self,
        *,
        min_interval_seconds: float = 0.5,
        timeout: float = 30.0,
        headers: dict[str, str] | None = None,
    ) -> None:
        self.limiter = RateLimiter(min_interval_seconds)
        base_headers = {"User-Agent": USER_AGENT, "Accept": "*/*"}
        if headers:
            base_headers.update(headers)
        self._client = httpx.Client(
            headers=base_headers,
            timeout=timeout,
            follow_redirects=True,
        )

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> HttpClient:
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()

    @retry(
        retry=retry_if_exception_type((httpx.TransportError, httpx.TimeoutException)),
        wait=wait_exponential(multiplier=1, min=1, max=20),
        stop=stop_after_attempt(3),
        reraise=True,
    )
    def get(self, url: str, **kwargs: Any) -> httpx.Response:
        self.limiter.wait()
        logger.debug("GET %s", url)
        resp = self._client.get(url, **kwargs)
        if resp.status_code == 429:
            retry_after = float(resp.headers.get("Retry-After", "5"))
            logger.warning("429 from %s; sleeping %.1fs", url, retry_after)
            time.sleep(retry_after)
            self.limiter.wait()
            resp = self._client.get(url, **kwargs)
        resp.raise_for_status()
        return resp

    def get_text(self, url: str, **kwargs: Any) -> str:
        return self.get(url, **kwargs).text

    def get_bytes(self, url: str, **kwargs: Any) -> bytes:
        return self.get(url, **kwargs).content

    def get_json(self, url: str, **kwargs: Any) -> Any:
        return self.get(url, **kwargs).json()
