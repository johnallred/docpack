"""Score the corpus on a golden set of questions.

Every other check in this repository asks whether the documentation is
*correct*: links resolve, samples execute, front matter validates. None of them
ask the question a reader actually cares about, which is whether asking the
docs something gets the right page back.

This module answers that. A golden set pairs real questions with the page that
should answer them. The harness runs each question through the shipped
retriever and reports:

- **hit@1**  the top result is the right page
- **hit@3**  the right page is in the top three
- **MRR**    mean reciprocal rank, which distinguishes "second" from "ninth"
- **routing** the top result has the Diataxis type the question calls for
- **grounded** the top result contains the terms an answer must cite

The last two are the ones worth arguing about. **Routing** matters because a
reference page and an explanation page can both be topically correct while only
one of them can answer the question asked: "how do I" wants a command and
"why does" wants a tradeoff. **Grounded** is a cheap stand-in for answer
accuracy: if the retrieved chunk does not contain the fact, no amount of
generation will invent it correctly.

### The headroom number, and why it is not a score

The report also runs every question a second time with a filter on the
Diataxis type the question expects. That filtered figure is **not** an
achievable score: at query time nobody knows what type the question wants.

It measures something else, and something more useful: the gap between the two
numbers is how much accuracy is sitting unclaimed behind a query router. A
small gap says routing is not worth building. A large gap says the content
model is carrying information the retriever is throwing away, which is an
argument for a classifier rather than for a better embedding model.

Usage:
    docpack eval evals/golden.yaml --docs docs
    docpack eval evals/golden.yaml --docs docs --fail-under 0.8
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from .frontmatter import DIATAXIS_TYPES
from .retrieve import Index

#: How deep to look when computing hit@k and MRR.
DEPTH = 3


class GoldenSetError(ValueError):
    """Raised when the golden set is malformed or points at a missing page."""


@dataclass(frozen=True)
class Case:
    """One question and the answer it is supposed to retrieve.

    Attributes:
        id: Stable short identifier, used in the report and in diffs.
        question: The question as a reader would type it.
        expect_source: Page path, relative to the docs root, that should answer it.
        expect_diataxis: The Diataxis type the question's phrasing calls for.
        must_contain: Terms the retrieved chunk has to contain for an answer
            built on it to be grounded. Matched case-insensitively.
        why: Optional note on what the case is probing. Documentation for the
            eval set itself, which otherwise becomes unmaintainable.
    """

    id: str
    question: str
    expect_source: str
    expect_diataxis: str
    must_contain: tuple[str, ...] = ()
    why: str = ""


@dataclass(frozen=True)
class Result:
    """The outcome of one case."""

    case: Case
    rank: int | None
    filtered_rank: int | None
    top_source: str
    top_diataxis: str
    top_breadcrumb: str
    grounded: bool
    missing_terms: tuple[str, ...] = ()

    @property
    def hit_1(self) -> bool:
        return self.rank == 1

    @property
    def hit_k(self) -> bool:
        return self.rank is not None

    @property
    def routed(self) -> bool:
        return self.top_diataxis == self.case.expect_diataxis

    @property
    def reciprocal_rank(self) -> float:
        return 1.0 / self.rank if self.rank else 0.0


@dataclass(frozen=True)
class Report:
    """Aggregate scores across a golden set."""

    results: tuple[Result, ...]

    @property
    def total(self) -> int:
        return len(self.results)

    def _mean(self, values: list[float]) -> float:
        return sum(values) / len(values) if values else 0.0

    @property
    def hit_at_1(self) -> float:
        return self._mean([float(r.hit_1) for r in self.results])

    @property
    def hit_at_k(self) -> float:
        return self._mean([float(r.hit_k) for r in self.results])

    @property
    def mrr(self) -> float:
        return self._mean([r.reciprocal_rank for r in self.results])

    @property
    def routing_accuracy(self) -> float:
        return self._mean([float(r.routed) for r in self.results])

    @property
    def grounded_rate(self) -> float:
        return self._mean([float(r.grounded) for r in self.results])

    @property
    def filtered_hit_at_1(self) -> float:
        """hit@1 when the retriever is told which Diataxis type to search.

        An upper bound on what a perfect query router could reach, not a score
        this system achieves. See the module docstring.
        """
        return self._mean([float(r.filtered_rank == 1) for r in self.results])

    @property
    def routing_headroom(self) -> float:
        """Accuracy currently left on the table by not routing queries."""
        return self.filtered_hit_at_1 - self.hit_at_1

    @property
    def failures(self) -> tuple[Result, ...]:
        """Cases where the expected page was not in the top results at all."""
        return tuple(r for r in self.results if not r.hit_k)


def load_golden_set(path: Path, *, docs_dir: Path | None = None) -> list[Case]:
    """Load and validate a golden set from YAML.

    Validation is strict for the same reason the content model is: a golden set
    that silently points at a renamed page stops measuring anything, and it
    fails open, reporting a drop in accuracy that has nothing to do with the
    retriever.

    Args:
        path: YAML file containing a list of cases.
        docs_dir: When given, every `expect_source` is checked to exist.

    Raises:
        GoldenSetError: On a malformed case, an unknown Diataxis type, a
            duplicate id, or an `expect_source` with no file behind it.
    """
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise GoldenSetError(f"{path}: expected a list of cases")

    cases: list[Case] = []
    seen: set[str] = set()
    for i, item in enumerate(raw):
        label = f"{path}[{i}]"
        if not isinstance(item, dict):
            raise GoldenSetError(f"{label}: each case must be a mapping")
        for required in ("id", "question", "expect_source", "expect_diataxis"):
            if required not in item:
                raise GoldenSetError(f"{label}: missing {required!r}")

        case_id = str(item["id"])
        if case_id in seen:
            raise GoldenSetError(f"{label}: duplicate id {case_id!r}")
        seen.add(case_id)

        if item["expect_diataxis"] not in DIATAXIS_TYPES:
            raise GoldenSetError(
                f"{label}: expect_diataxis must be one of {sorted(DIATAXIS_TYPES)}, "
                f"got {item['expect_diataxis']!r}"
            )

        source = str(item["expect_source"])
        if docs_dir is not None and not (docs_dir / source).exists():
            raise GoldenSetError(f"{label}: expect_source {source!r} does not exist")

        cases.append(
            Case(
                id=case_id,
                question=str(item["question"]),
                expect_source=source,
                expect_diataxis=str(item["expect_diataxis"]),
                must_contain=tuple(str(t) for t in item.get("must_contain", ()) or ()),
                why=str(item.get("why", "")),
            )
        )

    if not cases:
        raise GoldenSetError(f"{path}: golden set is empty")
    return cases


def _rank_of(hits: list[Any], expect_source: str) -> int | None:
    """1-indexed rank of the first hit from the expected page, or None."""
    for position, hit in enumerate(hits, start=1):
        if hit.source == expect_source:
            return position
    return None


def evaluate(index: Index, cases: list[Case], *, depth: int = DEPTH) -> Report:
    """Run every case through the retriever and collect results."""
    results: list[Result] = []
    for case in cases:
        hits = index.search(case.question, limit=depth)
        filtered = index.search(case.question, diataxis=case.expect_diataxis, limit=depth)

        top = hits[0] if hits else None
        missing: tuple[str, ...] = ()
        if top and case.must_contain:
            haystack = f"{top.breadcrumb}\n{top.text}".lower()
            missing = tuple(t for t in case.must_contain if t.lower() not in haystack)
        elif not top:
            missing = case.must_contain

        results.append(
            Result(
                case=case,
                rank=_rank_of(hits, case.expect_source),
                filtered_rank=_rank_of(filtered, case.expect_source),
                top_source=top.source if top else "",
                top_diataxis=top.diataxis if top else "",
                top_breadcrumb=top.breadcrumb if top else "",
                grounded=not missing,
                missing_terms=missing,
            )
        )
    return Report(tuple(results))


def format_report(report: Report, *, verbose: bool = False) -> str:
    """Render a report as plain text for a terminal or a CI log."""
    out: list[str] = []
    pct = lambda v: f"{v * 100:5.1f}%"  # noqa: E731

    out.append(f"retrieval evaluation: {report.total} cases, top-{DEPTH}")
    out.append("")
    out.append(f"  hit@1               {pct(report.hit_at_1)}")
    out.append(f"  hit@{DEPTH}               {pct(report.hit_at_k)}")
    out.append(f"  MRR                 {report.mrr:6.3f}")
    out.append(f"  routing accuracy    {pct(report.routing_accuracy)}")
    out.append(f"  grounded@1          {pct(report.grounded_rate)}")
    out.append("")
    out.append(f"  hit@1 with type filter   {pct(report.filtered_hit_at_1)}")
    out.append(
        f"  routing headroom         {report.routing_headroom * 100:+5.1f}% "
        "(not an achievable score; see docs/explanation/evaluating-retrieval.md)"
    )

    rows = [r for r in report.results if verbose or not r.hit_1]
    if rows:
        out.append("")
        width = max(len(r.case.id) for r in rows)
        out.append(f"  {'case':<{width + 2}} rank  top result")
        out.append("  " + "-" * (width + 40))
        for r in rows:
            rank = str(r.rank) if r.rank else "-"
            flag = " " if r.hit_1 else "!"
            got = r.top_source if not r.hit_1 else ""
            out.append(f"  {flag} {r.case.id:<{width}} {rank:>4}  {got}")

    ungrounded = [r for r in report.results if not r.grounded]
    if ungrounded:
        out.append("")
        out.append("  top chunk missing required terms:")
        for r in ungrounded:
            # The term check reads the chunk, so the message has to name the
            # chunk. Naming the page instead reads as "this page never mentions
            # size", which sends a reader to grep pack-for-rag.md, find
            # "## Control chunk size", and conclude the metric is broken. The
            # failure grounded@1 exists to catch is the right page and the
            # wrong section, and only the breadcrumb says which section.
            where = r.top_breadcrumb or r.top_source or "(nothing retrieved)"
            out.append(f"    {r.case.id}: {list(r.missing_terms)} not in {where}")

    return "\n".join(out)
