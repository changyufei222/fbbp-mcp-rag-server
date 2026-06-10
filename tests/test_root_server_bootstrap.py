from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SERVER_PATH = REPO_ROOT / "server.py"

spec = importlib.util.spec_from_file_location("fbtp_root_server", SERVER_PATH)
root_server = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(root_server)


class RootServerBootstrapTests(unittest.TestCase):
    def test_linux_prefers_wsl_site_packages_layout(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir) / "repo"
            windows_site = repo_root / ".venv" / "Lib" / "site-packages"
            linux_site = repo_root / ".venv_wsl" / "lib" / "python3.12" / "site-packages"
            runtime_site = repo_root.parent / "_runtime_venv" / "Lib" / "site-packages"
            windows_site.mkdir(parents=True)
            linux_site.mkdir(parents=True)
            runtime_site.mkdir(parents=True)

            candidates = root_server._candidate_site_packages(repo_root, platform_name="linux")

        self.assertEqual(candidates[0], linux_site)
        self.assertEqual(candidates[1], runtime_site)
        self.assertEqual(candidates[2], windows_site)

    def test_windows_prefers_windows_site_packages_layout(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir) / "repo"
            windows_site = repo_root / ".venv" / "Lib" / "site-packages"
            linux_site = repo_root / ".venv_wsl" / "lib" / "python3.12" / "site-packages"
            runtime_site = repo_root.parent / "_runtime_venv" / "Lib" / "site-packages"
            windows_site.mkdir(parents=True)
            linux_site.mkdir(parents=True)
            runtime_site.mkdir(parents=True, exist_ok=True)

            candidates = root_server._candidate_site_packages(repo_root, platform_name="win32")

        self.assertEqual(candidates[0], windows_site)
        self.assertEqual(candidates[1], runtime_site)

    def test_bootstrap_paths_keeps_linux_site_packages_ahead_of_windows(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir) / "repo"
            windows_site = repo_root / ".venv" / "Lib" / "site-packages"
            linux_site = repo_root / ".venv_wsl" / "lib" / "python3.12" / "site-packages"
            runtime_site = repo_root.parent / "_runtime_venv" / "Lib" / "site-packages"
            src_root = repo_root / "src"
            windows_site.mkdir(parents=True)
            linux_site.mkdir(parents=True)
            runtime_site.mkdir(parents=True)
            src_root.mkdir(parents=True)
            sys_path: list[str] = []

            root_server._bootstrap_paths(
                sys_path=sys_path,
                src_root=src_root,
                repo_root=repo_root,
                platform_name="linux",
            )

        self.assertEqual(sys_path[0], str(src_root))
        self.assertEqual(sys_path[1], str(linux_site))
        self.assertEqual(sys_path[2], str(runtime_site))
        self.assertEqual(sys_path[3], str(windows_site))

    def test_candidate_site_packages_include_pywin32_support_dirs(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir) / "repo"
            windows_site = repo_root / ".venv" / "Lib" / "site-packages"
            pywin32_system32 = windows_site / "pywin32_system32"
            win32_dir = windows_site / "win32"
            win32_lib = win32_dir / "lib"
            windows_site.mkdir(parents=True)
            pywin32_system32.mkdir(parents=True)
            win32_lib.mkdir(parents=True)

            candidates = root_server._candidate_site_packages(repo_root, platform_name="win32")

        rendered = [str(path) for path in candidates]
        self.assertIn(str(pywin32_system32), rendered)
        self.assertIn(str(win32_dir), rendered)
        self.assertIn(str(win32_lib), rendered)


if __name__ == "__main__":
    unittest.main()
