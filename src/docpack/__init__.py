"""docpack: turn a documentation tree into retrieval-ready, agent-readable artifacts.

This package is the subject of the documentation in this repository. It is small
on purpose: the point of the repo is the documentation system around it.
"""

from .chunk import Chunk, chunk_markdown
from .frontmatter import ContentModelError, PageMeta, parse_page
from .pack import Page, load_tree, to_jsonl, to_llms_full_txt, to_llms_txt

__version__ = "0.3.0"

__all__ = [
    "Chunk",
    "ContentModelError",
    "Page",
    "PageMeta",
    "chunk_markdown",
    "load_tree",
    "parse_page",
    "to_jsonl",
    "to_llms_full_txt",
    "to_llms_txt",
]
