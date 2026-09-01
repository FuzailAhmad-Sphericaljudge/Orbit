param(
    [Parameter(Mandatory=$true)][string]$DatabaseUrl,
    [Parameter(Mandatory=$true)][string]$BackupFile,
    [switch]$ConfirmRestore
)
$ErrorActionPreference = "Stop"
if (-not $ConfirmRestore) { throw "Restore is destructive. Re-run with -ConfirmRestore after verifying the target database." }
$resolvedBackup = (Resolve-Path -LiteralPath $BackupFile).Path
if (-not [System.IO.File]::Exists($resolvedBackup)) { throw "Backup file not found" }
pg_restore --clean --if-exists --no-owner --no-privileges --dbname=$DatabaseUrl $resolvedBackup
if ($LASTEXITCODE -ne 0) { throw "pg_restore failed" }
