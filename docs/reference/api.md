---
title: Python API reference
summary: Generated reference for every public function and class in docpack.
diataxis: reference
audience: developer
updated: 2026-10-26
tags: [api]
---

# Python API reference

Generated from docstrings at build time. If something here is wrong, the
docstring is wrong.

## Chunking

::: docpack.chunk
    options:
      show_root_heading: false
      members: [Chunk, chunk_markdown, split_sections]

## Content model

::: docpack.frontmatter
    options:
      show_root_heading: false
      members: [PageMeta, ContentModelError, parse_page, split_front_matter]

## Packaging

::: docpack.pack
    options:
      show_root_heading: false
      members: [Page, load_tree, to_jsonl, to_llms_txt, to_llms_full_txt]

## Retrieval

::: docpack.retrieve
    options:
      show_root_heading: false
      members: [Index, Hit, tokenize]

## Evaluation

::: docpack.evaluate
    options:
      show_root_heading: false
      members: [Case, Result, Report, GoldenSetError, load_golden_set, evaluate, format_report]

## Page generation

::: docpack.scaffold
    options:
      show_root_heading: false
      members: [NewPage, ScaffoldError, render_page, new_page, write_page, slugify]
