"""Tests for the SEO and GEO hooks.

These matter because the failure they guard against is silent: if the hook
stops firing, every page still builds, still renders, and still looks correct
in a browser. It just quietly serves the site-wide description eleven times,
and nobody notices until a crawler or an assistant has already indexed it
that way.

The hooks are tested directly rather than through a full `mkdocs build`, so
the suite stays fast and does not need the docs extra installed.
"""

from __future__ import annotations

import importlib.util
import json
import re
from pathlib import Path
from types import SimpleNamespace

import pytest

HOOK_PATH = Path(__file__).resolve().parent.parent / "hooks" / "seo.py"


def _load_hook():
    spec = importlib.util.spec_from_file_location("seo_hook", HOOK_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


seo = _load_hook()


def make_page(**meta):
    base = {
        "title": "Pack a tree for retrieval",
        "summary": "Produce JSONL records sized and tagged for a vector store.",
        "diataxis": "how-to",
        "audience": "developer",
        "updated": "2026-10-26",
        "tags": ["rag", "retrieval"],
    }
    base.update(meta)
    return SimpleNamespace(meta=base, url="how-to/pack-for-rag/", title=base["title"])


CONFIG = {"site_url": "https://example.github.io/docpack/", "site_name": "docpack"}

SHELL = "<html><head><title>x</title></head><body></body></html>"


def test_summary_becomes_the_page_description():
    page = make_page()
    seo.on_page_context({}, page, CONFIG, None)
    assert page.meta["description"] == page.meta["summary"]


def test_an_explicit_description_wins_over_the_summary():
    page = make_page(description="Hand-written, deliberately different.")
    seo.on_page_context({}, page, CONFIG, None)
    assert page.meta["description"] == "Hand-written, deliberately different."


def test_open_graph_and_twitter_tags_are_injected():
    out = seo.on_post_page(SHELL, make_page(), CONFIG)
    assert '<meta property="og:title" content="Pack a tree for retrieval">' in out
    assert '<meta property="og:type" content="article">' in out
    assert '<meta name="twitter:card" content="summary">' in out
    assert "og:url" in out and "https://example.github.io/docpack/how-to/pack-for-rag/" in out


def test_structured_data_carries_the_diataxis_type():
    """The GEO half: an assistant can tell what kind of answer the page supports."""
    out = seo.on_post_page(SHELL, make_page(), CONFIG)
    payload = json.loads(
        re.search(r'<script type="application/ld\+json">(.*?)</script>', out, re.S).group(1)
    )
    assert payload["@type"] == "TechArticle"
    assert payload["about"].startswith("How-to guide")
    assert payload["audience"]["audienceType"] == "developer"
    assert payload["dateModified"] == "2026-10-26"


def test_tags_land_in_structured_data_keywords():
    out = seo.on_post_page(SHELL, make_page(), CONFIG)
    payload = json.loads(
        re.search(r'<script type="application/ld\+json">(.*?)</script>', out, re.S).group(1)
    )
    assert payload["keywords"] == "rag, retrieval"


def test_quotes_in_a_summary_cannot_break_out_of_the_attribute():
    page = make_page(summary='A "quoted" phrase & an <angle> bracket.')
    out = seo.on_post_page(SHELL, page, CONFIG)
    head = out.split("</head>")[0]
    # The raw characters must not appear unescaped inside the attribute.
    assert 'content="A "quoted"' not in head
    assert "&quot;quoted&quot;" in head
    assert "&amp;" in head
    assert "&lt;angle&gt;" in head


def test_a_page_with_no_summary_is_left_alone():
    """Pages outside the content model, such as a generated redirect, pass through."""
    page = SimpleNamespace(meta={}, url="x/", title="x")
    assert seo.on_post_page(SHELL, page, CONFIG) == SHELL


@pytest.mark.parametrize("diataxis", ["tutorial", "how-to", "reference", "explanation"])
def test_every_diataxis_type_has_a_structured_data_role(diataxis):
    """A new type added to the content model must not silently emit an empty role."""
    assert seo.ROLE.get(diataxis)
