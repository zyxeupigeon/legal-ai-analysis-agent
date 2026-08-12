param(
    [ValidateSet("auto", "claude", "opencode", "codex", "gemini")]
    [string]$Agent = "auto",
    [switch]$CheckOnly,
    [switch]$SelfTest
)

$ErrorActionPreference = "Stop"
$RepoRoot = (Resolve-Path -LiteralPath (Split-Path -Parent $PSScriptRoot)).Path
Set-Location $RepoRoot
$env:LEGAL_AI_PROJECT_ROOT = $RepoRoot
$env:LEGAL_AI_OUTPUT_ROOT = Join-Path $RepoRoot "agent_outputs"
$env:LEGAL_AI_PROTOCOL_ID = "portable-agent-0.4"

function Resolve-AgentLauncher([string]$Name) {
    $command = Get-Command $Name -ErrorAction SilentlyContinue
    if (-not $command) {
        return $null
    }

    $source = $command.Source
    if ($source -and $source.EndsWith(".ps1", [StringComparison]::OrdinalIgnoreCase)) {
        $cmdSibling = [IO.Path]::ChangeExtension($source, ".cmd")
        if (Test-Path -LiteralPath $cmdSibling) {
            $source = $cmdSibling
        }
    }
    try {
        & $source --version *> $null
        if ($LASTEXITCODE -ne 0) {
            return $null
        }
    }
    catch {
        return $null
    }
    return $source
}

Write-Host "Legal AI Analysis Project - Agent launcher" -ForegroundColor Cyan
Write-Host "Project root: $RepoRoot"
Write-Host "Output root: $env:LEGAL_AI_OUTPUT_ROOT"
& powershell.exe -NoProfile -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot "check_agent_workspace.ps1")
if ($LASTEXITCODE -ne 0) {
    throw "Workspace preflight failed. Agent launch stopped."
}

if ($CheckOnly -and $SelfTest) {
    throw "Choose either -CheckOnly or -SelfTest, not both."
}
if ($SelfTest) {
    & powershell.exe -NoProfile -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot "self_test_document_pipeline.ps1")
    exit $LASTEXITCODE
}

$launchers = [ordered]@{}
foreach ($name in @("claude", "opencode", "codex", "gemini")) {
    $launchers[$name] = Resolve-AgentLauncher $name
}

Write-Host ""
Write-Host "Detected agents:"
foreach ($item in $launchers.GetEnumerator()) {
    $state = if ($item.Value) { "available" } else { "not installed" }
    Write-Host ("- {0}: {1}" -f $item.Key, $state)
}

if ($CheckOnly) {
    Write-Host "AGENT_LAUNCH_CHECK_OK"
    exit 0
}

$selected = $Agent
if ($selected -eq "auto") {
    $selected = @("claude", "opencode", "codex", "gemini") |
        Where-Object { $launchers[$_] } |
        Select-Object -First 1
}
if (-not $selected -or -not $launchers[$selected]) {
    throw "No supported Agent launcher was found. Install and sign in to Claude Code, OpenCode, Codex CLI, or Gemini CLI."
}

Write-Host ""
Write-Host "Launching: $selected" -ForegroundColor Green
Write-Host "This session is bound to: $env:LEGAL_AI_PROJECT_ROOT"
Write-Host "After the Agent opens, ask it to read PROJECT_AGENT_PROTOCOL.md, allocate a task workspace, and analyze your legal AI product."
Write-Host ""

if ($selected -eq "opencode") {
    & $launchers[$selected] $RepoRoot
}
else {
    & $launchers[$selected]
}
exit $LASTEXITCODE
