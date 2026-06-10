from __future__ import annotations

import os
import sys
from functools import lru_cache
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


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


def _candidate_site_packages_for_platform(repo_root: Path, platform_name: str | None = None) -> list[Path]:
    platform_name = platform_name or sys.platform
    windows_site = repo_root / ".venv" / "Lib" / "site-packages"
    linux_sites = _linux_site_packages(repo_root)

    runtime_sites = _runtime_site_packages(repo_root)
    ordered = [windows_site, *_windows_site_support_dirs(windows_site), *runtime_sites, *linux_sites]
    if platform_name.startswith("linux"):
        ordered = [*linux_sites, *runtime_sites, windows_site, *_windows_site_support_dirs(windows_site)]

    # Keep order stable while removing duplicates.
    return list(dict.fromkeys(ordered))


def _candidate_site_packages() -> list[Path]:
    return _candidate_site_packages_for_platform(_repo_root())


def _candidate_ragkb_paths() -> list[Path]:
    candidates: list[Path] = []
    env_path = os.getenv("RAGKB_SRC_PATH")
    if env_path:
        candidates.append(Path(env_path).expanduser())

    repo_root = _repo_root()
    candidates.append(repo_root.parent / "llm-rag-knowledge-base" / "src")
    return candidates


def describe_bootstrap_environment(
    repo_root: Path | None = None,
    platform_name: str | None = None,
) -> dict[str, object]:
    repo_root = repo_root or _repo_root()
    candidates = _candidate_site_packages_for_platform(repo_root, platform_name=platform_name)
    selected = next((str(path) for path in candidates if str(path) in sys.path), None)
    return {
        "repo_root": str(repo_root),
        "platform": platform_name or sys.platform,
        "candidate_site_packages": [str(path) for path in candidates],
        "selected_site_package": selected,
        "candidate_ragkb_paths": [str(path) for path in _candidate_ragkb_paths()],
    }


@lru_cache(maxsize=1)
def ensure_local_site_packages() -> str | None:
    existing_candidates = [candidate for candidate in _candidate_site_packages() if candidate.exists()]
    if not existing_candidates:
        return None

    for candidate in reversed(existing_candidates):
        rendered = str(candidate)
        if rendered in sys.path:
            sys.path.remove(rendered)
        sys.path.insert(0, rendered)

    return str(existing_candidates[0])


@lru_cache(maxsize=1)
def ensure_ragkb_importable() -> str:
    ensure_local_site_packages()
    try:
        import ragkb  # noqa: F401

        return "installed"
    except ModuleNotFoundError:
        for candidate in _candidate_ragkb_paths():
            if candidate.exists() and str(candidate) not in sys.path:
                sys.path.insert(0, str(candidate))
                try:
                    import ragkb  # noqa: F401

                    return str(candidate)
                except ModuleNotFoundError:
                    continue

    raise RuntimeError(
        "Could not import ragkb. Install it with `pip install -e ../llm-rag-knowledge-base` "
        "or set RAGKB_SRC_PATH to the sibling `src` directory."
    )
