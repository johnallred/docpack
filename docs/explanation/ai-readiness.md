---
title: AI-readiness patterns
summary: Three output formats for three consumers, and why one file is not enough.
diataxis: explanation
audience: developer
updated: 2026-10-26
tags: [llms-txt, rag, agents]
---

# AI-readiness patterns

"Make the docs AI-ready" collapses three different consumers into one phrase.
They want different things, so this project emits three artifacts.

## The three consumers

**A retriever** wants small, independently meaningful units with metadata to
filter on. That is `chunks.jsonl`.

**An assistant choosing where to look** wants a map: what pages exist, what
each one covers, and what kind of answer it can support. That is `llms.txt`.

**An assistant doing a one-shot read** wants everything in a single fetch
without crawling thirty pages. That is `llms-full.txt`.

Serving only one of these means failing two consumers.

## About llms.txt

The convention was proposed by Jeremy Howard of Answer.AI in September 2024: a
Markdown file at `/llms.txt` with an H1 name, a blockquote summary, and H2
sections of annotated links. A companion `llms-full.txt` concatenates the
corpus.

Adoption grew substantially after Mintlify rolled it out across the
documentation sites it hosts, and it is now served by a large number of
developer-facing sites.

**It is worth being accurate about its status.** It is a community proposal,
not a ratified standard. No major model provider has formally committed to
consuming it, and some practitioners argue it duplicates what a well-structured
sitemap already provides. The honest position is that it is cheap to generate,
it demonstrably gets fetched, and the structural discipline it imposes is
useful regardless of who reads the file.

This project groups the index by Diátaxis type, which is a small addition to
the convention. Telling an assistant that a page is a how-to rather than an
explanation helps it pick, in the same way it helps a human.

## Why generated and not hand-maintained

A hand-written `llms.txt` is accurate on the day it is written. Here it is
generated from the same front matter that drives navigation and retrieval, so
it cannot drift from the corpus: adding a page updates all three artifacts, or
the build fails.

Hand-maintained index files are the most reliably stale artifact in any
documentation system.

## What is deliberately not here

No embeddings, and no vector store. `docpack` stops at producing records with
stable IDs and clean metadata. Which embedding model, which store, and which
retrieval strategy are decisions that depend on the deployment, and a library
that made them for you would be in the way.

The boundary is drawn where the general problem ends and the specific one
begins.
