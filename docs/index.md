---
title: docpack
summary: Turn a documentation tree into retrieval-ready, agent-readable artifacts.
diataxis: explanation
audience: new-user
updated: 2026-10-26
tags: [overview]
---

# docpack

`docpack` reads a documentation tree, validates it against a declared content
model, splits it into retrieval-sized chunks that keep their heading context,
and emits artifacts for three different consumers.

## Where to start

| You want to | Go to |
|---|---|
| Get something working in ten minutes | [Package your first tree](tutorials/getting-started.md) |
| Solve a specific problem | The [how-to guides](how-to/pack-for-rag.md) |
| Look up a function signature | The [API reference](reference/api.md) |
| Understand why it works this way | The [explanations](explanation/content-model.md) |

That table is the Diataxis framework in miniature: learning, task, information,
and understanding are four different needs, and mixing them into one page
serves none of them.

## What it produces

**`chunks.jsonl`** for a vector store. One record per chunk, carrying the
chunk text plus the page's content-model metadata so a retriever can filter
before it ranks.

**`llms.txt`** for an assistant that needs a map of the site. An annotated
index grouped by Diataxis type.

**`llms-full.txt`** for an assistant that would rather make one request than
thirty.

## About this repository

This repo is two things at once. `docpack` is a working library, and the
documentation around it is a demonstration of a documentation system: content
model validation, prose linting, link checking, executable code samples, and
cold-start testing of the quickstart, all enforced in CI.

See [How this repository is built](explanation/how-this-repo-works.md).
