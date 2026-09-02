param(
    [string]$ApiEnvPath = "api/.env",
    [switch]$ForPublicDeployment,
    [switch]$KeycloakAdminHardened
)

$ErrorActionPreference = "Stop"

function Read-EnvironmentFile {
    param([string]$Path)
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) { throw "Required environment file was not found: $Path" }
    $values = @{}
    foreach ($line in Get-Content -LiteralPath $Path) {
        if ($line -match '^\s*#' -or $line -notmatch '=') { continue }
        $name, $value = $line -split '=', 2
        $values[$name.Trim()] = $value.Trim()
    }
    return $values
}

function Require-Setting {
    param([hashtable]$Values, [string]$Name)
    if (-not $Values.ContainsKey($Name) -or [string]::IsNullOrWhiteSpace($Values[$Name])) {
        throw "Missing required public-deployment setting: $Name"
    }
}

$settings = Read-EnvironmentFile $ApiEnvPath
if (-not $ForPublicDeployment) {
    Write-Output "LOCAL SECURITY PREFLIGHT PASSED (use -ForPublicDeployment before a public release)"
    exit 0
}

foreach ($name in "ENVIRONMENT", "AUTH_JWT_SECRET", "DATABASE_URL", "OIDC_JWKS_URL", "OIDC_ISSUER", "OIDC_AUDIENCE", "DATA_ENCRYPTION_KEY", "TRUSTED_HOSTS", "CORS_ORIGINS") {
    Require-Setting $settings $name
}

if ($settings["ENVIRONMENT"].ToLowerInvariant() -ne "production") { throw "ENVIRONMENT must be production" }
if ($settings["AUTH_JWT_SECRET"] -match "replace-with|local_only" -or $settings["AUTH_JWT_SECRET"].Length -lt 32) { throw "AUTH_JWT_SECRET must be a non-default secret of at least 32 characters" }
if ($settings["DATABASE_URL"] -match "orbit_local_only|localhost|127\.0\.0\.1") { throw "DATABASE_URL must point to the production database, not a local default" }
if ($settings["OIDC_ISSUER"] -match "localhost|127\.0\.0\.1") { throw "OIDC_ISSUER must use the public HTTPS issuer" }
if ($settings["TRUSTED_HOSTS"] -match "trycloudflare\.com|localhost|127\.0\.0\.1") { throw "TRUSTED_HOSTS must not include temporary-tunnel or localhost hosts" }
if ($settings["CORS_ORIGINS"] -match "trycloudflare\.com|localhost|127\.0\.0\.1") { throw "CORS_ORIGINS must use the public HTTPS command-center origin" }
if (-not $KeycloakAdminHardened) { throw "Create a permanent Keycloak master-realm admin and remove the bootstrap admin before release; then re-run with -KeycloakAdminHardened" }

Write-Output "PUBLIC SECURITY PREFLIGHT PASSED"
