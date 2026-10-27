---
title: Why heading-aware chunking
summary: Fixed-size chunking destroys the context that makes documentation retrievable.
diataxis: explanation
audience: developer
updated: 2026-10-26
tags: [rag, retrieval, chunking]
---

# Why heading-aware chunking

The default approach to chunking is a sliding window: cut every 512 tokens,
overlap by 50, move on. It is simple, it is fast, and for documentation it
throws away the single most useful signal in the document.

## What the window destroys

Consider a page with a section called **Rotating credentials** containing the
sentence *"Run the command twice: once to issue, once to revoke."*

Cut by character count, that sentence can land in a chunk that begins mid-list
in the previous section and ends mid-sentence in the next. Embedded on its own
it is nearly meaningless. Retrieved, it is worse than nothing, because an
assistant will confidently relay an instruction without the operation it
belongs to.

The heading said what the text was about. The window discarded it.

## What this chunker does instead

Split on heading boundaries first. Each chunk carries its full heading trail,
from the document root down. Only when a single section exceeds the soft token
ceiling does it split further, on paragraph boundaries, with every piece
keeping the same trail.

The result is that `Guide > Credentials > Rotating credentials` travels with
the chunk, and can be embedded alongside the text or used as a retrieval
filter.

## The bug every naive implementation has

A line starting with `#` inside a fenced code block is not a heading. It is a
shell comment.

```bash
# install the dependencies
pip install docpack
```

A regex that matches `^#` across the whole document will split that sample in
half and produce a chunk whose heading is "install the dependencies". This
chunker tracks fence state and ignores headings inside fences. There is a test
for it, because it is the kind of thing that silently returns plausible
garbage.

## Why identifiers are not positional

A chunk ID derived from "this is the fourth chunk in the file" changes whenever
anything above it changes. Insert a paragraph in the introduction and every
downstream ID shifts, so a re-index rewrites the entire document even though
one paragraph changed.

IDs here derive from the source path, the heading trail, and an ordinal within
the section. Editing the introduction leaves the credentials section's IDs
untouched, so incremental re-indexing actually works.

This is the same reasoning as diff-based change detection in a data pipeline:
the expensive part is not computing what changed, it is avoiding work on what
did not.

## What this approach costs

A document with poor heading structure chunks poorly, because the chunker
inherits whatever structure the author gave it. A twelve-page page with one H1
produces one enormous section that falls back to paragraph splitting with no
useful trail.

That is a real limitation, and the honest response is that it pushes the
problem to where it belongs. If a document cannot be chunked usefully, it is
usually because it cannot be read usefully either.
