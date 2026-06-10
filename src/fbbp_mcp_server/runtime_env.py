from __future__ import annotations

from collections import OrderedDict
import os
from pathlib import Path


DEFAULT_ENV_VALUES = OrderedDict(
    [
        ("PGHOST", "localhost"),
        ("PGPORT", "5432"),
        ("PGDATABASE", "ragkb"),
        ("PGUSER", "ragkb"),
        ("PGPASSWORD", "ragkb"),
        ("PGTABLE", "rag_documents_bge_m3"),
        ("OPENAI_API_KEY", ""),
        ("BASE_URL", "https://llmapi.paratera.com"),
        ("OPENAI_BASE_URL", "https://llmapi.paratera.com"),
        ("OPENAI_API_BASE", "https://llmapi.paratera.com"),
        ("LLM_PROVIDER", "openai"),
        ("LLM_MODEL", "DeepSeek-V3.2"),
        ("ANSWER_MODE", "openai"),
        ("MIN_SCORE", "0.15"),
        ("HF_HUB_OFFLINE", "1"),
        ("TRANSFORMERS_OFFLINE", "1"),
        ("EMBEDDING_PROVIDER", "bge_m3"),
        ("EMBEDDING_MODEL", r"..\models\bge-m3-local"),
        ("EMBEDDING_DIM", "1024"),
        ("BGE_M3_USE_FP16", "auto"),
        ("BGE_M3_BATCH_SIZE", "8"),
        ("BGE_M3_MAX_LENGTH", "8192"),
        ("RAGKB_SRC_PATH", ""),
        ("FBBP_MCP_DEFAULT_TOP_K", "5"),
        ("FBBP_MCP_DEFAULT_ANSWER_MODE", "openai"),
        ("FBBP_MCP_RUNTIME_MODE", "research-dev"),
        ("FBTP_MCP_DEFAULT_TOP_K", "5"),
        ("FBTP_MCP_DEFAULT_ANSWER_MODE", "openai"),
        ("FBTP_MCP_RUNTIME_MODE", "research-dev"),
    ]
)


def _parse_env_file(path: Path) -> OrderedDict[str, str]:
    values: OrderedDict[str, str] = OrderedDict()
    if not path.exists():
        return values

    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def build_runtime_env_values(repo_root: Path) -> OrderedDict[str, str]:
    values = OrderedDict(DEFAULT_ENV_VALUES)

    ragkb_env = repo_root.parent / "llm-rag-knowledge-base" / ".env"
    for key, value in _parse_env_file(ragkb_env).items():
        if key in values and value:
            values[key] = value

    for key in values:
        env_value = os.getenv(key)
        if env_value:
            values[key] = env_value

    return values


def render_runtime_env(values: OrderedDict[str, str] | None = None) -> str:
    env_values = values or DEFAULT_ENV_VALUES
    return "\n".join(f"{key}={value}" for key, value in env_values.items()) + "\n"


def runtime_env_path(repo_root: Path) -> Path:
    return repo_root / ".env"


def detect_runtime_mode(repo_root: Path) -> str:
    values = build_runtime_env_values(repo_root)
    return (
        values.get("FBBP_MCP_RUNTIME_MODE")
        or values.get("FBTP_MCP_RUNTIME_MODE")
        or "research-dev"
    )


def ensure_runtime_env_file(repo_root: Path) -> Path:
    env_path = runtime_env_path(repo_root)
    if env_path.exists():
        return env_path
    env_path.write_text(render_runtime_env(build_runtime_env_values(repo_root)), encoding="utf-8")
    return env_path
