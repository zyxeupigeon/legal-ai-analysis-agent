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
$declaredRoot = $env:LEGAL_AI_PROJECT_ROOT
$bindingPassed = (-not $declaredRoot) -or ([IO.Path]::GetFullPath($declaredRoot).TrimEnd("\") -ieq $expectedRoot)
$bindingDetail = if ($declaredRoot) { "launcher=$declaredRoot; expected=$expectedRoot" } else { "launcher binding not set; current directory is authoritative" }
Add-Check -Name "launcher_root_binding" -Passed $bindingPassed -Detail $bindingDetail

$requiredFiles = @(
    "PROJECT_AGENT_PROTOCOL.md",
    "agent\core\v1.1\SYSTEM_PROMPT.md",
    "agent\core\v1.1\WORKFLOW.md",
    "agent\skills\legal-report-review-and-verification\SKILL.md",
    "scripts\create_task_workspace.py"
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
    Set-Content -LiteralPath $probePath -Value "portable-agent-0.3" -Encoding UTF8
    $writePassed = Test-Path -LiteralPath $probePath -PathType Leaf
} finally {
    if (Test-Path -LiteralPath $probePath) { Remove-Item -LiteralPath $probePath -Force }
}
Add-Check -Name "output_writable" -Passed $writePassed -Detail $outputDirectory

$wordComAvailable = $false
try { $wordComAvailable = $null -ne [Type]::GetTypeFromProgID("Word.Application") } catch { $wordComAvailable = $false }
$libreOffice = Get-Command soffice, libreoffice -ErrorAction SilentlyContinue | Select-Object -First 1
if (-not $libreOffice) {
    foreach ($candidate in @(
        "C:\Program Files\LibreOffice\program\soffice.exe",
        "C:\Program Files (x86)\LibreOffice\program\soffice.exe"
    )) {
        if (Test-Path -LiteralPath $candidate -PathType Leaf) {
            $libreOffice = Get-Item -LiteralPath $candidate
            break
        }
    }
}
$converterPassed = $wordComAvailable -or ($null -ne $libreOffice)
if ($wordComAvailable) {
    $converterDetail = "Microsoft Word COM"
}
elseif ($libreOffice) {
    $converterDetail = if ($libreOffice.Source) { $libreOffice.Source } else { $libreOffice.FullName }
}
else {
    $converterDetail = "not found; install Microsoft Word or LibreOffice, or use an Agent with equivalent rendering"
}
Add-Check -Name "docx_to_pdf" -Passed $converterPassed -Detail $converterDetail -Required $false

$pageRendererCommand = Get-Command pdftoppm.exe, pdftoppm -ErrorAction SilentlyContinue | Select-Object -First 1
$pageRendererPath = $null
if ($pageRendererCommand) {
    $pageRendererPath = if ($pageRendererCommand.Source) { $pageRendererCommand.Source } else { $pageRendererCommand.Path }
    if ([IO.Path]::GetExtension($pageRendererPath) -ine ".exe") {
        $searchRoot = Split-Path -Parent $pageRendererPath
        for ($depth = 0; $depth -lt 3 -and $searchRoot; $depth++) {
            foreach ($relativePath in @(
                "pdftoppm.exe",
                "Library\bin\pdftoppm.exe",
                "native\poppler\Library\bin\pdftoppm.exe"
            )) {
                $candidate = Join-Path $searchRoot $relativePath
                if (Test-Path -LiteralPath $candidate -PathType Leaf) {
                    $pageRendererPath = $candidate
                    break
                }
            }
            if ([IO.Path]::GetExtension($pageRendererPath) -ieq ".exe") { break }
            $searchRoot = Split-Path -Parent $searchRoot
        }
    }
}
$rendererDetail = if ($pageRendererPath) { $pageRendererPath } else { "not found; install Poppler/pdftoppm, or use an Agent with equivalent rendering" }
Add-Check -Name "pdf_to_png" -Passed ($null -ne $pageRendererPath) -Detail $rendererDetail -Required $false

$selfTestScript = Join-Path $expectedRoot "scripts\self_test_document_pipeline.ps1"
Add-Check -Name "self_test_script" -Passed (Test-Path -LiteralPath $selfTestScript -PathType Leaf) -Detail $selfTestScript

$checks | Format-Table -AutoSize
$failedRequired = @($checks | Where-Object { $_.Required -and -not $_.Passed })
if ($failedRequired.Count -gt 0) {
    Write-Error "Portable Agent preflight failed: $($failedRequired.Count) required check(s) failed."
    exit 1
}

Write-Output "PREFLIGHT_BASE_OK protocol=portable-agent-0.3"
Write-Output ("LOCAL_DOCUMENT_PIPELINE_READY " + ($converterPassed -and ($null -ne $pageRendererPath)).ToString().ToLowerInvariant())
Write-Output "TIP run START_AGENT.cmd -SelfTest before the first real analysis"
Write-Output "NOTE internet search, page reading, model access, and visual document inspection must be declared by the running Agent; this local script cannot prove them."
