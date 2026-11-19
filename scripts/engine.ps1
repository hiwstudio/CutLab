param(
    [Parameter(Mandatory = $true, Position = 0)]
    [ValidateSet("mixfix", "clipinn", "viral", "recap", "hiw")]
    [string]$Engine,
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$CommandArgs
)

$ErrorActionPreference = "Stop"
$root = Split-Path $PSScriptRoot -Parent
$engineRoot = switch ($Engine) {
    "mixfix" { Join-Path $root "engines\mixfix" }
    "clipinn" { Join-Path $root "engines\clipinn" }
    "viral" { Join-Path $root "engines\viral-clip-engine" }
    "recap" { Join-Path $root "engines\recap-engine" }
    "hiw" { Join-Path $root "engines\hiw-studio" }
}

if ($Engine -eq "hiw") {
    if (-not (Test-Path (Join-Path $engineRoot "node_modules"))) {
        throw "HIW Studio dependencies are missing. Run scripts\setup.ps1 first."
    }
    Push-Location $engineRoot
    try {
        $npmCommand = Get-Command npm.cmd -ErrorAction SilentlyContinue
        if (-not $npmCommand) { $npmCommand = Get-Command npm -ErrorAction SilentlyContinue }
        if (-not $npmCommand) { throw "npm was not found. Install Node.js and rerun setup." }
        & $npmCommand.Source run hiw -- @CommandArgs
        exit $LASTEXITCODE
    } finally {
        Pop-Location
    }
}

$enginePython = Join-Path $root "engines\.venv\Scripts\python.exe"
if (-not (Test-Path $enginePython)) {
    throw "Engine dependencies are missing. Run scripts\setup.ps1 first."
}

$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"
$env:PYTHONPATH = if ($env:PYTHONPATH) { (Join-Path $root "engines") + [IO.Path]::PathSeparator + $env:PYTHONPATH } else { Join-Path $root "engines" }
if ($Engine -in @("clipinn", "viral")) { $env:AGENT_OPERATOR = "1" }
if ($Engine -eq "recap" -and -not $env:LLM_BACKEND) { $env:LLM_BACKEND = "manual" }

Push-Location $engineRoot
try {
    switch ($Engine) {
        "mixfix" { & $enginePython -m mixfix.cli @CommandArgs }
        "clipinn" { & $enginePython -m clipinn @CommandArgs }
        "viral" { & $enginePython run.py @CommandArgs }
        "recap" { & $enginePython run.py @CommandArgs }
    }
    exit $LASTEXITCODE
} finally {
    Pop-Location
}
