@echo off
setlocal
title Claude Usage Widget
powershell -NoProfile -ExecutionPolicy Bypass -Command "Get-CimInstance Win32_Process -Filter \"(CommandLine LIKE '%%widget.py%%' OR CommandLine LIKE '%%receiver.py%%') AND (Name='pythonw.exe' OR Name='python.exe')\" | ForEach-Object { Stop-Process -Id $_.ProcessId -Force; Write-Host ('stopped: ' + $_.CommandLine) }"
echo Widget and receiver stopped.
timeout /t 3 >nul
endlocal
