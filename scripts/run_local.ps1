$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $RepoRoot ".venv\Scripts\python.exe"
$Uvicorn = Join-Path $RepoRoot ".venv\Scripts\uvicorn.exe"
$NodeModules = Join-Path $RepoRoot "apps\web\node_modules"
$EnvFile = Join-Path $RepoRoot ".env"

if (-not (Test-Path $Uvicorn)) {
    Write-Error "尚未安装本地API依赖。请先按README执行一次安装命令。"
}
if (-not (Test-Path $NodeModules)) {
    Write-Error "尚未安装页面依赖。请先按README执行一次npm install。"
}

$ApiArguments = @("-m", "uvicorn", "services.api.app.main:app", "--port", "8000")
if (Test-Path $EnvFile) {
    $ApiArguments += @("--env-file", $EnvFile)
}

$ApiProcess = Start-Process -FilePath $Python -ArgumentList $ApiArguments `
    -WorkingDirectory $RepoRoot -NoNewWindow -PassThru

try {
    Push-Location (Join-Path $RepoRoot "apps\web")
    npm run dev
}
finally {
    Pop-Location
    if (-not $ApiProcess.HasExited) {
        Stop-Process -Id $ApiProcess.Id
    }
}
