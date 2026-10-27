"""Lexical retrieval over a packed corpus.

This is the reference retriever. It exists for two reasons, and it is important
to be clear about what it is not.

**What it is.** A dependency-free BM25 implementation over the chunks produced
by `docpack.chunk`, shared by the MCP server and the evaluation harness. Both
call `search()`. If the evaluator scored a private copy of the ranking logic,
the scores would describe code that nobody ships, which is the most common way
a retrieval evaluation ends up meaningless.

**What it is not.** A production retrieval stack. There are no embeddings, no
vector store, and no reranker. That is deliberate: the packaged artifacts are
the product here, and a lexical baseline runs in CI in milliseconds with no API
key and no network. The point of `docpack eval` is to tell you whether your
corpus is retrievable at all, and to give you a number to beat before you add
an embedding model. A corpus that a lexical baseline cannot search is usually
badly structured rather than badly embedded, and swapping in vectors hides that
instead of fixing it.

BM25 is used rather than raw term frequency because term frequency alone ranks
by chunk length: the longest chunk wins every multi-word query. BM25's length
normalisation and inverse document frequency are the two corrections that
matter most, and together they are about twenty lines.

See `docs/explanation/evaluating-retrieval.md` for the reasoning and the
current scores.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from .pack import Page

#: BM25 term-frequency saturation. Higher means repeated terms keep adding value.
K1 = 1.2

#: BM25 length normalisation. 0 disables it, 1 applies it fully.
B = 0.75

#: How many times the page title and heading trail are repeated in a chunk's
#: indexed text. A heading is a deliberate statement of what the text below is
#: about, which makes it worth more per word than the body.
HEADING_WEIGHT = 3

#: How many times the page summary is repeated. The summary is the author's own
#: one-sentence answer to "what is this page for", so it is often the closest
#: text in the corpus to how a reader would phrase a question.
#:
#: It was omitted from the index in the first version of this module, and
#: `docpack eval` is what caught it: a question phrased almost verbatim from a
#: page's summary failed to retrieve that page at all. Worth noting that this
#: was a field the index was missing, not a weight tuned until the golden set
#: went green. Tuning weights against the eval set would make the set a
#: training target and the scores meaningless.
#:
#: The cost is real: every chunk on a page carries that page's summary, so
#: summary terms cannot discriminate *between* chunks of the same page. It is
#: weighted below headings for that reason.
SUMMARY_WEIGHT = 2

_TOKEN = re.compile(r"[a-z0-9]+")


def tokenize(text: str) -> list[str]:
    """Split text into comparable terms.

    Lowercases, splits on anything that is not alphanumeric, drops
    single-character tokens, and strips one trailing `s` from tokens of three
    characters or more.

    The plural handling is crude on purpose. Real stemming is a dependency and
    a source of surprises. What matters is that queries and documents get the
    same treatment, so `ids` in a question matches `ID` in a heading even
    though the rule also mangles a few words that are not plurals.

    Example:
        >>> tokenize("Chunking the docs, with IDs!")
        ['chunking', 'the', 'doc', 'with', 'id']
    """
    out = []
    for token in _TOKEN.findall(text.lower()):
        if len(token) < 2:
            continue
        if len(token) > 2 and token.endswith("s") and not token.endswith("ss"):
            token = token[:-1]
        out.append(token)
    return out


@dataclass(frozen=True)
class Hit:
    """One ranked retrieval result.

    Attributes:
        score: BM25 score. Comparable within one query, not across queries.
        source: Page path relative to the docs root, for example
            `how-to/pack-for-rag.md`.
        chunk_id: Stable identifier of the matching chunk.
        breadcrumb: The heading trail of the matching chunk.
        text: The chunk's text.
        title: Title of the page the chunk came from.
        summary: The page's one-sentence summary.
        diataxis: The page's Diataxis type.
        audience: The page's declared audience.
    """

    score: float
    source: str
    chunk_id: str
    breadcrumb: str
    text: str
    title: str
    summary: str
    diataxis: str
    audience: str

    def render(self) -> str:
        """Format the hit as Markdown, for an agent or a terminal."""
        return (
            f"## {self.title} > {self.breadcrumb}\n"
            f"source: {self.source} ({self.diataxis}, for {self.audience})\n\n"
            f"{self.text.strip()}"
        )


@dataclass(frozen=True)
class _Doc:
    """One indexed unit: a chunk plus the page metadata needed to filter it."""

    source: str
    chunk_id: str
    breadcrumb: str
    text: str
    title: str
    summary: str
    diataxis: str
    audience: str
    terms: Counter[str]
    length: int


class Index:
    """A searchable BM25 index over a documentation tree.

    Built once and queried many times. Construction is the expensive part, and
    on a corpus this size it is still a few milliseconds.

    Example:
        >>> from pathlib import Path
        >>> index = Index.from_tree(Path("docs"))
        >>> hits = index.search("what are the exit codes", limit=1)
        >>> hits[0].source
        'reference/cli.md'
        >>> hits[0].breadcrumb
        'Command line reference > Exit codes'
    """

    def __init__(self, docs: list[_Doc]) -> None:
        self._docs = docs
        self._avg_length = (sum(d.length for d in docs) / len(docs)) if docs else 0.0
        document_frequency: Counter[str] = Counter()
        for doc in docs:
            document_frequency.update(doc.terms.keys())
        total = len(docs)
        # Standard BM25 idf, with the +1 inside the log so a term appearing in
        # every chunk scores near zero rather than going negative.
        self._idf = {
            term: math.log(1 + (total - count + 0.5) / (count + 0.5))
            for term, count in document_frequency.items()
        }

    @classmethod
    def from_pages(cls, pages: list[Page], docs_dir: Path | None = None) -> Index:
        """Build an index from already-parsed pages."""
        docs: list[_Doc] = []
        for page in pages:
            source = (
                page.path.relative_to(docs_dir).as_posix() if docs_dir else page.path.as_posix()
            )
            for chunk in page.chunks:
                heading_text = f"{page.meta.title} {chunk.breadcrumb} "
                indexed = (
                    heading_text * HEADING_WEIGHT
                    + f"{page.meta.summary} " * SUMMARY_WEIGHT
                    + chunk.text
                )
                terms = Counter(tokenize(indexed))
                docs.append(
                    _Doc(
                        source=source,
                        chunk_id=chunk.chunk_id,
                        breadcrumb=chunk.breadcrumb,
                        text=chunk.text,
                        title=page.meta.title,
                        summary=page.meta.summary,
                        diataxis=page.meta.diataxis,
                        audience=page.meta.audience,
                        terms=terms,
                        length=sum(terms.values()),
                    )
                )
        return cls(docs)

    @classmethod
    def from_tree(cls, docs_dir: Path) -> Index:
        """Parse, chunk, and index a documentation tree in one call."""
        from .pack import load_tree

        return cls.from_pages(load_tree(docs_dir), docs_dir=docs_dir)

    def __len__(self) -> int:
        return len(self._docs)

    def search(
        self,
        query: str,
        *,
        diataxis: str | None = None,
        audience: str | None = None,
        limit: int = 5,
    ) -> list[Hit]:
        """Rank chunks against a query, optionally filtered by content-model fields.

        Filtering happens before ranking, which is the whole argument for having
        a validated content model: a structured field is a hard constraint, while
        a hope that the ranking picked up on the page's genre is not.

        Args:
            query: Free-text query.
            diataxis: Restrict to one Diataxis type.
            audience: Restrict to one declared audience.
            limit: Maximum hits to return.

        Returns:
            Hits sorted by score, highest first. Ties break on source path then
            chunk id, so results are deterministic.
        """
        terms = tokenize(query)
        if not terms:
            return []

        scored: list[Hit] = []
        for doc in self._docs:
            if diataxis and doc.diataxis != diataxis:
                continue
            if audience and doc.audience != audience:
                continue

            score = 0.0
            for term in terms:
                frequency = doc.terms.get(term, 0)
                if not frequency:
                    continue
                norm = 1 - B + B * (doc.length / self._avg_length if self._avg_length else 1)
                score += self._idf.get(term, 0.0) * (frequency * (K1 + 1)) / (
                    frequency + K1 * norm
                )

            if score > 0:
                scored.append(
                    Hit(
                        score=score,
                        source=doc.source,
                        chunk_id=doc.chunk_id,
                        breadcrumb=doc.breadcrumb,
                        text=doc.text,
                        title=doc.title,
                        summary=doc.summary,
                        diataxis=doc.diataxis,
                        audience=doc.audience,
                    )
                )

        scored.sort(key=lambda h: (-h.score, h.source, h.chunk_id))
        return scored[:limit]
