param(
    [Parameter(Mandatory=$true)][string]$DatabaseUrl,
    [Parameter(Mandatory=$true)][string]$OutputDirectory
)
$ErrorActionPreference = "Stop"
$targetDirectory = [System.IO.Path]::GetFullPath($OutputDirectory)
New-Item -ItemType Directory -Path $targetDirectory -Force | Out-Null
$timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$targetFile = Join-Path $targetDirectory "orbit-$timestamp.dump"
pg_dump --format=custom --no-owner --no-privileges --file=$targetFile $DatabaseUrl
if ($LASTEXITCODE -ne 0) { throw "pg_dump failed" }
Write-Output $targetFile
