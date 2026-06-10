from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest import mock


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
RAGKB_SRC_ROOT = REPO_ROOT.parent / "llm-rag-knowledge-base" / "src"
for candidate in (SRC_ROOT, RAGKB_SRC_ROOT):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

from fbbp_mcp_server import db_worker


class _FakeCursor:
    def execute(self, _sql: str) -> None:
        return None

    def fetchone(self):
        return (1,)

    def close(self) -> None:
        return None


class _FakeConnection:
    def cursor(self) -> _FakeCursor:
        return _FakeCursor()

    def close(self) -> None:
        return None


class DbWorkerTests(unittest.TestCase):
    def test_server_status_warms_wsl_route_before_connect(self) -> None:
        with (
            mock.patch("ragkb.wsl_pg.warm_wsl_postgres_route") as mocked_warm,
            mock.patch("psycopg.connect", return_value=_FakeConnection()),
        ):
            payload = db_worker._run({"action": "server_status"})

        self.assertTrue(payload["db_probe"]["ok"])
        mocked_warm.assert_called_once_with(payload["pg_host"])

    def test_search_knowledge_passes_structured_evidence_bundle_into_answer_generation(self) -> None:
        fake_contexts = [
            {
                "source": "interaction_cards_v2.jsonl",
                "chunk_id": "interaction-v2:INT-01109",
                "score": 0.88,
                "content": "Interaction Centered Card: INT-01109",
                "metadata": {"record_type": "jsonl"},
            }
        ]
        fake_evidence = {"query_center": "interaction", "anchor": {"interaction_id": "INT-01109"}}
        with (
            mock.patch("ragkb.wsl_pg.warm_wsl_postgres_route"),
            mock.patch("ragkb.retrieval.retriever.retrieve", return_value=fake_contexts) as mocked_retrieve,
            mock.patch("ragkb.search_payloads.assemble_evidence_bundle", return_value=fake_evidence) as mocked_bundle,
            mock.patch("ragkb.answer.generator.build_answer", return_value="Grounded knottin summary.") as mocked_build_answer,
        ):
            payload = db_worker._run(
                {
                    "action": "search_knowledge",
                    "query": "knottin scaffold",
                    "top_k": 5,
                    "filters": [],
                    "include_answer": True,
                    "include_evidence": True,
                    "answer_mode": "openai",
                }
            )

        self.assertEqual(payload["answer"], "Grounded knottin summary.")
        self.assertEqual(payload["result_count"], 1)
        self.assertIn("evidence", payload)
        mocked_retrieve.assert_called_once()
        mocked_bundle.assert_called_once()
        mocked_build_answer.assert_called_once()
        _, kwargs = mocked_build_answer.call_args
        self.assertEqual(kwargs["evidence_bundle"], fake_evidence)


if __name__ == "__main__":
    unittest.main()
