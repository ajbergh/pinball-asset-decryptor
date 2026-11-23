# Launch an extracted SPIKE 2 title and its PAD-patched Visual Pinball table.
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$GameDir,
    [Parameter(Mandatory = $true)][string]$Table,
    [string]$VpxExe,
    [string]$Distro,
    [string]$Python,
    [ValidateRange(1, 3600)][int]$StartupTimeout = 180
)

$ErrorActionPreference = 'Stop'
if (-not $Python) {
    $bundledPython = Join-Path $env:ProgramFiles 'Pinball Asset Decryptor/python/python.exe'
    $Python = if (Test-Path -LiteralPath $bundledPython -PathType Leaf) { $bundledPython } else { 'python.exe' }
}
$launcher = Join-Path $PSScriptRoot 'tools/spike2_emu/vpx/play_spike2.py'
$launchArgs = @('--game-dir', $GameDir, '--table', $Table, '--startup-timeout', $StartupTimeout)
if ($VpxExe) { $launchArgs += @('--vpx-exe', $VpxExe) }
if ($Distro) { $launchArgs += @('--distro', $Distro) }

& $Python $launcher @launchArgs
exit $LASTEXITCODE
