---
title: The content model
summary: Why every page declares its type and audience, and why CI enforces it.
diataxis: explanation
audience: developer
updated: 2026-10-26
tags: [content-model, information-architecture]
---

# The content model

Most documentation sites have an information architecture that exists only in
the navigation file. Move a page, and nothing breaks. Write a reference page
that is secretly a tutorial, and nothing complains. The architecture is a
convention, and conventions decay.

This project treats the content model as a schema with a validator.

## What the model declares

Five required fields on every page: `title`, `summary`, `diataxis`,
`audience`, and `updated`. Two of them are closed vocabularies.

`diataxis` must be one of four values, because the
[Diátaxis framework](https://diataxis.fr) is the organizing idea of the corpus.
`audience` must be one of four values, because a page written for an operator
and a page written for a new user need different assumptions and should not be
returned interchangeably.

## Why closed vocabularies

An open tag field drifts. Within a year you have `howto`, `how-to`, `How To`,
and `guide`, all meaning the same thing, and any system built on top of them is
built on sand.

Closed vocabularies make drift a build failure instead of a slow degradation.
The cost is that adding a value requires a code change, which is the point:
adding a fifth Diátaxis type should require a conversation.

The `tags` field is deliberately open, because faceting benefits from
flexibility and nothing structural depends on it.

## Why summary is required

`summary` does three jobs:

1. It becomes the HTML meta description, which matters for search.
2. It becomes the annotation in `llms.txt`, which is what an assistant reads
   when choosing a page.
3. It becomes the snippet in retrieval results.

In all three cases it is read without the page around it. That is why the
guidance is to write a sentence that makes sense in isolation, and why a
missing summary fails the build rather than falling back to the first
paragraph. An auto-generated summary is usually wrong in a way nobody notices.

## Why updated is a date and not a string

`updated` drives the staleness check, and a staleness check that cannot parse
its own dates is theater. Making it a typed field means
`updated: "last reviewed in spring"` fails immediately rather than silently
disabling the check for that page.

Freshness is reported as a warning rather than an error. A stale page is a
prompt for review, not a reason to block a deploy.

## What this costs

Every new page requires five lines of front matter and a decision about what
kind of page it is. That friction is intentional. The decision has to be made
either way; the model forces it to the front, where it is cheap, instead of
leaving it to a reader who cannot find what they need.
