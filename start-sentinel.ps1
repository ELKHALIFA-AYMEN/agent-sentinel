# Script de démarrage rapide d'AgentSentinel (Backend FastAPI + Frontend Next.js)

Write-Host "Démarrage d'AgentSentinel..." -ForegroundColor Green

$backendJob = Start-Process -FilePath ".\.venv\Scripts\uvicorn.exe" `
    -ArgumentList "app.main:app --reload --app-dir backend --host 127.0.0.1 --port 8000" `
    -PassThru -NoNewWindow

Write-Host "Backend FastAPI lancé sur http://localhost:8000 (PID: $($backendJob.Id))" -ForegroundColor Cyan
Write-Host "Lancement du Frontend Next.js sur http://localhost:3000..." -ForegroundColor Cyan

try {
    Set-Location -Path ".\frontend"
    npm run dev
} finally {
    Set-Location -Path ".."
    if (-not $backendJob.HasExited) {
        Stop-Process -Id $backendJob.Id -Force
    }
}
