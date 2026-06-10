from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import sys


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_ROOT = REPO_ROOT / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

import run_live_client_acceptance
from final_release_check import (
    LIVE_ACCEPTANCE_JSON,
    LIVE_ACCEPTANCE_MD,
    check_client_matrix,
    check_contract_docs,
    check_live_client_acceptance,
    check_ops_docs,
    run_final_release_check,
    write_summary,
)


class FinalReleaseCheckTests(unittest.TestCase):
    def test_client_matrix_configs_exist(self) -> None:
        result = check_client_matrix()
        self.assertTrue(result["ok"])

    def test_contract_docs_cover_core_tools(self) -> None:
        result = check_contract_docs()
        self.assertTrue(result["ok"])

    def test_ops_docs_cover_client_and_service_story(self) -> None:
        result = check_ops_docs()
        self.assertTrue(result["ok"])

    def test_live_client_acceptance_artifacts_exist(self) -> None:
        if not LIVE_ACCEPTANCE_JSON.exists():
            LIVE_ACCEPTANCE_JSON.parent.mkdir(parents=True, exist_ok=True)
            LIVE_ACCEPTANCE_JSON.write_text(
                json.dumps(
                    {
                        "clients": [
                            {"label": "Codex", "ok": True},
                            {"label": "Claude Code", "ok": True},
                            {"label": "Cursor", "ok": True},
                            {"label": "DeerFlow", "ok": True},
                        ]
                    }
                ),
                encoding="utf-8",
            )
        if not LIVE_ACCEPTANCE_MD.exists():
            LIVE_ACCEPTANCE_MD.write_text("# Live acceptance\n", encoding="utf-8")
        result = check_live_client_acceptance()
        self.assertTrue(result["ok"])

    def test_write_summary_outputs_json_and_markdown(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            outputs = write_summary([{"name": "x", "ok": True, "details": {}}], Path(temp_dir))
            payload = json.loads(Path(outputs["summary_json"]).read_text(encoding="utf-8"))
            md_exists = Path(outputs["summary_md"]).exists()

        self.assertTrue(payload["ok"])
        self.assertTrue(md_exists)

    def test_run_final_release_check_can_be_mocked(self) -> None:
        ok_check = {"name": "ok", "ok": True, "details": {}}
        with (
            mock.patch("final_release_check.check_tool_registration", return_value=ok_check),
            mock.patch("final_release_check.check_response_contract", return_value=ok_check),
            mock.patch("final_release_check.check_client_matrix", return_value=ok_check),
            mock.patch("final_release_check.check_contract_docs", return_value=ok_check),
            mock.patch("final_release_check.check_ops_docs", return_value=ok_check),
            mock.patch("final_release_check.check_live_client_acceptance", return_value=ok_check),
            mock.patch("final_release_check.check_deployment_assets", return_value=ok_check),
            mock.patch("final_release_check.check_public_naming", return_value=ok_check),
            tempfile.TemporaryDirectory() as temp_dir,
            mock.patch("final_release_check.OUTPUT_ROOT", Path(temp_dir)),
        ):
            result = run_final_release_check()

        self.assertTrue(result["ok"])

    def test_live_acceptance_prefers_repo_local_python(self) -> None:
        chosen = run_live_client_acceptance._server_python_executable()

        self.assertEqual(chosen, str(REPO_ROOT / ".venv" / "Scripts" / "python.exe"))

    def test_live_acceptance_timeout_reports_server_stderr_path(self) -> None:
        fake_process = mock.Mock()
        fake_process.poll.return_value = 1
        fake_process.wait.return_value = 1

        with tempfile.TemporaryDirectory() as temp_dir:
            log_dir = Path(temp_dir)
            stderr_path = log_dir / "http_mcp_live_acceptance.err.log"
            stderr_path.write_text("ModuleNotFoundError: fake dependency\n", encoding="utf-8")
            stdout_path = log_dir / "http_mcp_live_acceptance.out.log"
            stdout_path.write_text("", encoding="utf-8")

            with (
                mock.patch.object(run_live_client_acceptance, "_http_health_ok", return_value=False),
                mock.patch.object(run_live_client_acceptance, "_live_acceptance_log_paths", return_value=(stdout_path, stderr_path)),
                mock.patch.object(run_live_client_acceptance.subprocess, "Popen", return_value=fake_process),
                mock.patch.object(run_live_client_acceptance.time, "sleep", return_value=None),
            ):
                with self.assertRaises(RuntimeError) as ctx:
                    run_live_client_acceptance._start_http_server()

        self.assertIn(str(stderr_path), str(ctx.exception))
        self.assertIn("exited early", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
