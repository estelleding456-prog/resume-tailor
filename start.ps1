$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$backend = Join-Path $root 'backend'
$frontend = Join-Path $root 'frontend'

if (-not (Test-Path (Join-Path $backend '.venv\Scripts\python.exe'))) {
    throw "未找到后端虚拟环境，请先运行根目录的 setup.ps1"
}

Start-Process -FilePath (Join-Path $backend '.venv\Scripts\python.exe') `
    -ArgumentList '-m','uvicorn','app.main:app','--reload','--port','8000' `
    -WorkingDirectory $backend

Start-Process -FilePath 'npm.cmd' `
    -ArgumentList 'run','dev','--','--host','127.0.0.1','--port','5173' `
    -WorkingDirectory $frontend

Start-Sleep -Seconds 3
Start-Process 'http://localhost:5173'
Write-Host 'Local Resume Tailor 已启动： http://localhost:5173'
