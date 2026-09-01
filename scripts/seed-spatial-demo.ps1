$ErrorActionPreference = "Stop"

$api = "http://localhost:8000"
$headers = @{ "X-User-Id" = "local-commander"; "X-User-Role" = "commander,operator,admin" }

function Invoke-Orbit([string]$method, [string]$path, $body = $null) {
    $params = @{ Uri = "$api$path"; Method = $method; Headers = $headers; ContentType = "application/json" }
    if ($null -ne $body) { $params.Body = $body | ConvertTo-Json -Depth 12 }
    Invoke-RestMethod @params
}

$title = "DEMO - Payment authorization outage"
$existing = Invoke-Orbit "GET" "/api/incidents" | Where-Object { $_.title -eq $title } | Select-Object -First 1
if ($existing) {
    Write-Output "Spatial demo already exists: $($existing.id)"
    exit 0
}

$incident = Invoke-Orbit "POST" "/api/incidents" @{ title = $title; service = "payments"; severity = "SEV1"; commander_id = "local-commander"; customer_impact = "Card payments are failing in US East."; affected_regions = @("us-east", "eu-west", "ap-south"); recovery_criteria = "Payment error rate stays below 1% for 15 minutes." }
$id = $incident.id

@(
    @{ agora_uid = "1001"; display_name = "Maya Chen"; role = "Incident Commander" },
    @{ agora_uid = "1002"; display_name = "Arjun Rao"; role = "Backend Engineer" },
    @{ agora_uid = "1003"; display_name = "Elena Park"; role = "SRE" }
) | ForEach-Object { Invoke-Orbit "POST" "/api/incidents/$id/participants" $_ | Out-Null }

@(
    @{ claim = "Payment authorization failures climbed from 1.2% to 9.2% in us-east."; classification = "confirmed_fact"; confidence = 97; source = "prometheus-demo" },
    @{ claim = "The payment database connection pool may be saturated."; classification = "hypothesis"; confidence = 62; source = "sre-room" },
    @{ claim = "Traffic shift requires explicit commander approval before execution."; classification = "decision"; confidence = 100; source = "incident-commander" }
) | ForEach-Object { Invoke-Orbit "POST" "/api/incidents/$id/evidence" $_ | Out-Null }

Invoke-Orbit "POST" "/api/incidents/$id/actions" @{ task = "Inspect payment database saturation and confirm safe traffic-shift target."; owner_id = "arjun" } | Out-Null

$now = [DateTime]::UtcNow
$observations = @()
foreach ($point in @(@(15, 1.2), @(10, 3.1), @(5, 6.4), @(0, 9.2))) {
    $observations += @{ metric = "payment_error_rate"; service = "payments"; region = "us-east"; observed_at = $now.AddMinutes(-[double]$point[0]).ToString("o"); value = [double]$point[1]; baseline = 1; threshold = 10; higher_is_worse = $true; source_event_id = "demo-payment-$($point[0])"; labels = @{ environment = "local-demo" } }
}
foreach ($point in @(@(15, 180), @(10, 290), @(5, 510), @(0, 735))) {
    $observations += @{ metric = "database_latency_ms"; service = "payment-db"; region = "us-east"; observed_at = $now.AddMinutes(-[double]$point[0]).ToString("o"); value = [double]$point[1]; baseline = 180; threshold = 800; higher_is_worse = $true; source_event_id = "demo-db-$($point[0])"; labels = @{ environment = "local-demo" } }
}

$telemetry = Invoke-Orbit "POST" "/api/incidents/$id/telemetry" @{ source = "local-prometheus-demo"; observations = $observations; auto_forecast = $true; forecast_horizon_minutes = 30; dependency_map = @{ "payment-db" = @("payments"); payments = @("checkout", "refunds") }; region_catalog = @(@{ code = "us-east"; latitude = 37.4; longitude = -78.7; traffic_share = .58; customers = 240000; services = @("payment-db", "payments") }, @{ code = "eu-west"; latitude = 53.3; longitude = -6.2; traffic_share = .27; customers = 110000; services = @("checkout") }, @{ code = "ap-south"; latitude = 19.1; longitude = 72.9; traffic_share = .15; customers = 85000; services = @("payments") }) }

if ($telemetry.prediction_run_id) {
    Invoke-Orbit "POST" "/api/incidents/$id/simulations/run" @{ name = "Shift 40% traffic to healthy region"; prediction_run_id = $telemetry.prediction_run_id; iterations = 500; intervention = @{ effectiveness_percent = 42; implementation_delay_minutes = 6; failure_probability_percent = 8 }; assumptions = @{ risk_volatility = 7 } } | Out-Null
}

Write-Output "Spatial demo ready: $id"
