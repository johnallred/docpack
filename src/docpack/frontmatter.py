"""Parse and validate the documentation content model.

Every page in this project carries YAML front matter conforming to a declared
content model. The model is not decoration: CI rejects pages that violate it,
which is what keeps navigation, search facets, and retrieval metadata coherent
as the corpus grows.

See `docs/explanation/content-model.md` for the reasoning.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any

import yaml

#: The four Diataxis types. Every page is exactly one of these.
DIATAXIS_TYPES = frozenset({"tutorial", "how-to", "reference", "explanation"})

#: Audiences the corpus is written for. Drives both navigation and retrieval filters.
AUDIENCES = frozenset({"new-user", "developer", "operator", "contributor"})

REQUIRED_FIELDS = ("title", "summary", "diataxis", "audience", "updated")


class ContentModelError(ValueError):
    """Raised when a page violates the declared content model."""


@dataclass(frozen=True)
class PageMeta:
    """Validated front matter for a single documentation page.

    Attributes:
        title: Page title. Also the H1 and the link text in generated indexes.
        summary: One sentence. Used as the meta description, the llms.txt
            annotation, and the retrieval snippet, so it carries real weight.
        diataxis: Which of the four Diataxis types this page is. Exactly one.
        audience: Who the page is written for.
        updated: Last meaningful review date, used for freshness checks.
        tags: Optional free taxonomy, used for faceting.
    """

    title: str
    summary: str
    diataxis: str
    audience: str
    updated: date
    tags: tuple[str, ...] = field(default_factory=tuple)

    @property
    def is_stale(self) -> bool:
        """True when the page has not been reviewed in over a year."""
        return (date.today() - self.updated).days > 365


def split_front_matter(text: str) -> tuple[dict[str, Any], str]:
    """Split a markdown document into its front matter and body.

    Args:
        text: Full file contents, front matter first.

    Returns:
        A `(metadata, body)` tuple. Metadata is an empty dict when the document
        has no front matter.

    Example:
        >>> meta, body = split_front_matter("---\\ntitle: Hi\\n---\\nBody text\\n")
        >>> meta["title"]
        'Hi'
        >>> body.strip()
        'Body text'
    """
    if not text.startswith("---"):
        return {}, text
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}, text
    loaded = yaml.safe_load(parts[1]) or {}
    if not isinstance(loaded, dict):
        raise ContentModelError("front matter must be a mapping")
    return loaded, parts[2]


def parse_page(text: str, *, source: str = "<string>") -> tuple[PageMeta, str]:
    """Parse a page and validate it against the content model.

    Args:
        text: Full file contents.
        source: Path or label used in error messages.

    Returns:
        A `(PageMeta, body)` tuple.

    Raises:
        ContentModelError: If required fields are missing, or `diataxis` or
            `audience` fall outside their allowed sets.

    Example:
        >>> page = '''---
        ... title: Chunk a corpus
        ... summary: Turn a docs tree into retrieval records.
        ... diataxis: how-to
        ... audience: developer
        ... updated: 2026-10-26
        ... ---
        ... Steps go here.
        ... '''
        >>> meta, _ = parse_page(page)
        >>> meta.diataxis, meta.audience
        ('how-to', 'developer')
    """
    raw, body = split_front_matter(text)

    missing = [f for f in REQUIRED_FIELDS if f not in raw]
    if missing:
        raise ContentModelError(f"{source}: missing required field(s): {', '.join(missing)}")

    if raw["diataxis"] not in DIATAXIS_TYPES:
        raise ContentModelError(
            f"{source}: diataxis must be one of {sorted(DIATAXIS_TYPES)}, got {raw['diataxis']!r}"
        )
    if raw["audience"] not in AUDIENCES:
        raise ContentModelError(
            f"{source}: audience must be one of {sorted(AUDIENCES)}, got {raw['audience']!r}"
        )

    updated = raw["updated"]
    if not isinstance(updated, date):
        raise ContentModelError(f"{source}: updated must be a date, got {type(updated).__name__}")

    return (
        PageMeta(
            title=str(raw["title"]),
            summary=str(raw["summary"]),
            diataxis=str(raw["diataxis"]),
            audience=str(raw["audience"]),
            updated=updated,
            tags=tuple(raw.get("tags", ()) or ()),
        ),
        body,
    )
