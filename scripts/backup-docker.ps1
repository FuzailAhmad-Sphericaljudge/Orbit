param(
    [string]$OutputDirectory = "backups",
    [ValidateRange(1, 3650)][int]$RetentionDays = 14,
    [switch]$SkipRetention
)

$ErrorActionPreference = "Stop"
$targetDirectory = [System.IO.Path]::GetFullPath($OutputDirectory)
New-Item -ItemType Directory -Path $targetDirectory -Force | Out-Null

$containerId = (& docker compose ps -q db).Trim()
if (-not $containerId) { throw "The ORBIT database container is not running." }

$timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$containerFile = "/tmp/orbit-$timestamp.dump"
$targetFile = Join-Path $targetDirectory "orbit-$timestamp.dump"

& docker compose exec -T db pg_dump -U orbit -d orbit --format=custom --no-owner --no-privileges --file=$containerFile
if ($LASTEXITCODE -ne 0) { throw "pg_dump failed" }

& docker cp "${containerId}:$containerFile" $targetFile
if ($LASTEXITCODE -ne 0) { throw "Could not copy the backup from the database container" }

& docker compose exec -T db rm -f $containerFile
if ($LASTEXITCODE -ne 0) { throw "Backup was created but its temporary container file could not be removed" }

if (-not $SkipRetention) {
    $cutoff = (Get-Date).AddDays(-$RetentionDays)
    $expiredBackups = Get-ChildItem -LiteralPath $targetDirectory -Filter "orbit-*.dump" -File |
        Where-Object { $_.LastWriteTime -lt $cutoff }

    foreach ($expiredBackup in $expiredBackups) {
        Remove-Item -LiteralPath $expiredBackup.FullName -Force
        Write-Output "Removed expired backup: $($expiredBackup.FullName)"
    }
}

Write-Output $targetFile
