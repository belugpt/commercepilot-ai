$ErrorActionPreference = 'Stop'
$repoPath = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$pythonPath = Join-Path $repoPath '.venv\Scripts\python.exe'
$tunnelPath = Join-Path $repoPath '.local\tools\cloudflared.exe'
$owned = Get-CimInstance Win32_Process | Where-Object {
    ($_.CommandLine -and $_.CommandLine.Contains($pythonPath) -and $_.CommandLine.Contains('commercepilot.cli serve')) -or
    ($_.ExecutablePath -eq $tunnelPath -and $_.CommandLine -and $_.CommandLine.Contains('127.0.0.1:8002'))
}
foreach ($process in $owned) {
    Stop-Process -Id $process.ProcessId -ErrorAction SilentlyContinue
    Write-Output "Stopped this project's process $($process.ProcessId)."
}
