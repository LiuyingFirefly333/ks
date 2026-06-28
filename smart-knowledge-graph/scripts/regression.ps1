$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
$Backend = Join-Path $Root "backend"
$Frontend = Join-Path $Root "frontend"

Push-Location $Backend
try {
  python -m pytest
}
finally {
  Pop-Location
}

Push-Location $Root
try {
  python -m compileall backend
}
finally {
  Pop-Location
}

Push-Location $Frontend
try {
  npm run build
}
finally {
  Pop-Location
}
