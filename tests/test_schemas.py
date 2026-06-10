from __future__ import annotations

import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from fbbp_mcp_server.schemas import CONTRACT_VERSION, build_error_response, build_tool_response


class SchemaTests(unittest.TestCase):
    def test_tool_response_contains_standard_fields(self) -> None:
        response = build_tool_response(tool="server_status", request={"ping": True})

        self.assertTrue(response["ok"])
        self.assertEqual(response["tool"], "server_status")
        self.assertEqual(response["contract_version"], CONTRACT_VERSION)
        self.assertEqual(response["request"], {"ping": True})
        self.assertEqual(response["result"], {})
        self.assertEqual(response["provenance"], {})
        self.assertEqual(response["diagnostics"], {})
        self.assertIsNone(response["error"])

    def test_error_response_preserves_error_payload(self) -> None:
        response = build_error_response(
            tool="search_knowledge",
            request={"query": "KLK7"},
            error={"code": "INVALID_REQUEST", "message": "bad input"},
        )

        self.assertFalse(response["ok"])
        self.assertEqual(response["tool"], "search_knowledge")
        self.assertEqual(response["contract_version"], CONTRACT_VERSION)
        self.assertEqual(response["request"], {"query": "KLK7"})
        self.assertEqual(response["result"], {})
        self.assertEqual(response["error"]["code"], "INVALID_REQUEST")


if __name__ == "__main__":
    unittest.main()
