param(
  [switch]$PreviewOnly
)

$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$descriptorPath = Join-Path $repoRoot "configs\datasets\fbbp_private_v2026_04.json"
$descriptor = Get-Content $descriptorPath -Raw | ConvertFrom-Json
$sourceAllowlist = @($descriptor.rebuild.source_allowlist)
$upstreamSourceAllowlist = @($descriptor.rebuild.upstream_source_allowlist)
$sourceRegistry = $descriptor.source_registry
$snapshotRoot = [string]$descriptor.formal_snapshot.root

$snapshotPlan = foreach ($relativePath in $sourceAllowlist) {
  $fileName = Split-Path $relativePath -Leaf
  $registryEntry = $sourceRegistry.PSObject.Properties[$fileName].Value
  $runtimeSnapshot = if ($registryEntry -and $registryEntry.runtime_snapshot) {
    [string]$registryEntry.runtime_snapshot
  } else {
    [string]$relativePath
  }
  $destinationPath = if ([System.IO.Path]::IsPathRooted($runtimeSnapshot)) {
    $runtimeSnapshot
  } else {
    Join-Path $repoRoot $runtimeSnapshot
  }
  $upstreamSource = $upstreamSourceAllowlist | Where-Object { (Split-Path $_ -Leaf) -eq $fileName } | Select-Object -First 1
  if (-not $upstreamSource -and $registryEntry -and $registryEntry.upstream_pipeline -and [System.IO.Path]::IsPathRooted([string]$registryEntry.upstream_pipeline)) {
    $upstreamSource = [string]$registryEntry.upstream_pipeline
  }
  [pscustomobject]@{
    source = [string]$upstreamSource
    runtime_snapshot = $runtimeSnapshot
    destination = $destinationPath
  }
}

if ($PreviewOnly) {
  [ordered]@{
    dataset_version = [string]$descriptor.dataset_version
    snapshot_root = $snapshotRoot
    source_allowlist = $sourceAllowlist
    files = $snapshotPlan
  } | ConvertTo-Json -Depth 6
  return
}

foreach ($item in $snapshotPlan) {
  if (-not $item.source) {
    throw "No canonical upstream source was found for snapshot item: $($item.runtime_snapshot)"
  }
  if (-not (Test-Path $item.source)) {
    throw "Snapshot source is missing: $($item.source)"
  }
  $destinationDir = Split-Path $item.destination -Parent
  New-Item -ItemType Directory -Force -Path $destinationDir | Out-Null
  Copy-Item -Path $item.source -Destination $item.destination -Force
}

$manifestPath = Join-Path $repoRoot (Join-Path $snapshotRoot "MANIFEST.json")
$manifestFiles = foreach ($item in $snapshotPlan) {
  $fileInfo = Get-Item $item.destination
  [ordered]@{
    source = $item.source
    runtime_snapshot = $item.runtime_snapshot
    destination = $item.destination
    size_bytes = [int64]$fileInfo.Length
    last_write_time = $fileInfo.LastWriteTime.ToString("s")
  }
}
$manifest = [ordered]@{
  dataset_version = [string]$descriptor.dataset_version
  snapshot_root = $snapshotRoot
  created_at = (Get-Date).ToString("s")
  source_allowlist = $sourceAllowlist
  files = $manifestFiles
}
$manifest | ConvertTo-Json -Depth 6 | Set-Content -Path $manifestPath -Encoding UTF8

[ordered]@{
  dataset_version = [string]$descriptor.dataset_version
  snapshot_root = $snapshotRoot
  source_allowlist = $sourceAllowlist
  manifest = $manifestPath
  files = $manifestFiles
} | ConvertTo-Json -Depth 6
