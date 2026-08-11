param(
    [switch]$KeepArtifacts
)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
$OutputEncoding = [Console]::OutputEncoding

$scriptDirectory = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectRoot = Split-Path -Parent $scriptDirectory
$tempRoot = Join-Path $projectRoot "tmp"
$testDirectory = Join-Path $tempRoot ("agent-self-test-" + [guid]::NewGuid().ToString("N"))
$docxPath = Join-Path $testDirectory "self-test.docx"
$pdfPath = Join-Path $testDirectory "self-test.pdf"
$pngPrefix = Join-Path $testDirectory "self-test-page"

function Resolve-CommandPath {
    param([string[]]$Names)
    foreach ($name in $Names) {
        $command = Get-Command $name -ErrorAction SilentlyContinue
        if ($command) {
            if ($command.Source) { return $command.Source }
            if ($command.Path) { return $command.Path }
        }
    }
    return $null
}

function Resolve-PdfToPpm {
    $command = Get-Command pdftoppm.exe, pdftoppm -ErrorAction SilentlyContinue | Select-Object -First 1
    if (-not $command) { return $null }
    $source = if ($command.Source) { $command.Source } else { $command.Path }
    if ([IO.Path]::GetExtension($source) -ieq ".exe") { return $source }

    $searchRoot = Split-Path -Parent $source
    for ($depth = 0; $depth -lt 3 -and $searchRoot; $depth++) {
        foreach ($relativePath in @(
            "pdftoppm.exe",
            "Library\bin\pdftoppm.exe",
            "native\poppler\Library\bin\pdftoppm.exe"
        )) {
            $candidate = Join-Path $searchRoot $relativePath
            if (Test-Path -LiteralPath $candidate -PathType Leaf) { return $candidate }
        }
        $searchRoot = Split-Path -Parent $searchRoot
    }
    return $source
}

function Resolve-LibreOffice {
    $commandPath = Resolve-CommandPath @("soffice", "libreoffice")
    if ($commandPath) { return $commandPath }
    foreach ($candidate in @(
        "C:\Program Files\LibreOffice\program\soffice.exe",
        "C:\Program Files (x86)\LibreOffice\program\soffice.exe"
    )) {
        if (Test-Path -LiteralPath $candidate -PathType Leaf) { return $candidate }
    }
    return $null
}

function Test-WordComAvailable {
    try { return $null -ne [Type]::GetTypeFromProgID("Word.Application") }
    catch { return $false }
}

function Convert-WithWord {
    param([string]$InputPath, [string]$OutputPath)
    $word = $null
    $document = $null
    try {
        $word = New-Object -ComObject Word.Application
        $word.Visible = $false
        $word.DisplayAlerts = 0
        $document = $word.Documents.Open($InputPath, $false, $true)
        $document.ExportAsFixedFormat($OutputPath, 17)
    }
    finally {
        if ($document) {
            $document.Close($false)
            [void][Runtime.InteropServices.Marshal]::FinalReleaseComObject($document)
        }
        if ($word) {
            $word.Quit()
            [void][Runtime.InteropServices.Marshal]::FinalReleaseComObject($word)
        }
        [GC]::Collect()
        [GC]::WaitForPendingFinalizers()
    }
}

function Test-PngSignature {
    param([string]$Path)
    $bytes = [IO.File]::ReadAllBytes($Path)
    if ($bytes.Length -lt 8) { return $false }
    return ([BitConverter]::ToString($bytes[0..7]) -eq "89-50-4E-47-0D-0A-1A-0A")
}

$converter = $null
$renderer = $null
try {
    New-Item -ItemType Directory -Path $testDirectory | Out-Null

    $python = Resolve-CommandPath @("python", "python3")
    if (-not $python) { throw "Python was not found. Install Python 3.12 or make it available to the Agent." }

    & $python (Join-Path $scriptDirectory "create_self_test_docx.py") $docxPath
    if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $docxPath -PathType Leaf)) {
        throw "The standard-library DOCX generator failed."
    }

    if (Test-WordComAvailable) {
        try {
            Convert-WithWord -InputPath $docxPath -OutputPath $pdfPath
            $converter = "Microsoft Word COM"
        }
        catch {
            Write-Warning "Microsoft Word conversion failed; trying LibreOffice if available: $($_.Exception.Message)"
        }
    }

    if (-not (Test-Path -LiteralPath $pdfPath -PathType Leaf)) {
        $libreOffice = Resolve-LibreOffice
        if ($libreOffice) {
            & $libreOffice --headless --convert-to pdf --outdir $testDirectory $docxPath *> $null
            if ($LASTEXITCODE -eq 0 -and (Test-Path -LiteralPath $pdfPath -PathType Leaf)) {
                $converter = "LibreOffice"
            }
        }
    }

    if (-not (Test-Path -LiteralPath $pdfPath -PathType Leaf)) {
        throw "No working DOCX-to-PDF converter was found. Install Microsoft Word or LibreOffice, or use an Agent with an equivalent document renderer."
    }
    $pdfBytes = [IO.File]::ReadAllBytes($pdfPath)
    if ($pdfBytes.Length -lt 5) { throw "The converter output is not a valid PDF." }
    $pdfHeader = [Text.Encoding]::ASCII.GetString($pdfBytes, 0, 5)
    if ($pdfHeader -ne "%PDF-") { throw "The converter output is not a valid PDF." }

    $pdfToPpm = Resolve-PdfToPpm
    if ($pdfToPpm) {
        & $pdfToPpm -png -r 120 $pdfPath $pngPrefix *> $null
        if ($LASTEXITCODE -eq 0) { $renderer = "pdftoppm" }
    }

    $pages = @(Get-ChildItem -LiteralPath $testDirectory -Filter "self-test-page-*.png" -File)
    if ($pages.Count -eq 0) {
        throw "No working PDF-to-PNG renderer was found. Install Poppler/pdftoppm, or use an Agent with an equivalent page renderer."
    }
    foreach ($page in $pages) {
        if (-not (Test-PngSignature -Path $page.FullName)) { throw "A rendered page is not a valid PNG: $($page.Name)" }
    }

    Write-Output "SELF_TEST_OK converter=$converter renderer=$renderer pages=$($pages.Count)"
    exit 0
}
catch {
    Write-Output "SELF_TEST_FAIL"
    Write-Output "- $($_.Exception.Message)"
    exit 1
}
finally {
    if ($KeepArtifacts) {
        Write-Output "SELF_TEST_ARTIFACTS $testDirectory"
    }
    elseif (Test-Path -LiteralPath $testDirectory) {
        $resolvedTempRoot = [IO.Path]::GetFullPath($tempRoot).TrimEnd("\")
        $resolvedTestDirectory = [IO.Path]::GetFullPath($testDirectory)
        if ($resolvedTestDirectory.StartsWith($resolvedTempRoot + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) {
            Remove-Item -LiteralPath $resolvedTestDirectory -Recurse -Force
        }
    }
}
