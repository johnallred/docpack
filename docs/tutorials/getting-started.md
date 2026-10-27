---
title: Package your first documentation tree
summary: Go from an empty directory to a set of retrieval-ready artifacts in about ten minutes.
diataxis: tutorial
audience: new-user
updated: 2026-10-26
tags: [quickstart, golden-path]
---

# Package your first documentation tree

By the end of this tutorial you will have taken a small documentation tree and
produced three artifacts from it: a JSONL file of retrieval records, an
`llms.txt` index, and a single-file corpus dump.

You need Python 3.10 or newer and nothing else. **This page is executed by CI
from a clean container on every commit**, so if a step here does not work, the
build fails before you ever read it.

## Step 1: Install docpack

```bash
python -m venv .venv
source .venv/bin/activate
pip install docpack
```

Check that it worked:

```bash
docpack --help
```

You should see the usage message. If you see `command not found`, the virtual
environment is not active; run the `source` line again.

## Step 2: Make a documentation tree

Create two pages. The front matter is not optional, and step 4 explains why.

```bash
mkdir -p mydocs/how-to
```

Write `mydocs/index.md`:

```markdown
---
title: Widget API
summary: A small API for managing widgets.
diataxis: explanation
audience: new-user
updated: 2026-10-26
---

# Widget API

The Widget API lets you create, list, and retire widgets.

## Concepts

A widget has an identifier and a state. States are `active` and `retired`.
```

Write `mydocs/how-to/create-a-widget.md`:

```markdown
---
title: Create a widget
summary: Create a widget and confirm it exists.
diataxis: how-to
audience: developer
updated: 2026-10-26
---

# Create a widget

Send a POST request to the widgets endpoint.

## Confirm it worked

List the widgets and check that yours appears.
```

## Step 3: Pack it

```bash
docpack mydocs --out dist --site-name "Widget API" --site-url "https://widgets.example"
```

You should see:

```
packed 2 pages into 4 chunks -> dist
```

Four chunks from two pages, because each heading starts a new chunk and both
pages have two headings.

## Step 4: Look at what you got

```bash
cat dist/llms.txt
```

The file groups your pages by their Diátaxis type, with the `summary` from the
front matter as each link's annotation. That is why the content model requires
a summary: it is not decoration, it is the text an assistant reads when
deciding which page answers a question.

```bash
head -1 dist/chunks.jsonl
```

Each record carries the chunk text plus the page's metadata. A retriever can
filter to `"diataxis": "how-to"` before ranking, so a user asking *how do I*
gets instructions rather than conceptual background.

## Step 5: Break it on purpose

Edit `mydocs/how-to/create-a-widget.md` and change the `diataxis` line to
`diataxis: blog-post`. Then run:

```bash
docpack mydocs --check
```

The command fails and names the file and the problem. **This is the whole point
of the content model.** A page that does not declare what it is cannot be
routed, filtered, or retrieved correctly, so the build refuses it rather than
letting it rot in the corpus.

Change it back to `how-to` and run `docpack mydocs --check` again. It passes.

## What you built

You now have a documentation tree that validates against a content model, and
three artifacts generated from it for three different consumers.

## Next

- [Pack a tree for RAG](../how-to/pack-for-rag.md) covers the output formats in detail.
- [Why heading-aware chunking](../explanation/why-heading-aware-chunking.md)
  explains what the chunker is doing and why the naive approach fails.
