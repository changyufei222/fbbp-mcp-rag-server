param(
  [switch]$PreviewOnly
)

$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$descriptorPath = Join-Path $repoRoot "configs\datasets\fbbp_private_v2026_04.json"

@"
from pathlib import Path
import json
import sys

repo = Path(r"$repoRoot")
descriptor = json.loads(Path(r"$descriptorPath").read_text(encoding="utf-8"))
source_allowlist = ((descriptor.get("rebuild") or {}).get("source_allowlist") or [])

def _resolve_repo_path(raw_path: str) -> Path:
    candidate = Path(raw_path)
    return candidate if candidate.is_absolute() else (repo / candidate)

if $($PreviewOnly.IsPresent):
    print(
        json.dumps(
            {
                "dataset_version": descriptor.get("dataset_version"),
                "db_identity": descriptor.get("db_identity"),
                "source_allowlist": source_allowlist,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    raise SystemExit(0)

workspace_root = repo.parent
sys.path = [str(repo / "src"), str(workspace_root / "llm-rag-knowledge-base" / "src"), str(repo / ".venv" / "Lib" / "site-packages")] + list(sys.path)

from fbbp_mcp_server.bootstrap import ensure_local_site_packages, ensure_ragkb_importable

ensure_local_site_packages()
ensure_ragkb_importable()

from ragkb.config import Settings
from ragkb.ingest.pipeline import run_ingest
from ragkb.storage.pgvector_store import reset_table

settings = Settings()
reset_table(settings)

insertions = []
for input_path in source_allowlist:
    current = _resolve_repo_path(input_path)
    if not current.exists():
        raise FileNotFoundError(f"Rebuild source is missing: {current}")
    inserted = run_ingest(
        input_path=str(current),
        settings=settings,
        limit=None,
        chunk_size=800,
        chunk_overlap=120,
        batch_size=64,
    )
    insertions.append({"input_path": str(current), "inserted": inserted})

print(
    json.dumps(
        {
            "dataset_version": descriptor.get("dataset_version"),
            "db_identity": descriptor.get("db_identity"),
            "source_allowlist": source_allowlist,
            "insertions": insertions,
        },
        ensure_ascii=False,
        indent=2,
    )
)
"@ | python -
