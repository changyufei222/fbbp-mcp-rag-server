param(
  [string]$ExpectedHost = "localhost",
  [int]$ExpectedPort = 5432,
  [string]$PgDatabase = "ragkb",
  [string]$PgUser = "ragkb",
  [string]$PgPassword = "ragkb"
)

$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$pythonExe = Join-Path $repoRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $pythonExe)) {
  $pythonExe = "python"
}

function Convert-ToWslPath {
  param([string]$Path)

  $resolved = (Resolve-Path $Path).Path
  if ($resolved -match '^(?<drive>[A-Za-z]):\\(?<rest>.*)$') {
    $drive = $Matches['drive'].ToLowerInvariant()
    $rest = ($Matches['rest'] -replace '\\', '/')
    return "/mnt/$drive/$rest"
  }

  throw "Could not convert path to WSL path: $resolved"
}

function Save-TextFile {
  param(
    [string]$Path,
    [string]$Content
  )

  $dir = Split-Path -Parent $Path
  if ($dir) {
    New-Item -ItemType Directory -Force -Path $dir | Out-Null
  }
  $utf8NoBom = New-Object System.Text.UTF8Encoding($false)
  [System.IO.File]::WriteAllText($Path, $Content, $utf8NoBom)
}

function Test-PostgresQueryReady {
  param(
    [string]$ProbeHost,
    [int]$Port,
    [string]$Database,
    [string]$User,
    [string]$Password,
    [int]$TimeoutSeconds = 5
  )

  $probeScript = @"
import json

try:
    import psycopg
except Exception:
    print(json.dumps({"ok": False, "error": "psycopg unavailable"}))
    raise SystemExit(0)

payload = {"ok": False}
try:
    with psycopg.connect(
        host=r"$ProbeHost",
        port=$Port,
        dbname=r"$Database",
        user=r"$User",
        password=r"$Password",
        connect_timeout=$TimeoutSeconds,
    ) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1")
            payload["ok"] = cur.fetchone()[0] == 1
except Exception as exc:
    payload["error"] = str(exc)

print(json.dumps(payload, ensure_ascii=False))
"@

  try {
    $raw = $probeScript | & $pythonExe -
    if ($LASTEXITCODE -ne 0) {
      return $false
    }
    $payload = $raw | ConvertFrom-Json
    return [bool]$payload.ok
  } catch {
    return $false
  }
}

function Remove-LocalPostgresPortProxy {
  param([int]$Port = 5432)

  foreach ($listenAddress in @("127.0.0.1", "0.0.0.0")) {
    try {
      netsh interface portproxy delete v4tov4 listenaddress=$listenAddress listenport=$Port | Out-Null
    } catch {
    }
  }
}

if (Test-PostgresQueryReady -ProbeHost $ExpectedHost -Port $ExpectedPort -Database $PgDatabase -User $PgUser -Password $PgPassword) {
  [ordered]@{
    ok = $true
    host = $ExpectedHost
    port = $ExpectedPort
    mode = "already_ready"
  } | ConvertTo-Json -Depth 4
  exit 0
}

Remove-LocalPostgresPortProxy -Port $ExpectedPort

$wslCommands = @'
set -euo pipefail
if ! command -v pg_ctlcluster >/dev/null 2>&1; then
  echo "PostgreSQL 16 is not installed in WSL."
  exit 1
fi
pg_ctlcluster 16 main start
if ! runuser -u postgres -- psql -tAc "SELECT 1 FROM pg_roles WHERE rolname='ragkb'" | grep -q 1; then
  runuser -u postgres -- psql -c "CREATE ROLE ragkb LOGIN PASSWORD 'ragkb';"
fi
if ! runuser -u postgres -- psql -tAc "SELECT 1 FROM pg_database WHERE datname='ragkb'" | grep -q 1; then
  runuser -u postgres -- createdb -O ragkb ragkb
fi
runuser -u postgres -- psql -d ragkb -c "CREATE EXTENSION IF NOT EXISTS vector;"
pg_isready -h 127.0.0.1 -p 5432
'@

$tempScript = Join-Path ([System.IO.Path]::GetTempPath()) 'fbbp_formal_pg_ready.sh'
Save-TextFile -Path $tempScript -Content ($wslCommands -replace "`r`n", "`n")
$wslScriptPath = Convert-ToWslPath $tempScript
try {
  & wsl -u root bash $wslScriptPath
} finally {
  Remove-Item $tempScript -ErrorAction SilentlyContinue
}

$deadline = (Get-Date).AddSeconds(30)
while ((Get-Date) -lt $deadline) {
  if (Test-PostgresQueryReady -ProbeHost $ExpectedHost -Port $ExpectedPort -Database $PgDatabase -User $PgUser -Password $PgPassword) {
    [ordered]@{
      ok = $true
      host = $ExpectedHost
      port = $ExpectedPort
      mode = "started_wsl_postgres"
    } | ConvertTo-Json -Depth 4
    exit 0
  }
  Start-Sleep -Seconds 2
}

throw "PostgreSQL is still not query-ready at ${ExpectedHost}:$ExpectedPort after WSL startup."
