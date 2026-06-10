from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"


def _linux_site_packages(repo_root: Path) -> list[Path]:
    candidates = sorted((repo_root / ".venv_wsl" / "lib").glob("python*/site-packages"))
    legacy = repo_root / ".venv_wsl" / "Lib" / "site-packages"
    if legacy.exists():
        candidates.append(legacy)
    return candidates


def _runtime_site_packages(repo_root: Path) -> list[Path]:
    runtime_root = repo_root.parent / "_runtime_venv"
    candidates = [
        runtime_root / "Lib" / "site-packages",
        *sorted((runtime_root / "lib").glob("python*/site-packages")),
    ]
    return [path for path in candidates if path.exists()]


def _windows_site_support_dirs(windows_site: Path) -> list[Path]:
    extras = [
        windows_site / "pywin32_system32",
        windows_site / "win32",
        windows_site / "win32" / "lib",
        windows_site / "Pythonwin",
    ]
    return [path for path in extras if path.exists()]


def _candidate_site_packages(repo_root: Path = ROOT, platform_name: str | None = None) -> list[Path]:
    platform_name = platform_name or sys.platform
    windows_site = repo_root / ".venv" / "Lib" / "site-packages"
    linux_sites = _linux_site_packages(repo_root)

    runtime_sites = _runtime_site_packages(repo_root)
    ordered = [windows_site, *_windows_site_support_dirs(windows_site), *runtime_sites, *linux_sites]
    if platform_name.startswith("linux"):
        ordered = [*linux_sites, *runtime_sites, windows_site, *_windows_site_support_dirs(windows_site)]

    return list(dict.fromkeys(ordered))


def _bootstrap_paths(
    sys_path: list[str] | None = None,
    src_root: Path = SRC,
    repo_root: Path = ROOT,
    platform_name: str | None = None,
) -> None:
    sys_path = sys_path if sys_path is not None else sys.path

    planned = [str(src_root)]
    planned.extend(
        str(candidate)
        for candidate in _candidate_site_packages(repo_root, platform_name=platform_name)
        if candidate.exists()
    )

    for entry in reversed(planned):
        if entry not in sys_path:
            sys_path.insert(0, entry)


_bootstrap_paths()


def main() -> None:
    from fbbp_mcp_server.server import main as run_main

    run_main()


if __name__ == "__main__":
    main()
