param(
  [string]$ListenHost = "127.0.0.1",
  [int]$Port = 8000,
  [string]$PgHost = "127.0.0.1",
  [int]$PgPort = 5434,
  [string]$PgDatabase = "ragkb",
  [string]$PgUser = "ragkb",
  [string]$PgPassword = "ragkb",
  [string]$PgTable = "rag_documents_bge_m3",
  [string]$DatasetVersion = "",
  [string]$RuntimeProfile = ""
)

$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$env:PGHOST = $PgHost
$env:PGPORT = "$PgPort"
$env:PGDATABASE = $PgDatabase
$env:PGUSER = $PgUser
$env:PGPASSWORD = $PgPassword
$env:PGTABLE = $PgTable
$env:PYTHONNOUSERSITE = "1"

$resolvedDatasetVersion = if ($DatasetVersion) {
  $DatasetVersion
} elseif ($env:FBBP_FORMAL_DATASET_VERSION) {
  $env:FBBP_FORMAL_DATASET_VERSION
} elseif ($env:FBTP_FORMAL_DATASET_VERSION) {
  $env:FBTP_FORMAL_DATASET_VERSION
} else {
  "fbbp_private_v2026_04"
}

$resolvedRuntimeProfile = if ($RuntimeProfile) {
  $RuntimeProfile
} elseif ($env:FBBP_FORMAL_RUNTIME_PROFILE) {
  $env:FBBP_FORMAL_RUNTIME_PROFILE
} elseif ($env:FBTP_FORMAL_RUNTIME_PROFILE) {
  $env:FBTP_FORMAL_RUNTIME_PROFILE
} else {
  "local_formal"
}

$env:FBBP_FORMAL_DATASET_VERSION = $resolvedDatasetVersion
$env:FBTP_FORMAL_DATASET_VERSION = $resolvedDatasetVersion
$env:FBBP_FORMAL_RUNTIME_PROFILE = $resolvedRuntimeProfile
$env:FBTP_FORMAL_RUNTIME_PROFILE = $resolvedRuntimeProfile

Write-Host "Starting MCP HTTP server"
Write-Host "  MCP: http://$ListenHost`:$Port/mcp"
Write-Host "  PG : $PgHost`:$PgPort / $PgDatabase / $PgTable"
Write-Host "  Formal dataset : $resolvedDatasetVersion"
Write-Host "  Runtime profile: $resolvedRuntimeProfile"

$pythonExe = Join-Path $repoRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $pythonExe)) {
  $pythonExe = "python"
}

& $pythonExe -S (Join-Path $repoRoot "server.py") --transport streamable-http --host $ListenHost --port $Port
