function ConvertFrom-JsonTailPayload {
  param(
    [Parameter(Mandatory = $true)]
    [string]$RawText
  )

  $rendered = if ($null -eq $RawText) { "" } else { [string]$RawText }
  $trimmed = $rendered.Trim()
  if (-not $trimmed) {
    throw "No output was available for JSON parsing."
  }

  for ($index = $trimmed.Length - 1; $index -ge 0; $index--) {
    if ($trimmed[$index] -ne '{') {
      continue
    }
    $candidate = $trimmed.Substring($index)
    try {
      return $candidate | ConvertFrom-Json
    } catch {
      continue
    }
  }

  throw "Could not extract a JSON payload from the provided output."
}
