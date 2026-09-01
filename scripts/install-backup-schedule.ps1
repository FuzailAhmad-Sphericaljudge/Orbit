param(
    [ValidateRange(1, 3650)][int]$RetentionDays = 14,
    [ValidatePattern('^([01]\d|2[0-3]):[0-5]\d$')][string]$DailyAt = "02:30"
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
$backupScript = Join-Path $PSScriptRoot "backup-docker.ps1"
$taskName = "ORBIT Daily Database Backup"
$powershellPath = (Get-Command powershell.exe -ErrorAction Stop).Source
$arguments = "-NoProfile -ExecutionPolicy Bypass -File `"$backupScript`" -OutputDirectory `"$(Join-Path $projectRoot 'backups')`" -RetentionDays $RetentionDays"

$action = New-ScheduledTaskAction -Execute $powershellPath -Argument $arguments -WorkingDirectory $projectRoot
$trigger = New-ScheduledTaskTrigger -Daily -At $DailyAt
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -MultipleInstances IgnoreNew

Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Settings $settings -Description "Creates an ORBIT PostgreSQL backup and retains the latest $RetentionDays days." -Force | Out-Null
Write-Output "Scheduled '$taskName' daily at $DailyAt with $RetentionDays-day retention."
