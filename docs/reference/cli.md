---
title: Command line reference
summary: Every docpack command, flag, and exit code.
diataxis: reference
audience: developer
updated: 2026-10-26
tags: [cli, api]
---

# Command line reference

## Synopsis

```
docpack DOCS [--out DIR] [--site-name NAME] [--site-url URL]
             [--tagline TEXT] [--check]

docpack new TYPE --title TITLE [--docs DIR] [--audience AUDIENCE]
                 [--summary TEXT] [--tags LIST] [--dry-run]

docpack eval GOLDEN [--docs DIR] [-v] [--fail-under MRR]
```

Packing is the default command and takes the documentation directory as its
first argument, so it needs no subcommand name. A first argument of `new` or
`eval` selects those commands instead.

## Pack

## Arguments

| Argument | Required | Default | Description |
|---|---|---|---|
| `DOCS` | yes | | Path to the documentation tree |
| `--out` | no | `dist` | Output directory for generated artifacts |
| `--site-name` | no | `docpack` | H1 of the generated `llms.txt` |
| `--site-url` | no | `https://example.com` | Base URL for generated links |
| `--tagline` | no | see below | Blockquote summary in `llms.txt` |
| `--check` | no | off | Validate and exit without writing |

The default tagline is `Retrieval-ready documentation packaging.`

## Outputs

Writing mode produces three files in `--out`:

| File | Consumer |
|---|---|
| `chunks.jsonl` | Vector store or search index. One record per line |
| `llms.txt` | An assistant choosing which page to read |
| `llms-full.txt` | An assistant reading the whole corpus at once |

## New

Generates a page with valid front matter and a skeleton matching its type.

```
docpack new {tutorial|how-to|reference|explanation} --title TITLE
```

| Argument | Required | Default | Description |
|---|---|---|---|
| `TYPE` | yes | | One of the four Diátaxis types |
| `--title` | yes | | Page title. Also sets the filename, slugified |
| `--docs` | no | `docs` | Root of the documentation tree |
| `--audience` | no | by type | One of `new-user`, `developer`, `operator`, `contributor` |
| `--summary` | no | a `TODO` placeholder | One-sentence summary |
| `--tags` | no | none | Comma-separated tags |
| `--dry-run` | no | off | Print the page instead of writing it |

The directory is determined by the type, not by the caller: `tutorial` goes to
`tutorials/`, `how-to` to `how-to/`, and so on.

An existing file is never overwritten and there is no `--force`.

## Eval

Scores retrieval over the corpus against a golden set of questions. See
[Evaluating retrieval](../explanation/evaluating-retrieval.md).

```
docpack eval GOLDEN [--fail-under MRR]
```

| Argument | Required | Default | Description |
|---|---|---|---|
| `GOLDEN` | yes | | YAML golden set |
| `--docs` | no | `docs` | Root of the documentation tree |
| `-v`, `--verbose` | no | off | Show every case, not just the misses |
| `--fail-under` | no | none | Exit `1` if MRR falls below this value |

## Exit codes

| Code | Meaning |
|---|---|
| `0` | Success. In `--check` mode, all pages conform |
| `1` | A page violated the content model, or `eval` fell below `--fail-under` |
| `2` | Argument parsing failed, or a malformed golden set, or a target file exists |

Staleness produces a warning on stdout and does not affect the exit code.

## Examples

Validate without writing:

```bash
docpack docs --check
```

Build artifacts for a published site:

```bash
docpack docs --out site/static --site-name "Widget API" --site-url "https://widgets.example"
```

Start a new how-to guide:

```bash
docpack new how-to --title "Rotate the signing key" --summary "Replace the key with no downtime."
```

Score retrieval and fail the build if it regresses:

```bash
docpack eval evals/golden.yaml --docs docs --fail-under 0.70
```
