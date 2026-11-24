#!/usr/bin/env python3
"""Copy the Markdown sources into the built site, with snippets expanded.

    python3 scripts/publish_sources.py docs site/docs

llms.txt links to the Markdown source of each page, served beside the HTML. A
plain copy would serve include lines (`--8<-- "vocabularies.md"`) in place of
the text they include, so an agent reading the source would get the directive
and not the fact. This expands them with the same function the packer uses.
"""

import sys
from pathlib import Path

from docpack.pack import expand_snippets


def main(source: str, target: str) -> int:
    source_dir, target_dir = Path(source), Path(target)
    snippets = source_dir.parent / "snippets"
    count = 0
    for page in sorted(source_dir.rglob("*.md")):
        out = target_dir / page.relative_to(source_dir)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(expand_snippets(page.read_text(encoding="utf-8"), snippets,
                                       source=str(page)), encoding="utf-8")
        count += 1
    print(f"published {count} Markdown sources to {target_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:3]))
