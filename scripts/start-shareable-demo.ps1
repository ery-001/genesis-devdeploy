# Start the single-hostname demo proxy + one cloudflared quick tunnel.
# Prerequisites: API on :8741 and web on :43127 already running.
#
# Usage:
#   .\scripts\start-shareable-demo.ps1
#   .\scripts\start-shareable-demo.ps1 -ApplyEnv   # also rewrite local .env for the public origin
param(
  [int]$ProxyPort = 18080,
  [switch]$ApplyEnv
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

Write-Host "Starting cloudflared quick tunnel → http://127.0.0.1:$ProxyPort ..."
$cfArgs = @("tunnel", "--url", "http://127.0.0.1:$ProxyPort")
$cfProc = Start-Process -FilePath $cloudflaredPath -ArgumentList $cfArgs `
  -RedirectStandardError $logFile -RedirectStandardOutput (Join-Path $logDir "cloudflared.out.log") `
  -PassThru -WindowStyle Hidden

$publicUrl = $null
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

$publicUrl | Set-Content -LiteralPath (Join-Path $logDir "public-url.txt") -Encoding utf8
$cfProc.Id | Set-Content -LiteralPath (Join-Path $logDir "cloudflared.pid") -Encoding utf8

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
