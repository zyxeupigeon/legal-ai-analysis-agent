$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
$OutputEncoding = [Console]::OutputEncoding

$scriptDirectory = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectRoot = Split-Path -Parent $scriptDirectory
$currentRoot = (Get-Location).Path.TrimEnd("\")
$expectedRoot = (Resolve-Path -LiteralPath $projectRoot).Path.TrimEnd("\")
$checks = [System.Collections.Generic.List[object]]::new()

function Add-Check {
    param([string]$Name, [bool]$Passed, [string]$Detail, [bool]$Required = $true)
    $checks.Add([PSCustomObject]@{ Check = $Name; Required = $Required; Passed = $Passed; Detail = $Detail })
}

Add-Check -Name "project_root" -Passed ($currentRoot -ieq $expectedRoot) -Detail "current=$currentRoot; expected=$expectedRoot"

$requiredFiles = @(
    "PROJECT_AGENT_PROTOCOL.md",
    "agent\core\v1.1\SYSTEM_PROMPT.md",
    "agent\core\v1.1\WORKFLOW.md",
    "agent\skills\legal-report-review-and-verification\SKILL.md"
)
foreach ($relativePath in $requiredFiles) {
    $fullPath = Join-Path $expectedRoot $relativePath
    Add-Check -Name "file:$relativePath" -Passed (Test-Path -LiteralPath $fullPath -PathType Leaf) -Detail $fullPath
}

$python = Get-Command python -ErrorAction SilentlyContinue
if (-not $python) {
    $venvPython = Join-Path $expectedRoot ".venv\Scripts\python.exe"
    if (Test-Path -LiteralPath $venvPython -PathType Leaf) { $python = Get-Item -LiteralPath $venvPython }
}
$pythonDetail = if ($python.Source) { $python.Source } elseif ($python.FullName) { $python.FullName } else { "not found" }
Add-Check -Name "python" -Passed ($null -ne $python) -Detail $pythonDetail

$outputDirectory = Join-Path $expectedRoot "agent_outputs"
if (-not (Test-Path -LiteralPath $outputDirectory)) { New-Item -ItemType Directory -Path $outputDirectory | Out-Null }
$probePath = Join-Path $outputDirectory ".write_probe"
$writePassed = $false
try {
    Set-Content -LiteralPath $probePath -Value "portable-agent-poc-0.1" -Encoding UTF8
    $writePassed = Test-Path -LiteralPath $probePath -PathType Leaf
} finally {
    if (Test-Path -LiteralPath $probePath) { Remove-Item -LiteralPath $probePath -Force }
}
Add-Check -Name "output_writable" -Passed $writePassed -Detail $outputDirectory

$word = Get-Command winword.exe -ErrorAction SilentlyContinue
$wordDetail = if ($word) { $word.Source } else { "not on PATH; an Agent may still use Python, LibreOffice, or Word COM" }
Add-Check -Name "word_cli" -Passed ($null -ne $word) -Detail $wordDetail -Required $false

$checks | Format-Table -AutoSize
$failedRequired = @($checks | Where-Object { $_.Required -and -not $_.Passed })
if ($failedRequired.Count -gt 0) {
    Write-Error "Portable Agent preflight failed: $($failedRequired.Count) required check(s) failed."
    exit 1
}

Write-Output "PREFLIGHT_OK protocol=portable-agent-poc-0.1"
Write-Output "NOTE internet search, page reading, model access, and visual document inspection must be declared by the running Agent; this local script cannot prove them."