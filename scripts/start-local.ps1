param([switch]$WithTunnel)
$ErrorActionPreference = 'Stop'
$repoPath = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$pythonPath = Join-Path $repoPath '.venv\Scripts\python.exe'
$localPath = Join-Path $repoPath '.local'
New-Item -ItemType Directory -Force -Path $localPath | Out-Null
if (-not (Test-Path -LiteralPath $pythonPath)) { throw 'Install the project virtual environment first.' }
$probe = [System.Net.Sockets.TcpClient]::new()
try {
    $probe.Connect('127.0.0.1', 8000)
    $alreadyRunning = $true
} catch { $alreadyRunning = $false } finally { $probe.Dispose() }
if ($alreadyRunning) { throw 'Port 8000 is already in use. Stop the existing runtime before starting another.' }
$runtime = Start-Process -FilePath $pythonPath -ArgumentList '-m','commercepilot.cli','serve' -WorkingDirectory $repoPath -WindowStyle Hidden -RedirectStandardOutput (Join-Path $localPath 'runtime.stdout.log') -RedirectStandardError (Join-Path $localPath 'runtime.stderr.log') -PassThru
$runtime.Id | Set-Content -LiteralPath (Join-Path $localPath 'runtime.pid')
Write-Output "Private dashboard: http://127.0.0.1:8000 (process $($runtime.Id))"
if ($WithTunnel) {
    $tunnelPath = Join-Path $localPath 'tools\cloudflared.exe'
    if (-not (Test-Path -LiteralPath $tunnelPath)) { throw 'Install the official cloudflared utility into .local/tools first.' }
    $tunnel = Start-Process -FilePath $tunnelPath -ArgumentList 'tunnel','--url','http://127.0.0.1:8002','--no-autoupdate','--protocol','http2' -WorkingDirectory $repoPath -WindowStyle Hidden -RedirectStandardOutput (Join-Path $localPath 'tunnel.stdout.log') -RedirectStandardError (Join-Path $localPath 'tunnel.stderr.log') -PassThru
    $tunnel.Id | Set-Content -LiteralPath (Join-Path $localPath 'tunnel.pid')
    Write-Output "Tunnel process: $($tunnel.Id). Read .local/tunnel.stderr.log for its HTTPS URL, then explicitly renew the Meta callback."
}
