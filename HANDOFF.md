# HANDOFF (docpack)
WHAT: a Diataxis docs site that also packs itself into retrieval chunks and records, with an MCP server; published at johnallred.github.io/docpack.
DONE: code-sample validation (tests/test_doc_samples.py) and published figures re-derived from live runs (tests/test_published_figures.py).
DONE: Vale rules in styles/; the Terms swap 'Diátaxis' -> 'Diataxis' was an identity no-op and is fixed.
DONE: STYLE.md, the human half of the style guide, held to the Vale rules by tests/test_style_guide.py.
DONE: single-sourcing: snippets/vocabularies.md included via pymdownx.snippets in two pages.
DONE: the packer expands includes (pack.expand_snippets), so chunks carry text, not include lines.
DONE: scripts/publish_sources.py publishes Markdown sources with snippets expanded (replaced cp -r in the docs workflow).
FIGURES after the snippet change: hit@1 70%, MRR 0.800, routing 80%, headroom +5%; 86 chunks and records; 153 tests.
DONE: Related links to fieldguide and coldlab; .DS_Store untracked; Node-24 actions; deploy split into build/deploy jobs.
DONE: setup notes for publishing your own copy; Windows activation command in the tutorial.
FAILED (local only): mkdocs build errors here with "Highlight.__init__ missing md"; predates these changes, CI builds fine.
NEXT (John): push ac629dd and earlier local commits.
NEXT: none required for the interview; fieldguide records style-guide and single-sourcing as full from this repo.
WHY: single-sourcing exposed a leak; without expansion the retrieval artifacts would have indexed include lines.
Commit messages: no Co-Authored-By or Claude-Session trailers.
