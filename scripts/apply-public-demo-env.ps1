# Apply public demo origin to local env files (does not print secrets).
# Usage:
#   .\scripts\apply-public-demo-env.ps1 -PublicOrigin https://xxxx.trycloudflare.com
param(
  [Parameter(Mandatory = $true)]
  [string]$PublicOrigin
)

$ErrorActionPreference = "Stop"
$PublicOrigin = $PublicOrigin.TrimEnd("/")

if ($PublicOrigin -notmatch "^https://") {
  throw "PublicOrigin must be an https:// URL (got: $PublicOrigin)"
}

$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot

function Set-EnvKey {
  param(
    [string]$Path,
    [string]$Key,
    [string]$Value
  )
  if (-not (Test-Path $Path)) {
    Write-Warning "Skipping missing file: $Path"
    return
  }
  $lines = Get-Content -LiteralPath $Path
  $found = $false
  $updated = foreach ($line in $lines) {
    if ($line -match "^\s*$([regex]::Escape($Key))\s*=") {
      $found = $true
      "$Key=$Value"
    } else {
      $line
    }
  }
  if (-not $found) {
    $updated = @($updated) + "$Key=$Value"
  }
  Set-Content -LiteralPath $Path -Value $updated -Encoding utf8
  Write-Host "Updated $Key in $Path"
}

$cors = "http://127.0.0.1:43127,http://localhost:43127,$PublicOrigin"

foreach ($envFile in @(".env", "apps\api\.env")) {
  Set-EnvKey -Path $envFile -Key "CORS_ORIGINS" -Value $cors
  Set-EnvKey -Path $envFile -Key "WEB_ORIGIN" -Value $PublicOrigin
  Set-EnvKey -Path $envFile -Key "API_PUBLIC_URL" -Value $PublicOrigin
  Set-EnvKey -Path $envFile -Key "SESSION_COOKIE_SECURE" -Value "true"
  Set-EnvKey -Path $envFile -Key "NEXT_PUBLIC_API_URL" -Value $PublicOrigin
}

# Web only needs the public API origin at build/dev time.
$webEnv = "apps\web\.env.local"
if (Test-Path $webEnv) {
  Set-EnvKey -Path $webEnv -Key "NEXT_PUBLIC_API_URL" -Value $PublicOrigin
} else {
  Set-Content -LiteralPath $webEnv -Value "NEXT_PUBLIC_API_URL=$PublicOrigin" -Encoding utf8
  Write-Host "Created $webEnv"
}

Write-Host ""
Write-Host "Public origin: $PublicOrigin"
Write-Host "GitHub App User authorization callback URL:"
Write-Host "  $PublicOrigin/api/v1/auth/oauth/github/callback"
Write-Host ""
Write-Host "Restart API and web so the new env values load."
