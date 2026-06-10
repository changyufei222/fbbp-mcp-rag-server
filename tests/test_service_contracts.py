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


class ServiceContractTests(unittest.TestCase):
    def test_service_env_defaults_prefer_fbbp_keys(self) -> None:
        with mock.patch.dict(
            "os.environ",
            {
                "FBBP_MCP_DEFAULT_TOP_K": "9",
                "FBBP_MCP_DEFAULT_ANSWER_MODE": "formal",
                "FBTP_MCP_DEFAULT_TOP_K": "3",
                "FBTP_MCP_DEFAULT_ANSWER_MODE": "extractive",
                "FBBP_FORMAL_QUERY_GATEWAY_URL": "http://127.0.0.1:8101/api/fbbp/formal-search",
                "FBTP_FORMAL_QUERY_GATEWAY_URL": "http://127.0.0.1:8001/api/fbtp/formal-search",
                "FBBP_FORMAL_QUERY_GATEWAY_TIMEOUT_SECONDS": "45",
                "FBTP_FORMAL_QUERY_GATEWAY_TIMEOUT_SECONDS": "300",
            },
            clear=True,
        ):
            self.assertEqual(service._default_top_k(), 9)
            self.assertEqual(service._default_answer_mode(), "formal")
            self.assertEqual(
                service._formal_query_gateway_url(),
                "http://127.0.0.1:8101/api/fbbp/formal-search",
            )
            self.assertEqual(service._formal_query_gateway_timeout_seconds(), 45.0)

    def test_server_status_returns_contract_shape(self) -> None:
        with (
            mock.patch.object(service, "_run_db_worker", return_value={"status": "ok"}),
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
            response = service.server_status()

        self.assertEqual(response["tool"], "server_status")
        self.assertTrue(response["ok"])
        self.assertEqual(response["result"]["status"], "ok")
        self.assertEqual(response["contract_version"], "1.1")
        self.assertEqual(response["result"]["dataset_version"], "fbbp_private_v2026_04")
        self.assertEqual(response["result"]["db_identity"], "fbbp_formal_pgvector")
        self.assertEqual(response["result"]["build_id"], "fbbp-2026-04-formal")
        self.assertEqual(response["result"]["source_registry_version"], "2026-04-16")
        self.assertIn("diagnostics", response)

    def test_search_knowledge_returns_contract_shape(self) -> None:
        fake_result = {
            "query": "KLK7",
            "result_count": 1,
            "results": [{"source": "plmsearch_results.csv", "chunk_id": "plmsearch_results.csv#chunk-1"}],
            "answer": {"text": "sample"},
        }
        service._SEARCH_CACHE.clear()

        with (
            mock.patch.object(service, "_run_db_worker", return_value=fake_result),
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
                                "source_description": "PLM search output for the full FBBP build",
                                "upstream_pipeline": "llm-rag-knowledge-base/schema_tables_rag_ready",
                                "quality_notes": "Real FBBP export; no filename inference allowed",
                                "owner_table": "plmsearch_results",
                            }
                        }
                    },
                },
            ),
        ):
            response = service.search_knowledge(
                "KLK7",
                top_k=5,
                filters=["Scaffold_Category=knottin"],
                answer_mode="openai",
            )

        self.assertEqual(response["tool"], "search_knowledge")
        self.assertTrue(response["ok"])
        self.assertEqual(response["contract_version"], "1.1")
        self.assertEqual(response["request"]["query"], "KLK7")
        self.assertEqual(response["result"]["result_count"], 1)
        self.assertEqual(response["provenance"]["dataset_version"], "fbbp_private_v2026_04")
        self.assertEqual(response["provenance"]["runtime_profile"], "local_formal")
        self.assertEqual(response["provenance"]["db_identity"], "fbbp_formal_pgvector")
        self.assertEqual(response["provenance"]["build_id"], "fbbp-2026-04-formal")
        self.assertEqual(response["provenance"]["source_registry_version"], "2026-04-16")
        self.assertEqual(response["result"]["structured_output"]["claims"][0]["text"], "sample")
        self.assertEqual(
            response["result"]["structured_output"]["evidence_rows"][0]["source_category"],
            "structure_screen",
        )
        self.assertEqual(
            response["result"]["structured_output"]["evidence_rows"][0]["owner_table"],
            "plmsearch_results",
        )
        self.assertEqual(response["result"]["structured_output"]["summary"], "sample")
        self.assertIn("key_findings", response["result"]["structured_output"])
        self.assertIn("known_unknowns", response["result"]["structured_output"])
        self.assertIn("evidence_table", response["result"]["structured_output"])
        self.assertEqual(
            response["result"]["structured_output"]["source_registry_used"][0]["owner_table"],
            "plmsearch_results",
        )
        self.assertIn("limitations", response["result"]["structured_output"])
        self.assertIn("provenance_caveats", response["result"]["structured_output"])
        self.assertIn("diagnostics", response)

    def test_list_sources_enriches_rows_with_formal_source_registry_metadata(self) -> None:
        fake_result = {
            "count": 1,
            "record_type": "csv",
            "sources": [
                {
                    "source": "plmsearch_results.csv",
                    "record_type": "csv",
                    "chunk_count": 38079,
                }
            ],
        }

        with (
            mock.patch.object(service, "_run_db_worker", return_value=fake_result),
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
                                "source_description": "PLM search output for the full FBBP build",
                                "upstream_pipeline": "llm-rag-knowledge-base/schema_tables_rag_ready",
                                "quality_notes": "Formal full-data source",
                                "owner_table": "plmsearch_results",
                            }
                        }
                    },
                },
            ),
        ):
            response = service.list_available_sources(record_type="csv", limit=5)

        self.assertTrue(response["ok"])
        self.assertEqual(response["contract_version"], "1.1")
        self.assertEqual(response["provenance"]["source_registry_version"], "2026-04-16")
        self.assertEqual(response["result"]["sources"][0]["source_category"], "structure_screen")
        self.assertEqual(response["result"]["sources"][0]["owner_table"], "plmsearch_results")
        self.assertEqual(
            response["result"]["sources"][0]["upstream_pipeline"],
            "llm-rag-knowledge-base/schema_tables_rag_ready",
        )

    def test_public_lookup_returns_contract_shape(self) -> None:
        fake_result = {"count": 1, "articles": [{"pmid": "1"}]}

        with mock.patch.object(service, "run_search_pubmed", return_value=fake_result):
            response = service.search_pubmed_articles("binding protein", retmax=3)

        self.assertEqual(response["tool"], "search_pubmed")
        self.assertTrue(response["ok"])
        self.assertEqual(response["request"]["retmax"], 3)
        self.assertEqual(response["result"]["count"], 1)

    def test_search_knowledge_falls_back_to_retrieval_only_when_answer_generation_fails(self) -> None:
        service._SEARCH_CACHE.clear()
        fake_result = {
            "query": "RBD",
            "result_count": 1,
            "results": [{"source": "cov.csv", "chunk_id": "chunk-1"}],
            "answer": None,
        }

        with (
            mock.patch.object(
                service,
                "_run_db_worker",
                side_effect=[RuntimeError("Error code: 401"), fake_result],
            ),
            mock.patch.object(
                service,
                "formal_runtime_snapshot",
                return_value={"dataset_version": "covunibind_v2026_04", "runtime_profile": "local_formal"},
            ),
        ):
            response = service.search_knowledge(
                "RBD",
                top_k=5,
                include_answer=True,
                include_evidence=True,
                answer_mode="openai",
            )

        self.assertTrue(response["ok"])
        self.assertEqual(response["request"]["include_answer"], False)
        self.assertTrue(response["result"]["answer_generation_failed"])
        self.assertEqual(response["result"]["result_count"], 1)
        self.assertEqual(response["diagnostics"]["fallback_mode"], "retrieval_only")

    def test_search_knowledge_prefers_inprocess_worker_path(self) -> None:
        service._SEARCH_CACHE.clear()
        fake_result = {
            "query": "ITI-D2",
            "result_count": 1,
            "results": [{"source": "protein_cards_v2.jsonl", "chunk_id": "protein-v2:PROT-00007"}],
            "answer": None,
        }

        with (
            mock.patch.object(service, "_run_db_worker_direct", return_value=fake_result) as direct_worker,
            mock.patch.object(
                service,
                "_run_db_worker_subprocess",
                side_effect=AssertionError("subprocess worker should not be used for default search path"),
            ),
            mock.patch.object(
                service,
                "formal_runtime_snapshot",
                return_value={"dataset_version": "covunibind_v2026_04", "runtime_profile": "local_formal"},
            ),
        ):
            response = service.search_knowledge("ITI-D2", top_k=3, include_answer=False)

        direct_worker.assert_called_once()
        self.assertTrue(response["ok"])
        self.assertEqual(response["result"]["result_count"], 1)

    def test_search_knowledge_formal_mode_uses_multi_query_fusion_and_deterministic_summary(self) -> None:
        service._SEARCH_CACHE.clear()
        fake_responses = [
            {
                "query": "knottin scaffold summary",
                "result_count": 1,
                "results": [
                    {
                        "source": "interaction_cards_v2.jsonl",
                        "chunk_id": "interaction-v2:INT-001",
                        "score": 0.74,
                        "excerpt": (
                            "Scaffold Type: knottin\n"
                            "Target Gene Name: EGFR\n"
                            "Organism: Homo sapiens\n"
                            "Interaction ID: INT-001\n"
                            "Date: 2025-03-14"
                        ),
                    }
                ],
                "answer": None,
            },
            {
                "query": "knottin structure domain motif",
                "result_count": 1,
                "results": [
                    {
                        "source": "loop_annotations.csv",
                        "chunk_id": "loop_annotations.csv#chunk-7",
                        "score": 0.68,
                        "excerpt": (
                            "Scaffold Type: knottin\n"
                            "Domain Id: DOM-007\n"
                            "Organism: Homo sapiens"
                        ),
                    }
                ],
                "answer": None,
            },
            {
                "query": "knottin evidence provenance identifier",
                "result_count": 1,
                "results": [
                    {
                        "source": "plmsearch_results.csv",
                        "chunk_id": "plmsearch_results.csv#chunk-18",
                        "score": 0.66,
                        "excerpt": (
                            "Scaffold Type: knottin\n"
                            "Target Gene Name: EGFR\n"
                            "Interaction ID: INT-001"
                        ),
                    }
                ],
                "answer": None,
            },
            {
                "query": "knottin target gene interaction affinity binding receptor",
                "result_count": 1,
                "results": [
                    {
                        "source": "interaction_cards_v2.jsonl",
                        "chunk_id": "interaction-v2:INT-017",
                        "score": 0.63,
                        "excerpt": (
                            "Scaffold Type: knottin\n"
                            "Target Gene Name: EGFR\n"
                            "Interaction ID: INT-017"
                        ),
                    }
                ],
                "answer": None,
            },
        ]

        with (
            mock.patch.object(service, "_run_db_worker", side_effect=fake_responses) as worker,
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
                            "interaction_cards_v2.jsonl": {
                                "source_category": "interaction_card",
                                "source_description": "Real interaction cards from the formal FBBP build",
                                "upstream_pipeline": "formal_interactions_export",
                                "quality_notes": "Grounded interaction evidence",
                                "owner_table": "interaction_cards_v2",
                            },
                            "loop_annotations.csv": {
                                "source_category": "structural_annotation",
                                "source_description": "Loop/domain annotations for FBBP proteins",
                                "upstream_pipeline": "formal_domain_annotation_export",
                                "quality_notes": "Supports scaffold and domain interpretation",
                                "owner_table": "loop_annotations",
                            },
                            "plmsearch_results.csv": {
                                "source_category": "structure_screen",
                                "source_description": "PLM search output for the full FBBP build",
                                "upstream_pipeline": "schema_tables_rag_ready",
                                "quality_notes": "Real FBBP export; no filename inference allowed",
                                "owner_table": "plmsearch_results",
                            },
                        }
                    },
                },
            ),
        ):
            response = service.search_knowledge(
                "Please summarize the knottin scaffold landscape, common targets, and evidence sources.",
                top_k=5,
                filters=["Scaffold_Category=knottin"],
                include_answer=True,
                include_evidence=True,
                answer_mode="formal",
            )

        self.assertTrue(response["ok"])
        self.assertGreaterEqual(worker.call_count, 3)
        self.assertEqual(response["diagnostics"]["retrieval_strategy"], "multi_query_fusion")
        self.assertTrue(response["diagnostics"]["query_plan"])
        self.assertIn("knottin", response["result"]["structured_output"]["summary"].lower())
        self.assertIn("EGFR", "\n".join(response["result"]["structured_output"]["key_findings"]))
        self.assertGreaterEqual(len(response["result"]["structured_output"]["source_registry_used"]), 2)
        self.assertEqual(response["result"]["structured_output"]["evidence_table"][0]["target"], "EGFR")
        self.assertIn("Key findings", response["result"]["answer"])
        self.assertEqual(response["result"]["structured_output"]["claims"][0]["support"], "retrieved_evidence")

    def test_search_knowledge_formal_mode_can_report_full_12_class_dataset_profile(self) -> None:
        service._SEARCH_CACHE.clear()
        fake_result = {
            "query": "请总结当前 FBBP 全量 12 类 scaffold 的分布和代表性靶点。",
            "result_count": 2,
            "results": [
                {
                    "source": "interaction_cards_v2.jsonl",
                    "chunk_id": "interaction-v2:INT-01001",
                    "score": 0.61,
                    "excerpt": "Interaction Centered Card\n- Scaffold Type: adnectin\n- Gene Name: EGFR",
                },
                {
                    "source": "interaction_cards_v2.jsonl",
                    "chunk_id": "interaction-v2:INT-01002",
                    "score": 0.59,
                    "excerpt": "Interaction Centered Card\n- Scaffold Type: knottin\n- Gene Name: SCN9A",
                },
            ],
            "answer": None,
        }

        with (
            mock.patch.object(service, "_run_db_worker", return_value=fake_result),
            mock.patch.object(
                service,
                "_get_corpus_scaffold_profile",
                return_value={
                    "class_count": 12,
                    "classes": [
                        {"scaffold": "adnectin", "count": 456, "target_rows": 37, "top_targets": [("EGFR", 11)]},
                        {"scaffold": "cyclotide", "count": 404, "target_rows": 2, "top_targets": [("OPRK1", 2)]},
                        {"scaffold": "knottin", "count": 310, "target_rows": 1, "top_targets": [("SCN9A", 1)]},
                    ],
                    "by_scaffold": {
                        "adnectin": {"count": 456, "target_rows": 37, "top_targets": [("EGFR", 11)]},
                        "knottin": {"count": 310, "target_rows": 1, "top_targets": [("SCN9A", 1)]},
                    },
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
                            "interaction_cards_v2.jsonl": {
                                "source_category": "aggregate_jsonl",
                                "source_description": "Interaction cards",
                                "upstream_pipeline": "schema_tables_rag_ready/interaction_cards_v2.jsonl",
                                "quality_notes": "Full-data scaffold cards",
                                "owner_table": "interaction_cards_v2",
                            }
                        }
                    },
                },
            ),
        ):
            response = service.search_knowledge(
                "请总结当前 FBBP 全量 12 类 scaffold 的分布和代表性靶点。",
                top_k=5,
                include_answer=True,
                include_evidence=True,
                answer_mode="formal",
            )

        self.assertTrue(response["ok"])
        self.assertIn("12 类", response["result"]["structured_output"]["summary"])
        self.assertIn("adnectin", response["result"]["structured_output"]["summary"])
        self.assertIn("knottin", response["result"]["structured_output"]["summary"])
        self.assertIn("EGFR", "\n".join(response["result"]["structured_output"]["key_findings"]))
        self.assertEqual(response["diagnostics"]["retrieval_strategy"], "multi_query_fusion")

    def test_interaction_cards_source_path_prefers_repo_local_runtime_snapshot(self) -> None:
        runtime = {
            "dataset_version": "fbbp_private_v2026_04",
            "dataset_descriptor": {
                "source_registry": {
                    "interaction_cards_v2.jsonl": {
                        "upstream_pipeline": "llm-rag-knowledge-base/data/schema_tables_rag_ready/interaction_cards_v2.jsonl",
                        "runtime_snapshot": "formal_snapshots/fbbp_private_v2026_04/interaction_cards_v2.jsonl",
                    }
                }
            },
        }

        resolved = service._interaction_cards_source_path(runtime)

        self.assertEqual(
            resolved,
            REPO_ROOT / "formal_snapshots" / "fbbp_private_v2026_04" / "interaction_cards_v2.jsonl",
        )


if __name__ == "__main__":
    unittest.main()
