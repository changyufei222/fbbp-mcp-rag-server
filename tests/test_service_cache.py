from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest import mock


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from fbbp_mcp_server import service


class ServiceCacheTests(unittest.TestCase):
    def test_search_knowledge_uses_cache_for_identical_payload(self) -> None:
        service._SEARCH_CACHE.clear()
        fake_result = {"query": "KLK7", "result_count": 1, "results": [{"source": "sample.csv"}]}

        with mock.patch.object(service, "_run_db_worker", return_value=fake_result) as mocked:
            first = service.search_knowledge(
                "KLK7",
                top_k=5,
                filters=["Scaffold_Category=knottin"],
                answer_mode="openai",
            )
            second = service.search_knowledge(
                "KLK7",
                top_k=5,
                filters=["Scaffold_Category=knottin"],
                answer_mode="openai",
            )

        self.assertEqual(first, second)
        self.assertEqual(mocked.call_count, 1)

    def test_search_knowledge_does_not_cache_error_responses(self) -> None:
        service._SEARCH_CACHE.clear()
        failure = {
            "ok": False,
            "tool": "search_knowledge",
            "request": {"query": "KLK7"},
            "result": {},
            "error": {"message": "connection timeout expired"},
        }
        success = {"query": "KLK7", "result_count": 1, "results": [{"source": "sample.csv"}]}

        with (
            mock.patch.object(service, "_tool_call", side_effect=[failure, {"ok": True, "result": success}]) as tool_call,
            mock.patch.object(service, "formal_runtime_snapshot", return_value={"dataset_version": "fbbp_private_v2026_04"}),
        ):
            first = service.search_knowledge("KLK7", top_k=5, include_answer=False)
            second = service.search_knowledge("KLK7", top_k=5, include_answer=False)

        self.assertFalse(first["ok"])
        self.assertTrue(second["ok"])
        self.assertEqual(tool_call.call_count, 2)
        self.assertEqual(service._SEARCH_CACHE[next(iter(service._SEARCH_CACHE))][1], second)


if __name__ == "__main__":
    unittest.main()
