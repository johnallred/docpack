---
title: Pack a tree for retrieval
summary: Produce JSONL records sized and tagged for a vector store.
diataxis: how-to
audience: developer
updated: 2026-10-26
tags: [rag, retrieval]
---

# Pack a tree for retrieval

## Generate the records

```bash
docpack docs --out dist
```

`dist/chunks.jsonl` holds one JSON object per line.

## Control chunk size

To make chunks smaller or larger, change the token ceiling. The default soft
ceiling is 400 estimated tokens. Sections under that become a single chunk;
longer ones split on paragraph boundaries and keep the same heading trail.

To change it, call the library directly:

```python
from docpack.chunk import chunk_markdown

doc = "# Guide\n\nShort intro.\n\n## Details\n\nMore text here.\n"
chunks = chunk_markdown(doc, source="guide.md", max_tokens=120)
print([c.breadcrumb for c in chunks])
```

## Filter before you rank

Every record carries `diataxis`, `audience`, `updated`, and `tags`. Use them as
pre-filters rather than hoping the embedding captured them:

```python
import json
from pathlib import Path
from docpack.pack import load_tree, to_jsonl

pages = load_tree(Path("docs"))
records = [json.loads(line) for line in to_jsonl(pages).splitlines()]

how_tos = [r for r in records if r["diataxis"] == "how-to"]
print(f"{len(how_tos)} how-to chunks out of {len(records)}")
```

A user asking *how do I* wants instructions. Filtering to `how-to` before
ranking is cheaper and more reliable than hoping cosine similarity sorts it
out.

## Keep identifiers stable

Chunk IDs derive from the source path and heading trail, not from position.
Editing a paragraph near the top of a page does not renumber every chunk below
it, so re-indexing touches only what changed.

```python
from docpack.chunk import chunk_markdown

before = chunk_markdown("# A\n\nalpha\n\n## B\n\nbravo\n", source="t.md")
after = chunk_markdown("# A\n\nalpha rewritten\n\n## B\n\nbravo\n", source="t.md")
b_before = [c for c in before if c.breadcrumb == "A > B"][0]
b_after = [c for c in after if c.breadcrumb == "A > B"][0]
assert b_before.chunk_id == b_after.chunk_id
print("stable")
```

## Related

- [Why heading-aware chunking](../explanation/why-heading-aware-chunking.md)
- [API reference](../reference/api.md)
