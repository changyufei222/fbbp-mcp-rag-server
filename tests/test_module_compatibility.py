from __future__ import annotations

import importlib
import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))


class ModuleCompatibilityTests(unittest.TestCase):
    def test_new_and_legacy_package_names_are_both_importable(self) -> None:
        new_service = importlib.import_module("fbbp_mcp_server.service")
        legacy_service = importlib.import_module("fbtp_mcp_server.service")

        self.assertEqual(new_service.search_knowledge.__name__, "search_knowledge")
        self.assertEqual(legacy_service.search_knowledge.__name__, "search_knowledge")


if __name__ == "__main__":
    unittest.main()
