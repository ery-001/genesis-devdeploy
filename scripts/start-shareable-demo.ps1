# Start the single-hostname demo proxy + cloudflared tunnel.
# Prerequisites: API on :8741 and web on :43127 already running.
#
# Usage:
#   .\scripts\start-shareable-demo.ps1
#   .\scripts\start-shareable-demo.ps1 -ApplyEnv   # also rewrite local .env for the public origin
#
# Named / stable tunnel (recommended for dogfood):
#   $env:CLOUDFLARE_TUNNEL_TOKEN = "<token from Cloudflare Zero Trust → Tunnels>"
#   $env:PUBLIC_DEMO_URL = "https://demo.example.com"   # hostname routed to this tunnel
#   .\scripts\start-shareable-demo.ps1 -ApplyEnv
#
# Without CLOUDFLARE_TUNNEL_TOKEN, falls back to an ephemeral trycloudflare.com quick tunnel.
param(
  [int]$ProxyPort = 18080,
  [switch]$ApplyEnv,
  [string]$PublicUrl = ""
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot

$cloudflared = Get-Command cloudflared -ErrorAction SilentlyContinue
if (-not $cloudflared) {
  $fallback = Join-Path $env:USERPROFILE ".local\bin\cloudflared.exe"
  if (Test-Path $fallback) {
    $cloudflaredPath = $fallback
  } else {
    throw "cloudflared not found on PATH (or ~/.local/bin/cloudflared.exe)"
  }
} else {
  $cloudflaredPath = $cloudflared.Source
}

# Health checks
foreach ($pair in @(
  @{ Name = "API"; Url = "http://127.0.0.1:8741/api/v1/health/ready" },
  @{ Name = "Web"; Url = "http://127.0.0.1:43127/" }
)) {
  try {
    $null = Invoke-WebRequest -Uri $pair.Url -UseBasicParsing -TimeoutSec 5
  } catch {
    throw "$($pair.Name) is not reachable at $($pair.Url). Start make api / make web first."
  }
}

$proxyListening = Get-NetTCPConnection -LocalPort $ProxyPort -State Listen -ErrorAction SilentlyContinue
if (-not $proxyListening) {
  Write-Host "Starting demo proxy on :$ProxyPort ..."
  $proxyCmd = "Set-Location '$repoRoot'; `$env:DEMO_PROXY_PORT='$ProxyPort'; node .\scripts\demo-proxy.mjs"
  Start-Process -FilePath "powershell.exe" -ArgumentList @(
    "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", $proxyCmd
  ) -WindowStyle Minimized
  Start-Sleep -Seconds 1
}

try {
  $null = Invoke-WebRequest -Uri "http://127.0.0.1:$ProxyPort/" -UseBasicParsing -TimeoutSec 5
} catch {
  throw "Demo proxy did not become ready on :$ProxyPort"
}

$logDir = Join-Path $repoRoot ".demo-tunnel"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$logFile = Join-Path $logDir "cloudflared.log"
if (Test-Path $logFile) { Remove-Item $logFile -Force }

$tunnelToken = $env:CLOUDFLARE_TUNNEL_TOKEN
if (-not $PublicUrl -and $env:PUBLIC_DEMO_URL) {
  $PublicUrl = $env:PUBLIC_DEMO_URL.TrimEnd("/")
}

$publicUrl = $null
$cfProc = $null

if ($tunnelToken) {
  if (-not $PublicUrl) {
    throw "Named tunnel requires -PublicUrl or env PUBLIC_DEMO_URL (stable https:// hostname)."
  }
  if ($PublicUrl -notmatch "^https://") {
    throw "PUBLIC_DEMO_URL / -PublicUrl must be https://... (got: $PublicUrl)"
  }
  Write-Host "Starting named Cloudflare tunnel (token) → http://127.0.0.1:$ProxyPort ..."
  Write-Host "  Stable hostname: $PublicUrl"
  # Token-run connectors use dashboard ingress; ensure the public hostname points at :ProxyPort there.
  $cfArgs = @("tunnel", "run", "--token", $tunnelToken)
  $cfProc = Start-Process -FilePath $cloudflaredPath -ArgumentList $cfArgs `
    -RedirectStandardError $logFile -RedirectStandardOutput (Join-Path $logDir "cloudflared.out.log") `
    -PassThru -WindowStyle Hidden
  Start-Sleep -Seconds 3
  if ($cfProc.HasExited) {
    throw "Named tunnel exited early. See $logFile"
  }
  $publicUrl = $PublicUrl.TrimEnd("/")
} else {
  Write-Host "Starting cloudflared quick tunnel → http://127.0.0.1:$ProxyPort ..."
  Write-Host "  (Set CLOUDFLARE_TUNNEL_TOKEN + PUBLIC_DEMO_URL for a stable hostname.)"
  $cfArgs = @("tunnel", "--url", "http://127.0.0.1:$ProxyPort")
  $cfProc = Start-Process -FilePath $cloudflaredPath -ArgumentList $cfArgs `
    -RedirectStandardError $logFile -RedirectStandardOutput (Join-Path $logDir "cloudflared.out.log") `
    -PassThru -WindowStyle Hidden

  for ($i = 0; $i -lt 60; $i++) {
    Start-Sleep -Seconds 1
    if (Test-Path $logFile) {
      $text = Get-Content -LiteralPath $logFile -Raw -ErrorAction SilentlyContinue
      if ($text -match "https://[a-z0-9-]+\.trycloudflare\.com") {
        $publicUrl = $Matches[0]
        break
      }
    }
    if ($cfProc.HasExited) {
      throw "cloudflared exited early. See $logFile"
    }
  }

  if (-not $publicUrl) {
    throw "Timed out waiting for trycloudflare.com URL. See $logFile"
  }
}

$publicUrl | Set-Content -LiteralPath (Join-Path $logDir "public-url.txt") -Encoding utf8
$cfProc.Id | Set-Content -LiteralPath (Join-Path $logDir "cloudflared.pid") -Encoding utf8
if ($tunnelToken) {
  "named" | Set-Content -LiteralPath (Join-Path $logDir "tunnel-mode.txt") -Encoding utf8
} else {
  "quick" | Set-Content -LiteralPath (Join-Path $logDir "tunnel-mode.txt") -Encoding utf8
}

Write-Host ""
Write-Host "Public demo URL:"
Write-Host "  $publicUrl"
Write-Host ""
Write-Host "GitHub App → User authorization callback URL (you must set this in GitHub):"
Write-Host "  $publicUrl/api/v1/auth/oauth/github/callback"
Write-Host ""
Write-Host "cloudflared PID: $($cfProc.Id)  (log: $logFile)"

if ($ApplyEnv) {
  & "$PSScriptRoot\apply-public-demo-env.ps1" -PublicOrigin $publicUrl
}

Write-Host "Done. Keep this machine awake; the tunnel dies when cloudflared exits."
