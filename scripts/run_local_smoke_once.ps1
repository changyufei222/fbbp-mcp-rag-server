param(
  [string]$TargetHost = "localhost",
  [int]$PgPort = 5432,
  [string]$PgDatabase = "ragkb",
  [string]$PgUser = "ragkb",
  [string]$PgPassword = "ragkb",
  [string]$PgTable = "rag_documents_bge_m3",
  [string]$DatasetVersion = "fbbp_private_v2026_04",
  [string]$RuntimeProfile = "local_formal",
  [string]$Query = "VEGF_CKP9.63",
  [switch]$PlanOnly
)

$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$jsonHelper = Join-Path $repoRoot "scripts\common_json_output.ps1"
. $jsonHelper
$ensurePgScript = Join-Path $repoRoot "scripts\ensure_local_formal_pg_ready.ps1"
$smokeScript = Join-Path $repoRoot "scripts\smoke_local_stack.ps1"
$rebuildScript = Join-Path $repoRoot "scripts\rebuild_fbbp_formal_db.ps1"

$plan = [ordered]@{
  mode = "reuse_prepared_formal_db"
  dataset_version = $DatasetVersion
  runtime_profile = $RuntimeProfile
  pg_host = $TargetHost
  pg_port = $PgPort
  pg_table = $PgTable
  query = $Query
  ensure_pg_command = "powershell -ExecutionPolicy Bypass -File `"$ensurePgScript`" -ExpectedHost $TargetHost -ExpectedPort $PgPort"
  smoke_script = $smokeScript
  rebuild_command = "powershell -ExecutionPolicy Bypass -File `"$rebuildScript`""
}

if ($PlanOnly) {
  $plan | ConvertTo-Json -Depth 4
  exit 0
}

$ensurePgRaw = & $ensurePgScript `
  -ExpectedHost $TargetHost `
  -ExpectedPort $PgPort `
  -PgDatabase $PgDatabase `
  -PgUser $PgUser `
  -PgPassword $PgPassword

$smokeRaw = & $smokeScript `
  -PgHost $TargetHost `
  -PgPort $PgPort `
  -PgDatabase $PgDatabase `
  -PgUser $PgUser `
  -PgPassword $PgPassword `
  -PgTable $PgTable `
  -DatasetVersion $DatasetVersion `
  -RuntimeProfile $RuntimeProfile `
  -Query $Query `
  -ResolveTopChunk

$payload = [ordered]@{
  ensure_pg = ConvertFrom-JsonTailPayload -RawText ($ensurePgRaw | Out-String)
  smoke = ConvertFrom-JsonTailPayload -RawText ($smokeRaw | Out-String)
}

$payload | ConvertTo-Json -Depth 12
