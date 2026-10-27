"""Split documentation into retrieval-sized chunks that keep their context.

The naive approach to chunking, a sliding window over characters, destroys the
thing that makes documentation retrievable: a heading tells you what the text
under it is about. `docpack` splits on heading boundaries first and only falls
back to size-based splitting inside an oversized section, so every chunk keeps
its heading trail.

See `docs/explanation/why-heading-aware-chunking.md`.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field

HEADING = re.compile(r"^(#{1,6})\s+(.*)$")
FENCE = re.compile(r"^\s*(```|~~~)")


@dataclass(frozen=True)
class Chunk:
    """One retrieval-sized unit of documentation.

    Attributes:
        chunk_id: Stable identifier. Derived from the source path and the
            heading trail, never from position, so inserting a paragraph
            earlier in the file does not renumber every chunk after it.
        text: The chunk body, excluding the heading line itself.
        heading_trail: Headings from the document root down to this chunk.
        source: Path of the document this came from.
        token_estimate: Rough token count, four characters per token.
    """

    chunk_id: str
    text: str
    heading_trail: tuple[str, ...]
    source: str
    token_estimate: int

    @property
    def breadcrumb(self) -> str:
        """The heading trail as a single readable string.

        Example:
            >>> c = Chunk("x", "body", ("Guide", "Install"), "a.md", 1)
            >>> c.breadcrumb
            'Guide > Install'
        """
        return " > ".join(self.heading_trail)

    def to_record(self) -> dict[str, object]:
        """Render as a flat dict suitable for a vector store or JSONL export."""
        return {
            "id": self.chunk_id,
            "text": self.text,
            "breadcrumb": self.breadcrumb,
            "source": self.source,
            "tokens": self.token_estimate,
        }


@dataclass
class _Section:
    trail: tuple[str, ...]
    lines: list[str] = field(default_factory=list)


def _estimate_tokens(text: str) -> int:
    """Estimate tokens at four characters each. Deliberately crude."""
    return max(1, len(text) // 4)


def _stable_id(source: str, trail: tuple[str, ...], ordinal: int) -> str:
    """Build a position-independent identifier for a chunk."""
    basis = f"{source}::{'/'.join(trail)}::{ordinal}"
    return hashlib.sha256(basis.encode()).hexdigest()[:16]


def split_sections(markdown: str) -> list[_Section]:
    """Split markdown into sections at heading boundaries.

    Headings inside fenced code blocks are ignored, which is the bug every
    naive implementation of this has.
    """
    sections: list[_Section] = []
    current = _Section(trail=())
    stack: list[str] = []
    in_fence = False

    for line in markdown.splitlines():
        if FENCE.match(line):
            in_fence = not in_fence
            current.lines.append(line)
            continue

        match = None if in_fence else HEADING.match(line)
        if match:
            if current.lines or current.trail:
                sections.append(current)
            level = len(match.group(1))
            title = match.group(2).strip()
            stack = stack[: level - 1]
            while len(stack) < level - 1:
                stack.append("")
            stack.append(title)
            current = _Section(trail=tuple(s for s in stack if s))
        else:
            current.lines.append(line)

    if current.lines or current.trail:
        sections.append(current)
    return sections


def chunk_markdown(
    markdown: str,
    *,
    source: str = "<string>",
    max_tokens: int = 400,
) -> list[Chunk]:
    """Chunk a markdown document, preserving heading context.

    Sections shorter than `max_tokens` become one chunk each. Longer sections
    are split on blank lines into several chunks that all keep the same
    heading trail.

    Args:
        markdown: The document body, front matter already removed.
        source: Path recorded on each chunk.
        max_tokens: Soft ceiling per chunk.

    Returns:
        Chunks in document order. Sections containing only whitespace are
        dropped.

    Example:
        >>> doc = "# Guide\\n\\nIntro text.\\n\\n## Install\\n\\nRun the installer.\\n"
        >>> chunks = chunk_markdown(doc, source="guide.md")
        >>> for c in chunks:
        ...     print(c.breadcrumb)
        Guide
        Guide > Install
        >>> chunks[1].text.strip()
        'Run the installer.'
    """
    chunks: list[Chunk] = []
    for section in split_sections(markdown):
        body = "\n".join(section.lines).strip()
        if not body:
            continue
        if _estimate_tokens(body) <= max_tokens:
            pieces = [body]
        else:
            pieces = _split_oversized(body, max_tokens)
        for ordinal, piece in enumerate(pieces):
            chunks.append(
                Chunk(
                    chunk_id=_stable_id(source, section.trail, ordinal),
                    text=piece,
                    heading_trail=section.trail,
                    source=source,
                    token_estimate=_estimate_tokens(piece),
                )
            )
    return chunks


def _split_oversized(body: str, max_tokens: int) -> list[str]:
    """Split an oversized section on paragraph boundaries."""
    paragraphs = [p for p in body.split("\n\n") if p.strip()]
    out: list[str] = []
    buffer: list[str] = []
    size = 0
    for para in paragraphs:
        cost = _estimate_tokens(para)
        if buffer and size + cost > max_tokens:
            out.append("\n\n".join(buffer))
            buffer, size = [], 0
        buffer.append(para)
        size += cost
    if buffer:
        out.append("\n\n".join(buffer))
    return out
