# install_task.ps1 - register the background component as a Scheduled Task that
# starts at logon. Replaces the macOS launchd agent.
#
#   powershell -ExecutionPolicy Bypass -File install_task.ps1              # cookie/paste method: fetch_usage.py --loop
#   powershell -ExecutionPolicy Bypass -File install_task.ps1 -Receiver   # Chrome-extension method: receiver.py

param([switch]$Receiver)

$ErrorActionPreference = "Stop"
$TaskName = "ClaudeUsageWidget"
$Repo = $PSScriptRoot

# Prefer pythonw.exe (no console window); fall back to python.exe.
$py = (Get-Command pythonw.exe -ErrorAction SilentlyContinue).Source
if (-not $py) { $py = (Get-Command python.exe -ErrorAction SilentlyContinue).Source }
if (-not $py) { Write-Error "Python not found on PATH. Install Python 3.10+ first."; exit 1 }

if ($Receiver) {
    $arg = "`"$Repo\receiver.py`""
    $desc = "Receives claude.ai usage from the Chrome extension for the desktop widget."
} else {
    $arg = "`"$Repo\fetch_usage.py`" --loop"
    $desc = "Fetches claude.ai usage for the desktop widget."
}

$action  = New-ScheduledTaskAction -Execute $py -Argument $arg -WorkingDirectory $Repo
$trigger = New-ScheduledTaskTrigger -AtLogOn
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries -StartWhenAvailable -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1)

Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger `
    -Settings $settings -Description $desc -Force | Out-Null

Start-ScheduledTask -TaskName $TaskName
Write-Host "Installed and started scheduled task '$TaskName'."
if ($Receiver) {
    Write-Host "It runs receiver.py at logon. Keep Chrome open with the extension loaded."
} else {
    Write-Host "It refreshes usage_data.json every 5 minutes at logon."
}
Write-Host "Now show the widget with:  python widget.py"
