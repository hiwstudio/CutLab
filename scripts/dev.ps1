# Start the CutLab server (port 8787) and studio (port 3000) together.
$ErrorActionPreference = "Stop"
$root = Split-Path $PSScriptRoot -Parent

$serverPython = Join-Path $root "apps\server\.venv\Scripts\python.exe"
if (-not (Test-Path $serverPython)) {
    Write-Error "Server venv missing. Run: python -m venv apps\server\.venv; apps\server\.venv\Scripts\pip install -e apps\server"
}

Write-Host "Starting CutLab server on http://127.0.0.1:8787 ..."
$server = Start-Process -PassThru -NoNewWindow -WorkingDirectory (Join-Path $root "apps\server") `
    -FilePath $serverPython -ArgumentList "-m", "cutlab.main"

Write-Host "Starting studio on http://localhost:3000 ..."
$studio = Start-Process -PassThru -NoNewWindow -WorkingDirectory (Join-Path $root "apps\studio") `
    -FilePath "npm.cmd" -ArgumentList "run", "dev"

Write-Host "Server PID $($server.Id), Studio PID $($studio.Id). Ctrl+C to stop both."
try {
    Wait-Process -Id $server.Id, $studio.Id
} finally {
    foreach ($p in @($server, $studio)) {
        if ($p -and -not $p.HasExited) { Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue }
    }
}
