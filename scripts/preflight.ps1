param(
    [string]$ApiUrl = "http://localhost:8000",
    [string]$WebUrl = "http://localhost:5174",
    [string]$TunnelUrl = ""
)

$ErrorActionPreference = "Stop"

function Assert-Endpoint {
    param([string]$Name, [string]$Url)
    $response = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 15
    if ($response.StatusCode -ne 200) { throw "$Name returned HTTP $($response.StatusCode)" }
    Write-Output "PASS  $Name"
}

& docker compose ps
if ($LASTEXITCODE -ne 0) { throw "Docker Compose is not available or the ORBIT stack is not running." }

Assert-Endpoint "API health" "$ApiUrl/health"
Assert-Endpoint "API readiness" "$ApiUrl/ready"
Assert-Endpoint "API metrics" "$ApiUrl/metrics"
Assert-Endpoint "Command center" $WebUrl

if ($TunnelUrl) {
    $publicUrl = $TunnelUrl.TrimEnd("/")
    Assert-Endpoint "Cloudflare tunnel" "$publicUrl/health"
}

Write-Output "ORBIT PREFLIGHT PASSED"
