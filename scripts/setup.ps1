param(
    [switch]$CoreOnly
)

$ErrorActionPreference = "Stop"
$root = Split-Path $PSScriptRoot -Parent

function Invoke-Checked {
    param(
        [Parameter(Mandatory = $true)][string]$FilePath,
        [Parameter(Mandatory = $true)][string[]]$CommandArgs,
        [string]$WorkingDirectory = $root
    )
    Push-Location $WorkingDirectory
    try {
        & $FilePath @CommandArgs
        if ($LASTEXITCODE -ne 0) {
            throw "Command failed ($LASTEXITCODE): $FilePath $($CommandArgs -join ' ')"
        }
    } finally {
        Pop-Location
    }
}

$pythonCommand = Get-Command python -ErrorAction SilentlyContinue
if (-not $pythonCommand) { throw "Python 3.11+ was not found. Install Python and reopen this terminal." }
$pythonVersionText = & $pythonCommand.Source --version
if ($pythonVersionText -notmatch "Python\s+(\d+)\.(\d+)") { throw "Could not read Python version: $pythonVersionText" }
$pythonMajor = [int]$Matches[1]
$pythonMinor = [int]$Matches[2]
if ($pythonMajor -lt 3 -or ($pythonMajor -eq 3 -and $pythonMinor -lt 11)) {
    throw "CutLab needs Python 3.11 or newer. Found $pythonVersionText."
}

$nodeCommand = Get-Command node -ErrorAction SilentlyContinue
$npmCommand = Get-Command npm.cmd -ErrorAction SilentlyContinue
if (-not $npmCommand) { $npmCommand = Get-Command npm -ErrorAction SilentlyContinue }
if (-not $nodeCommand -or -not $npmCommand) { throw "Node.js 20+ and npm were not found. Install Node.js and reopen this terminal." }
$nodeVersionText = & $nodeCommand.Source --version
if ($nodeVersionText -notmatch "v?(\d+)") { throw "Could not read Node.js version: $nodeVersionText" }
if ([int]$Matches[1] -lt 20) { throw "CutLab Studio needs Node.js 20 or newer. Found $nodeVersionText." }

if (-not (Get-Command ffmpeg -ErrorAction SilentlyContinue) -or -not (Get-Command ffprobe -ErrorAction SilentlyContinue)) {
    throw "FFmpeg and ffprobe were not found on PATH. On Windows run 'winget install Gyan.FFmpeg', reopen the terminal, then retry."
}

Write-Host "Setting up the CutLab server..."
$serverVenv = Join-Path $root "apps\server\.venv"
if (-not (Test-Path (Join-Path $serverVenv "Scripts\python.exe"))) {
    Invoke-Checked -FilePath $pythonCommand.Source -CommandArgs @("-m", "venv", $serverVenv)
}
$serverPython = Join-Path $serverVenv "Scripts\python.exe"
Invoke-Checked -FilePath $serverPython -CommandArgs @("-m", "pip", "install", "-e", ".") -WorkingDirectory (Join-Path $root "apps\server")

Write-Host "Installing CutLab Studio dependencies..."
Invoke-Checked -FilePath $npmCommand.Source -CommandArgs @("ci") -WorkingDirectory (Join-Path $root "apps\studio")

if (-not $CoreOnly) {
    Write-Host "Setting up the bundled production engines..."
    $engineVenv = Join-Path $root "engines\.venv"
    if (-not (Test-Path (Join-Path $engineVenv "Scripts\python.exe"))) {
        Invoke-Checked -FilePath $pythonCommand.Source -CommandArgs @("-m", "venv", $engineVenv)
    }
    $enginePython = Join-Path $engineVenv "Scripts\python.exe"
    foreach ($requirements in @(
        "engines\mixfix\requirements.txt",
        "engines\clipinn\requirements.txt",
        "engines\viral-clip-engine\requirements.txt",
        "engines\recap-engine\requirements.txt"
    )) {
        Invoke-Checked -FilePath $enginePython -CommandArgs @("-m", "pip", "install", "-r", (Join-Path $root $requirements))
    }
    Write-Host "Installing HIW Studio dependencies..."
    Invoke-Checked -FilePath $npmCommand.Source -CommandArgs @("ci") -WorkingDirectory (Join-Path $root "engines\hiw-studio")
} else {
    Write-Host "Core-only setup complete. Rerun scripts\setup.ps1 later to install the bundled engines."
}

Write-Host "Setup complete. Start CutLab with scripts\dev.ps1."
