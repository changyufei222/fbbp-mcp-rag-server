from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
SITE_PACKAGES = REPO_ROOT / ".venv" / "Lib" / "site-packages"


class MCPServerToolTests(unittest.TestCase):
    def test_formal_tool_names_are_registered(self) -> None:
        script = """
from pathlib import Path
import json
import sys

repo_root = Path.cwd()
sys.path = [str(repo_root / ".venv" / "Lib" / "site-packages"), str(repo_root / "src")] + list(sys.path)
import fbbp_mcp_server.server as mcp_server
print(json.dumps(sorted(mcp_server.mcp._tool_manager._tools.keys())))
"""
        proc = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
            check=False,
        )
        self.assertEqual(proc.returncode, 0, msg=proc.stderr)
        registered = set(json.loads(proc.stdout.strip()))

        expected = {
            "server_status",
            "health_status",
            "tool_contract_version",
            "list_sources",
            "list_record_types",
            "get_source_summary",
            "get_document_chunk",
            "search_knowledge",
            "explain_search",
            "preview_ingest",
            "ingest_sources",
            "search_pubmed",
            "get_uniprot_entry",
            "get_pdb_entry",
        }

        self.assertTrue(expected.issubset(registered))

    def test_loopback_transport_security_stays_enabled(self) -> None:
        script = """
from pathlib import Path
import json
import sys

repo_root = Path.cwd()
sys.path = [str(repo_root / ".venv" / "Lib" / "site-packages"), str(repo_root / "src")] + list(sys.path)
import fbbp_mcp_server.server as mcp_server
settings = mcp_server._resolve_transport_security("127.0.0.1")
print(json.dumps({
    "enabled": settings.enable_dns_rebinding_protection,
    "hosts": settings.allowed_hosts,
}))
"""
        proc = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
            check=False,
        )
        self.assertEqual(proc.returncode, 0, msg=proc.stderr)
        payload = json.loads(proc.stdout.strip())
        self.assertTrue(payload["enabled"])
        self.assertIn("127.0.0.1:*", payload["hosts"])

    def test_non_loopback_transport_security_disables_host_lock(self) -> None:
        script = """
from pathlib import Path
import json
import sys

repo_root = Path.cwd()
sys.path = [str(repo_root / ".venv" / "Lib" / "site-packages"), str(repo_root / "src")] + list(sys.path)
import fbbp_mcp_server.server as mcp_server
settings = mcp_server._resolve_transport_security("0.0.0.0")
print(json.dumps({
    "enabled": settings.enable_dns_rebinding_protection,
    "hosts": settings.allowed_hosts,
}))
"""
        proc = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
            check=False,
        )
        self.assertEqual(proc.returncode, 0, msg=proc.stderr)
        payload = json.loads(proc.stdout.strip())
        self.assertFalse(payload["enabled"])
        self.assertEqual(payload["hosts"], [])


if __name__ == "__main__":
    unittest.main()
