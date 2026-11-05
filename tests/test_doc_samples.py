"""Execute every Python code sample in the documentation.

A code sample that CI does not run is a sample that will eventually be wrong.
This module extracts every fenced ```python block from `docs/` and executes it
in a fresh namespace with the repository root as the working directory.

A sample that genuinely cannot run standalone is marked with `# docpack: skip`
on its first line. That makes the exception visible and countable rather than
silent, and the test below asserts that skips stay rare.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
DOCS = REPO_ROOT / "docs"

#: Fenced blocks tagged `python`, capturing the body.
PY_BLOCK = re.compile(r"^```python\s*\n(.*?)^```", re.MULTILINE | re.DOTALL)
SKIP_MARKER = "# docpack: skip"


@dataclass(frozen=True)
class Sample:
    """One extracted code sample."""

    path: Path
    index: int
    code: str

    @property
    def skipped(self) -> bool:
        return SKIP_MARKER in self.code.splitlines()[0] if self.code.strip() else False

    @property
    def label(self) -> str:
        return f"{self.path.relative_to(DOCS)}#{self.index}"


def collect_samples() -> list[Sample]:
    """Find every Python sample in the documentation tree."""
    out: list[Sample] = []
    for page in sorted(DOCS.rglob("*.md")):
        text = page.read_text(encoding="utf-8")
        for i, match in enumerate(PY_BLOCK.finditer(text)):
            out.append(Sample(path=page, index=i, code=match.group(1)))
    return out


SAMPLES = collect_samples()
RUNNABLE = [s for s in SAMPLES if not s.skipped]


def test_documentation_contains_samples():
    """Guard against the extractor silently matching nothing."""
    assert SAMPLES, "no Python samples found; the extractor regex is probably wrong"


def test_skipped_samples_stay_rare():
    """Skips are an escape hatch, not a habit."""
    ratio = (len(SAMPLES) - len(RUNNABLE)) / len(SAMPLES)
    assert ratio <= 0.25, f"{ratio:.0%} of samples are skipped; make them runnable"


@pytest.mark.parametrize("sample", RUNNABLE, ids=lambda s: s.label)
def test_sample_executes(sample: Sample, monkeypatch, capsys):
    """Execute a documentation sample and fail the build if it raises."""
    monkeypatch.chdir(REPO_ROOT)
    namespace: dict[str, object] = {"__name__": "__doc_sample__"}
    try:
        exec(compile(sample.code, sample.label, "exec"), namespace)
    except Exception as exc:  # noqa: BLE001 - we want the sample's own error
        captured = capsys.readouterr()
        pytest.fail(
            f"sample {sample.label} raised {type(exc).__name__}: {exc}\n"
            f"--- stdout ---\n{captured.out}\n"
            f"--- code ---\n{sample.code}"
        )


# ------------------------------------------- the README's own first impression


def _readme_quick_start_commands() -> list[str]:
    """Every shell command in the README's "Quick start" section, in order."""
    text = (Path(__file__).resolve().parent.parent / "README.md").read_text("utf-8")
    section = text.partition("## Quick start")[2].partition("\n## ")[0]
    commands: list[str] = []
    for block in re.findall(r"```bash\n(.*?)```", section, re.S):
        for line in block.splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                commands.append(line.split("#")[0].strip())
    return commands


#: Commands that leave the reader holding something: a file, an answer, a
#: running process. Anything else prints a report and exits zero.
PRODUCES_SOMETHING = ("docpack docs --out", "docpack search", "docpack new", "mcp_server/server.py")


def test_the_quick_start_leads_with_a_command_that_produces_something():
    """The metric this encodes is time-to-first-success, and it was once infinite.

    `scripts/coldstart.sh` asserts that a reader reaches a working result in
    about nine seconds. It passed throughout, while the first reader to follow
    the README ran every command, watched them all exit zero, and could not
    tell what the library did. The cold-start test measured the tutorial's
    command sequence; the reader followed the README's, where the first four
    commands were validators and the artifact command came ninth.

    An entry point nobody instrumented is an entry point where the metric is
    silently absent, so this test instruments the other door.
    """
    commands = _readme_quick_start_commands()
    assert commands, "the README has no Quick start commands"

    installs = [c for c in commands if c.startswith("pip install")]
    rest = [c for c in commands if not c.startswith("pip install")]
    assert installs, "the quick start should still say how to install"

    first = rest[0]
    assert any(first.startswith(p) or p in first for p in PRODUCES_SOMETHING), (
        f"the first quick-start command after install is {first!r}, which only "
        "reports. Lead with a command that leaves the reader holding something."
    )
