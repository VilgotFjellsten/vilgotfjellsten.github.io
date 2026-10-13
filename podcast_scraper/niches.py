"""Niche partitions for controllable jobs."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class NichePartition:
    """A controllable scrape job partition."""

    niche: str
    sub_niche: str | None = None
    # Podcast Index category names (case-insensitive match against feed categories)
    podcast_index_categories: tuple[str, ...] = ()
    # Search terms for Podcast Index API / Apple Search
    search_terms: tuple[str, ...] = ()
    # Apple Podcasts genre IDs
    apple_genre_ids: tuple[int, ...] = ()
    # Optional title prefix slice, e.g. ("A", "F") for A–F
    title_slice: tuple[str, str] | None = None

    @property
    def job_id(self) -> str:
        parts = [self.niche]
        if self.sub_niche:
            parts.append(self.sub_niche)
        if self.title_slice:
            parts.append(f"{self.title_slice[0]}-{self.title_slice[1]}")
        return "_".join(parts)


# Apple: Health & Fitness = 1512; common subgenres
# https://podcasts.apple.com/us/genre/podcasts-health-fitness/id1512
APPLE_HEALTH_FITNESS = 1512
APPLE_HEALTH_SUBGENRES = (
    1512,  # Health & Fitness (parent)
    1513,  # Alternative Health
    1514,  # Fitness
    1515,  # Medicine
    1516,  # Mental Health
    1517,  # Nutrition
    1518,  # Sexuality
)


HEALTH = NichePartition(
    niche="health",
    podcast_index_categories=(
        "Health",
        "Health & Fitness",
        "Fitness",
        "Medicine",
        "Mental Health",
        "Nutrition",
        "Alternative Health",
        "Self-Improvement",
    ),
    search_terms=(
        "health",
        "fitness",
        "nutrition",
        "wellness",
        "mental health",
        "medicine",
        "sleep",
        "training",
        "diet",
    ),
    apple_genre_ids=APPLE_HEALTH_SUBGENRES,
)

HEALTH_SLEEP = NichePartition(
    niche="health",
    sub_niche="sleep",
    podcast_index_categories=("Health", "Health & Fitness", "Mental Health"),
    search_terms=("sleep", "insomnia", "sleep hygiene", "circadian"),
    apple_genre_ids=(APPLE_HEALTH_FITNESS, 1516),
)

HEALTH_FOOD = NichePartition(
    niche="health",
    sub_niche="food",
    podcast_index_categories=("Health", "Health & Fitness", "Nutrition"),
    search_terms=("nutrition", "diet", "food health", "eating"),
    apple_genre_ids=(APPLE_HEALTH_FITNESS, 1517),
)

HEALTH_TRAINING = NichePartition(
    niche="health",
    sub_niche="training",
    podcast_index_categories=("Health", "Health & Fitness", "Fitness"),
    search_terms=("fitness", "training", "workout", "exercise"),
    apple_genre_ids=(APPLE_HEALTH_FITNESS, 1514),
)

PARTITIONS: dict[str, NichePartition] = {
    "health": HEALTH,
    "health_sleep": HEALTH_SLEEP,
    "health_food": HEALTH_FOOD,
    "health_training": HEALTH_TRAINING,
}


def get_partition(job: str, title_slice: str | None = None) -> NichePartition:
    """Resolve a job name to a NichePartition.

    ``job`` examples: ``health``, ``health_sleep``, ``health_food``, ``health_training``.
    ``title_slice`` optional ``A-F`` style prefix filter.
    """
    key = job.strip().lower().replace("-", "_").replace("/", "_")
    if key not in PARTITIONS:
        known = ", ".join(sorted(PARTITIONS))
        raise ValueError(f"Unknown job '{job}'. Known partitions: {known}")

    base = PARTITIONS[key]
    if not title_slice:
        return base

    parts = title_slice.upper().split("-", 1)
    if len(parts) != 2 or not parts[0] or not parts[1]:
        raise ValueError("title_slice must look like 'A-F'")
    return NichePartition(
        niche=base.niche,
        sub_niche=base.sub_niche,
        podcast_index_categories=base.podcast_index_categories,
        search_terms=base.search_terms,
        apple_genre_ids=base.apple_genre_ids,
        title_slice=(parts[0], parts[1]),
    )


def title_in_slice(title: str, title_slice: tuple[str, str] | None) -> bool:
    if not title_slice:
        return True
    if not title:
        return False
    first = title.strip()[0].upper()
    start, end = title_slice
    return start <= first <= end
