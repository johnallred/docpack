"""Every figure the documentation quotes is the figure the tools produce.

`tests/test_doc_samples.py` executes the samples and asserts they run. That is
the easier half and it was the only half: nothing compared a sample's *output*
to the output printed beside it in the page. So the README could promise
"packed 12 pages into 85 chunks" indefinitely after either number moved, and
the gate that exists to keep documentation honest would have stayed green,
because the command still exited zero.

This is the defect this repository exists to prevent, found in this repository.
A page that quotes output makes two claims, that the command does this and that
this is what the command does, and executing the command tests only the first.

The figures are deliberately checked against live runs rather than against
constants duplicated here. A constant in a test is a second place to update,
and the second place is the one that rots.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
README = REPO / "README.md"
DOCS = REPO / "docs"


def readme() -> str:
    return README.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def packed(tmp_path_factory) -> tuple[str, Path]:
    """Run the README's own pack command into a temporary directory."""
    out = tmp_path_factory.mktemp("dist")
    result = subprocess.run(
        [sys.executable, "-m", "docpack.cli", "docs", "--out", str(out)],
        cwd=REPO,
        capture_output=True,
        text=True,
        timeout=300,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    return result.stdout.strip(), out


def test_the_readme_quotes_the_pack_line_the_command_prints(packed):
    """The headline figure, which is the first output a reader sees."""
    printed, out = packed
    pages, chunks = re.search(r"packed (\d+) pages into (\d+) chunks", printed).groups()

    quoted = re.search(r"packed (\d+) pages into (\d+) chunks -> dist", readme())
    assert quoted, "the README no longer quotes the pack line at all"
    assert (quoted.group(1), quoted.group(2)) == (pages, chunks), (
        f"the README says {quoted.group(1)} pages and {quoted.group(2)} chunks; "
        f"the command prints {pages} and {chunks}"
    )


def test_the_chunk_count_matches_the_file_it_describes(packed):
    """The same number again, counted off the artifact rather than the message.

    Two independent routes to one figure, because the pack line and the file
    are written by the same code: if that code is wrong, the message and the
    file agree with each other and both disagree with the corpus.
    """
    _printed, out = packed
    records = [
        line for line in (out / "chunks.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    for record in records:
        json.loads(record)

    quoted = re.search(r"dist/chunks\.jsonl\s+\S+\s+(\d+) records", readme())
    assert quoted, "the README no longer states a record count for chunks.jsonl"
    assert int(quoted.group(1)) == len(records), (
        f"the README says {quoted.group(1)} records; the file holds {len(records)}"
    )


@pytest.mark.parametrize(
    "artifact", ["chunks.jsonl", "llms.txt", "llms-full.txt"]
)
def test_the_quoted_artifact_sizes_are_the_right_order_of_magnitude(packed, artifact):
    """Sizes to one significant figure, which is what the README prints.

    A byte-exact assertion would fail on any edit to any page, so this checks
    the rounded figure the README actually shows. The looser check is the
    honest one: the claim on the page is "74K", not 75,049 bytes.
    """
    _printed, out = packed
    actual = (out / artifact).stat().st_size

    quoted = re.search(
        r"dist/" + re.escape(artifact) + r"\s+([\d.]+)K", readme()
    )
    assert quoted, f"the README no longer states a size for {artifact}"
    claimed = float(quoted.group(1)) * 1024
    assert abs(actual - claimed) / claimed < 0.15, (
        f"the README says {quoted.group(1)}K for {artifact}; it is "
        f"{actual / 1024:.1f}K, which is more than 15 per cent out"
    )


def test_the_evaluation_page_quotes_the_scores_the_evaluator_produces():
    """The five figures on the retrieval page, against a live scoring run.

    These are the numbers a reader is most likely to repeat back, and they are
    the ones least likely to survive a change to chunking or to the corpus.
    """
    result = subprocess.run(
        [sys.executable, "-m", "docpack.cli", "eval", "evals/golden.yaml"],
        cwd=REPO,
        capture_output=True,
        text=True,
        timeout=300,
    )
    assert result.returncode == 0, result.stdout + result.stderr

    live = {}
    for name, pattern in (
        ("hit@1", r"hit@1\s+([\d.]+)%"),
        ("hit@3", r"hit@3\s+([\d.]+)%"),
        ("MRR", r"MRR\s+([\d.]+)"),
        ("routing accuracy", r"routing accuracy\s+([\d.]+)%"),
        ("grounded@1", r"grounded@1\s+([\d.]+)%"),
    ):
        match = re.search(pattern, result.stdout)
        assert match, f"the evaluator no longer prints {name}"
        live[name] = float(match.group(1))

    page = (DOCS / "explanation" / "evaluating-retrieval.md").read_text(encoding="utf-8")
    wrong = []
    for name, value in live.items():
        row = re.search(r"\|\s*" + re.escape(name) + r"\s*\|\s*([\d.]+)%?\s*\|", page)
        assert row, f"the page no longer has a row for {name}"
        if abs(float(row.group(1)) - value) > 0.05:
            wrong.append(f"{name}: page says {row.group(1)}, run gives {value}")

    assert not wrong, "published scores disagree with a live run:\n  " + "\n  ".join(wrong)


def test_the_readme_states_the_number_of_gates_the_workflow_has():
    """A count in prose, checked against the file it counts.

    The companion repository had the same class of defect in eight places at
    once: a contract gained a seventh section and its documentation went on
    saying six, in both front doors, a table cell, a front-matter summary, a
    CLI message and a docstring. A wrong number written as a word is valid
    prose that spell-checks clean.
    """
    import yaml

    workflow = yaml.safe_load(
        (REPO / ".github" / "workflows" / "docs.yml").read_text(encoding="utf-8")
    )

    # Gates are counted by job rather than by step name. The first version of
    # this filtered out any step whose name began with "Generate", meaning to
    # exclude the publish job's "Generate AI-readable artifacts", and it
    # swallowed the quality job's "Generated pages pass validation" with it.
    # It then reported nine gates for a workflow with ten and failed against a
    # correct README. A prefix match on a human-written label is a guess; the
    # job a step belongs to is a fact.
    publishing = {"publish", "deploy"}
    gates: list[str] = []
    for name, job in workflow["jobs"].items():
        if name in publishing:
            continue
        for step in job.get("steps", []):
            label = step.get("name")
            if label and not label.startswith(("Install", "Checkout", "Set up")):
                gates.append(f"{name}: {label}")

    words = {9: "Nine", 10: "Ten", 11: "Eleven", 12: "Twelve", 13: "Thirteen"}
    quoted = re.search(r"\|\s*(\w+) gates on every pull request: (\w+) checks", readme())
    assert quoted, "the README no longer states a gate count"
    # Case-insensitive: the README capitalises the first of the two counts
    # because it opens a sentence and lower-cases the second.
    assert quoted.group(1).lower() == (words.get(len(gates)) or "").lower(), (
        f"the README says {quoted.group(1)} gates; the workflow has "
        f"{len(gates)}: {gates}"
    )

    # The README splits that total, so check the split too: the cold start is
    # its own job precisely because it is slow, and "nine checks plus the cold
    # start" is a claim about where the gates live.
    checks = [g for g in gates if not g.startswith("coldstart")]
    assert quoted.group(2).lower() == (words.get(len(checks)) or "").lower(), (
        f"the README says {quoted.group(2)} checks outside the cold start; "
        f"there are {len(checks)}"
    )


def test_the_readme_states_the_number_of_tests_that_exist():
    """The claim that rotted four times in the companion repository.

    Collected rather than run, so this stays fast and cannot recurse.
    """
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q", "-p", "no:cacheprovider"],
        cwd=REPO,
        capture_output=True,
        text=True,
        timeout=300,
    )
    collected = re.search(r"(\d+) tests? collected", result.stdout)
    assert collected, f"could not read a collected count:\n{result.stdout[-500:]}"

    quoted = re.search(r"#\s*(\d+) tests: units, doctests, doc samples", readme())
    assert quoted, "the README no longer states a test count"
    assert int(quoted.group(1)) == int(collected.group(1)), (
        f"the README says {quoted.group(1)} tests; pytest collects "
        f"{collected.group(1)}"
    )
