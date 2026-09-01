param(
    [string]$TargetUrl = "http://localhost:8000",
    [string]$CloudflaredPath = ""
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
if (-not $CloudflaredPath) {
    $CloudflaredPath = Join-Path $projectRoot "cloudflared.exe"
}

if (-not (Test-Path -LiteralPath $CloudflaredPath -PathType Leaf)) {
    throw "cloudflared was not found at '$CloudflaredPath'. Download Cloudflare Tunnel, or pass -CloudflaredPath with its full path."
}

Write-Output "Starting a temporary Cloudflare Quick Tunnel for $TargetUrl"
Write-Output "Keep this terminal open. The trycloudflare.com hostname changes whenever the tunnel restarts."
Write-Output "Use the printed HTTPS hostname with /api/alerts/grafana for Grafana webhooks, then run scripts/preflight.ps1 with that hostname."
& $CloudflaredPath tunnel --url $TargetUrl
if ($LASTEXITCODE -ne 0) { throw "Cloudflare Quick Tunnel exited with code $LASTEXITCODE" }
