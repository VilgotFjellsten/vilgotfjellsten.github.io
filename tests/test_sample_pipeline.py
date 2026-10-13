"""Smoke tests against packaged fixtures (no network)."""

from __future__ import annotations

from pathlib import Path

from podcast_scraper.dedupe import dedupe
from podcast_scraper.models import PodcastRow
from podcast_scraper.pipeline import JobConfig, run_job
from podcast_scraper.rss import parse_rss_bytes
from podcast_scraper.website import extract_from_html


FIXTURES = Path(__file__).resolve().parents[1] / "podcast_scraper" / "fixtures"


def test_rss_owner_email():
    xml = (FIXTURES / "feeds" / "sleep-science.xml").read_bytes()
    meta = parse_rss_bytes(xml)
    assert meta.raw_ok
    assert meta.owner_email == "ava.rest@sleepscience.example"
    assert "Ava" in meta.owner_name or "Ava" in meta.author


def test_website_mailto():
    html = (FIXTURES / "websites" / "thin-contact.html").read_text(encoding="utf-8")
    contact = extract_from_html(html, "https://example-fixtures.local/sites/thin-contact")
    assert "casey@thincontact.example" in contact.emails


def test_dedupe_same_rss_and_email():
    a = PodcastRow(
        podcast_name="Training Lab Podcast",
        email_official="sam@traininglab.example",
        rss_url="https://example-fixtures.local/feeds/training-lab.xml",
        apple_id="100003",
        host_names="Sam Peak",
        platforms_found_on="Apple",
    )
    b = PodcastRow(
        podcast_name="Training Lab Podcast",
        email_official="sam@traininglab.example",
        rss_url="https://example-fixtures.local/feeds/training-lab.xml",
        apple_id="100003",
        host_names="Sam Peak",
        platforms_found_on="Podcast Index",
        source_urls="dup",
    )
    out = dedupe([a, b])
    assert len(out) == 1
    assert "Podcast Index" in out[0].platforms_found_on
    assert "Apple" in out[0].platforms_found_on


def test_sample_job(tmp_path: Path):
    result = run_job(
        JobConfig(
            job="health",
            sample=True,
            output_dir=str(tmp_path),
            formats=("csv", "xlsx"),
        )
    )
    assert result.candidates >= 4
    # Duplicate Training Lab collapsed
    assert len(result.rows) == 4
    emails = {r.email_official for r in result.rows}
    assert "ava.rest@sleepscience.example" in emails
    assert "casey@thincontact.example" in emails  # from website fixture
    assert (tmp_path / "health_podcasts.csv").exists()
    assert (tmp_path / "health_podcasts.xlsx").exists()
