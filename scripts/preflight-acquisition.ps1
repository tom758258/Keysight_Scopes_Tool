[CmdletBinding()]
param(
    [ValidateSet("DSOX4024A", "DSOX4034A", "DSOX3024A", "DSOX2004A")]
    [string[]] $Model = @("DSOX4024A", "DSOX4034A", "DSOX3024A", "DSOX2004A"),

    [string] $Python = ".\.venv\Scripts\python.exe",

    [string] $OutputRoot = ".tmp_tests\acquisition_preflight"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Invoke-Cli {
    param(
        [Parameter(Mandatory = $true)]
        [string[]] $Arguments
    )

    & $Python -m keysight_scope.cli @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Command failed with exit code ${LASTEXITCODE}: $Python -m keysight_scope.cli $($Arguments -join ' ')"
    }
}

function Remove-ModelOutput {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Root,

        [Parameter(Mandatory = $true)]
        [string] $Path
    )

    New-Item -ItemType Directory -Path $Root -Force | Out-Null
    $rootPath = (Resolve-Path -LiteralPath $Root).Path

    if (Test-Path -LiteralPath $Path) {
        $targetPath = (Resolve-Path -LiteralPath $Path).Path
        if (-not $targetPath.StartsWith($rootPath + [System.IO.Path]::DirectorySeparatorChar)) {
            throw "Refusing to remove output outside ${rootPath}: ${targetPath}"
        }
        Remove-Item -LiteralPath $targetPath -Recurse -Force
    }
}

if (-not (Get-Command $Python -ErrorAction SilentlyContinue)) {
    throw "Python executable not found: ${Python}"
}

foreach ($targetModel in $Model) {
    $outputDir = Join-Path $OutputRoot $targetModel
    $reportPath = Join-Path $outputDir "report.json"
    $summaryPath = Join-Path $outputDir "summary.md"

    Write-Host "== Acquisition preflight: ${targetModel} =="
    Write-Host "Dry-run: no VISA backend will be opened."
    Invoke-Cli -Arguments @(
        "acquisition-check",
        "--dry-run",
        "--json",
        "--model",
        $targetModel,
        "--output-dir",
        $outputDir
    )

    Remove-ModelOutput -Root $OutputRoot -Path $outputDir

    Write-Host "Simulate: writing ${outputDir}"
    Invoke-Cli -Arguments @(
        "acquisition-check",
        "--simulate",
        "--json",
        "--model",
        $targetModel,
        "--output-dir",
        $outputDir
    )

    if (-not (Test-Path -LiteralPath $reportPath)) {
        throw "Expected report was not created: ${reportPath}"
    }

    Write-Host "Rendering summary: ${summaryPath}"
    $summary = & $Python -m keysight_scope.cli hardware-report $reportPath
    if ($LASTEXITCODE -ne 0) {
        throw "hardware-report failed for ${reportPath}"
    }
    $summary | Set-Content -LiteralPath $summaryPath -Encoding UTF8

    Write-Host "Preflight passed: ${targetModel}"
}
