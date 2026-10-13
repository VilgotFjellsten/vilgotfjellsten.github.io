"""Core data models for the discovery pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any


@dataclass
class Candidate:
    """A show discovered from an enumeration source (pre-RSS enrich)."""

    title: str = ""
    rss_url: str = ""
    apple_id: str | None = None
    podcast_index_id: int | None = None
    podcast_index_guid: str | None = None
    categories: list[str] = field(default_factory=list)
    author: str = ""
    website: str = ""
    description: str = ""
    source: str = ""  # podcast_index | apple | fixture
    source_urls: list[str] = field(default_factory=list)
    platforms: list[str] = field(default_factory=list)
    niche: str = "health"
    sub_niche: str = ""

    def identity_key(self) -> str:
        if self.rss_url:
            return f"rss:{self.rss_url.strip().lower()}"
        if self.apple_id:
            return f"apple:{self.apple_id}"
        if self.podcast_index_id is not None:
            return f"pi:{self.podcast_index_id}"
        return f"title:{self.title.strip().lower()}"


@dataclass
class PodcastRow:
    """One spreadsheet row — a podcast with contact info."""

    podcast_name: str = ""
    niche: str = "health"
    sub_niche: str = ""
    description: str = ""
    email_official: str = ""
    email_host_derived: str = ""  # reserved; v1 leaves empty
    contact_form_url: str = ""
    website: str = ""
    socials: str = ""  # reserved; v1 may capture show-level only if found on site
    host_names: str = ""
    platforms_found_on: str = ""
    source_urls: str = ""
    rss_url: str = ""
    apple_id: str = ""
    podcast_index_id: str = ""
    confidence_notes: str = ""
    do_not_contact: str = ""  # reserved for suppression

    def to_export_dict(self) -> dict[str, Any]:
        return {
            "Podcast name": self.podcast_name,
            "Niche / sub-niche": f"{self.niche} / {self.sub_niche}".strip(" /"),
            "Description": self.description,
            "Email (official)": self.email_official,
            "Email (host-derived)": self.email_host_derived,
            "Contact form URL": self.contact_form_url,
            "Website": self.website,
            "Socials": self.socials,
            "Host name(s)": self.host_names,
            "Platforms found on": self.platforms_found_on,
            "Source URLs": self.source_urls,
            "RSS URL": self.rss_url,
            "Apple ID": self.apple_id,
            "Podcast Index ID": self.podcast_index_id,
            "Confidence / notes": self.confidence_notes,
            "Do not contact": self.do_not_contact,
        }

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
