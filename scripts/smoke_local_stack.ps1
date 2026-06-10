param(
  [string]$PgHost = "localhost",
  [int]$PgPort = 5432,
  [string]$PgDatabase = "ragkb",
  [string]$PgUser = "ragkb",
  [string]$PgPassword = "ragkb",
  [string]$PgTable = "rag_documents_bge_m3",
  [string]$DatasetVersion = "fbbp_private_v2026_04",
  [string]$RuntimeProfile = "local_formal",
  [string]$Query = "VEGF_CKP9.63",
  [string[]]$Filters = @(),
  [int]$TopK = 5,
  [switch]$ResolveTopChunk
)

$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$workspaceRoot = Split-Path -Parent $repoRoot
$ragkbSrc = Join-Path $workspaceRoot "llm-rag-knowledge-base\src"
$filtersJson = ConvertTo-Json $Filters -Compress

$env:PGHOST = $PgHost
$env:PGPORT = "$PgPort"
$env:PGDATABASE = $PgDatabase
$env:PGUSER = $PgUser
$env:PGPASSWORD = $PgPassword
$env:PGTABLE = $PgTable
$env:PGCONNECT_TIMEOUT = "5"
$env:PYTHONNOUSERSITE = "1"
$env:FBBP_FORMAL_DATASET_VERSION = $DatasetVersion
$env:FBBP_FORMAL_RUNTIME_PROFILE = $RuntimeProfile
$env:FBTP_FORMAL_DATASET_VERSION = $DatasetVersion
$env:FBTP_FORMAL_RUNTIME_PROFILE = $RuntimeProfile

@"
from pathlib import Path
import json
import sys

repo = Path(r"$repoRoot")
ragkb_src = Path(r"$ragkbSrc")
sys.path = [str(repo / "src"), str(ragkb_src), str(repo / ".venv" / "Lib" / "site-packages")] + list(sys.path)

from fbbp_mcp_server import service

filters = json.loads(r'''$filtersJson''')
payload = {}
payload["server_status"] = service.server_status()
payload["health_status"] = service.health_status()
payload["list_sources"] = service.list_available_sources(limit=10)
payload["search"] = service.search_knowledge(
    r"$Query",
    top_k=$TopK,
    filters=filters,
    include_answer=True,
    include_evidence=True,
    answer_mode="extractive",
)
payload["source_summary"] = None
payload["chunk"] = None

top_source = None
search_rows = (((payload["search"] or {}).get("result") or {}).get("results") or [])
if search_rows:
    first = search_rows[0]
    top_source = first.get("source")
    if $($ResolveTopChunk.IsPresent) and first.get("source") and first.get("chunk_id"):
        payload["chunk"] = service.get_document_chunk_by_id(first["source"], first["chunk_id"])

if (not top_source) and ((payload["list_sources"] or {}).get("result") or {}).get("sources"):
    top_source = payload["list_sources"]["result"]["sources"][0].get("source")

if top_source:
    payload["source_summary"] = service.get_source_summary(top_source, limit=5)

search_provenance = payload["search"].get("provenance") or {}
payload["formal_checks"] = {
    "contract_version": payload["search"].get("contract_version"),
    "dataset_version": search_provenance.get("dataset_version"),
    "runtime_profile": search_provenance.get("runtime_profile"),
    "db_identity": search_provenance.get("db_identity"),
    "build_id": search_provenance.get("build_id"),
    "source_registry_version": search_provenance.get("source_registry_version"),
    "result_count": (((payload["search"] or {}).get("result") or {}).get("result_count") or 0),
}

print(json.dumps(payload, ensure_ascii=False, indent=2))
"@ | python -
