param(
  [string]$PythonExe = "python",
  [string]$VenvDir = ".venv",
  [switch]$Recreate
)

$ErrorActionPreference = "Stop"

function Invoke-Step {
  param(
    [string]$Label,
    [scriptblock]$Action
  )

  Write-Host "==> $Label"
  & $Action
  if ($LASTEXITCODE -ne 0) {
    throw "Step failed: $Label (exit code $LASTEXITCODE)"
  }
}

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$ragkbRoot = Resolve-Path (Join-Path $repoRoot "..\llm-rag-knowledge-base")
$venvPath = Join-Path $repoRoot $VenvDir
$venvPython = Join-Path $venvPath "Scripts\python.exe"

function Test-VenvUsable {
  param([string]$PythonPath)

  if (-not (Test-Path $PythonPath)) {
    return $false
  }

  try {
    & $PythonPath -c "import sys; print(sys.executable)" *> $null
  } catch {
    return $false
  }
  return $LASTEXITCODE -eq 0
}

if ($Recreate -or -not (Test-VenvUsable $venvPython)) {
  if (Test-Path $venvPath) {
    Write-Host "Removing unusable virtual environment:" $venvPath
    Remove-Item -Recurse -Force $venvPath
  }

  Invoke-Step "Create virtual environment" { & $PythonExe -m venv $venvPath }
}

Invoke-Step "Upgrade pip" { & $venvPython -m pip install --upgrade pip }
Invoke-Step "Install ragkb editable" { & $venvPython -m pip install -e $ragkbRoot }
Invoke-Step "Install MCP server editable" { & $venvPython -m pip install -e $repoRoot }
Invoke-Step "Create repo .env for real mode" { & $venvPython -c "from pathlib import Path; from fbbp_mcp_server.runtime_env import ensure_runtime_env_file; print(ensure_runtime_env_file(Path(r'$repoRoot')))" }

Write-Host "Created virtual environment:" $venvPath
Write-Host "Installed editable packages:"
Write-Host "  -" $ragkbRoot
Write-Host "  -" $repoRoot
Write-Host "Real-mode env file:"
Write-Host "  " (Join-Path $repoRoot ".env")
Write-Host "Use this interpreter in DeerFlow extensions_config.json:"
Write-Host "  $venvPython"
