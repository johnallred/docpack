"""Command line interface for docpack.

Four commands:

- `docpack <dir>`        pack a tree into retrieval artifacts
- `docpack search`       ask the corpus a question and see what comes back
- `docpack new`          generate a page that conforms to the content model
- `docpack eval`         score the corpus against a golden set of questions

The packing command is the default and takes the documentation directory as its
first positional argument, so `docpack docs --out dist` works with no
subcommand. That shape predates the other two commands and is asserted on by
`scripts/coldstart.sh`, quoted in the tutorial, and used in CI, so it is kept
rather than migrated: a documented interface that a cold-start test depends on
is not worth breaking for symmetry. `main()` dispatches on whether the first
argument names a subcommand.

Run `docpack --help`, `docpack new --help`, or `docpack eval --help` for usage.
Every command in the documentation is executed by CI, so the examples there are
known to work.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .evaluate import GoldenSetError, evaluate, format_report, load_golden_set
from .frontmatter import AUDIENCES, ContentModelError, DIATAXIS_TYPES
from .pack import load_tree, to_jsonl, to_llms_full_txt, to_llms_txt
from .retrieve import Index
from .scaffold import ScaffoldError, new_page, write_page

#: Subcommand names. A first argument matching one of these is dispatched to
#: that subcommand; anything else is treated as a path to pack.
SUBCOMMANDS = ("new", "eval", "search")


# --------------------------------------------------------------------- parsers


def build_parser() -> argparse.ArgumentParser:
    """Construct the parser for the default packing command."""
    p = argparse.ArgumentParser(prog="docpack", description=__doc__.splitlines()[0])
    p.add_argument("docs", type=Path, help="Path to the documentation tree")
    p.add_argument("--out", type=Path, default=Path("dist"), help="Output directory")
    p.add_argument("--site-name", default="docpack")
    p.add_argument("--site-url", default="https://example.com")
    p.add_argument("--tagline", default="Retrieval-ready documentation packaging.")
    p.add_argument("--check", action="store_true",
                   help="Validate the content model and exit without writing")
    return p


def build_new_parser() -> argparse.ArgumentParser:
    """Construct the parser for `docpack new`."""
    p = argparse.ArgumentParser(
        prog="docpack new",
        description="Generate a page that already conforms to the content model.",
    )
    p.add_argument("diataxis", choices=sorted(DIATAXIS_TYPES),
                   help="Which of the four documentation types this page is")
    p.add_argument("--title", required=True, help="Page title; also sets the filename")
    p.add_argument("--docs", type=Path, default=Path("docs"),
                   help="Root of the documentation tree")
    p.add_argument("--audience", choices=sorted(AUDIENCES),
                   help="Declared audience; defaults by type")
    p.add_argument("--summary", help="One sentence; a TODO placeholder is written if omitted")
    p.add_argument("--tags", default="", help="Comma-separated tags")
    p.add_argument("--dry-run", action="store_true",
                   help="Print the page instead of writing it")
    return p


def build_eval_parser() -> argparse.ArgumentParser:
    """Construct the parser for `docpack eval`."""
    p = argparse.ArgumentParser(
        prog="docpack eval",
        description="Score retrieval over the corpus against a golden set.",
    )
    p.add_argument("golden", type=Path, help="YAML golden set")
    p.add_argument("--docs", type=Path, default=Path("docs"),
                   help="Root of the documentation tree")
    p.add_argument("-v", "--verbose", action="store_true",
                   help="Show every case, not just the misses")
    p.add_argument("--fail-under", type=float, metavar="MRR",
                   help="Exit non-zero if MRR falls below this value")
    return p


# -------------------------------------------------------------------- commands


def cmd_pack(argv: list[str]) -> int:
    """Pack a documentation tree, or validate it with `--check`."""
    args = build_parser().parse_args(argv)
    pages = load_tree(args.docs)

    if args.check:
        print(f"ok: {len(pages)} pages conform to the content model")
        stale = [p for p in pages if p.meta.is_stale]
        if stale:
            print(f"warning: {len(stale)} page(s) not reviewed in over a year")
            for p in stale:
                print(f"  {p.path}")
        return 0

    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "chunks.jsonl").write_text(to_jsonl(pages), encoding="utf-8")
    (args.out / "llms.txt").write_text(
        to_llms_txt(pages, site_name=args.site_name, site_url=args.site_url,
                    tagline=args.tagline),
        encoding="utf-8",
    )
    (args.out / "llms-full.txt").write_text(
        to_llms_full_txt(pages, site_name=args.site_name), encoding="utf-8"
    )

    chunks = sum(len(p.chunks) for p in pages)
    print(f"packed {len(pages)} pages into {chunks} chunks -> {args.out}")
    return 0


def cmd_new(argv: list[str]) -> int:
    """Generate a conforming page."""
    args = build_new_parser().parse_args(argv)
    tags = tuple(t.strip() for t in args.tags.split(",") if t.strip())

    try:
        page = new_page(
            args.docs,
            title=args.title,
            diataxis=args.diataxis,
            audience=args.audience,
            summary=args.summary,
            tags=tags,
        )
    except ScaffoldError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    if args.dry_run:
        print(f"# would write {page.path}")
        print(page.text, end="")
        return 0

    path = write_page(page)
    print(f"created {path}")
    if not args.summary:
        print("next: replace the TODO summary, then run `docpack docs --check`")
    return 0


def build_search_parser() -> argparse.ArgumentParser:
    """Construct the parser for the search command."""
    p = argparse.ArgumentParser(
        prog="docpack search",
        description="Ask the corpus a question and see which chunks come back.",
    )
    p.add_argument("question", help="The question, in a reader's own words")
    p.add_argument("--docs", type=Path, default=Path("docs"), help="Documentation tree")
    p.add_argument("-n", "--limit", type=int, default=3, help="Results to show")
    p.add_argument(
        "--type",
        dest="diataxis",
        choices=sorted(DIATAXIS_TYPES),
        help="Restrict to one Diataxis type: the filter `eval` measures headroom for",
    )
    return p


def cmd_search(argv: list[str]) -> int:
    """Answer one question from the corpus, for a human.

    This command exists because of a cold-start failure, reported by the only
    reader who had run the quick start. Every other command validates something
    and prints "ok", so a reader could run all nine, watch them pass, and still
    not know what the library is for. `eval` scores a fixed golden set, which
    answers "is retrieval working" rather than "what does this do". Retrieval
    is the entire point of the package and there had been no way to try it by
    hand.
    """
    args = build_search_parser().parse_args(argv)

    try:
        index = Index.from_tree(args.docs)
    except ContentModelError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    hits = index.search(args.question, diataxis=args.diataxis, limit=args.limit)
    if not hits:
        print(f'nothing in {len(index)} chunks matched "{args.question}"')
        return 1

    print(f'\n  "{args.question}"   ({len(index)} chunks indexed)\n')
    for position, hit in enumerate(hits, 1):
        snippet = " ".join(hit.text.split())[:150]
        print(f"  {position}. {hit.breadcrumb}")
        print(f"     {hit.source}  [{hit.diataxis}]")
        print(f"     {snippet}...\n")
    return 0


def cmd_eval(argv: list[str]) -> int:
    """Score retrieval against a golden set."""
    args = build_eval_parser().parse_args(argv)

    try:
        cases = load_golden_set(args.golden, docs_dir=args.docs)
    except (GoldenSetError, ContentModelError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    report = evaluate(Index.from_tree(args.docs), cases)
    print(format_report(report, verbose=args.verbose))

    if args.fail_under is not None and report.mrr < args.fail_under:
        print(
            f"\nFAIL: MRR {report.mrr:.3f} is below the floor of {args.fail_under:.3f}",
            file=sys.stderr,
        )
        return 1
    return 0


# -------------------------------------------------------------------- dispatch


def main(argv: list[str] | None = None) -> int:
    """Entry point. Returns a process exit code."""
    argv = list(sys.argv[1:] if argv is None else argv)

    if argv and argv[0] in SUBCOMMANDS:
        return {"new": cmd_new, "eval": cmd_eval, "search": cmd_search}[argv[0]](argv[1:])
    return cmd_pack(argv)


if __name__ == "__main__":
    sys.exit(main())
