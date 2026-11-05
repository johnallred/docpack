#!/usr/bin/env python3
"""A Model Context Protocol server exposing this documentation to agents.

`llms.txt` serves an assistant that can fetch URLs. An MCP server serves a
coding agent working inside an editor, which wants structured, filterable
access rather than a flat file.

It speaks JSON-RPC 2.0 over stdio and implements the subset of MCP a docs
server actually needs: `initialize`, `tools/list`, and `tools/call`.

Three tools are exposed:

- `search_docs`    keyword search over chunks, filterable by Diataxis type
- `get_page`       full Markdown of one page, by path
- `list_pages`     the corpus index, filterable by type and audience

Deliberately dependency-free beyond `docpack` itself, so it can be read in one
sitting and run anywhere.

Usage:
    python mcp_server/server.py --docs docs
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from docpack.frontmatter import DIATAXIS_TYPES  # noqa: E402
from docpack.pack import Page, load_tree  # noqa: E402
from docpack.retrieve import Index  # noqa: E402

PROTOCOL_VERSION = "2024-11-05"


class ToolError(Exception):
    """A tool could not do what was asked.

    Raised rather than returned. MCP reports a tool-level failure as a
    successful JSON-RPC response carrying `isError: true`, which is the only
    channel a client can check. Two of these cases used to return a string
    beginning "Error:" with `isError` left false, so the text and the flag
    disagreed and a client that checked the flag, which is the documented
    thing to check, was told a rejected path lookup had succeeded.
    """

TOOLS: list[dict[str, Any]] = [
    {
        "name": "search_docs",
        "description": (
            "Keyword search across documentation chunks. Returns matching chunks with "
            "their heading trail and source page. Filter by diataxis type to get the "
            "right kind of answer: 'how-to' for instructions, 'reference' for "
            "signatures, 'explanation' for reasoning."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Keywords to search for"},
                "diataxis": {
                    "type": "string",
                    "enum": ["tutorial", "how-to", "reference", "explanation"],
                    "description": "Restrict results to one documentation type",
                },
                "limit": {"type": "integer", "default": 5},
            },
            "required": ["query"],
        },
    },
    {
        "name": "get_page",
        "description": "Return the full Markdown source of one documentation page by its path.",
        "inputSchema": {
            "type": "object",
            "properties": {"path": {"type": "string", "description": "e.g. how-to/pack-for-rag.md"}},
            "required": ["path"],
        },
    },
    {
        "name": "list_pages",
        "description": (
            "List every page with its title, summary, type, and audience. Use this "
            "first to see what the corpus covers before searching."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "diataxis": {
                    "type": "string",
                    "enum": ["tutorial", "how-to", "reference", "explanation"],
                },
                "audience": {
                    "type": "string",
                    "enum": ["new-user", "developer", "operator", "contributor"],
                },
            },
        },
    },
]


class DocsServer:
    """Serves a loaded documentation tree over MCP."""

    def __init__(self, docs_dir: Path) -> None:
        self.docs_dir = docs_dir
        self.pages: list[Page] = load_tree(docs_dir)
        # The same index the evaluation harness scores. If this server ranked
        # results its own way, `docpack eval` would be measuring code that
        # nobody ships.
        self.index = Index.from_pages(self.pages, docs_dir=docs_dir)

    # ---------------------------------------------------------------- tools

    def search_docs(self, query: str, diataxis: str | None = None, limit: int = 5) -> str:
        """Rank chunks with the shared BM25 retriever."""
        # An unknown filter value used to pass straight through to the index,
        # match nothing, and come back as "No matches", which is
        # indistinguishable from a question the corpus genuinely cannot answer.
        # A typo in a filter and an empty result set are different answers.
        if diataxis is not None and diataxis not in DIATAXIS_TYPES:
            raise ToolError(
                f"unknown diataxis type {diataxis!r}; "
                f"expected one of {', '.join(sorted(DIATAXIS_TYPES))}"
            )
        hits = self.index.search(query, diataxis=diataxis, limit=limit)
        if not hits:
            return f"No matches for {query!r}."
        return "\n\n---\n\n".join(hit.render() for hit in hits)

    def get_page(self, path: str) -> str:
        """Return one page's full Markdown."""
        target = (self.docs_dir / path).resolve()
        if not target.is_relative_to(self.docs_dir.resolve()):
            raise ToolError("path escapes the documentation tree")
        if not target.exists():
            available = ", ".join(
                p.path.relative_to(self.docs_dir).as_posix() for p in self.pages
            )
            raise ToolError(f"no page at {path!r}. Available: {available}")
        return target.read_text(encoding="utf-8")

    def list_pages(self, diataxis: str | None = None, audience: str | None = None) -> str:
        """Return the corpus index as readable Markdown."""
        rows = []
        for page in self.pages:
            if diataxis and page.meta.diataxis != diataxis:
                continue
            if audience and page.meta.audience != audience:
                continue
            rel = page.path.relative_to(self.docs_dir).as_posix()
            rows.append(
                f"- `{rel}` [{page.meta.diataxis}, {page.meta.audience}] "
                f"**{page.meta.title}**: {page.meta.summary}"
            )
        return "\n".join(rows) if rows else "No pages match that filter."

    # ------------------------------------------------------------ dispatch

    def call_tool(self, name: str, arguments: dict[str, Any]) -> str:
        if name == "search_docs":
            if "query" not in arguments:
                raise ToolError("search_docs requires a 'query' argument")
            return self.search_docs(
                arguments["query"],
                arguments.get("diataxis"),
                int(arguments.get("limit", 5)),
            )
        if name == "get_page":
            # A bare KeyError stringifies to just the key name, so the client
            # saw `Error: 'path'`, which names the problem without stating it.
            if "path" not in arguments:
                raise ToolError("get_page requires a 'path' argument")
            return self.get_page(arguments["path"])
        if name == "list_pages":
            return self.list_pages(arguments.get("diataxis"), arguments.get("audience"))
        raise ToolError(
            f"unknown tool: {name}; expected one of "
            f"{', '.join(tool['name'] for tool in TOOLS)}"
        )

    def handle(self, request: dict[str, Any]) -> dict[str, Any] | None:
        """Handle one JSON-RPC request. Returns None for notifications."""
        method = request.get("method")
        req_id = request.get("id")

        if req_id is None:
            return None  # a notification; nothing to answer

        def ok(result: Any) -> dict[str, Any]:
            return {"jsonrpc": "2.0", "id": req_id, "result": result}

        if method == "initialize":
            return ok({
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "docpack-docs", "version": "0.3.0"},
            })

        if method == "tools/list":
            return ok({"tools": TOOLS})

        if method == "tools/call":
            params = request.get("params", {})
            try:
                text = self.call_tool(params["name"], params.get("arguments", {}))
            except Exception as exc:  # noqa: BLE001 - report to the client, do not crash
                return ok({
                    "content": [{"type": "text", "text": f"Error: {exc}"}],
                    "isError": True,
                })
            return ok({"content": [{"type": "text", "text": text}], "isError": False})

        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "error": {"code": -32601, "message": f"method not found: {method}"},
        }


def serve(server: DocsServer, stdin=sys.stdin, stdout=sys.stdout) -> None:
    """Read newline-delimited JSON-RPC from stdin and write responses to stdout."""
    for line in stdin:
        line = line.strip()
        if not line:
            continue
        try:
            request = json.loads(line)
        except json.JSONDecodeError:
            continue
        response = server.handle(request)
        if response is not None:
            stdout.write(json.dumps(response) + "\n")
            stdout.flush()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--docs", type=Path, default=Path("docs"))
    args = parser.parse_args(argv)
    serve(DocsServer(args.docs))
    return 0


if __name__ == "__main__":
    sys.exit(main())
