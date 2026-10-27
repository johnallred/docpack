"""MkDocs hooks that wire the content model into page-level SEO and GEO.

Without this, every page inherits the site-wide `site_description`, so search
engines and link previews see the same sentence eleven times. The content
model already requires a per-page `summary`; this makes the build use it.

Registered in `mkdocs.yml` under `hooks:`.

What it sets, per page:

- `meta name="description"`  the per-page summary, for search engines
- `og:` and `twitter:` tags   for link previews
- JSON-LD `TechArticle`       structured data, including the Diataxis type,
                              which is the GEO half: machine-readable context
                              about what kind of answer the page can support
"""

from __future__ import annotations

import json
from typing import Any

#: Diataxis type -> a human-readable role, used in structured data.
ROLE = {
    "tutorial": "Tutorial: learning-oriented, assumes no prior context",
    "how-to": "How-to guide: task-oriented, assumes familiarity",
    "reference": "Reference: factual description of the interface",
    "explanation": "Explanation: design reasoning and tradeoffs",
}


def on_page_context(context: dict[str, Any], page, config, nav):  # noqa: ANN001
    """Promote the content model's `summary` to the description Material renders."""
    summary = page.meta.get("summary")
    if summary and not page.meta.get("description"):
        page.meta["description"] = summary
    return context


def on_post_page(output: str, page, config) -> str:  # noqa: ANN001
    """Inject Open Graph, Twitter, and JSON-LD tags into the rendered head."""
    meta = page.meta
    summary = meta.get("summary")
    if not summary:
        return output

    site_url = (config.get("site_url") or "").rstrip("/")
    page_url = f"{site_url}/{page.url}" if site_url else page.url
    title = meta.get("title") or page.title or config.get("site_name", "")

    tags = [
        f'<meta property="og:type" content="article">',
        f'<meta property="og:title" content="{_esc(title)}">',
        f'<meta property="og:description" content="{_esc(summary)}">',
        f'<meta property="og:url" content="{_esc(page_url)}">',
        f'<meta name="twitter:card" content="summary">',
        f'<meta name="twitter:title" content="{_esc(title)}">',
        f'<meta name="twitter:description" content="{_esc(summary)}">',
    ]

    # Structured data. The `about` field carries the Diataxis type, which tells
    # a crawler or an assistant what kind of question this page can answer.
    jsonld = {
        "@context": "https://schema.org",
        "@type": "TechArticle",
        "headline": title,
        "description": summary,
        "url": page_url,
        "dateModified": str(meta.get("updated", "")),
        "audience": {"@type": "Audience", "audienceType": meta.get("audience", "")},
        "about": ROLE.get(meta.get("diataxis", ""), ""),
        "keywords": ", ".join(meta.get("tags", []) or []),
    }
    tags.append(
        '<script type="application/ld+json">'
        + json.dumps(jsonld, separators=(",", ":"))
        + "</script>"
    )

    return output.replace("</head>", "\n".join(tags) + "\n</head>", 1)


def _esc(text: str) -> str:
    """Escape a string for an HTML attribute."""
    return (
        str(text)
        .replace("&", "&amp;")
        .replace('"', "&quot;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )
