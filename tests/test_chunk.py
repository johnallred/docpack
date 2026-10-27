"""Unit tests for heading-aware chunking."""
from docpack.chunk import chunk_markdown, split_sections


def test_headings_become_section_boundaries():
    doc = "# A\n\nalpha\n\n## B\n\nbravo\n"
    chunks = chunk_markdown(doc, source="t.md")
    assert [c.breadcrumb for c in chunks] == ["A", "A > B"]


def test_heading_trail_nests():
    doc = "# A\n\nx\n\n## B\n\ny\n\n### C\n\nz\n"
    assert [c.breadcrumb for c in chunk_markdown(doc)] == ["A", "A > B", "A > B > C"]


def test_returning_to_shallower_level_truncates_trail():
    doc = "# A\n\n1\n\n## B\n\n2\n\n# D\n\n3\n"
    assert [c.breadcrumb for c in chunk_markdown(doc)] == ["A", "A > B", "D"]


def test_headings_inside_code_fences_are_not_headings():
    doc = "# Real\n\nbefore\n\n```bash\n# not a heading\necho hi\n```\n\nafter\n"
    chunks = chunk_markdown(doc)
    assert len(chunks) == 1
    assert chunks[0].breadcrumb == "Real"
    assert "not a heading" in chunks[0].text


def test_empty_sections_are_dropped():
    doc = "# A\n\n## Empty\n\n## B\n\ncontent\n"
    assert [c.breadcrumb for c in chunk_markdown(doc)] == ["A > B"]


def test_chunk_ids_are_stable_against_earlier_edits():
    first = chunk_markdown("# A\n\nalpha\n\n## B\n\nbravo\n", source="t.md")
    second = chunk_markdown("# A\n\nalpha EDITED\n\n## B\n\nbravo\n", source="t.md")
    b_first = [c for c in first if c.breadcrumb == "A > B"][0]
    b_second = [c for c in second if c.breadcrumb == "A > B"][0]
    assert b_first.chunk_id == b_second.chunk_id


def test_oversized_sections_split_on_paragraphs():
    para = "word " * 200
    doc = f"# Big\n\n{para}\n\n{para}\n\n{para}\n"
    chunks = chunk_markdown(doc, max_tokens=150)
    assert len(chunks) > 1
    assert all(c.breadcrumb == "Big" for c in chunks)


def test_record_round_trips():
    c = chunk_markdown("# A\n\nbody\n", source="t.md")[0]
    rec = c.to_record()
    assert rec["source"] == "t.md" and rec["breadcrumb"] == "A"
    assert set(rec) == {"id", "text", "breadcrumb", "source", "tokens"}


def test_document_without_headings_still_chunks():
    assert len(chunk_markdown("just a paragraph\n")) == 1


def test_split_sections_handles_empty_input():
    assert split_sections("") == []
