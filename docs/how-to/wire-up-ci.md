---
title: Wire up documentation CI
summary: Run content, prose, link, and sample checks on every pull request.
diataxis: how-to
audience: operator
updated: 2026-10-26
tags: [ci, automation]
---

# Wire up documentation CI

The pipeline in `.github/workflows/docs.yml` runs five checks. Each one catches
a different class of rot.

## The five checks

| Check | Command | Catches |
|---|---|---|
| Content model | `docpack docs --check` | Pages that cannot be routed or filtered |
| Prose | `vale docs/` | Style drift, banned terms, passive voice |
| Links | `python scripts/check_links.py docs/` | Internal links to pages that moved |
| Samples | `pytest tests/test_doc_samples.py` | Code in the docs that no longer runs |
| Cold start | `scripts/coldstart.sh` | A quickstart that only works on your machine |

## Why cold start matters most

The other four checks run against the repository as it exists. The cold-start
check starts from an empty container, installs the package the way a reader
would, and executes the tutorial's commands in order.

It is the only check that catches the most common documentation failure: a
quickstart that works for the person who wrote it because of something already
installed on their machine.

## Run the whole suite locally

```bash
docpack docs --check
python scripts/check_links.py docs/
python -m pytest -q
```

Vale needs a separate install; see the [Vale documentation](https://vale.sh).

## Add a new check

Checks live in `scripts/` and are plain Python with no framework. Add the
script, call it from the workflow, and make it exit non-zero on failure.

Keep each check fast and single-purpose. A slow check gets skipped, and a check
that reports three unrelated kinds of problem gets ignored.
