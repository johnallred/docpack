# Style guide

How this repository's documentation is written. It has two halves, and they
are kept apart on purpose.

The **mechanical** half is enforced by Vale in CI, from the rules in
`styles/Showcase/`. It is listed here so a writer can see the rules before the
build does, not so a reviewer can check them: no reviewer should spend
attention on what a machine catches. The **editorial** half is the part no
linter can check. It is what a reviewer reads for.

`tests/test_style_guide.py` holds this page to the rules: every rule file has a
row below at its real level, every term and every hedge word the rules name is
listed, and no terminology rule swaps a word for itself. That last check exists
because one did, for weeks, and caught nothing.

## The mechanical half: what Vale enforces

`vale docs/` runs on every pull request. Errors fail the build; warnings and
suggestions are reported and do not.

<!-- vale off -->
<!-- The rules' own words are quoted below, so Vale would flag them. -->

| Rule | Level | What it catches | Why |
|---|---|---|---|
| `Terms` | error | A term written the wrong way | One name per thing, or search and retrieval split it in two |
| `Hedging` | warning | Words that hedge or condescend | They add length and tell the reader nothing; "simply" is an insult when it is not simple |
| `HeadingCase` | warning | A heading not in sentence case | Consistency, and title case reads as shouting in a long navigation |
| `FutureTense` | suggestion | "will be able to", "is going to" | Reference and how-to content describes what is, in the present tense |

**Terms**, written the right way:

| Write | Not |
|---|---|
| Diataxis | Diátaxis |
| front matter | front-matter |
| GitHub | Github |
| JavaScript | Javascript |

**Hedge words** to cut or replace with the specific claim: simply, just,
obviously, of course, easy, easily, clearly.

**Heading case** has exceptions for proper names and acronyms: Diataxis,
Python, JSONL, API, CI, CLI, MCP, RAG, AI, docpack, Markdown, YAML and Vale.
Tutorials are exempt, because numbered steps read better as "Step 1: Install
docpack".

<!-- vale on -->

Add a term to `styles/Showcase/Terms.yml` the second time a reviewer has to
correct it, not the first, and add it to the table above in the same change.

## The editorial half: what a reviewer reads for

**One page, one type.** Every page is a tutorial, a how-to guide, a reference
page or an explanation, declared in its front matter and enforced by its
directory. A page that would need two types is two pages.
`docs/how-to/add-a-page.md` has the two questions that decide which.

**Write the summary for a stranger.** The `summary` field is one sentence, and
it is read by more than people: it becomes the meta description, the line in
`llms.txt` and the snippet a retriever ranks. Write it in the words a reader
would search with, not the words the code uses.

**Every sample runs.** A Python block in `docs/` is executed in CI. If a sample
cannot run on its own, mark it `# docpack: skip` so the exception is visible and
counted, and expect a reviewer to ask whether it could run instead.

**Show the output you promise.** A command is followed by what it prints, and
the tutorial's promised output is asserted by the cold-start harness. Do not
paraphrase output; paste it.

**Numbers come from the code.** A figure in the README or the docs, such as a
page count or a retrieval score, has to be one a test re-derives
(`tests/test_published_figures.py`). A number typed by hand goes stale the first
time anything changes.

**Second person, present tense, active voice.** "Run `docpack docs`", not "The
user should run". "It writes three files", not "Three files will be written".

**Say what it does not do.** A limitation stated plainly is worth more to a
reader than one they discover. The README's last sections are the model.

**Prefer an example to a paragraph** when the reader would otherwise have to
build the example in their head, and a table to prose when they will compare
across rows.
