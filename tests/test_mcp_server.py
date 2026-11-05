"""Tests for the MCP server, written from a client's point of view.

These exist because of a specific confusion. MCP reports a tool-level failure
as a *successful* JSON-RPC response whose result carries `isError: true`, and
that flag is the only thing a client can branch on. Two of this server's
failure paths used to return a string beginning "Error:" with `isError` left
false, so the text and the flag disagreed: a client checking the documented
field was told that a rejected path traversal had succeeded.

So every test here asserts on the flag rather than on the prose, which is what
an integrator would do.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "mcp_server"))

from server import DocsServer, ToolError  # noqa: E402


@pytest.fixture(scope="module")
def server() -> DocsServer:
    return DocsServer(REPO / "docs")


def call(server: DocsServer, name: str, arguments: dict) -> dict:
    """Make a tools/call request the way a client would, and return the result."""
    response = server.handle(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": name, "arguments": arguments},
        }
    )
    assert response is not None
    assert "error" not in response, "a tool failure is not a JSON-RPC error"
    return response["result"]


# ------------------------------------------------------------------ the happy path


def test_initialize_names_the_server(server):
    result = server.handle({"jsonrpc": "2.0", "id": 1, "method": "initialize"})["result"]
    assert result["serverInfo"]["name"]
    assert result["protocolVersion"]


def test_every_advertised_tool_can_be_called(server):
    """`tools/list` is a promise. Keep it checkable."""
    listed = server.handle({"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
    names = [tool["name"] for tool in listed["result"]["tools"]]
    assert names, "the server advertises no tools"

    minimal = {
        "search_docs": {"query": "chunk"},
        "get_page": {"path": "index.md"},
        "list_pages": {},
    }
    assert set(minimal) == set(names), "a tool was added without a test"
    for name in names:
        result = call(server, name, minimal[name])
        assert result["isError"] is False
        assert result["content"][0]["text"].strip()


def test_an_unknown_method_is_a_jsonrpc_error(server):
    """Protocol-level failures use the error channel; tool failures do not."""
    response = server.handle({"jsonrpc": "2.0", "id": 1, "method": "tools/frobnicate"})
    assert response["error"]["code"] == -32601


def test_a_notification_gets_no_response(server):
    assert server.handle({"jsonrpc": "2.0", "method": "initialize"}) is None


# ---------------------------------------------------------------- failure reporting


@pytest.mark.parametrize(
    ("name", "arguments", "expected_in_message"),
    [
        ("nope", {}, "unknown tool"),
        ("get_page", {}, "requires a 'path'"),
        ("search_docs", {}, "requires a 'query'"),
        ("get_page", {"path": "../../etc/passwd"}, "escapes"),
        ("get_page", {"path": "no/such/page.md"}, "no page at"),
        ("search_docs", {"query": "x", "diataxis": "nonsense"}, "unknown diataxis type"),
    ],
)
def test_every_failure_sets_is_error(server, name, arguments, expected_in_message):
    result = call(server, name, arguments)
    assert result["isError"] is True, (
        "the flag is the only thing a client can branch on, so a failure that "
        "leaves it false is invisible however clearly the text explains itself"
    )
    assert expected_in_message in result["content"][0]["text"]


def test_no_successful_result_announces_an_error_in_its_text(server):
    """The two channels must agree, in both directions."""
    for name, arguments in [
        ("search_docs", {"query": "chunk"}),
        ("get_page", {"path": "index.md"}),
        ("list_pages", {}),
        ("search_docs", {"query": "zzzqqq wwwvvv xxxyyy"}),
    ]:
        result = call(server, name, arguments)
        if not result["isError"]:
            assert not result["content"][0]["text"].lstrip().startswith("Error")


def test_an_empty_result_is_not_a_failure(server):
    """A question the corpus cannot answer is a real answer, not an error.

    The query has to be genuinely out of vocabulary. BM25 over a small corpus
    returns something for any query containing an ordinary English word, so
    "no such term anywhere" matches on `term` and `anywhere`. An integrator
    cannot use an empty result set to detect a bad query; empty is rare, and
    the normal failure is a confident low-relevance match.
    """
    result = call(server, "search_docs", {"query": "zzzqqq wwwvvv xxxyyy"})
    assert result["isError"] is False
    assert "No matches" in result["content"][0]["text"]


def test_a_bad_filter_value_is_distinguishable_from_an_empty_result(server):
    """The reason the diataxis check exists: a typo and a miss are different."""
    typo = call(server, "search_docs", {"query": "chunk", "diataxis": "how_to"})
    miss = call(server, "search_docs", {"query": "zzzqqq wwwvvv", "diataxis": "how-to"})
    assert typo["isError"] is True
    assert miss["isError"] is False


def test_path_traversal_is_refused_rather_than_read(server):
    with pytest.raises(ToolError, match="escapes"):
        server.get_page("../../etc/passwd")
