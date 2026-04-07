$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$AppRoot = Join-Path $RepoRoot "FRAUD_TRANSACTION"
$VenvActivate = Join-Path $AppRoot ".venv\\Scripts\\Activate.ps1"
$VenvPython = Join-Path $AppRoot ".venv\\Scripts\\python.exe"

function Ensure-Venv {
  if (-not (Test-Path $VenvPython)) {
    return $false
  }
  try {
    & $VenvPython -V | Out-Null
    return $true
  } catch {
    return $false
  }
}

if (-not (Ensure-Venv)) {
  Write-Host "[run.ps1] Creating (or repairing) venv at $AppRoot\\.venv ..."
  python -m venv (Join-Path $AppRoot ".venv")
}

if (Test-Path $VenvActivate) {
  & $VenvActivate
} else {
  Write-Host "[run.ps1] Failed to find venv activate script at $VenvActivate"
  Write-Host "[run.ps1] Continuing with system Python..."
}

if (Test-Path (Join-Path $AppRoot "requirements.txt")) {
  python -m pip install --disable-pip-version-check -r (Join-Path $AppRoot "requirements.txt")
}

python (Join-Path $AppRoot "run_all.py")
