from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


def current_dataset_version() -> str:
    return os.getenv("FBBP_FORMAL_DATASET_VERSION") or os.getenv("FBTP_FORMAL_DATASET_VERSION", "unknown")


def current_runtime_profile() -> str:
    return os.getenv("FBBP_FORMAL_RUNTIME_PROFILE") or os.getenv("FBTP_FORMAL_RUNTIME_PROFILE", "unknown")


def load_dataset_descriptor(repo_root: Path, dataset_version: str) -> dict[str, Any]:
    descriptor_path = repo_root / "configs" / "datasets" / f"{dataset_version}.json"
    if not descriptor_path.exists():
        return {}
    return json.loads(descriptor_path.read_text(encoding="utf-8"))


def source_registry(descriptor: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    registry = (descriptor or {}).get("source_registry") or {}
    return registry if isinstance(registry, dict) else {}


def get_source_registry_entry(descriptor: dict[str, Any] | None, source: str | None) -> dict[str, Any]:
    if not source:
        return {}
    entry = source_registry(descriptor).get(str(source).strip()) or {}
    return entry if isinstance(entry, dict) else {}


def formal_runtime_snapshot(repo_root: Path) -> dict[str, Any]:
    dataset_version = current_dataset_version()
    runtime_profile = current_runtime_profile()
    dataset_descriptor = load_dataset_descriptor(repo_root, dataset_version) if dataset_version != "unknown" else {}
    return {
        "dataset_version": dataset_version,
        "runtime_profile": runtime_profile,
        "dataset_descriptor": dataset_descriptor,
        "formal_db_mode": dataset_descriptor.get("formal_db_mode", "unknown"),
        "db_identity": dataset_descriptor.get("db_identity", "unknown"),
        "build_id": dataset_descriptor.get("build_id", "unknown"),
        "source_registry_version": dataset_descriptor.get("source_registry_version", "unknown"),
        "source_registry_count": len(source_registry(dataset_descriptor)),
        "statistics": dataset_descriptor.get("statistics") or {},
        "rebuild": dataset_descriptor.get("rebuild") or {},
    }
