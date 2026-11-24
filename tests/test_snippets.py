"""Topic-level reuse: a snippet written once, included in pages, expanded everywhere.

The site build expands includes through pymdownx.snippets. The packer has to do
the same, or every retrieval artifact carries the include line instead of the
fact. And a snippet that states what the code enforces has to agree with it.
"""

import re
from pathlib import Path

import pytest

from docpack.frontmatter import AUDIENCES, DIATAXIS_TYPES, ContentModelError
from docpack.pack import SNIPPET, expand_snippets, load_tree

ROOT = Path(__file__).resolve().parent.parent
SNIPPETS = ROOT / "snippets"


def test_no_include_line_survives_into_a_chunk():
    pages = load_tree(ROOT / "docs")
    leaked = [c.id for p in pages for c in p.chunks if "--8<--" in c.text]
    assert not leaked


def test_the_vocabulary_snippet_is_included_in_more_than_one_page():
    users = [p for p in (ROOT / "docs").rglob("*.md")
             if '--8<-- "vocabularies.md"' in p.read_text(encoding="utf-8")]
    assert len(users) >= 2, "a snippet used once is a page fragment, not reuse"


def test_the_vocabulary_snippet_states_what_the_code_enforces():
    text = (SNIPPETS / "vocabularies.md").read_text(encoding="utf-8")
    diataxis, audience = text.splitlines()[:2]
    assert set(re.findall(r"`([\w-]+)`", diataxis)) - {"diataxis"} == DIATAXIS_TYPES
    assert set(re.findall(r"`([\w-]+)`", audience)) - {"audience"} == AUDIENCES


def test_a_missing_snippet_fails_rather_than_leaving_a_hole(tmp_path):
    with pytest.raises(ContentModelError, match="nowhere.md"):
        expand_snippets('Text.\n\n--8<-- "nowhere.md"\n', tmp_path, source="page.md")


def test_every_include_names_a_snippet_that_exists():
    for page in (ROOT / "docs").rglob("*.md"):
        for name in SNIPPET.findall(page.read_text(encoding="utf-8")):
            assert (SNIPPETS / name).is_file(), f"{page} includes missing {name}"
