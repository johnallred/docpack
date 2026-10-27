"""Package a documentation tree for retrieval and for AI assistants.

Three outputs, each for a different consumer:

- **JSONL records** for a vector store or search index.
- **`llms.txt`** for an assistant that needs a map of the site.
- **`llms-full.txt`** for an assistant that wants the whole corpus in one fetch.

See `docs/explanation/ai-readiness.md` for why these are three files and not one.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from .chunk import Chunk, chunk_markdown
from .frontmatter import PageMeta, parse_page


@dataclass(frozen=True)
class Page:
    """A parsed documentation page with its chunks."""

    path: Path
    meta: PageMeta
    body: str
    chunks: tuple[Chunk, ...]


def load_tree(docs_dir: Path) -> list[Page]:
    """Parse and chunk every markdown page under a directory.

    Args:
        docs_dir: Root of the documentation tree.

    Returns:
        Pages sorted by path, so output is deterministic and diffs are small.

    Raises:
        ContentModelError: If any page violates the content model. The whole
            build fails rather than silently skipping the bad page.
    """
    pages: list[Page] = []
    for path in sorted(docs_dir.rglob("*.md")):
        text = path.read_text(encoding="utf-8")
        meta, body = parse_page(text, source=str(path))
        rel = path.relative_to(docs_dir).as_posix()
        pages.append(
            Page(
                path=path,
                meta=meta,
                body=body,
                chunks=tuple(chunk_markdown(body, source=rel)),
            )
        )
    return pages


def to_jsonl(pages: list[Page]) -> str:
    """Render all chunks as JSONL, one retrieval record per line.

    Each record carries the page's content-model metadata alongside the chunk
    text, so a retriever can filter by audience or Diataxis type before
    ranking. Filtering on structured metadata beats hoping the embedding
    captured it.
    """
    lines = []
    for page in pages:
        for chunk in page.chunks:
            record = chunk.to_record()
            record.update(
                {
                    "title": page.meta.title,
                    "summary": page.meta.summary,
                    "diataxis": page.meta.diataxis,
                    "audience": page.meta.audience,
                    "updated": page.meta.updated.isoformat(),
                    "tags": list(page.meta.tags),
                }
            )
            lines.append(json.dumps(record, sort_keys=True))
    return "\n".join(lines) + "\n"


def to_llms_txt(pages: list[Page], *, site_name: str, site_url: str, tagline: str) -> str:
    """Render an `llms.txt` index of the corpus.

    Follows the convention proposed by Jeremy Howard in September 2024: an H1
    name, a blockquote summary, then H2 sections of annotated links. Pages are
    grouped by Diataxis type, because that grouping tells an assistant what
    kind of answer each page can support.

    Example:
        >>> from datetime import date
        >>> from .frontmatter import PageMeta
        >>> m = PageMeta("Install", "How to install.", "how-to", "developer", date(2026, 1, 1))
        >>> p = Page(Path("docs/how-to/install.md"), m, "", ())
        >>> out = to_llms_txt([p], site_name="Demo", site_url="https://x.test", tagline="A demo.")
        >>> "# Demo" in out and "## How-to guides" in out
        True
    """
    order = [
        ("tutorial", "Tutorials", "Learning-oriented. Start here with no prior context."),
        ("how-to", "How-to guides", "Task-oriented recipes. Assume familiarity."),
        ("reference", "Reference", "Factual API description. Structured to mirror the code."),
        ("explanation", "Explanation", "Design reasoning and tradeoffs."),
    ]

    out = [f"# {site_name}", "", f"> {tagline}", ""]
    out.append(
        "This file is a map of the documentation for language models. "
        "Each link points to a Markdown source file rather than a rendered page."
    )
    out.append("")

    for key, label, blurb in order:
        group = [p for p in pages if p.meta.diataxis == key]
        if not group:
            continue
        out.append(f"## {label}")
        out.append("")
        out.append(f"{blurb}")
        out.append("")
        for page in group:
            rel = page.path.as_posix()
            out.append(f"- [{page.meta.title}]({site_url.rstrip('/')}/{rel}): {page.meta.summary}")
        out.append("")

    stale = [p for p in pages if p.meta.is_stale]
    if stale:
        out.append("## Optional")
        out.append("")
        out.append("Pages not reviewed in over a year. Treat with lower confidence.")
        out.append("")
        for page in stale:
            out.append(f"- [{page.meta.title}]({site_url.rstrip('/')}/{page.path.as_posix()})")
        out.append("")

    return "\n".join(out)


def to_llms_full_txt(pages: list[Page], *, site_name: str) -> str:
    """Concatenate the whole corpus into a single Markdown document.

    For assistants that would rather make one request than thirty. Pages are
    separated by a rule and each is prefixed with its content-model metadata,
    so the model can still tell a tutorial from a reference page.
    """
    out = [f"# {site_name}: complete documentation", ""]
    for page in pages:
        out.append("---")
        out.append("")
        out.append(f"# {page.meta.title}")
        out.append("")
        out.append(
            f"*Type: {page.meta.diataxis} | Audience: {page.meta.audience} "
            f"| Updated: {page.meta.updated.isoformat()}*"
        )
        out.append("")
        out.append(page.meta.summary)
        out.append("")
        out.append(page.body.strip())
        out.append("")
    return "\n".join(out)
