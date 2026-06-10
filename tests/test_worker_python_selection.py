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


class WorkerPythonSelectionTests(unittest.TestCase):
    def test_worker_python_prefers_repo_local_venv(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir)
            local_python = repo_root / ".venv" / "Scripts" / "python.exe"
            local_python.parent.mkdir(parents=True)
            local_python.write_text("", encoding="utf-8")

            with mock.patch.object(service, "_python_executable_usable", return_value=True):
                chosen = service._worker_python_executable(repo_root=repo_root, fallback_python="python")

        self.assertEqual(chosen, str(local_python))

    def test_worker_python_prefers_repo_local_venv_over_runtime_venv(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir) / "repo"
            local_python = repo_root / ".venv" / "Scripts" / "python.exe"
            runtime_python = repo_root.parent / "_runtime_venv" / "Scripts" / "python.exe"
            local_python.parent.mkdir(parents=True)
            runtime_python.parent.mkdir(parents=True)
            local_python.write_text("", encoding="utf-8")
            runtime_python.write_text("", encoding="utf-8")

            with mock.patch.object(service, "_python_executable_usable", return_value=True):
                chosen = service._worker_python_executable(repo_root=repo_root, fallback_python="python")

        self.assertEqual(chosen, str(local_python))

    def test_run_db_worker_uses_selected_worker_python(self) -> None:
        with (
            mock.patch.object(service, "_run_db_worker_direct", side_effect=RuntimeError("direct path unavailable")),
            mock.patch.object(service, "_worker_python_executable", return_value="<local_path_removed>"),
            mock.patch.object(service.subprocess, "run") as mocked_run,
        ):
            mocked_run.return_value = mock.Mock(
                stdout='{"ok": true, "result": {"status": "ok"}}',
                stderr="",
                returncode=0,
            )
            result = service._run_db_worker("server_status")

        self.assertEqual(result, {"status": "ok"})
        self.assertEqual(mocked_run.call_args[0][0][0], "<local_path_removed>")

    def test_broken_local_python_falls_back_to_system_python(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir)
            local_python = repo_root / ".venv" / "Scripts" / "python.exe"
            local_python.parent.mkdir(parents=True)
            local_python.write_text("", encoding="utf-8")

            with mock.patch.object(service, "_python_executable_usable", return_value=False):
                chosen = service._worker_python_executable(repo_root=repo_root, fallback_python="python")

        self.assertEqual(chosen, "python")

    def test_run_db_worker_falls_back_to_subprocess_when_direct_worker_fails(self) -> None:
        with (
            mock.patch.object(service, "_run_db_worker_direct", side_effect=RuntimeError("connection timeout expired")),
            mock.patch.object(service, "_run_db_worker_subprocess", return_value={"status": "ok"}) as subprocess_worker,
        ):
            result = service._run_db_worker("server_status")

        subprocess_worker.assert_called_once_with("server_status", None)
        self.assertEqual(result, {"status": "ok"})

    def test_child_pythonpath_prefers_repo_sources_without_runtime_site_packages(self) -> None:
        rendered = service._child_pythonpath().split(service.os.pathsep)

        self.assertIn(str((service._repo_src_path().parent.parent / "llm-rag-knowledge-base" / "src")), rendered)
        self.assertEqual(rendered[0], str(service._repo_src_path()))
        self.assertTrue(all("_runtime_venv" not in entry for entry in rendered))


if __name__ == "__main__":
    unittest.main()
