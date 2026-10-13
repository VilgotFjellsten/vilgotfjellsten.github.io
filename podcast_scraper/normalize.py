"""Normalize emails, URLs, and niche labels."""

from __future__ import annotations

import re
from urllib.parse import urlparse, urlunparse

EMAIL_RE = re.compile(r"^[A-Z0-9._%+\-]+@[A-Z0-9.\-]+\.[A-Z]{2,}$", re.I)


def normalize_email(email: str | None) -> str:
    if not email:
        return ""
    email = email.strip().lower().rstrip(".,;)>")
    if email.startswith("mailto:"):
        email = email[7:]
    if not EMAIL_RE.match(email):
        return ""
    return email


def canonicalize_url(url: str | None) -> str:
    if not url:
        return ""
    url = url.strip()
    if not url:
        return ""
    if url.startswith("//"):
        url = "https:" + url
    parsed = urlparse(url)
    if not parsed.scheme:
        url = "https://" + url
        parsed = urlparse(url)
    # Drop fragments; keep query (some feeds need it)
    cleaned = parsed._replace(fragment="")
    # Normalize host lowercase; strip trailing slash on path-only roots
    netloc = cleaned.netloc.lower()
    path = cleaned.path or ""
    if path == "/":
        path = ""
    return urlunparse(cleaned._replace(netloc=netloc, path=path))


def map_sub_niche(categories: list[str], partition_sub: str, description: str = "") -> str:
    """Map categories onto our sub-niche labels when partition is broad health."""
    if partition_sub:
        return partition_sub

    blob = " ".join(categories).lower() + " " + (description or "").lower()
    rules = [
        ("sleep", ("sleep", "insomnia", "circadian")),
        ("food", ("nutrition", "diet", "food", "eating", "weight")),
        ("training", ("fitness", "training", "workout", "exercise", "gym", "strength")),
        ("mental", ("mental", "therapy", "anxiety", "depression", "mindfulness")),
        ("medicine", ("medicine", "medical", "doctor", "clinical")),
    ]
    for label, keys in rules:
        if any(k in blob for k in keys):
            return label
    return ""
