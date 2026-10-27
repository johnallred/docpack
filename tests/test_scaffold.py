"""Tests for the page generator.

The load-bearing test here is `test_every_generated_type_passes_validation`.
The README claims this project makes the right way the easy way, and that claim
is only true while the generator and the validator agree. They are separate
modules with separate notions of what a valid page is, so nothing but a test
keeps them in step.
"""

from __future__ import annotations

from datetime import date

import pytest

from docpack.frontmatter import AUDIENCES, DIATAXIS_TYPES, parse_page
from docpack.scaffold import (
    DIRECTORIES,
    TEMPLATES,
    ScaffoldError,
    new_page,
    render_page,
    slugify,
    write_page,
)

TODAY = date(2026, 10, 26)


# ------------------------------------------------------------------- slugify


@pytest.mark.parametrize(
    ("title", "expected"),
    [
        ("Pack a tree for RAG", "pack-a-tree-for-rag"),
        ("Why heading-aware chunking", "why-heading-aware-chunking"),
        ("  Lots   of   space  ", "lots-of-space"),
        ("Punctuation!? Everywhere...", "punctuation-everywhere"),
        ("Rotate the signing key (v2)", "rotate-the-signing-key-v2"),
    ],
)
def test_slugify(title, expected):
    assert slugify(title) == expected


def test_slugify_rejects_a_title_with_no_usable_characters():
    with pytest.raises(ScaffoldError, match="empty filename"):
        slugify("!!!")


# -------------------------------------------------------- the important test


@pytest.mark.parametrize("diataxis", sorted(DIATAXIS_TYPES))
def test_every_generated_type_passes_validation(diataxis):
    """The generator and the content model must not drift apart.

    If this fails, `docpack new` is producing pages that `docpack docs --check`
    rejects, which means the project is telling contributors to do something
    that CI then refuses.
    """
    text = render_page(title="A generated page", diataxis=diataxis, today=TODAY)
    meta, body = parse_page(text, source=f"generated-{diataxis}")
    assert meta.diataxis == diataxis
    assert meta.audience in AUDIENCES
    assert meta.updated == TODAY
    assert meta.title == "A generated page"
    assert meta.summary  # required field, never blank
    assert body.strip().startswith("# A generated page")


@pytest.mark.parametrize("diataxis", sorted(DIATAXIS_TYPES))
def test_every_type_has_a_template_and_a_directory(diataxis):
    """A type added to the content model must not fall through the generator."""
    assert diataxis in TEMPLATES
    assert diataxis in DIRECTORIES


# ----------------------------------------------------------------- rendering


def test_the_title_is_used_for_the_heading_and_the_front_matter():
    text = render_page(title="Rotate the signing key", diataxis="how-to", today=TODAY)
    assert "title: Rotate the signing key" in text
    assert "# Rotate the signing key" in text


def test_a_supplied_summary_is_used_verbatim():
    text = render_page(
        title="X", diataxis="reference", summary="Every flag and exit code.", today=TODAY
    )
    assert "summary: Every flag and exit code." in text
    assert "TODO" not in text


def test_an_omitted_summary_becomes_a_visible_placeholder():
    """A blank summary would fail validation, so the placeholder has to be valid."""
    text = render_page(title="Some Page", diataxis="how-to", today=TODAY)
    meta, _ = parse_page(text)
    assert "TODO" in meta.summary


def test_tags_are_written_as_a_yaml_list():
    text = render_page(
        title="X", diataxis="how-to", tags=("rag", "retrieval"), today=TODAY
    )
    meta, _ = parse_page(text)
    assert meta.tags == ("rag", "retrieval")


def test_tags_are_omitted_entirely_when_empty():
    text = render_page(title="X", diataxis="how-to", today=TODAY)
    assert "tags:" not in text


def test_audience_defaults_differ_by_type():
    tutorial = render_page(title="X", diataxis="tutorial", today=TODAY)
    reference = render_page(title="X", diataxis="reference", today=TODAY)
    assert "audience: new-user" in tutorial
    assert "audience: developer" in reference


def test_an_explicit_audience_overrides_the_default():
    text = render_page(
        title="X", diataxis="tutorial", audience="contributor", today=TODAY
    )
    assert "audience: contributor" in text


def test_an_unknown_type_is_rejected_with_the_valid_options():
    with pytest.raises(ScaffoldError, match="explanation"):
        render_page(title="X", diataxis="blog-post", today=TODAY)


def test_an_unknown_audience_is_rejected_with_the_valid_options():
    with pytest.raises(ScaffoldError, match="new-user"):
        render_page(title="X", diataxis="how-to", audience="executives", today=TODAY)


# --------------------------------------------------------------- file placement


@pytest.mark.parametrize(
    ("diataxis", "directory"),
    [
        ("tutorial", "tutorials"),
        ("how-to", "how-to"),
        ("reference", "reference"),
        ("explanation", "explanation"),
    ],
)
def test_pages_land_in_the_directory_their_type_requires(tmp_path, diataxis, directory):
    page = new_page(tmp_path, title="My Page", diataxis=diataxis, today=TODAY)
    assert page.path == tmp_path / directory / "my-page.md"


def test_new_page_does_not_touch_the_disk(tmp_path):
    """A dry run is the default, so `--dry-run` needs no special path."""
    page = new_page(tmp_path, title="My Page", diataxis="how-to", today=TODAY)
    assert not page.path.exists()


def test_write_page_creates_missing_directories(tmp_path):
    page = new_page(tmp_path, title="My Page", diataxis="explanation", today=TODAY)
    path = write_page(page)
    assert path.read_text(encoding="utf-8") == page.text


def test_an_existing_page_is_never_overwritten(tmp_path):
    page = new_page(tmp_path, title="My Page", diataxis="how-to", today=TODAY)
    write_page(page)
    with pytest.raises(ScaffoldError, match="already exists"):
        new_page(tmp_path, title="My Page", diataxis="how-to", today=TODAY)


# ------------------------------------------------- the whole-tree integration


def test_a_tree_built_entirely_by_the_generator_validates_as_a_corpus(tmp_path):
    """End to end: generate one page of every type, then run the real loader."""
    from docpack.pack import load_tree

    for diataxis in sorted(DIATAXIS_TYPES):
        write_page(
            new_page(
                tmp_path,
                title=f"Generated {diataxis} page",
                diataxis=diataxis,
                summary=f"A generated {diataxis} page.",
                today=TODAY,
            )
        )

    pages = load_tree(tmp_path)
    assert len(pages) == len(DIATAXIS_TYPES)
    assert {p.meta.diataxis for p in pages} == DIATAXIS_TYPES
    # Every generated page produces retrievable chunks, not just valid metadata.
    assert all(p.chunks for p in pages)
