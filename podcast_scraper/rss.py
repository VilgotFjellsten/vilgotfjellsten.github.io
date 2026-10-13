"""RSS feed fetch + parse: itunes:owner email, author, website, categories."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any

import feedparser

from podcast_scraper.http_client import HttpClient

logger = logging.getLogger(__name__)

EMAIL_RE = re.compile(r"[A-Z0-9._%+\-]+@[A-Z0-9.\-]+\.[A-Z]{2,}", re.I)


@dataclass
class RssMeta:
    title: str = ""
    description: str = ""
    author: str = ""
    owner_name: str = ""
    owner_email: str = ""
    website: str = ""
    categories: list[str] = field(default_factory=list)
    last_published: datetime | None = None
    image_url: str = ""
    raw_ok: bool = False
    error: str = ""


def _first(*vals: Any) -> str:
    for v in vals:
        if isinstance(v, str) and v.strip():
            return v.strip()
        if isinstance(v, dict):
            # feedparser sometimes nests
            for key in ("email", "name", "href", "content", "value"):
                if key in v and isinstance(v[key], str) and v[key].strip():
                    return v[key].strip()
    return ""


def _extract_owner(feed: dict) -> tuple[str, str]:
    """Return (owner_name, owner_email) from itunes:owner / managingEditor."""
    name = ""
    email = ""

    owner = feed.get("publisher_detail") or feed.get("itunes_owner") or {}
    if isinstance(owner, dict):
        name = _first(owner.get("name"), owner.get("email"))
        # feedparser maps itunes:owner email oddly; try common keys
        email = _first(owner.get("email"), owner.get("href"))

    # Explicit itunes_* attrs some versions expose
    email = _first(email, feed.get("itunes_owner_email"), feed.get("owner_email"))
    name = _first(
        feed.get("itunes_owner_name"),
        feed.get("publisher"),
        feed.get("author"),
        name,
    )

    # managingEditor often "email (Name)" or "email"
    managing = _first(feed.get("managingEditor"), feed.get("managing_editor"))
    if managing:
        m = EMAIL_RE.search(managing)
        if m and not email:
            email = m.group(0)
        if "(" in managing and ")" in managing and not name:
            name = managing[managing.find("(") + 1 : managing.rfind(")")].strip()

    if email and not EMAIL_RE.fullmatch(email):
        m = EMAIL_RE.search(email)
        email = m.group(0) if m else ""

    return name, email.lower() if email else ""


def _parse_date(entry: dict) -> datetime | None:
    for key in ("published", "updated", "created"):
        raw = entry.get(key)
        if not raw:
            continue
        try:
            dt = parsedate_to_datetime(raw)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except (TypeError, ValueError, IndexError):
            continue
    parsed = entry.get("published_parsed") or entry.get("updated_parsed")
    if parsed:
        try:
            return datetime(*parsed[:6], tzinfo=timezone.utc)
        except (TypeError, ValueError):
            return None
    return None


def _owner_from_raw_xml(content: bytes | str) -> tuple[str, str]:
    """Fallback: pull itunes:owner name/email with a light regex (namespace-safe)."""
    text = content.decode("utf-8", errors="replace") if isinstance(content, bytes) else content
    name = ""
    email = ""
    # Match <itunes:owner>...</itunes:owner> or default-ns equivalents
    block = re.search(
        r"<([a-zA-Z0-9_]+\:)?owner\b[^>]*>(.*?)</\1?owner>",
        text,
        re.I | re.S,
    )
    if block:
        inner = block.group(2)
        m_email = re.search(
            r"<([a-zA-Z0-9_]+\:)?email\b[^>]*>(.*?)</\1?email>",
            inner,
            re.I | re.S,
        )
        m_name = re.search(
            r"<([a-zA-Z0-9_]+\:)?name\b[^>]*>(.*?)</\1?name>",
            inner,
            re.I | re.S,
        )
        if m_email:
            email = re.sub(r"<[^>]+>", "", m_email.group(2)).strip()
        if m_name:
            name = re.sub(r"<[^>]+>", "", m_name.group(2)).strip()
    if email:
        m = EMAIL_RE.search(email)
        email = m.group(0).lower() if m else ""
    return name, email


def parse_rss_bytes(content: bytes | str, *, source_url: str = "") -> RssMeta:
    """Parse RSS/Atom content into RssMeta."""
    parsed = feedparser.parse(content)
    feed = parsed.feed or {}
    if parsed.bozo and not feed:
        err = getattr(parsed, "bozo_exception", None)
        return RssMeta(error=f"parse error: {err}", raw_ok=False)

    owner_name, owner_email = _extract_owner(feed)

    # Also scan itunes:owner in tags if feedparser missed it
    if not owner_email and hasattr(parsed, "feed"):
        for key, val in list(feed.items()):
            if "owner" in key.lower() and isinstance(val, str):
                m = EMAIL_RE.search(val)
                if m:
                    owner_email = m.group(0).lower()

    if not owner_email:
        raw_name, raw_email = _owner_from_raw_xml(content)
        owner_email = owner_email or raw_email
        owner_name = owner_name or raw_name

    cats: list[str] = []
    for tag in feed.get("tags") or []:
        term = tag.get("term") if isinstance(tag, dict) else None
        if term:
            cats.append(str(term))
    itunes_cat = feed.get("itunes_category") or feed.get("category")
    if isinstance(itunes_cat, str):
        cats.append(itunes_cat)
    elif isinstance(itunes_cat, list):
        for c in itunes_cat:
            if isinstance(c, dict):
                cats.append(str(c.get("text") or c.get("term") or ""))
            elif c:
                cats.append(str(c))

    website = _first(feed.get("link"), feed.get("href"), source_url)
    title = _first(feed.get("title"))
    desc = _first(feed.get("subtitle"), feed.get("summary"), feed.get("description"))
    if len(desc) > 800:
        desc = desc[:797] + "..."
    author = _first(feed.get("itunes_author"), owner_name, feed.get("author"))
    # Prefer a human name over a bare email / "email (Name)" managingEditor form
    if author and EMAIL_RE.fullmatch(author.strip()):
        author = owner_name or ""
    if author and "@" in author and "(" in author and ")" in author:
        author = author[author.find("(") + 1 : author.rfind(")")].strip() or author


    last_pub: datetime | None = None
    for entry in parsed.entries[:5]:
        dt = _parse_date(entry)
        if dt and (last_pub is None or dt > last_pub):
            last_pub = dt

    image = ""
    img = feed.get("image")
    if isinstance(img, dict):
        image = _first(img.get("href"), img.get("url"))
    image = _first(image, feed.get("itunes_image"))

    return RssMeta(
        title=title,
        description=desc,
        author=author,
        owner_name=owner_name,
        owner_email=owner_email,
        website=website if website.startswith("http") else "",
        categories=[c for c in cats if c],
        last_published=last_pub,
        image_url=image if isinstance(image, str) else "",
        raw_ok=True,
    )


def fetch_and_parse(http: HttpClient, rss_url: str) -> RssMeta:
    try:
        content = http.get_bytes(rss_url)
    except Exception as exc:  # noqa: BLE001
        logger.warning("RSS fetch failed for %s: %s", rss_url, exc)
        return RssMeta(error=str(exc), raw_ok=False)
    return parse_rss_bytes(content, source_url=rss_url)
