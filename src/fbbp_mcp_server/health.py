from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from fbbp_mcp_server.bootstrap import describe_bootstrap_environment
from fbbp_mcp_server.runtime_env import detect_runtime_mode, runtime_env_path


def build_health_snapshot(
    *,
    repo_root: Path,
    db_probe: Callable[[], dict[str, Any]] | None = None,
    public_probe: Callable[[], dict[str, Any]] | None = None,
    ragkb_status: str = "unknown",
    formal_runtime: dict[str, Any] | None = None,
) -> dict[str, Any]:
    bootstrap = describe_bootstrap_environment(repo_root=repo_root)
    database = db_probe() if db_probe is not None else {"ok": False, "status": "not_checked"}
    public_lookups = public_probe() if public_probe is not None else {}
    formal_runtime = formal_runtime or {}

    return {
        "runtime": {
            "mode": detect_runtime_mode(repo_root),
            "env_path": str(runtime_env_path(repo_root)),
            "ragkb_status": ragkb_status,
            "candidate_site_packages": bootstrap["candidate_site_packages"],
            "selected_site_package": bootstrap["selected_site_package"],
            "dataset_version": formal_runtime.get("dataset_version", "unknown"),
            "runtime_profile": formal_runtime.get("runtime_profile", "unknown"),
            "formal_db_mode": formal_runtime.get("formal_db_mode", "unknown"),
            "db_identity": formal_runtime.get("db_identity", "unknown"),
            "build_id": formal_runtime.get("build_id", "unknown"),
            "source_registry_version": formal_runtime.get("source_registry_version", "unknown"),
            "source_registry_count": formal_runtime.get("source_registry_count", 0),
        },
        "database": database,
        "public_lookups": public_lookups,
    }
