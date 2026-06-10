param(
  [string]$TargetHost = "127.0.0.1",
  [int]$Port = 5434,
  [string]$User = "ragkb",
  [string]$Database = "ragkb"
)

$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$workspaceRoot = Split-Path -Parent $repoRoot
$binRoot = Join-Path $workspaceRoot ".conda_pg\Library\bin"
$psql = Join-Path $binRoot "psql.exe"
$createdb = Join-Path $binRoot "createdb.exe"

if (-not (Test-Path $psql)) {
  throw "Missing psql.exe at $psql"
}
if (-not (Test-Path $createdb)) {
  throw "Missing createdb.exe at $createdb"
}

$env:PATH = "$binRoot;$env:PATH"
$ready = $false
for ($i = 0; $i -lt 60; $i++) {
  & $psql -h $TargetHost -p $Port -U $User -d postgres -tAc "SELECT 1" 1>$null 2>$null
  if ($LASTEXITCODE -eq 0) {
    $ready = $true
    break
  }
  Start-Sleep -Seconds 2
}

if (-not $ready) {
  throw "PostgreSQL at $TargetHost`:$Port did not become ready in time."
}

$exists = (& $psql -h $TargetHost -p $Port -U $User -d postgres -tAc "SELECT 1 FROM pg_database WHERE datname='$Database';").Trim()
if ($exists -ne "1") {
  & $createdb -h $TargetHost -p $Port -U $User $Database
}

& $psql -h $TargetHost -p $Port -U $User -d $Database -c "CREATE EXTENSION IF NOT EXISTS vector;"

Write-Host "Fresh PostgreSQL database is ready:"
Write-Host "  host: $TargetHost"
Write-Host "  port: $Port"
Write-Host "  db:   $Database"
