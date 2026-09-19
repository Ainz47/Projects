# Register the daily vault export. Run once, from an elevated PowerShell.
$ErrorActionPreference = 'Stop'

$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$appRoot    = Split-Path -Parent $scriptRoot
$pyLauncher = (Get-Command py).Source

$action = New-ScheduledTaskAction -Execute $pyLauncher `
    -Argument 'scripts/export_to_vault.py' -WorkingDirectory $appRoot

$trigger = New-ScheduledTaskTrigger -Daily -At 5am

$settings = New-ScheduledTaskSettingsSet `
    -StartWhenAvailable `
    -DontStopIfGoingOnBatteries `
    -AllowStartIfOnBatteries `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 10)

Register-ScheduledTask -TaskName 'ScheduleVaultExport' `
    -Action $action -Trigger $trigger -Settings $settings `
    -Description 'Renders the schedule to the Obsidian vault once a day.' `
    -Force

Write-Host 'Registered ScheduleVaultExport (daily 05:00).'
