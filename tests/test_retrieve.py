"""Tests for the shared retriever.

These test ranking *properties* rather than specific orderings. A test that
asserts "query X returns page Y first" is an eval case, and it belongs in
`evals/golden.yaml` where a regression shows up as a score rather than as a
red build. Pinning exact orderings in the unit suite makes every content edit
break the tests, which teaches people to delete the tests.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from docpack.chunk import chunk_markdown
from docpack.frontmatter import PageMeta
from docpack.pack import Page
from docpack.retrieve import Index, tokenize


def make_page(path: str, diataxis: str, audience: str, title: str, summary: str, body: str):
    rel = path
    return Page(
        path=Path("docs") / path,
        meta=PageMeta(title, summary, diataxis, audience, date(2026, 10, 26)),
        body=body,
        chunks=tuple(chunk_markdown(body, source=rel)),
    )


@pytest.fixture
def index():
    pages = [
        make_page(
            "how-to/rotate-keys.md", "how-to", "operator",
            "Rotate the signing key", "Replace the signing key with no downtime.",
            "# Rotate the signing key\n\nRun the rotate command.\n\n"
            "## Verify\n\nCheck the key id changed.\n",
        ),
        make_page(
            "explanation/key-design.md", "explanation", "developer",
            "Why keys rotate", "The reasoning behind scheduled key rotation.",
            "# Why keys rotate\n\nA long-lived key is a long-lived risk.\n\n"
            "## Tradeoffs\n\nRotation costs availability during the swap.\n",
        ),
        make_page(
            "reference/api.md", "reference", "developer",
            "API reference", "Every endpoint and parameter.",
            "# API reference\n\n## rotate\n\nAccepts a key id. Returns the new id.\n",
        ),
    ]
    return Index.from_pages(pages, docs_dir=Path("docs"))


# ----------------------------------------------------------------- tokenizing


def test_tokenize_lowercases_and_splits_on_punctuation():
    assert tokenize("Rotate, the KEY-id!") == ["rotate", "the", "key", "id"]


def test_tokenize_drops_single_characters():
    assert "a" not in tokenize("a key")


def test_tokenize_normalizes_plurals_consistently():
    """Queries and documents get the same treatment, which is the whole point."""
    assert tokenize("keys") == tokenize("key")
    assert tokenize("chunks") == tokenize("chunk")


def test_tokenize_leaves_double_s_alone():
    assert tokenize("address") == ["address"]


# --------------------------------------------------------------------- basics


def test_the_index_covers_every_chunk(index):
    """Five chunks: two pages with an intro plus one section, one with no intro."""
    assert len(index) == 5


def test_an_empty_query_returns_nothing(index):
    assert index.search("") == []
    assert index.search("   ") == []


def test_a_query_matching_nothing_returns_nothing(index):
    assert index.search("kubernetes helm bluegreen") == []


def test_results_never_exceed_the_limit(index):
    assert len(index.search("key", limit=2)) <= 2


def test_every_hit_carries_its_page_metadata(index):
    hit = index.search("rotate the signing key", limit=1)[0]
    assert hit.diataxis in {"how-to", "explanation", "reference"}
    assert hit.source.endswith(".md")
    assert hit.title
    assert hit.summary
    assert hit.chunk_id


# -------------------------------------------------------------------- ranking


def test_scores_are_positive_and_descending(index):
    hits = index.search("rotate the key", limit=5)
    assert len(hits) > 1
    assert all(h.score > 0 for h in hits)
    assert [h.score for h in hits] == sorted((h.score for h in hits), reverse=True)


def test_ranking_is_deterministic(index):
    first = [h.chunk_id for h in index.search("rotate key", limit=5)]
    second = [h.chunk_id for h in index.search("rotate key", limit=5)]
    assert first == second


def test_a_rare_term_outranks_a_common_one():
    """Inverse document frequency: a term in every chunk carries little signal."""
    pages = [
        make_page(
            f"how-to/p{i}.md", "how-to", "developer", f"Page {i}", "A page.",
            f"# Page {i}\n\nThe widget is a widget. "
            + ("The flange matters here." if i == 0 else "Nothing special."),
        )
        for i in range(6)
    ]
    index = Index.from_pages(pages, docs_dir=Path("docs"))
    hits = index.search("widget flange", limit=6)
    assert hits[0].source == "how-to/p0.md"


def test_length_normalization_stops_long_chunks_winning_on_bulk():
    """Raw term frequency would rank the padded chunk first. BM25 should not."""
    short = make_page(
        "how-to/short.md", "how-to", "developer", "Flange", "About the flange.",
        "# Flange\n\nThe flange is described here.\n",
    )
    padded = make_page(
        "explanation/padded.md", "explanation", "developer", "Everything",
        "A long page about many things.",
        "# Everything\n\n" + "The flange is mentioned. " * 3 + "Filler. " * 400,
    )
    index = Index.from_pages([short, padded], docs_dir=Path("docs"))
    assert index.search("flange", limit=2)[0].source == "how-to/short.md"


def test_a_heading_match_beats_a_body_match():
    """Headings are weighted because they state what the text below is about."""
    in_heading = make_page(
        "reference/throttling.md", "reference", "developer", "Throttling",
        "Rate limits and backoff.",
        "# Throttling\n\n## Throttling behaviour\n\nSee the table.\n",
    )
    in_body = make_page(
        "explanation/misc.md", "explanation", "developer", "Miscellany",
        "Assorted notes.",
        "# Miscellany\n\n## Notes\n\nWe mention throttling in passing here.\n",
    )
    index = Index.from_pages([in_heading, in_body], docs_dir=Path("docs"))
    assert index.search("throttling", limit=2)[0].source == "reference/throttling.md"


def test_the_summary_is_searchable():
    """A question phrased like the page's summary must reach that page.

    This is the regression test for the bug `docpack eval` found: the summary
    field fed the meta description, llms.txt, and the retrieval snippet, but was
    never indexed, so a question using the author's own words missed the page.
    """
    described = make_page(
        "how-to/zero-downtime.md", "how-to", "operator", "Rotate the signing key",
        "Replace the signing key with no downtime.",
        "# Rotate the signing key\n\nRun the command.\n",
    )
    other = make_page(
        "explanation/other.md", "explanation", "developer", "Other", "Unrelated.",
        "# Other\n\nNothing about downtime or replacement.\n",
    )
    index = Index.from_pages([described, other], docs_dir=Path("docs"))
    hits = index.search("replace with no downtime", limit=2)
    assert hits
    assert hits[0].source == "how-to/zero-downtime.md"


# ------------------------------------------------------------------ filtering


def test_filtering_by_diataxis_excludes_every_other_type(index):
    hits = index.search("rotate key", diataxis="explanation", limit=10)
    assert hits
    assert {h.diataxis for h in hits} == {"explanation"}


def test_filtering_by_audience_excludes_every_other_audience(index):
    hits = index.search("key", audience="operator", limit=10)
    assert hits
    assert {h.audience for h in hits} == {"operator"}


def test_filters_combine(index):
    hits = index.search("key", diataxis="how-to", audience="developer", limit=10)
    assert hits == []  # the how-to page is for operators


def test_filtering_happens_before_ranking_not_after(index):
    """The point of the content model: a filter is a constraint, not a reranking.

    Asking for more results than exist in a type must still return only that
    type, which a post-hoc filter over a fixed top-k could not guarantee.
    """
    hits = index.search("key rotate verify", diataxis="reference", limit=50)
    assert hits
    assert all(h.diataxis == "reference" for h in hits)


def test_render_includes_the_source_and_the_type(index):
    rendered = index.search("rotate the signing key", limit=1)[0].render()
    assert "source:" in rendered
    assert ".md" in rendered
