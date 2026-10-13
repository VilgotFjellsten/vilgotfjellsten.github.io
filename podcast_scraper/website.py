"""Website contact scrape when RSS contact is thin.

Looks for mailto:, contact-page links, and obvious contact forms.
v1: no social-network enrichment.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from podcast_scraper.http_client import HttpClient

logger = logging.getLogger(__name__)

EMAIL_RE = re.compile(r"[A-Z0-9._%+\-]+@[A-Z0-9.\-]+\.[A-Z]{2,}", re.I)
MAILTO_RE = re.compile(r"mailto:([^?\"'\s>]+)", re.I)

CONTACT_HINTS = (
    "contact",
    "about",
    "advertise",
    "sponsorship",
    "sponsor",
    "reach",
    "booking",
    "press",
    "team",
)

SKIP_EMAIL_DOMAINS = {
    "example.com",
    "email.com",
    "domain.com",
    "sentry.io",
    "wixpress.com",
    "squareup.com",
    "schema.org",
}


@dataclass
class WebsiteContact:
    emails: list[str] = field(default_factory=list)
    contact_form_url: str = ""
    contact_page_urls: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


def _normalize_email(email: str) -> str:
    email = email.strip().lower().rstrip(".,;)")
    return email


def _email_ok(email: str) -> bool:
    email = _normalize_email(email)
    if not EMAIL_RE.fullmatch(email):
        return False
    domain = email.split("@", 1)[-1]
    if domain in SKIP_EMAIL_DOMAINS:
        return False
    if email.endswith((".png", ".jpg", ".gif", ".svg", ".webp")):
        return False
    # Skip common template / CDN junk
    if "noreply" in email or "no-reply" in email or "donotreply" in email:
        return False
    return True


def extract_from_html(html: str, base_url: str) -> WebsiteContact:
    soup = BeautifulSoup(html, "lxml")
    found_emails: list[str] = []
    contact_links: list[str] = []
    form_url = ""

    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        text = (a.get_text() or "").strip().lower()
        if href.lower().startswith("mailto:"):
            m = MAILTO_RE.search(href)
            if m and _email_ok(m.group(1)):
                found_emails.append(_normalize_email(m.group(1)))
            continue
        abs_url = urljoin(base_url, href)
        hay = f"{href} {text}".lower()
        if any(h in hay for h in CONTACT_HINTS):
            if abs_url.startswith("http"):
                contact_links.append(abs_url)
                if "contact" in hay and not form_url:
                    form_url = abs_url

    # Visible / script-free email patterns in page text
    text = soup.get_text(" ", strip=True)
    for m in EMAIL_RE.finditer(text):
        if _email_ok(m.group(0)):
            found_emails.append(_normalize_email(m.group(0)))

    # Deduplicate preserving order
    emails = list(dict.fromkeys(found_emails))
    contact_links = list(dict.fromkeys(contact_links))[:5]

    return WebsiteContact(
        emails=emails,
        contact_form_url=form_url,
        contact_page_urls=contact_links,
    )


def scrape_contacts(
    http: HttpClient,
    website_url: str,
    *,
    follow_contact_pages: bool = True,
    max_pages: int = 2,
) -> WebsiteContact:
    """Fetch show website (+ optional contact pages) for emails / forms."""
    if not website_url or not website_url.startswith("http"):
        return WebsiteContact(notes=["no website"])

    try:
        html = http.get_text(website_url)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Website fetch failed for %s: %s", website_url, exc)
        return WebsiteContact(notes=[f"website fetch failed: {exc}"])

    result = extract_from_html(html, website_url)
    pages_fetched = 1

    if follow_contact_pages and not result.emails and result.contact_page_urls:
        for page in result.contact_page_urls:
            if pages_fetched >= max_pages + 1:
                break
            # Stay on same host
            if urlparse(page).netloc != urlparse(website_url).netloc:
                continue
            try:
                page_html = http.get_text(page)
            except Exception as exc:  # noqa: BLE001
                result.notes.append(f"contact page failed: {page} ({exc})")
                continue
            pages_fetched += 1
            sub = extract_from_html(page_html, page)
            for e in sub.emails:
                if e not in result.emails:
                    result.emails.append(e)
            if sub.contact_form_url and not result.contact_form_url:
                result.contact_form_url = sub.contact_form_url
            if result.emails:
                result.notes.append(f"email found on {page}")
                break

    if not result.contact_form_url and result.contact_page_urls:
        result.contact_form_url = result.contact_page_urls[0]

    return result
