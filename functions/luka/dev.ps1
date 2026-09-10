# Avvia backend (uvicorn :8000) + frontend (vite :5173) in due finestre.
# Uso:  ./dev.ps1

$ErrorActionPreference = "Stop"
$root = $PSScriptRoot

if (-not (Test-Path "$root/.venv")) {
    Write-Host "Creo il virtualenv..." -ForegroundColor Cyan
    python -m venv "$root/.venv"
    & "$root/.venv/Scripts/python.exe" -m pip install --upgrade pip
    & "$root/.venv/Scripts/python.exe" -m pip install -r "$root/requirements.txt"
}

if (-not (Test-Path "$root/web/node_modules")) {
    Write-Host "Installo le dipendenze frontend..." -ForegroundColor Cyan
    Push-Location "$root/web"; npm install; Pop-Location
}

Start-Process powershell -ArgumentList "-NoExit", "-Command",
    "cd '$root'; ./.venv/Scripts/python.exe -m uvicorn app.main:app --reload --port 8000"
Start-Process powershell -ArgumentList "-NoExit", "-Command",
    "cd '$root/web'; npm run dev"

Write-Host ""
Write-Host "  API   -> http://127.0.0.1:8000  (/docs per lo Swagger)" -ForegroundColor Green
Write-Host "  App   -> http://localhost:5173" -ForegroundColor Green
