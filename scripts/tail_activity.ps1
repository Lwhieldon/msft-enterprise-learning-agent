# tail_activity.ps1
# Live-tail the Compliance Academy activity log.
#
# Open this in a second PowerShell window before starting a demo.
# The window will stream agent orchestration events in real time as
# the Chainlit UI (or CLI orchestrator) drives agent calls.
#
# Usage:
#   .\scripts\tail_activity.ps1            # follow the default log file
#   .\scripts\tail_activity.ps1 -Clear     # truncate log before tailing
#
# The activity log path defaults to logs/activity.log relative to the
# current working directory. Override via the ACTIVITY_LOG_PATH env var
# (must be set in this shell before launching agents in the other one).

param(
    [switch]$Clear
)

# Honor env var if set; otherwise use repo-relative default.
$logPath = $env:ACTIVITY_LOG_PATH
if ([string]::IsNullOrWhiteSpace($logPath)) {
    $logPath = Join-Path (Get-Location) "logs\activity.log"
}

# Ensure parent directory exists so Get-Content -Wait does not error.
$logDir = Split-Path -Parent $logPath
if (-not (Test-Path $logDir)) {
    New-Item -ItemType Directory -Path $logDir -Force | Out-Null
}

# Ensure the file exists.
if (-not (Test-Path $logPath)) {
    New-Item -ItemType File -Path $logPath -Force | Out-Null
}

# Optionally truncate so the demo starts with a clean view.
if ($Clear) {
    Clear-Content -Path $logPath
    Write-Host "[tail_activity] Cleared $logPath" -ForegroundColor DarkGray
}

Write-Host "[tail_activity] Tailing $logPath" -ForegroundColor DarkGray
Write-Host "[tail_activity] Press Ctrl+C to stop." -ForegroundColor DarkGray
Write-Host ""

# -Wait keeps the file handle open and streams new lines as they arrive.
# -Tail 0 starts from the END of the existing file rather than printing
# the whole history (which would be noisy if the previous session was
# long). Combine with -Clear to start truly fresh.
Get-Content -Path $logPath -Wait -Tail 0
