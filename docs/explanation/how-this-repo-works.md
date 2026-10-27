---
title: How this repository is built
summary: What this repo demonstrates and how the pieces fit together.
diataxis: explanation
audience: new-user
updated: 2026-10-26
tags: [meta, docs-as-code]
---

# How this repository is built

This repository is two things. `docpack` is a small working library. The
documentation around it is the actual subject: a demonstration of a
documentation system where the standards are enforced by machinery rather than
by review comments.

## The principle

**Make the right way the path of least resistance.** Every convention here is either automated
or validated. A convention that depends on everyone remembering it is not a
convention, it is a hope.

## The pieces

| Layer | What it does | Where |
|---|---|---|
| Content model | Typed front matter, closed vocabularies | `src/docpack/frontmatter.py` |
| Structure | Diátaxis, four directories, one type per page | `docs/` |
| Reference | Generated from docstrings, never hand-copied | `mkdocstrings` in `mkdocs.yml` |
| Prose | Style rules as lint | `.vale.ini`, `styles/` |
| Links | Every internal link resolves | `scripts/check_links.py` |
| Samples | Every Python block in the docs is executed | `tests/test_doc_samples.py` |
| Cold start | Quickstart run from an empty environment | `scripts/coldstart.sh` |
| Retrieval | Chunks, llms.txt, llms-full.txt | `docpack` CLI |
| Agents | Docs exposed over MCP | `mcp_server/server.py` |

## Why reference is generated

Hand-written API reference is wrong the moment a signature changes, and nobody
notices until a reader files an issue. `mkdocstrings` reads the docstrings out
of the source, so the reference cannot drift from the code.

The tradeoff is that docstring quality becomes documentation quality. That is
the right place for the pressure to land.

## Why samples are executed

A code sample that CI does not run is a sample that will eventually be wrong.
`tests/test_doc_samples.py` extracts every ```python block from `docs/` and
executes it. A sample that genuinely cannot run standalone is marked with a
`# docpack: skip` comment, which makes the exception visible and countable
rather than silent.

## Why cold start is separate

Every other check runs against the repository as it stands, with dependencies
already installed. The cold-start check starts from nothing, installs the way a
reader would, and follows the tutorial's commands in order.

It catches the most common documentation failure there is: a quickstart that
works on the author's machine because of something they installed six months
ago and forgot about.

## Why the summary field is load-bearing

The content model requires a one-sentence `summary` on every page. That single
field is consumed five times: as the HTML meta description, as the Open Graph
and Twitter card description, as the `description` in a JSON-LD `TechArticle`
block, as the annotation beside each link in `llms.txt`, and as the retrieval
snippet attached to every chunk in `chunks.jsonl`.

This is deliberate. The usual arrangement gives search engines their own
hand-written description, which is written once at publication and never looked
at again, so it describes a page that no longer exists. Deriving all five from a
required field means the page cannot be published without one, and updating it
updates everything downstream.

The JSON-LD block also carries the Diátaxis type, which is the part that matters
for retrieval rather than ranking. A crawler or an assistant reading the
structured data learns not just what the page is about but what kind of question
it can answer: a `reference` page will not explain a design tradeoff, and an
`explanation` page will not give a working command.

## What is measured

The checks above catch defects. They do not tell you whether the documentation
works. For that the metrics worth instrumenting are time to first success,
support deflection, and repeat questions.

Those are not implemented here, because they need a real audience to measure.
The hooks are noted in `docs/how-to/wire-up-ci.md` so the omission is
deliberate rather than overlooked.
