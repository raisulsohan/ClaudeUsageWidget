# uninstall_task.ps1 - remove the background fetcher scheduled task.
# Run:  powershell -ExecutionPolicy Bypass -File uninstall_task.ps1

$TaskName = "ClaudeUsageWidget"
try {
    Stop-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction Stop
    Write-Host "Removed scheduled task '$TaskName'."
} catch {
    Write-Host "No scheduled task '$TaskName' found (nothing to remove)."
}
