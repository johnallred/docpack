"""Unit tests for the content model."""
from datetime import date, timedelta

import pytest

from docpack.frontmatter import ContentModelError, parse_page, split_front_matter

GOOD = """---
title: Install docpack
summary: Get docpack running in a clean environment.
diataxis: how-to
audience: developer
updated: 2026-10-26
tags: [install]
---
Body.
"""


def test_valid_page_parses():
    meta, body = parse_page(GOOD)
    assert meta.title == "Install docpack"
    assert meta.diataxis == "how-to"
    assert meta.tags == ("install",)
    assert body.strip() == "Body."


def test_missing_required_field_is_rejected():
    bad = GOOD.replace("summary: Get docpack running in a clean environment.\n", "")
    with pytest.raises(ContentModelError, match="summary"):
        parse_page(bad)


def test_unknown_diataxis_type_is_rejected():
    bad = GOOD.replace("diataxis: how-to", "diataxis: blog-post")
    with pytest.raises(ContentModelError, match="diataxis"):
        parse_page(bad)


def test_unknown_audience_is_rejected():
    bad = GOOD.replace("audience: developer", "audience: everyone")
    with pytest.raises(ContentModelError, match="audience"):
        parse_page(bad)


def test_updated_must_be_a_date():
    bad = GOOD.replace("updated: 2026-10-26", 'updated: "last Tuesday"')
    with pytest.raises(ContentModelError, match="date"):
        parse_page(bad)


def test_staleness_is_computed_from_updated():
    recent = GOOD.replace("2026-10-26", date.today().isoformat())
    assert parse_page(recent)[0].is_stale is False
    old = GOOD.replace("2026-10-26", (date.today() - timedelta(days=400)).isoformat())
    assert parse_page(old)[0].is_stale is True


def test_document_without_front_matter():
    meta, body = split_front_matter("no front matter here")
    assert meta == {} and body == "no front matter here"
