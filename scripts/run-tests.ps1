[CmdletBinding(PositionalBinding = $false)]
param(
    [string] $Python = ".\.venv\Scripts\python.exe",

    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]] $PytestArguments = @()
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

if (-not (Get-Command $Python -ErrorAction SilentlyContinue)) {
    throw "Python executable not found: ${Python}"
}

foreach ($argument in $PytestArguments) {
    if ($argument -eq "--basetemp" -or $argument.StartsWith("--basetemp=")) {
        throw "Do not pass --basetemp. This script creates an isolated pytest temporary directory."
    }
}

$tempRoot = [System.IO.Path]::GetTempPath()
$tempPath = Join-Path $tempRoot ("scopes-tool-pytest-{0}" -f ([guid]::NewGuid().ToString("N")))
$exitCode = 1

Write-Host "Pytest temporary directory: ${tempPath}"

try {
    & $Python -m pytest -q "--basetemp=${tempPath}" @PytestArguments
    $exitCode = $LASTEXITCODE
} catch {
    Write-Error -ErrorRecord $_ -ErrorAction Continue
    $exitCode = 1
} finally {
    if ($exitCode -eq 0 -and (Test-Path -LiteralPath $tempPath)) {
        try {
            Remove-Item -LiteralPath $tempPath -Recurse -Force
        } catch {
            Write-Error "Tests passed, but the pytest temporary directory could not be removed: ${tempPath}" -ErrorAction Continue
            Write-Error -ErrorRecord $_ -ErrorAction Continue
            $exitCode = 1
        }
    }
}

if ($exitCode -ne 0 -and (Test-Path -LiteralPath $tempPath)) {
    Write-Host "Preserved pytest temporary directory: ${tempPath}"
}

exit $exitCode
