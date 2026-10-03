# VideoMemo (VideoNote) source-deployment launcher
# Backend:  FastAPI on http://localhost:8483
# Frontend: Vite dev server on http://localhost:3015 (proxies /api to backend)
# FunASR config (MODELSCOPE_CACHE / FUNASR_DEVICE) is loaded from backend\.env.
$root = "I:\70_applist\videomemo"
$backendPy = "$root\backend\venv\Scripts\python.exe"

Write-Host "Starting VideoMemo backend (port 8483)..."
Start-Process powershell -ArgumentList "-NoExit", "-Command", "Set-Location '$root\backend'; & '$backendPy' main.py"

Write-Host "Starting VideoMemo frontend (port 3015)..."
Start-Process powershell -ArgumentList "-NoExit", "-Command", "Set-Location '$root\VideoMemo_frontend'; pnpm dev"

Start-Sleep 5
Write-Host "Opening http://localhost:3015 ..."
Start-Process "http://localhost:3015/"
