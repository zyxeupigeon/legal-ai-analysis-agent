$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $RepoRoot ".venv\Scripts\python.exe"
$Uvicorn = Join-Path $RepoRoot ".venv\Scripts\uvicorn.exe"
$NodeModules = Join-Path $RepoRoot "apps\web\node_modules"
$NextCli = Join-Path $NodeModules "next\dist\bin\next"
$EnvFile = Join-Path $RepoRoot ".env"

if (-not (Test-Path $Uvicorn)) {
    Write-Error "Local API dependencies are missing. Follow the one-time setup in README.md."
}
if (-not (Test-Path $NodeModules)) {
    Write-Error "Web dependencies are missing. Run npm install in apps\web."
}
if (-not (Test-Path $NextCli)) {
    Write-Error "Next.js launcher is missing. Run npm install again in apps\web."
}

$NodeCommand = Get-Command node -ErrorAction Stop
$Node = $NodeCommand.Source

$ApiArguments = @("-m", "uvicorn", "services.api.app.main:app", "--port", "8000")
if (Test-Path $EnvFile) {
    $ApiArguments += @("--env-file", $EnvFile)
}

$ApiProcess = Start-Process -FilePath $Python -ArgumentList $ApiArguments `
    -WorkingDirectory $RepoRoot -NoNewWindow -PassThru

try {
    Push-Location (Join-Path $RepoRoot "apps\web")
    & $Node $NextCli dev
}
finally {
    Pop-Location
    if (-not $ApiProcess.HasExited) {
        Stop-Process -Id $ApiProcess.Id
    }
}
