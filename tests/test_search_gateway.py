from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from unittest import mock


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from fbbp_mcp_server import server, service


class _FakeHttpResponse:
    def __init__(self, payload: dict):
        self._payload = payload

    def read(self) -> bytes:
        return json.dumps(self._payload, ensure_ascii=False).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class FormalSearchGatewayTests(unittest.TestCase):
    def setUp(self) -> None:
        service._FORMAL_GATEWAY_SEARCH_CACHE.clear()

    def test_gateway_search_rewrites_transport_diagnostics_and_preserves_contract(self) -> None:
        payload = {
            "ok": True,
            "tool": "search_knowledge",
            "contract_version": "1.1",
            "request": {
                "query": "knottin",
                "top_k": 3,
                "record_type": "jsonl",
                "filters": ["Scaffold_Category=knottin"],
                "include_answer": False,
                "include_evidence": True,
                "answer_mode": "openai",
            },
            "result": {"query": "knottin", "result_count": 1, "results": [{"source": "plmsearch_results.csv"}]},
            "diagnostics": {"query_transport": "local_service_fallback"},
            "provenance": {"dataset_version": "fbbp_private_v2026_04"},
        }

        with mock.patch.object(
            service.urllib_request,
            "urlopen",
            return_value=_FakeHttpResponse(payload),
        ) as mocked:
            response = service.search_knowledge_via_formal_http_gateway(
                "knottin",
                top_k=3,
                record_type="jsonl",
                filters=["Scaffold_Category=knottin"],
                include_answer=False,
                include_evidence=True,
                answer_mode="openai",
            )

        mocked.assert_called_once()
        self.assertTrue(response["ok"])
        self.assertEqual(response["tool"], "search_knowledge")
        self.assertEqual(response["request"]["record_type"], "jsonl")
        self.assertFalse(response["request"]["include_answer"])
        self.assertEqual(response["diagnostics"]["query_transport"], "formal_http_gateway")
        self.assertEqual(response["diagnostics"]["gateway_backend_transport"], "local_service_fallback")
        self.assertIn("gateway_url", response["diagnostics"])

    def test_gateway_search_uses_cache_for_identical_requests(self) -> None:
        payload = {
            "ok": True,
            "tool": "search_knowledge",
            "contract_version": "1.1",
            "request": {"query": "KLK7"},
            "result": {"query": "KLK7", "result_count": 1, "results": [{"source": "plmsearch_results.csv"}]},
            "diagnostics": {"query_transport": "local_service_fallback"},
            "provenance": {"dataset_version": "fbbp_private_v2026_04"},
        }

        with mock.patch.object(
            service.urllib_request,
            "urlopen",
            return_value=_FakeHttpResponse(payload),
        ) as mocked:
            first = service.search_knowledge_via_formal_http_gateway("KLK7", top_k=5)
            second = service.search_knowledge_via_formal_http_gateway("KLK7", top_k=5)

        self.assertEqual(first, second)
        self.assertEqual(mocked.call_count, 1)


class MCPServerSearchGatewayTests(unittest.IsolatedAsyncioTestCase):
    async def test_mcp_search_tool_delegates_to_formal_gateway_runner(self) -> None:
        fake_response = {"ok": True, "tool": "search_knowledge", "result": {"query": "knottin"}}

        with mock.patch.object(
            server,
            "run_search_knowledge_via_formal_http_gateway",
            return_value=fake_response,
        ) as mocked:
            response = await server.search_knowledge(
                "knottin",
                top_k=4,
                record_type="jsonl",
                filters=["Scaffold_Category=knottin"],
                include_answer=False,
                include_evidence=True,
                answer_mode="openai",
            )

        mocked.assert_called_once_with(
            query="knottin",
            top_k=4,
            record_type="jsonl",
            filters=["Scaffold_Category=knottin"],
            include_answer=False,
            include_evidence=True,
            answer_mode="openai",
        )
        self.assertEqual(response, fake_response)


if __name__ == "__main__":
    unittest.main()
