# docpack

**A documentation system, demonstrated by building one.**

`docpack` is a small Python library that turns a documentation tree into
retrieval-ready, agent-readable artifacts. The library is real and tested, but
it is also the subject: this repository exists to show what a documentation
platform looks like when the standards are enforced by machinery rather than by
review comments.

## What it makes

One command, and three files:

```bash
docpack docs --out dist
```

```
packed 12 pages into 85 chunks -> dist

dist/chunks.jsonl    74K   85 records, one per section, for a vector store
dist/llms.txt       2.2K   a map of the corpus, grouped by Diátaxis type
dist/llms-full.txt   45K   every page as one file, for a long context window
```

`chunks.jsonl` is the real output. One record per heading-bounded section,
carrying the metadata a retriever filters on:

```json
{
  "id": "954d9bb259ea2405",
  "source": "explanation/evaluating-retrieval.md",
  "breadcrumb": "Evaluating retrieval > The golden set",
  "diataxis": "explanation",
  "audience": "developer",
  "tags": ["rag", "retrieval", "evaluation"],
  "summary": "Why a golden set of questions is the only check that measures whether the docs answer anything.",
  "text": "`evals/golden.yaml` holds twenty cases. Each one pairs a question with ..."
}
```

## What it is for

Ask the corpus a question the way a reader would phrase it:

```bash
docpack search "how do I make the chunks smaller"
```

```
  "how do I make the chunks smaller"   (85 chunks indexed)

  1. Pack a tree for retrieval > Control chunk size
     how-to/pack-for-rag.md  [how-to]
     To make chunks smaller or larger, change the token ceiling. The default ...
```

That is the whole proposition, and that result used to be wrong. It returned
the right page and the wrong section, because the page said "token ceiling" and
never said "smaller", so the reader's word was absent from a corpus of 1,159
terms. `docpack eval` is the same question asked twenty times with the answers
written down, which is how a missing synonym shows up as a number instead of a
hunch: adding that one word and one other moved four of five retrieval scores.
See [Evaluating retrieval](docs/explanation/evaluating-retrieval.md).

Which is the point of the repository. The artifacts are checkable, so the gap
between "the docs are correct" and "the docs answer questions" is a figure you
can argue about.

---

## What this repository demonstrates

| Capability | Where to look | Verified by |
|---|---|---|
| **Retrieval evaluation against a golden set** | [`evals/golden.yaml`](evals/golden.yaml), [`src/docpack/evaluate.py`](src/docpack/evaluate.py) | 20 cases scored on hit@k, MRR, routing, and grounding, with a floor enforced in CI |
| **Standards encoded in a generator, not just a validator** | [`src/docpack/scaffold.py`](src/docpack/scaffold.py) | `docpack new` output is validated by CI, so it cannot drift from the content model |
| **Golden path, clean environment to working result** | [`docs/tutorials/getting-started.md`](docs/tutorials/getting-started.md) | `scripts/coldstart.sh` |
| **Cold-start testing of the quickstart** | [`scripts/coldstart.sh`](scripts/coldstart.sh) | Runs the tutorial's commands in a fresh venv and asserts its promised output |
| **Docs-as-code pipeline** | [`.github/workflows/docs.yml`](.github/workflows/docs.yml) | Ten gates on every pull request: nine checks plus the cold start |
| **Published figures checked against live runs** | [`tests/test_published_figures.py`](tests/test_published_figures.py) | Every number this README and the retrieval page quote is re-derived from the tools, not duplicated as a constant |
| **Content model and information architecture** | [`src/docpack/frontmatter.py`](src/docpack/frontmatter.py) | `docpack docs --check` |
| **Diátaxis structure** | [`docs/`](docs/) | Four directories, one type per page, enforced |
| **Reference generated from source** | [`docs/reference/api.md`](docs/reference/api.md) | `mkdocstrings`, cannot drift from the code |
| **Prose linting** | [`.vale.ini`](.vale.ini), [`styles/`](styles/) | Vale, with terminology blocking and style advisory |
| **Link validation** | [`scripts/check_links.py`](scripts/check_links.py) | Internal links and heading anchors |
| **Code-sample validation** | [`tests/test_doc_samples.py`](tests/test_doc_samples.py) | Every Python block in the docs is executed |
| **RAG packaging** | [`src/docpack/pack.py`](src/docpack/pack.py) | Chunks with stable IDs and filterable metadata |
| **Retrieval you can try by hand** | [`src/docpack/cli.py`](src/docpack/cli.py) | `docpack search`, added after a reader ran the quick start and could not tell what the library did |
| **llms.txt and llms-full.txt** | `docpack docs --out dist` | Generated from front matter, so it cannot go stale |
| **Agent access over MCP** | [`mcp_server/server.py`](mcp_server/server.py) | JSON-RPC over stdio, three tools |
| **SEO and GEO from the content model** | [`hooks/seo.py`](hooks/seo.py) | `tests/test_seo_hook.py`; one `summary` feeds the meta description, Open Graph, JSON-LD, `llms.txt`, and the retrieval snippet |

## Quick start

```bash
pip install -e ".[dev,docs]"
```

**Commands that make or do something.** Start here. Each one leaves you with an
artifact or an answer.

```bash
docpack docs --out dist                   # the three files above
docpack search "how do I make the chunks smaller"   # ask the corpus
docpack new how-to --title "Rotate the key"         # a page that already conforms
python mcp_server/server.py --docs docs   # serve the docs to an agent
```

**Commands that check something.** Each one prints a report and exits zero when
the corpus is sound. They are the reason the artifacts above can be trusted, and
running them tells you nothing about what the library does, so do not start
with them.

```bash
docpack docs --check                      # validate the content model
python -m pytest -q                       # 142 tests: units, doctests, doc samples
python scripts/check_links.py docs/ --check-anchors
vale docs/                                # prose (install separately: https://vale.sh)
mkdocs build --strict                     # the site, warnings are errors
docpack eval evals/golden.yaml            # does the corpus answer questions
bash scripts/coldstart.sh                 # the tutorial, from an empty environment
```

That split is here because the first reader to run this quick start ran all
nine checkers, watched them pass, and could not tell what the library was for.
Eight of the nine print "ok" and produce nothing. `docpack search` did not exist
until that happened, and the ordering above is the fix.

## The ideas worth arguing about

Four decisions in here are opinions, not conventions, and the explanation pages
make the case for each.

**Correct documentation and useful documentation are different properties, and
only one of them is usually tested.** Links resolving and samples executing say
the docs are not broken. They say nothing about whether asking a question
returns the right page. `docpack eval` scores twenty real questions on hit@k,
MRR, whether the answer came back as the right *kind* of page, and whether the
retrieved chunk actually contains the fact an answer would need. It found two
bugs in this repository within minutes, one of them a required field that was
never indexed for search. Current scores are published, including the
unflattering ones. See
[Evaluating retrieval](docs/explanation/evaluating-retrieval.md).

**The content model is a schema, not a convention, and it ships with a
generator.** Five required front-matter fields, two of them closed
vocabularies, validated in CI. An open tag field drifts into `howto`, `how-to`,
and `How To` within a year, and anything built on top of it is built on sand.
But a validator alone only makes the right way *mandatory*, which is a
different and more annoying thing: a contributor who has to look up five fields
before writing a sentence copies whichever page is nearest and inherits its
mistakes. So `docpack new how-to --title "..."` writes a conforming page with a
skeleton of what that type owes its reader, and CI generates one page of every
type and validates it, so the generator cannot drift from the validator. See
[The content model](docs/explanation/content-model.md).

**Chunking splits on headings, not on character count.** A sliding window
destroys the heading that said what the text was about, which is the single
most useful retrieval signal a document has. Chunk IDs derive from the heading
trail rather than position, so editing the introduction does not force a
re-index of the whole document. See
[Why heading-aware chunking](docs/explanation/why-heading-aware-chunking.md).

**One summary, written once, serves five consumers.** The `summary` field is
required by the content model, so it exists on every page. The build sends it to
the meta description, the Open Graph tags, the JSON-LD block, the `llms.txt`
annotation, and the retrieval snippet in `chunks.jsonl`. Nobody writes an SEO
description separately, because a separately written one goes stale the first
time the page changes. See [`hooks/seo.py`](hooks/seo.py).

**"AI-ready" is three consumers, not one.** A retriever wants small filterable
units. An assistant choosing where to look wants a map. An assistant doing a
one-shot read wants everything in one fetch. Serving only one of those fails
the other two. See
[AI-readiness patterns](docs/explanation/ai-readiness.md).

## On the MkDocs ecosystem

This builds with MkDocs and Material. That ecosystem is in flux: Material
entered maintenance mode in late 2025 and several successor projects now exist,
including Zensical from the same team.

Nothing here except `mkdocs.yml` depends on the choice. The content model,
link checker, sample runner, cold-start script, packer, and MCP server all
operate on plain Markdown and front matter. The docs build unchanged against
the stock MkDocs theme, which is the point: **the generator is the most
replaceable part of a documentation system, so nothing important should be
coupled to it.**

## Layout

```
src/docpack/         the library
  frontmatter.py       the content model
  chunk.py             heading-aware chunking
  pack.py              JSONL, llms.txt, llms-full.txt
  retrieve.py          BM25 index, shared by the MCP server and the evaluator
  evaluate.py          scoring against a golden set
  scaffold.py          the page generator
  cli.py               docpack, docpack new, docpack eval
docs/                the corpus, organized by Diátaxis
  tutorials/           learning-oriented
  how-to/              task-oriented
  reference/           information-oriented, generated from docstrings
  explanation/         understanding-oriented
evals/golden.yaml    20 questions and the pages that should answer them
tests/               unit tests, doctests, and the doc-sample runner
hooks/               build hooks: per-page SEO and structured data
scripts/             link checker, cold-start harness
styles/              Vale rules
mcp_server/          MCP server exposing the docs to agents
.github/workflows/   the pipeline
```

## Status

Every command in this README has been run. 142 tests cover the library, its
docstrings, every executable sample in the documentation, and the SEO hook.
Retrieval scores are published in
[Evaluating retrieval](docs/explanation/evaluating-retrieval.md) and gated in
CI.

MIT licensed.
