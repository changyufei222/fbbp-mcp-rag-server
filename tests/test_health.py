from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from fbbp_mcp_server.health import build_health_snapshot


class HealthTests(unittest.TestCase):
    def test_health_snapshot_includes_runtime_database_and_public_sections(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir)
            snapshot = build_health_snapshot(
                repo_root=repo_root,
                db_probe=lambda: {"ok": True, "result": 1},
                public_probe=lambda: {"pubmed": {"ok": True}},
                ragkb_status="installed",
            )

        self.assertIn("runtime", snapshot)
        self.assertIn("database", snapshot)
        self.assertIn("public_lookups", snapshot)
        self.assertEqual(snapshot["database"]["ok"], True)
        self.assertEqual(snapshot["public_lookups"]["pubmed"]["ok"], True)

    def test_health_snapshot_reports_runtime_env_path(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir)
            snapshot = build_health_snapshot(
                repo_root=repo_root,
                db_probe=lambda: {"ok": False},
                public_probe=lambda: {},
                ragkb_status="installed",
            )

        self.assertTrue(snapshot["runtime"]["env_path"].endswith(".env"))
        self.assertIn("mode", snapshot["runtime"])
        self.assertIn("candidate_site_packages", snapshot["runtime"])

    def test_health_snapshot_includes_formal_runtime_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir)
            snapshot = build_health_snapshot(
                repo_root=repo_root,
                db_probe=lambda: {"ok": True},
                public_probe=lambda: {},
                ragkb_status="installed",
                formal_runtime={"dataset_version": "covunibind_v2026_04", "runtime_profile": "local_formal"},
            )

        self.assertEqual(snapshot["runtime"]["dataset_version"], "covunibind_v2026_04")
        self.assertEqual(snapshot["runtime"]["runtime_profile"], "local_formal")


if __name__ == "__main__":
    unittest.main()
