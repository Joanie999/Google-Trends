param([ValidateRange(1024,65535)][int]$Port = 8787)
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$pythonExe = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $pythonExe)) {
    if (Get-Command uv -ErrorAction SilentlyContinue) {
        uv sync --frozen --no-dev
        if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed.' }
    } else {
        python -m venv .venv
        if ($LASTEXITCODE -ne 0) { throw 'Python 3.11 or newer is required.' }
        & $pythonExe -m pip install -r requirements.txt
        if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed.' }
    }
}
& $pythonExe -c 'import fastapi, uvicorn, trendspyg'
if ($LASTEXITCODE -ne 0) { throw 'Missing dependencies. Run: uv sync --frozen' }
Write-Host "TrendScope: http://127.0.0.1:$Port" -ForegroundColor Green
Write-Host 'Keep this window open. Press Ctrl+C to stop.'
& $pythonExe -m uvicorn app.main:app --host 127.0.0.1 --port $Port
exit $LASTEXITCODE
