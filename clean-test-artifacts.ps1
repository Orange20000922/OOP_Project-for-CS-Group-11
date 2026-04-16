[CmdletBinding()]
param(
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"

$scriptPath = $MyInvocation.MyCommand.Path
if (-not $scriptPath) {
    throw "Cannot determine script path."
}

$repoRoot = Split-Path -Parent (Resolve-Path -LiteralPath $scriptPath)
$targetPattern = '^[._](pytest|tmp).*$'

$targets = Get-ChildItem -LiteralPath $repoRoot -Directory -Force |
    Where-Object { $_.Name -match $targetPattern } |
    Sort-Object -Property Name -Unique

if (-not $targets -or $targets.Count -eq 0) {
    Write-Host "No matching test cache or temp directories were found."
    exit 0
}

$mode = if ($DryRun) { "dry-run" } else { "delete" }
Write-Host "Repository root: $repoRoot"
Write-Host "Mode: $mode"

$removedCount = 0

foreach ($target in $targets) {
    $resolvedPath = (Resolve-Path -LiteralPath $target.FullName).Path

    if (-not $resolvedPath.StartsWith($repoRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing to delete a path outside the repository root: $resolvedPath"
    }

    if ($DryRun) {
        Write-Host "[dry-run] $resolvedPath"
        continue
    }

    Remove-Item -LiteralPath $resolvedPath -Recurse -Force
    $removedCount += 1
    Write-Host "[deleted] $resolvedPath"
}

if ($DryRun) {
    Write-Host ("Dry run complete. Matched {0} directories." -f $targets.Count)
} else {
    Write-Host ("Cleanup complete. Removed {0} directories." -f $removedCount)
}
