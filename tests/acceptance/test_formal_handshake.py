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


class FormalHandshakeAcceptanceTests(unittest.TestCase):
    def test_health_status_exposes_formal_handshake_fields(self) -> None:
        with (
            mock.patch.object(service, "ensure_ragkb_importable", return_value="installed"),
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
            mock.patch.object(service, "_run_db_worker", return_value={"db_probe": {"ok": True, "result": 1}}),
        ):
            response = service.health_status()

        self.assertTrue(response["ok"])
        self.assertEqual(response["contract_version"], "1.1")
        self.assertEqual(response["result"]["runtime"]["dataset_version"], "fbbp_private_v2026_04")
        self.assertEqual(response["result"]["runtime"]["runtime_profile"], "local_formal")
        self.assertEqual(response["result"]["runtime"]["db_identity"], "fbbp_formal_pgvector")
        self.assertEqual(response["result"]["runtime"]["build_id"], "fbbp-2026-04-formal")
        self.assertEqual(response["result"]["runtime"]["source_registry_version"], "2026-04-16")


if __name__ == "__main__":
    unittest.main()
