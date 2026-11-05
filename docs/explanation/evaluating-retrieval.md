---
title: Evaluating retrieval
summary: Why a golden set of questions is the only check that measures whether the docs answer anything.
diataxis: explanation
audience: developer
updated: 2026-10-26
tags: [rag, retrieval, evaluation]
---

# Evaluating retrieval

Every other check in this project asks whether the documentation is correct.
Links resolve, code samples execute, front matter validates, prose passes the
style rules. A corpus can pass all of them and still fail the only question a
reader cares about: when I ask this a question, do I get the right page back.

That question needs a different kind of test, because it has no single correct
answer to assert against. It needs a sample of real questions, a judgement
about what should answer each one, and a score that moves when the corpus or
the retriever changes.

## The golden set

`evals/golden.yaml` holds twenty cases. Each one pairs a question with the page
that should answer it, the type of answer the question is asking for, and the
terms a grounded answer has to cite.

```yaml
- id: why-not-fixed-size
  question: why not just split documents every thousand characters
  expect_source: explanation/why-heading-aware-chunking.md
  expect_diataxis: explanation
  must_contain: ["window"]
  why: The repo's central technical argument, asked in the reader's words.
```

Two conventions in there carry most of the value.

**Questions are phrased the way a reader would type them, not the way the page
is worded.** A case lifted from a page's own headings tests that string
matching works, which was never in doubt. The interesting cases are the ones
where the reader's vocabulary and the author's vocabulary disagree, because
that gap is the actual failure mode in documentation search.

**Every case carries a `why`.** Without it, nobody can tell a deliberately hard
case from a stale one, and six months later the whole set is unmaintainable
because no one dares delete anything.

## What is measured

Run it:

```bash
docpack eval evals/golden.yaml --docs docs
```

| Metric | What it tells you |
|---|---|
| hit@1 | The top result is the right page |
| hit@3 | The right page is somewhere in the top three |
| MRR | Mean reciprocal rank, so second place scores above ninth |
| routing accuracy | The top result is the *type* of page the question needs |
| grounded@1 | The top chunk actually contains the terms an answer must cite |

The last two deserve an argument.

**Routing accuracy** exists because topical correctness is not enough. A
reference page and an explanation page about the same subject can both be
relevant while only one of them can answer the question asked. "How do I" wants
a command; "why does" wants a tradeoff. A retriever that returns the right
subject in the wrong genre produces an assistant that confidently answers a
different question than the one asked.

**grounded@1** is a cheap proxy for answer accuracy. If the retrieved chunk
does not contain the fact, no amount of generation will invent it correctly. It
catches a failure that hit@1 hides: the right page, wrong section. A page-level
hit looks like a success and is not one, because what gets handed to the model
is a chunk, not a page.

## Current scores

Twenty cases, top-3, measured against the twelve pages in this repository:

| Metric | Score |
|---|---|
| hit@1 | 65% |
| hit@3 | 95% |
| MRR | 0.775 |
| routing accuracy | 75% |
| grounded@1 | 90% |

These are not good numbers and they are not meant to look like good numbers.
Six of the twenty cases are marked hard on purpose, and the set is deliberately
weighted toward the queries a lexical retriever handles worst. A golden set
tuned until it went green would measure nothing.

**Twenty cases is a small sample, and the report does not pretend otherwise.**
One case is five percentage points. Any difference below about ten points is
one or two cases changing places, which is noise, and treating it as signal is
the fastest way to make decisions out of randomness. The numbers here are
useful for catching a page that became unreachable, not for choosing between
two retrievers that score within a few points of each other.

`tests/test_evaluate.py` enforces a floor of MRR 0.70 and hit@3 of 80%, which
is a regression gate rather than a target. The floor sits below the current
score so that ordinary content edits do not trip it, and the real numbers live
on this page, where changing them shows up in a diff and has to be explained.

## The headroom number, and why it is not a score

The report ends with a second figure: hit@1 when the retriever is told which
Diátaxis type to search.

```
  hit@1                     65.0%
  hit@1 with type filter    75.0%
  routing headroom         +10.0%
```

That 75% is **not** an achievable score. At query time nobody knows what type a
question wants; the harness knows only because the golden set declares it.

It measures something more useful than a score. The gap is how much accuracy is
sitting unclaimed behind a query router. Fifteen points says the content model
is carrying real information that the retriever currently throws away, and that
the cheapest available improvement is classifying the question rather than
embedding the corpus better. A gap near zero would say the opposite: routing is
not worth building, and the problem is ranking.

This is the kind of question an evaluation harness exists to answer. Without
one, the choice between "add a reranker" and "add a router" is settled by
whoever argues hardest.

## Do not quote a golden question in the docs

The corpus and the test set live in the same repository, which creates a
contamination route with no equivalent in ordinary machine learning: a
documentation page that quotes one of the twenty questions becomes the
strongest lexical match for its own test case, and the evaluation starts
scoring the example rather than the answer.

Adding a `search` section to the [CLI reference](../reference/cli.md) cost five
points of `hit@1`, because its example used the `chunk-size` question verbatim
and `reference/cli.md` displaced the page that answers it. The second draft
replaced the example and quoted the question again inside a note explaining the
mistake, and cost exactly the same five points. The third draft names the case
and not its wording, and the score returned to 60%.

Two things follow. A documentation example must be phrased differently from
every golden question, which is a constraint on the docs that the evaluation
imposes and nothing enforces. And a five-point move is one case out of twenty,
so it was legible only because the recorded scores on this page are specific
enough to diff; a vaguer claim would have absorbed it silently.

## The cheapest fix is vocabulary, not ranking

Grounding measured across the whole retrieved window, rather than the top chunk
alone, says how much a wider context buys:

```
  grounded@1    16/20  (80%)
  grounded@3    18/20  (90%)
  grounded@5    18/20  (90%)
  grounded@10   18/20  (90%)
```

Ten points between one chunk and three, and then nothing at all out to ten.
That plateau is diagnostic: once widening the window stops helping, the
remaining failures are not ranking failures, and no reranker or embedding model
will touch them.

Both residual cases were vocabulary gaps, and the golden set had said so in its
own `why` field: in each, the reader's everyday word for the thing was absent
from the page that documents it, while the corpus used a precise term the
reader had no reason to know.

The fix was one sentence per page, each placing the reader's word beside the
corpus's. Following the rule above, the words are not reproduced here; the
cases are `chunk-size` and `prose-linting`, and the edits are in
[`how-to/pack-for-rag.md`](../how-to/pack-for-rag.md) and
[`how-to/add-a-page.md`](../how-to/add-a-page.md).

That rule is easy to break, and this section broke it. The first draft of this
paragraph set out both pairs of words in a table, which made this explanation
page compete with the two how-to pages for their own queries and gave back five
points of `hit@1`. Even a page about contamination contaminates.

```
             before   after
hit@1          60%     65%
hit@3          95%     95%
MRR          0.742   0.775
routing        70%     75%
grounded@1     80%     90%
grounded@3     90%    100%
headroom      +15%    +10%
```

Four of five scores moved, and the headroom narrowed, from two sentences. The
narrowing is the subtle part: routing headroom measures accuracy sitting behind
a query router, and some of that gap was never a routing problem at all. It was
a word the corpus did not use.

This is the argument for measuring before building. A ten-point `hit@1` gap
looks like a case for a reranker, and five points of it were a synonym.

## Why the retriever is lexical

`docpack.retrieve` is BM25 over the chunks. No embeddings, no vector store, no
reranker.

That is deliberate. The packaged artifacts are the product here, and a lexical
baseline runs in CI in milliseconds with no API key and no network, which means
the eval runs on every pull request instead of once a quarter. More importantly,
a corpus that a lexical baseline cannot search is usually badly *structured*
rather than badly embedded. Reaching for embeddings first hides that instead of
fixing it, and you end up paying per query to paper over a heading problem.

The number to beat before adding an embedding model is on this page.

## What the eval found

Three findings, all from the first few runs, all of them the argument for
having the harness at all.

### The summary field was not indexed

Every page carries a required one-sentence `summary`. It fed the meta
description, the Open Graph tags, the `llms.txt` annotation, and the retrieval
snippet in `chunks.jsonl`. It was not in the search index. So a question
phrased almost verbatim from a page's own summary failed to retrieve that page
at all: the `ci-setup` case was a total miss, and it is now rank 1.

Removing the summary from the index reproduces the old behaviour, which makes
the finding checkable rather than a claim:

| `SUMMARY_WEIGHT` | hit@1 | hit@3 | MRR | grounded@1 |
|---|---|---|---|---|
| 0 (not indexed) | 55% | 90% | 0.700 | 75% |
| 1 | 60% | 95% | 0.758 | 70% |
| **2 (shipped)** | **60%** | **95%** | **0.750** | **75%** |
| 3 | 60% | 95% | 0.742 | 75% |
| 4 | 65% | 90% | 0.750 | 75% |

Indexing the summary at all is worth a clear five points of hit@1 and a jump in
hit@3. That is the finding.

**The shipped weight was not chosen from this table.** Weight 4 scores better
on hit@1 and weight 1 better on MRR, and neither difference is larger than one
or two cases changing places. Picking the row with the best number would be
fitting the retriever to twenty hand-written questions and calling the result
an improvement. Weight 2 is there for a reason that survives the sample size:
a page summary describes the whole page, so it should rank below a heading,
which describes the specific section the reader needs.

### Indexing the summary has a cost, and the eval showed it

Every chunk on a page carries that page's summary, so summary terms cannot
discriminate between chunks of the *same* page. That is visible in the table
above as grounded@1 dropping at weight 1: the right page comes back, from the
wrong section. The cost is real, it is bounded, and it was measured instead of
guessed at.

### A meta page competes with the pages it describes

Adding this very page to the corpus moved four scores. hit@1 fell from 65% to
60% and routing accuracy from 75% to 70%, while hit@3 rose from 90% to 95%.

The cause is worth understanding because it generalises. This page discusses
chunking, filtering, the content model, and prose linting without being the
page *about* any of them, so it now competes for all of those queries.
`why-not-fixed-size` dropped behind it. That is the classic failure of a page
that mentions everything: it ranks for everything and answers nothing, and no
correctness check in this repository would have noticed.

The honest resolution is not to delete the page. It is to know the cost, keep
the page narrow, and have a number that moves when a new page starts absorbing
traffic that belongs elsewhere. A corpus is a system with interference between
its parts, and an eval is the only instrument here that can see it.

## What this does not do

It does not measure answer quality, because that needs a model in the loop and
a human reading the output. `grounded@1` is a floor, not a substitute: it tells
you the facts were available, not that the answer was right.

It does not measure whether the questions in the set are the questions people
actually ask. That needs real traffic, and the honest position is that twenty
hand-written cases are a stand-in for search logs nobody has yet. The first
thing to do with a real audience is replace them.

## Related

- [Why heading-aware chunking](why-heading-aware-chunking.md) for what is being retrieved.
- [AI-readiness patterns](ai-readiness.md) for the three consumers of the packaged output.
- [The content model](content-model.md) for where `diataxis` and `summary` come from.
