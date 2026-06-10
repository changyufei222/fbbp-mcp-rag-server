param(
  [string]$OutputPath = ""
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$jsonHelper = Join-Path $repoRoot "scripts\common_json_output.ps1"
. $jsonHelper
$resolvedOutputPath = if ($OutputPath) {
  $OutputPath
} else {
  Join-Path $repoRoot "docs\formal_acceptance_output.json"
}

Push-Location $repoRoot
try {
    $smokeOutput = & (Join-Path $repoRoot "scripts\smoke_local_stack.ps1") -ResolveTopChunk | Out-String
    $smokeJson = ConvertFrom-JsonTailPayload -RawText $smokeOutput
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $resolvedOutputPath) | Out-Null
    $smokeOutput | Set-Content -Path $resolvedOutputPath -Encoding utf8

    if (-not $smokeJson.search.ok) {
        throw "Real smoke search failed."
    }
    if ([int]$smokeJson.formal_checks.result_count -le 0) {
        throw "Real smoke search returned zero retrieval results."
    }
    if (-not $smokeJson.formal_checks.contract_version) {
        throw "Smoke output is missing formal contract metadata."
    }

    python -m unittest discover -s tests/acceptance -v
    if ($LASTEXITCODE -ne 0) {
        throw "Formal acceptance suite failed with exit code $LASTEXITCODE."
    }
    Write-Host "Formal acceptance suite passed."
    Write-Host "Acceptance smoke output written to $resolvedOutputPath"
} finally {
    Pop-Location
}
