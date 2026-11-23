# Launch a prepared SPIKE 2 title and its PAD-patched Visual Pinball table.
[CmdletBinding(DefaultParameterSetName = 'GameDir')]
param(
    [Parameter(Mandatory = $true, ParameterSetName = 'GameDir')][string]$GameDir,
    [Parameter(Mandatory = $true, ParameterSetName = 'Card')][string]$Card,
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
$launchArgs = @('--table', $Table, '--startup-timeout', $StartupTimeout)
if ($Card) { $launchArgs += @('--card', $Card) }
else { $launchArgs += @('--game-dir', $GameDir) }
if ($VpxExe) { $launchArgs += @('--vpx-exe', $VpxExe) }
if ($Distro) { $launchArgs += @('--distro', $Distro) }

& $Python $launcher @launchArgs
exit $LASTEXITCODE
