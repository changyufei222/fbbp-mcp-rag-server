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


from fbbp_mcp_server import bootstrap


class BootstrapPathTests(unittest.TestCase):
    def test_linux_prefers_wsl_site_packages_layout(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir) / "repo"
            windows_site = repo_root / ".venv" / "Lib" / "site-packages"
            linux_site = repo_root / ".venv_wsl" / "lib" / "python3.12" / "site-packages"
            runtime_site = repo_root.parent / "_runtime_venv" / "Lib" / "site-packages"
            windows_site.mkdir(parents=True)
            linux_site.mkdir(parents=True)
            runtime_site.mkdir(parents=True)

            candidates = bootstrap._candidate_site_packages_for_platform(repo_root, platform_name="linux")

        self.assertGreaterEqual(len(candidates), 3)
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

            candidates = bootstrap._candidate_site_packages_for_platform(repo_root, platform_name="win32")

        self.assertGreaterEqual(len(candidates), 3)
        self.assertEqual(candidates[0], windows_site)
        self.assertEqual(candidates[1], runtime_site)
        self.assertEqual(candidates[2], linux_site)

    def test_existing_linux_site_packages_are_not_overridden(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir) / "repo"
            windows_site = repo_root / ".venv" / "Lib" / "site-packages"
            linux_site = repo_root / ".venv_wsl" / "lib" / "python3.12" / "site-packages"
            windows_site.mkdir(parents=True)
            linux_site.mkdir(parents=True)

            bootstrap.ensure_local_site_packages.cache_clear()

            with mock.patch.object(bootstrap, "_repo_root", return_value=repo_root):
                with mock.patch.object(sys, "platform", "linux"):
                    with mock.patch.object(sys, "path", [str(linux_site)]):
                        selected = bootstrap.ensure_local_site_packages()
                        resolved_path = list(sys.path)

        self.assertEqual(selected, str(linux_site))
        self.assertEqual(resolved_path[0], str(linux_site))

    def test_windows_candidate_paths_include_pywin32_support_dirs(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir) / "repo"
            windows_site = repo_root / ".venv" / "Lib" / "site-packages"
            pywin32_system32 = windows_site / "pywin32_system32"
            win32_dir = windows_site / "win32"
            win32_lib = win32_dir / "lib"
            windows_site.mkdir(parents=True)
            pywin32_system32.mkdir(parents=True)
            win32_lib.mkdir(parents=True)

            candidates = bootstrap._candidate_site_packages_for_platform(repo_root, platform_name="win32")

        rendered = [str(path) for path in candidates]
        self.assertIn(str(pywin32_system32), rendered)
        self.assertIn(str(win32_dir), rendered)
        self.assertIn(str(win32_lib), rendered)

    def test_windows_does_not_keep_linux_site_packages_as_selected_runtime(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir) / "repo"
            windows_site = repo_root / ".venv" / "Lib" / "site-packages"
            linux_site = repo_root / ".venv_wsl" / "lib" / "python3.12" / "site-packages"
            runtime_site = repo_root.parent / "_runtime_venv" / "Lib" / "site-packages"
            windows_site.mkdir(parents=True)
            linux_site.mkdir(parents=True)
            runtime_site.mkdir(parents=True, exist_ok=True)

            bootstrap.ensure_local_site_packages.cache_clear()

            with mock.patch.object(bootstrap, "_repo_root", return_value=repo_root):
                with mock.patch.object(sys, "platform", "win32"):
                    with mock.patch.object(sys, "path", [str(linux_site)]):
                        selected = bootstrap.ensure_local_site_packages()
                        resolved_path = list(sys.path)

        self.assertEqual(selected, str(windows_site))
        self.assertEqual(resolved_path[0], str(windows_site))
        self.assertIn(str(linux_site), resolved_path)


if __name__ == "__main__":
    unittest.main()
