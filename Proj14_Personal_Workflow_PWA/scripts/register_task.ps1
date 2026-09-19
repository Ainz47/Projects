# Register the hourly calendar sync. Run once, from an elevated PowerShell.
$ErrorActionPreference = 'Stop'

$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$appRoot    = Split-Path -Parent $scriptRoot
$pyLauncher = (Get-Command py).Source

$action = New-ScheduledTaskAction -Execute $pyLauncher `
    -Argument 'scripts/sync_calendar.py' -WorkingDirectory $appRoot

$trigger = New-ScheduledTaskTrigger -Once -At (Get-Date) `
    -RepetitionInterval (New-TimeSpan -Hours 1)

$settings = New-ScheduledTaskSettingsSet `
    -StartWhenAvailable `
    -DontStopIfGoingOnBatteries `
    -AllowStartIfOnBatteries `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 10)

Register-ScheduledTask -TaskName 'ScheduleCalendarSync' `
    -Action $action -Trigger $trigger -Settings $settings `
    -Description 'Upserts the next week of schedule blocks into Google Calendar.' `
    -Force

Write-Host 'Registered ScheduleCalendarSync (hourly).'
