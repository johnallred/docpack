---
title: Add a page to the corpus
summary: Write a new page that passes content-model validation and CI.
diataxis: how-to
audience: contributor
updated: 2026-10-26
tags: [contributing, content-model]
---

# Add a page to the corpus

## Decide which of the four types it is

Before you write anything, answer two questions: does the reader need **action
or knowledge**, and are they **studying or working**?

| | Studying | Working |
|---|---|---|
| **Action** | Tutorial | How-to guide |
| **Knowledge** | Explanation | Reference |

A page that is two of these serves neither. If you cannot pick one, the page is
two pages.

## Generate the page

Do not hand-write the front matter. Generate it:

```bash
docpack new how-to --title "Rotate an API key" \
  --audience operator \
  --summary "Replace a key without downtime." \
  --tags security
```

That writes `docs/how-to/rotate-an-api-key.md` with valid front matter,
today's date, and a skeleton of the headings a how-to guide owes its reader.
The directory comes from the type, so you do not choose it. An existing file is
never overwritten.

Add `--dry-run` to see the page without writing it.

### What it generates, and why you should not write it by hand

```yaml
---
title: Rotate an API key
summary: Replace a key without downtime.
diataxis: how-to
audience: operator
updated: 2026-10-26
tags: [security]
---
```

All five of `title`, `summary`, `diataxis`, `audience`, and `updated` are
required. `diataxis` must be one of `tutorial`, `how-to`, `reference`, or
`explanation`. `audience` must be one of `new-user`, `developer`, `operator`,
or `contributor`.

Omitting `--summary` writes a `TODO` placeholder rather than leaving the field
blank, because a blank one fails validation and a missing one fails it louder.
Replace it before you push.

Write the summary as one sentence that makes sense out of context. It is used
five times: as the page's meta description, in its Open Graph tags and
structured data, as the annotation beside the page in `llms.txt`, and as the
retrieval snippet attached to every chunk of the page. It is also indexed for
search, so phrasing it the way a reader would ask about the page is worth a
minute of thought.

## Validate before you push

```bash
docpack docs --check
```

This is the same command CI runs. It fails on a missing field, an unknown type,
or a non-date `updated` value, and it warns on pages not reviewed in a year.

## Check your prose and links

Vale enforces the prose rules, so hedge words and banned terminology fail here
rather than in review:

```bash
vale docs/
python scripts/check_links.py docs/
```

## Put executable samples in a python block

Any ```python block in the docs is extracted and executed by the test suite.
If a sample cannot run standalone, mark it:

```python
# docpack: skip
client.connect(SECRET_TOKEN)
```

Prefer making the sample runnable over skipping it. A sample that CI does not
run is a sample that will eventually be wrong.

## Add a question to the evaluation set

A new page is not retrievable until something proves it is. Add one case to
`evals/golden.yaml`, phrased the way a reader would ask rather than the way
your page is worded:

```yaml
- id: rotate-key
  question: how do I replace an api key without taking the service down
  expect_source: how-to/rotate-an-api-key.md
  expect_diataxis: how-to
  must_contain: ["rotate"]
  why: The operator task this page exists for.
```

Then check it:

```bash
docpack eval evals/golden.yaml --docs docs -v
```

If your page does not come back first, the usual cause is that the page uses
vocabulary the question does not. That is worth fixing in the page, not in the
question. See [Evaluating retrieval](../explanation/evaluating-retrieval.md).

## Related

- [The content model](../explanation/content-model.md) for why the fields are required.
- [Command line reference](../reference/cli.md) for every flag.
