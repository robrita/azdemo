Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

if (-not (Test-Path ".venv")) {
    python -m venv .venv
}

& .\.venv\Scripts\python -m pip install --upgrade pip
& .\.venv\Scripts\python -m pip install -e ".[dev]"

if (-not (Test-Path "local.settings.json")) {
    Copy-Item "local.settings.example.json" "local.settings.json"
}

Set-Location "$root\frontend"
npm install

Write-Host "Bootstrap complete. Use '.\.venv\Scripts\Activate.ps1', 'make dev', and 'make frontend-dev'."