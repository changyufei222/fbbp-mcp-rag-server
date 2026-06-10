from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest import mock


REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from fbbp_mcp_server import service


class FormalProvenanceAcceptanceTests(unittest.TestCase):
    def test_get_document_chunk_provenance_is_sufficient_for_formal_evidence(self) -> None:
        with (
            mock.patch.object(
                service,
                "_run_db_worker",
                return_value={
                    "found": True,
                    "source": "cov.csv",
                    "chunk_id": "chunk-1",
                    "content": "Evidence excerpt",
                    "metadata": {"record_type": "csv"},
                },
            ),
            mock.patch.object(
                service,
                "formal_runtime_snapshot",
                return_value={
                    "dataset_version": "fbbp_private_v2026_04",
                    "runtime_profile": "local_formal",
                    "db_identity": "fbbp_formal_pgvector",
                    "build_id": "fbbp-2026-04-formal",
                    "source_registry_version": "2026-04-16",
                },
            ),
        ):
            response = service.get_document_chunk_by_id("cov.csv", "chunk-1")

        self.assertTrue(response["ok"])
        self.assertEqual(response["provenance"]["source"], "cov.csv")
        self.assertEqual(response["provenance"]["chunk_id"], "chunk-1")
        self.assertEqual(response["provenance"]["dataset_version"], "fbbp_private_v2026_04")
        self.assertEqual(response["provenance"]["db_identity"], "fbbp_formal_pgvector")
        self.assertEqual(response["provenance"]["build_id"], "fbbp-2026-04-formal")
        self.assertEqual(response["provenance"]["source_registry_version"], "2026-04-16")

    def test_get_source_summary_exposes_registry_metadata_without_filename_inference(self) -> None:
        with (
            mock.patch.object(
                service,
                "_run_db_worker",
                return_value={
                    "found": True,
                    "source": "plmsearch_results.csv",
                    "record_types": [{"record_type": "csv", "chunk_count": 38079}],
                    "total_chunks": 38079,
                },
            ),
            mock.patch.object(
                service,
                "formal_runtime_snapshot",
                return_value={
                    "dataset_version": "fbbp_private_v2026_04",
                    "runtime_profile": "local_formal",
                    "db_identity": "fbbp_formal_pgvector",
                    "build_id": "fbbp-2026-04-formal",
                    "source_registry_version": "2026-04-16",
                    "dataset_descriptor": {
                        "source_registry": {
                            "plmsearch_results.csv": {
                                "source_category": "structure_screen",
                                "source_description": "Full FBBP plmsearch table export",
                                "upstream_pipeline": "llm-rag-knowledge-base/schema_tables_rag_ready",
                                "quality_notes": "Canonical full formal source registry row",
                                "owner_table": "plmsearch_results",
                            }
                        }
                    },
                },
            ),
        ):
            response = service.get_source_summary("plmsearch_results.csv", limit=5)

        self.assertTrue(response["ok"])
        self.assertEqual(response["contract_version"], "1.1")
        self.assertEqual(response["provenance"]["source_registry_version"], "2026-04-16")
        self.assertEqual(response["result"]["source_registry"]["owner_table"], "plmsearch_results")
        self.assertEqual(response["result"]["source_registry"]["source_category"], "structure_screen")
        self.assertIn("source_description", response["result"]["source_registry"])


if __name__ == "__main__":
    unittest.main()
