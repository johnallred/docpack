#!/usr/bin/env python3
"""Check that every internal link in the docs resolves.

Internal links are the ones that rot silently. Rename a file, update the nav,
forget the three pages that linked to it, and nothing complains until a reader
hits a 404.

External links are reported but not failed on, because a third-party site
being down should not break your build.

Usage:
    python scripts/check_links.py docs/
    python scripts/check_links.py docs/ --check-anchors

Exit codes:
    0  every internal link resolves
    1  at least one internal link is broken
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

#: Markdown inline links: [text](target). Ignores image syntax deliberately.
LINK = re.compile(r"(?<!\!)\[([^\]]*)\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
#: ATX headings, used to build the anchor index.
HEADING = re.compile(r"^(#{1,6})\s+(.*)$", re.MULTILINE)
FENCE_BLOCK = re.compile(r"```.*?```", re.DOTALL)


def slugify(heading: str) -> str:
    """Convert a heading to the anchor slug most markdown renderers produce."""
    s = heading.strip().lower()
    s = re.sub(r"[^\w\s-]", "", s)
    return re.sub(r"[\s_]+", "-", s).strip("-")


def anchors_in(path: Path) -> set[str]:
    """Collect the anchor slugs a page defines."""
    text = FENCE_BLOCK.sub("", path.read_text(encoding="utf-8"))
    return {slugify(m.group(2)) for m in HEADING.finditer(text)}


def check(root: Path, *, check_anchors: bool) -> tuple[int, int, list[str]]:
    """Walk the tree and verify links.

    Returns:
        A `(checked, external, problems)` tuple.
    """
    problems: list[str] = []
    checked = external = 0
    anchor_cache: dict[Path, set[str]] = {}

    for page in sorted(root.rglob("*.md")):
        body = FENCE_BLOCK.sub("", page.read_text(encoding="utf-8"))
        for match in LINK.finditer(body):
            target = match.group(2)

            if target.startswith(("http://", "https://", "mailto:")):
                external += 1
                continue

            checked += 1
            path_part, _, anchor = target.partition("#")

            if not path_part:
                dest = page  # same-page anchor
            else:
                dest = (page.parent / path_part).resolve()

            if not dest.exists():
                rel = page.relative_to(root)
                problems.append(f"{rel}: broken link to {target!r}")
                continue

            if anchor and check_anchors and dest.suffix == ".md":
                if dest not in anchor_cache:
                    anchor_cache[dest] = anchors_in(dest)
                if anchor not in anchor_cache[dest]:
                    rel = page.relative_to(root)
                    problems.append(f"{rel}: anchor #{anchor} not found in {path_part}")

    return checked, external, problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("root", type=Path)
    parser.add_argument("--check-anchors", action="store_true",
                        help="Also verify that #fragments resolve to a heading")
    args = parser.parse_args(argv)

    checked, external, problems = check(args.root, check_anchors=args.check_anchors)

    for p in problems:
        print(f"FAIL  {p}", file=sys.stderr)

    status = "ok" if not problems else f"{len(problems)} broken"
    print(f"{status}: {checked} internal links checked, {external} external links skipped")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
