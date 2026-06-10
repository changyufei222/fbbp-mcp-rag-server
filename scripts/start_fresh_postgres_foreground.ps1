param(
  [string]$DataDir = "",
  [int]$Port = 5434,
  [string]$PgBinRoot = ""
)

$ErrorActionPreference = "Stop"

function Test-AsciiPath {
  param([string]$Value)

  return $Value -notmatch "[^\u0000-\u007F]"
}

function Test-IsElevatedWindowsSession {
  $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
  $principal = [Security.Principal.WindowsPrincipal]::new($identity)
  return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Resolve-PgBinRoot {
  param(
    [string]$WorkspaceRoot,
    [string]$Override
  )

  $workspaceDrive = [System.IO.Path]::GetPathRoot($WorkspaceRoot)
  $asciiMirror = Join-Path $workspaceDrive "fbtp_pg_runtime\Library\bin"
  $workspaceDefault = Join-Path $WorkspaceRoot ".conda_pg\Library\bin"

  $candidates = @()
  foreach ($candidate in @($Override, $env:FBTP_PG_BIN_ROOT, $asciiMirror, $workspaceDefault)) {
    if ($candidate -and -not ($candidates -contains $candidate)) {
      $candidates += $candidate
    }
  }

  foreach ($candidate in $candidates) {
    if (Test-Path (Join-Path $candidate "postgres.exe")) {
      return $candidate
    }
  }

  throw "Could not resolve a PostgreSQL binary root. Tried: $($candidates -join ', ')"
}

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$workspaceRoot = Split-Path -Parent $repoRoot
$workspaceDrive = [System.IO.Path]::GetPathRoot($workspaceRoot)
$pgRoot = Join-Path $workspaceRoot ".local_pg_fresh"
$asciiPgRoot = Join-Path $workspaceDrive "fbtp_pg_fresh"
$resolvedBinRoot = Resolve-PgBinRoot -WorkspaceRoot $workspaceRoot -Override $PgBinRoot
if (-not $DataDir) {
  $workspaceDataDir = Join-Path $pgRoot "data"
  if (Test-AsciiPath $workspaceDataDir) {
    $DataDir = $workspaceDataDir
  } else {
    $DataDir = Join-Path $asciiPgRoot "data"
  }
}

$initdb = Join-Path $resolvedBinRoot "initdb.exe"
$postgres = Join-Path $resolvedBinRoot "postgres.exe"

if (-not (Test-Path $initdb)) {
  throw "Missing initdb.exe at $initdb"
}
if (-not (Test-Path $postgres)) {
  throw "Missing postgres.exe at $postgres"
}

if (-not (Test-AsciiPath $resolvedBinRoot)) {
  throw "Resolved PgBinRoot '$resolvedBinRoot' contains non-ASCII characters. Mirror PostgreSQL to an ASCII path such as '$workspaceDrive`fbtp_pg_runtime\Library\bin' and rerun with -PgBinRoot, or use scripts\run_local_smoke_once.ps1."
}

if (-not (Test-AsciiPath $DataDir)) {
  throw "Resolved DataDir '$DataDir' contains non-ASCII characters. Provide -DataDir to an ASCII path such as '$workspaceDrive`fbtp_pg_fresh\data'."
}

if (Test-IsElevatedWindowsSession) {
  throw "Windows postgres.exe cannot run in an elevated session. Open a non-admin PowerShell or use scripts\run_local_smoke_once.ps1 for automatic WSL fallback."
}

New-Item -ItemType Directory -Force -Path $DataDir | Out-Null

$env:PATH = "$resolvedBinRoot;$env:PATH"

$configPath = Join-Path $DataDir "postgresql.conf"
if (-not (Test-Path $configPath)) {
  & $initdb -D $DataDir -U ragkb -A trust -E UTF8 --no-locale
  if (-not (Test-Path $configPath)) {
    throw "initdb did not produce postgresql.conf in $DataDir"
  }
}

$pidFile = Join-Path $DataDir "postmaster.pid"
if (Test-Path $pidFile) {
  cmd /c del /f /q "$pidFile" | Out-Null
}

Write-Host "Starting fresh PostgreSQL in foreground"
Write-Host "  bin root: $resolvedBinRoot"
Write-Host "  data dir: $DataDir"
Write-Host "  port: $Port"
Write-Host "Keep this terminal open while using MCP."

& $postgres -D $DataDir -p $Port
