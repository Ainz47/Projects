# Astorga Central -- start the demo (backend + pages), with Discord alerts if configured.
#
#   .\run_demo.ps1
#
# Put the webhook in .env.local (gitignored) so it survives a new terminal:
#   DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/...
# Without that file the demo still runs; alerts are simply skipped.

$ErrorActionPreference = "Stop"
$root = $PSScriptRoot
$py = Join-Path $root "backend\venv\Scripts\python.exe"

if (-not (Test-Path $py)) { throw "venv python not found at $py" }

$envFile = Join-Path $root ".env.local"
if (Test-Path $envFile) {
    Get-Content $envFile | ForEach-Object {
        if ($_ -match '^\s*([A-Z_][A-Z0-9_]*)\s*=\s*(.+?)\s*$') {
            Set-Item -Path "env:$($Matches[1])" -Value $Matches[2]
        }
    }
}

if ($env:DISCORD_WEBHOOK_URL) {
    $tail = $env:DISCORD_WEBHOOK_URL.Substring([Math]::Max(0, $env:DISCORD_WEBHOOK_URL.Length - 6))
    Write-Host "Discord alerts: ON  (webhook ...$tail)" -ForegroundColor Green
} else {
    Write-Host "Discord alerts: OFF (no .env.local / DISCORD_WEBHOOK_URL) - dashboard still works" -ForegroundColor Yellow
}

Get-NetTCPConnection -LocalPort 8000,5500 -State Listen -ErrorAction SilentlyContinue |
    ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }

Start-Process -FilePath $py -WorkingDirectory (Join-Path $root "backend") `
    -ArgumentList "-m","uvicorn","main:app","--host","0.0.0.0","--port","8000"
Start-Process -FilePath $py -WorkingDirectory $root `
    -ArgumentList "-m","http.server","5500"

Start-Sleep -Seconds 5
try {
    Invoke-RestMethod "http://127.0.0.1:8000/api/health" -TimeoutSec 5 | Out-Null
    Write-Host "`nBackend  http://localhost:8000   (simulator running)" -ForegroundColor Cyan
    Write-Host "Portal   http://localhost:5500/"
    Write-Host "DASHBOARD http://localhost:5500/dashboard/" -ForegroundColor Cyan
    Write-Host "Report   http://localhost:5500/report-form/"
    Write-Host "`nTrigger CRITICAL:  backend\venv\Scripts\python.exe firmware\post_test_reading.py --distance 30"
    Write-Host "Reset to NORMAL:   backend\venv\Scripts\python.exe firmware\post_test_reading.py --distance 100"
} catch {
    Write-Host "Backend did not come up - check the uvicorn window." -ForegroundColor Red
}
