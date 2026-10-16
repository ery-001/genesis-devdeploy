# Apply public demo origin to local env files (does not print secrets).
# Keeps local origins so http://127.0.0.1:43127 testing still works.
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

# Local UI + public tunnel (API picks callback from the request Host / X-Forwarded-*).
$cors = "http://127.0.0.1:43127,http://localhost:43127,$PublicOrigin"

foreach ($envFile in @(".env", "apps\api\.env")) {
  Set-EnvKey -Path $envFile -Key "CORS_ORIGINS" -Value $cors
  # Prefer local for password/OAuth return when hitting the API directly.
  Set-EnvKey -Path $envFile -Key "WEB_ORIGIN" -Value "http://127.0.0.1:43127"
  # Public URL kept for webhook hints + GitHub App callback list; OAuth start
  # uses the live request host so local + tunnel both work.
  Set-EnvKey -Path $envFile -Key "API_PUBLIC_URL" -Value $PublicOrigin
  # false so http://127.0.0.1 cookies work; HTTPS tunnel sets Secure per-request.
  Set-EnvKey -Path $envFile -Key "SESSION_COOKIE_SECURE" -Value "false"
}

# Web: keep local API for localhost testing. Tunnel pages use same-origin via getApiUrl().
$webEnv = "apps\web\.env.local"
if (-not (Test-Path $webEnv)) {
  Set-Content -LiteralPath $webEnv -Value "NEXT_PUBLIC_API_URL=http://127.0.0.1:8741" -Encoding utf8
  Write-Host "Created $webEnv"
} else {
  Set-EnvKey -Path $webEnv -Key "NEXT_PUBLIC_API_URL" -Value "http://127.0.0.1:8741"
}

Write-Host ""
Write-Host "Public origin: $PublicOrigin"
Write-Host "Register BOTH GitHub App User authorization callback URLs:"
Write-Host "  http://127.0.0.1:8741/api/v1/auth/oauth/github/callback"
Write-Host "  $PublicOrigin/api/v1/auth/oauth/github/callback"
Write-Host ""
Write-Host "Restart API and web so the new env values load."
