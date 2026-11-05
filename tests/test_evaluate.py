"""Tests for the evaluation harness.

Two things are being tested, and the second matters more than the first.

The first is arithmetic: MRR, hit@k, and the rest have to be right, because a
scoring bug reports a corpus as healthy when it is not.

The second is that the harness **fails loudly on a stale golden set**. An eval
set that silently points at a renamed page keeps running and keeps reporting a
lower score, and the obvious reading of a falling score is that the retriever
got worse. That misdiagnosis is expensive, so `load_golden_set` validates
every `expect_source` against the tree.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from docpack.chunk import chunk_markdown
from docpack.evaluate import (
    Case,
    GoldenSetError,
    Report,
    Result,
    evaluate,
    format_report,
    load_golden_set,
)
from docpack.frontmatter import PageMeta
from docpack.pack import Page
from docpack.retrieve import Index

REPO = Path(__file__).resolve().parent.parent


def make_result(case_id: str, rank: int | None, *, filtered: int | None = None,
                top: str = "wrong.md", top_type: str = "how-to",
                grounded: bool = True) -> Result:
    case = Case(
        id=case_id,
        question="q",
        expect_source="right.md",
        expect_diataxis="how-to",
    )
    return Result(
        case=case,
        rank=rank,
        filtered_rank=filtered if filtered is not None else rank,
        top_source=top,
        top_diataxis=top_type,
        top_breadcrumb="B",
        grounded=grounded,
    )


# ------------------------------------------------------------------ arithmetic


def test_mrr_is_the_mean_of_reciprocal_ranks():
    report = Report((make_result("a", 1), make_result("b", 2), make_result("c", 4)))
    # rank 4 is outside the top 3, so `evaluate` would record None; here we
    # check the formula itself: (1 + 0.5 + 0.25) / 3
    assert report.mrr == pytest.approx((1 + 0.5 + 0.25) / 3)


def test_a_missed_case_contributes_zero_to_mrr():
    report = Report((make_result("a", 1), make_result("b", None)))
    assert report.mrr == pytest.approx(0.5)


def test_hit_at_1_counts_only_top_results():
    report = Report((make_result("a", 1), make_result("b", 2), make_result("c", None)))
    assert report.hit_at_1 == pytest.approx(1 / 3)


def test_hit_at_k_counts_any_rank_within_depth():
    report = Report((make_result("a", 1), make_result("b", 3), make_result("c", None)))
    assert report.hit_at_k == pytest.approx(2 / 3)


def test_routing_accuracy_compares_the_top_type_to_the_expected_type():
    report = Report((
        make_result("a", 1, top_type="how-to"),
        make_result("b", 1, top_type="explanation"),
    ))
    assert report.routing_accuracy == pytest.approx(0.5)


def test_routing_headroom_is_the_gap_the_filter_opens():
    report = Report((
        make_result("a", 2, filtered=1),
        make_result("b", 1, filtered=1),
    ))
    assert report.hit_at_1 == pytest.approx(0.5)
    assert report.filtered_hit_at_1 == pytest.approx(1.0)
    assert report.routing_headroom == pytest.approx(0.5)


def test_failures_lists_only_total_misses():
    report = Report((make_result("a", 1), make_result("b", 3), make_result("c", None)))
    assert [r.case.id for r in report.failures] == ["c"]


def test_an_empty_report_does_not_divide_by_zero():
    report = Report(())
    assert report.mrr == 0.0
    assert report.hit_at_1 == 0.0
    assert report.routing_headroom == 0.0


# ------------------------------------------------------- golden set validation


def write_set(tmp_path: Path, body: str) -> Path:
    path = tmp_path / "golden.yaml"
    path.write_text(body, encoding="utf-8")
    return path


def test_a_valid_set_loads(tmp_path):
    path = write_set(tmp_path, """
- id: a
  question: how do I install
  expect_source: tutorials/getting-started.md
  expect_diataxis: tutorial
  must_contain: ["pip install"]
  why: the first question
""")
    cases = load_golden_set(path)
    assert cases[0].id == "a"
    assert cases[0].must_contain == ("pip install",)
    assert cases[0].why == "the first question"


def test_a_stale_expect_source_is_rejected(tmp_path):
    """The misdiagnosis this prevents is the whole reason the check exists."""
    path = write_set(tmp_path, """
- id: a
  question: q
  expect_source: how-to/page-that-was-renamed.md
  expect_diataxis: how-to
""")
    with pytest.raises(GoldenSetError, match="does not exist"):
        load_golden_set(path, docs_dir=REPO / "docs")


def test_an_unknown_diataxis_type_is_rejected(tmp_path):
    path = write_set(tmp_path, """
- id: a
  question: q
  expect_source: x.md
  expect_diataxis: blog-post
""")
    with pytest.raises(GoldenSetError, match="expect_diataxis"):
        load_golden_set(path)


def test_a_duplicate_id_is_rejected(tmp_path):
    """Duplicate ids make the report ambiguous and hide one of the two cases."""
    path = write_set(tmp_path, """
- id: a
  question: q
  expect_source: x.md
  expect_diataxis: how-to
- id: a
  question: r
  expect_source: y.md
  expect_diataxis: how-to
""")
    with pytest.raises(GoldenSetError, match="duplicate id"):
        load_golden_set(path)


def test_a_missing_field_is_rejected_by_name(tmp_path):
    path = write_set(tmp_path, """
- id: a
  question: q
  expect_diataxis: how-to
""")
    with pytest.raises(GoldenSetError, match="expect_source"):
        load_golden_set(path)


def test_an_empty_set_is_rejected(tmp_path):
    with pytest.raises(GoldenSetError, match="empty"):
        load_golden_set(write_set(tmp_path, "[]\n"))


def test_a_mapping_instead_of_a_list_is_rejected(tmp_path):
    with pytest.raises(GoldenSetError, match="list of cases"):
        load_golden_set(write_set(tmp_path, "id: a\n"))


# ------------------------------------------------------------------- end to end


@pytest.fixture
def tiny_index():
    def page(path, diataxis, title, summary, body):
        return Page(
            path=Path("docs") / path,
            meta=PageMeta(title, summary, diataxis, "developer", date(2026, 10, 26)),
            body=body,
            chunks=tuple(chunk_markdown(body, source=path)),
        )

    return Index.from_pages(
        [
            page("how-to/install.md", "how-to", "Install the thing",
                 "Install the thing with pip.",
                 "# Install the thing\n\nRun pip install thing.\n"),
            page("explanation/why.md", "explanation", "Why it works this way",
                 "The reasoning behind the design.",
                 "# Why it works this way\n\nBecause the alternative drifts.\n"),
        ],
        docs_dir=Path("docs"),
    )


def test_evaluate_finds_the_expected_page(tiny_index):
    cases = [Case("i", "how do I install with pip", "how-to/install.md", "how-to",
                  ("pip install",))]
    report = evaluate(tiny_index, cases)
    assert report.hit_at_1 == 1.0
    assert report.grounded_rate == 1.0
    assert report.results[0].routed


def test_evaluate_records_a_miss_rather_than_raising(tiny_index):
    cases = [Case("x", "how do I install with pip", "explanation/why.md", "explanation")]
    report = evaluate(tiny_index, cases)
    assert report.hit_at_1 == 0.0
    assert not report.results[0].routed


def test_a_query_matching_nothing_is_a_miss_not_a_crash(tiny_index):
    cases = [Case("x", "kubernetes istio sidecar", "how-to/install.md", "how-to", ("pip",))]
    report = evaluate(tiny_index, cases)
    assert report.results[0].rank is None
    assert report.results[0].top_source == ""
    assert not report.results[0].grounded


def test_grounding_fails_when_the_top_chunk_lacks_a_required_term(tiny_index):
    """Right page, wrong section: a page-level hit is not a grounded answer."""
    cases = [Case("g", "how do I install with pip", "how-to/install.md", "how-to",
                  ("kubernetes",))]
    report = evaluate(tiny_index, cases)
    assert report.hit_at_1 == 1.0
    assert report.grounded_rate == 0.0
    assert report.results[0].missing_terms == ("kubernetes",)


# ---------------------------------------------------------------- the real set


def test_the_repository_golden_set_is_valid():
    """Guards the golden set itself against drift as pages are renamed."""
    cases = load_golden_set(REPO / "evals" / "golden.yaml", docs_dir=REPO / "docs")
    assert len(cases) >= 20
    assert all(c.why for c in cases), "every case must say what it probes"


def test_the_repository_corpus_clears_the_quality_floor():
    """A regression gate, deliberately set below the current score.

    The floor is not a target. It is set low enough that ordinary content edits
    do not trip it, and the real number lives in
    `docs/explanation/evaluating-retrieval.md` where a change to it is visible
    in a diff and has to be explained.
    """
    cases = load_golden_set(REPO / "evals" / "golden.yaml", docs_dir=REPO / "docs")
    report = evaluate(Index.from_tree(REPO / "docs"), cases)
    assert report.mrr >= 0.70, format_report(report, verbose=True)
    assert report.hit_at_k >= 0.80, format_report(report, verbose=True)


def test_the_report_names_the_cases_that_missed():
    report = Report((make_result("good", 1), make_result("bad", None, top="other.md")))
    text = format_report(report)
    assert "bad" in text
    assert "other.md" in text
    assert "good" not in text  # misses only, unless verbose


def test_verbose_reports_every_case():
    report = Report((make_result("good", 1), make_result("bad", None)))
    assert "good" in format_report(report, verbose=True)


# --------------------------------------------------------------- search command


def test_search_prints_the_section_not_just_the_page(capsys):
    """The command exists so a reader can see what the library is for.

    Printing the page alone would repeat the mistake the grounding report made:
    "the right page" hides "the wrong section", and the breadcrumb is the only
    thing that distinguishes them.
    """
    from docpack.cli import main

    assert main(["search", "how do I make the chunks smaller", "--docs", "docs"]) == 0
    out = capsys.readouterr().out
    assert "chunks indexed" in out
    assert " > " in out, "every result should name its section, not only its page"
    assert ".md" in out


def test_search_respects_the_type_filter(capsys):
    from docpack.cli import main

    assert (
        main(
            [
                "search",
                "why not split every thousand characters",
                "--docs",
                "docs",
                "--type",
                "explanation",
                "-n",
                "3",
            ]
        )
        == 0
    )
    out = capsys.readouterr().out
    assert "[explanation]" in out
    for other in ("[tutorial]", "[how-to]", "[reference]"):
        assert other not in out


def test_search_exits_nonzero_when_nothing_matches(capsys):
    from docpack.cli import main

    assert main(["search", "zzzz nonexistent gibberish", "--docs", "docs"]) == 1
    assert "nothing in" in capsys.readouterr().out
