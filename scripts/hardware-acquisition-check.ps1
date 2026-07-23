[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateSet("DSOX4024A", "DSOX4034A", "DSOX3024A", "DSOX2004A")]
    [string] $Model,

    [Parameter(Mandatory = $true)]
    [ValidateSet("USB", "LAN")]
    [string] $Connection,

    [string] $Resource,

    [switch] $RestoreType,

    [string] $Python = ".\.venv\Scripts\python.exe"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Invoke-Cli {
    param(
        [Parameter(Mandatory = $true)]
        [string[]] $Arguments
    )

    $output = & $Python -m scopes_tool_cli.cli @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Command failed with exit code ${LASTEXITCODE}: $Python -m scopes_tool_cli.cli $($Arguments -join ' ')"
    }
    try {
        $payload = $output | ConvertFrom-Json -ErrorAction Stop
    } catch {
        throw "Command did not return JSON: $Python -m scopes_tool_cli.cli $($Arguments -join ' ')"
    }
    if (-not $payload.ok) {
        throw "Command JSON reported ok=false: $Python -m scopes_tool_cli.cli $($Arguments -join ' ')"
    }
    return $payload
}

if (-not (Get-Command $Python -ErrorAction SilentlyContinue)) {
    throw "Python executable not found: ${Python}"
}

if ([string]::IsNullOrWhiteSpace($Resource)) {
    throw "A live acquisition-check requires explicit -Resource."
}

if ($Connection -eq "LAN" -and $Model -notin @("DSOX4024A", "DSOX4034A")) {
    throw "LAN acquisition-check is not in first-scope validation for ${Model}; use USB for DSOX3024A and DSOX2004A."
}

$preflightScript = Join-Path $PSScriptRoot "preflight-acquisition.ps1"
if (-not (Test-Path -LiteralPath $preflightScript)) {
    throw "Missing preflight script: ${preflightScript}"
}

Write-Host "Running hardware-free preflight for ${Model} before live access."
& $preflightScript -Model $Model -Python $Python
if ($LASTEXITCODE -ne 0) {
    throw "Preflight failed for ${Model}"
}

Write-Host ""
Write-Host "Live acquisition-check target:"
Write-Host "  Model:      ${Model}"
Write-Host "  Connection: ${Connection}"
Write-Host "  Resource:   ${Resource}"
Write-Host ""
Write-Host "This live test changes acquisition settings in sequence:"
Write-Host "  1. acquisition type normal"
Write-Host "  2. acquisition type average, count 16"
Write-Host "  3. acquisition type high_resolution"
Write-Host "  4. acquisition type peak"
if ($RestoreType) {
    Write-Host "After the test, the CLI will attempt to restore the initial acquisition type."
} else {
    Write-Host "By default, the instrument may finish in peak acquisition mode."
}
Write-Host "Please confirm the front-panel acquisition mode/count changes and final state."
[void](Read-Host "Press Enter to start live acquisition-check")

$liveArgs = @(
    "acquisition-check",
    "--live",
    "--resource",
    $Resource,
    "--json",
    "--log-scpi"
)
if ($RestoreType) {
    $liveArgs += "--restore-type"
}

$live = Invoke-Cli -Arguments $liveArgs
if ($live.result.status -ne "completed") {
    throw "Live acquisition-check did not complete: $($live.result.status)"
}

$reportPath = $live.result.report_path
if ([string]::IsNullOrWhiteSpace($reportPath)) {
    throw "Live command JSON did not include result.report_path."
}
if (-not (Test-Path -LiteralPath $reportPath)) {
    throw "Reported live report.json does not exist: ${reportPath}"
}

$summaryPath = Join-Path (Split-Path -Parent $reportPath) "summary.md"
Write-Host "Rendering summary: ${summaryPath}"
$summary = & $Python -m scopes_tool_cli.cli hardware-report $reportPath
if ($LASTEXITCODE -ne 0) {
    throw "hardware-report failed for ${reportPath}"
}
$summary | Set-Content -LiteralPath $summaryPath -Encoding UTF8

Write-Host "Live acquisition-check complete."
Write-Host "Report:  ${reportPath}"
Write-Host "Summary: ${summaryPath}"
