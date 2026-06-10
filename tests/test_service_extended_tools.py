from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from fbbp_mcp_server import service


class ServiceExtendedToolTests(unittest.TestCase):
    def test_tool_contract_version_reports_current_version(self) -> None:
        response = service.tool_contract_version()

        self.assertTrue(response["ok"])
        self.assertEqual(response["tool"], "tool_contract_version")
        self.assertEqual(response["result"]["contract_version"], response["contract_version"])

    def test_health_status_wraps_health_snapshot(self) -> None:
        fake_snapshot = {"runtime": {"mode": "research-dev"}, "database": {"ok": True}, "public_lookups": {}}

        with mock.patch.object(service, "build_health_snapshot", return_value=fake_snapshot):
            response = service.health_status()

        self.assertTrue(response["ok"])
        self.assertEqual(response["tool"], "health_status")
        self.assertEqual(response["result"]["database"]["ok"], True)

    def test_list_record_types_aggregates_available_record_types(self) -> None:
        fake_result = {
            "record_types": [
                {"record_type": "jsonl", "source_count": 2, "chunk_count": 30},
                {"record_type": "docx", "source_count": 1, "chunk_count": 5},
            ]
        }

        with mock.patch.object(service, "_run_db_worker", return_value=fake_result):
            response = service.list_record_types()

        self.assertTrue(response["ok"])
        self.assertEqual(response["tool"], "list_record_types")
        self.assertEqual(len(response["result"]["record_types"]), 2)

    def test_explain_search_returns_request_echo_and_result(self) -> None:
        fake_result = {"pg_table": "rag_documents_bge_m3", "result_count": 3, "sources": ["a", "b"]}

        with mock.patch.object(service, "_run_db_worker", return_value=fake_result):
            response = service.explain_search("KLK7", top_k=7, filters=["record_type=jsonl"])

        self.assertTrue(response["ok"])
        self.assertEqual(response["tool"], "explain_search")
        self.assertEqual(response["request"]["top_k"], 7)
        self.assertEqual(response["result"]["result_count"], 3)

    def test_preview_ingest_rejects_missing_path_without_mutation(self) -> None:
        response = service.preview_ingest("<local_path_removed>")

        self.assertFalse(response["ok"])
        self.assertEqual(response["tool"], "preview_ingest")
        self.assertEqual(response["error"]["code"], "INGEST_INPUT_ERROR")

    def test_preview_ingest_summarizes_existing_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir)
            sample = repo_root / "sample.txt"
            sample.write_text("hello", encoding="utf-8")

            response = service.preview_ingest(str(sample))

        self.assertTrue(response["ok"])
        self.assertEqual(response["tool"], "preview_ingest")
        self.assertEqual(response["result"]["exists"], True)
        self.assertEqual(response["result"]["file_count"], 1)


if __name__ == "__main__":
    unittest.main()
