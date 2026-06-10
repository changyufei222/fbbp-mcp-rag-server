from __future__ import annotations

import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from fbbp_mcp_server.errors import MCPToolError, map_exception


class ErrorTests(unittest.TestCase):
    def test_map_runtime_error_to_config_error(self) -> None:
        error = map_exception(RuntimeError("Could not import ragkb"))

        self.assertEqual(error["code"], "IMPORT_ERROR")
        self.assertIn("ragkb", error["message"])

    def test_map_known_tool_error_preserves_code(self) -> None:
        error = map_exception(MCPToolError(code="TIMEOUT_ERROR", message="request timed out"))

        self.assertEqual(error["code"], "TIMEOUT_ERROR")
        self.assertEqual(error["message"], "request timed out")

    def test_map_value_error_to_invalid_request(self) -> None:
        error = map_exception(ValueError("bad filter"))

        self.assertEqual(error["code"], "INVALID_REQUEST")
        self.assertEqual(error["message"], "bad filter")


if __name__ == "__main__":
    unittest.main()
