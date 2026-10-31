param([Parameter(ValueFromRemainingArguments=$true)][string[]]$PioArgs)
$ErrorActionPreference = 'Stop'
# ESP-IDF needs a path without spaces. Reuse the existing local home alias.
$expectedRoot = [Environment]::GetFolderPath('UserProfile')
$mapping = @(& subst) | Where-Object { $_ -match '^V:\\: => ' }
$existing = ($mapping -replace '^V:\\: => ', '' | Out-String).Trim().TrimEnd('\')
if (Test-Path 'V:\') {
    if ($existing -ne $expectedRoot.TrimEnd('\')) { throw 'V: is in use by another location; choose a free alias before building.' }
} else {
    & subst V: $expectedRoot
    if ($LASTEXITCODE -ne 0) { throw 'Could not create V: build alias.' }
}
if (-not $PSScriptRoot.StartsWith($expectedRoot + '\', [StringComparison]::OrdinalIgnoreCase)) {
    throw 'Place this project under your Windows user folder, or configure a separate space-free build path.'
}
$projectPath = 'V:' + $PSScriptRoot.Substring($expectedRoot.Length)
$env:PLATFORMIO_CORE_DIR = 'V:/.platformio'
$idfPython = 'V:/.platformio/penv/.espidf-5.4.2/Scripts/python.exe'
if (Test-Path -LiteralPath $idfPython) {
    $version = & $idfPython -c "import importlib.metadata; print(importlib.metadata.version('esp-idf-kconfig'))"
    if ($version -ne '2.5.4') {
        & $idfPython -m pip install 'esp-idf-kconfig==2.5.4'
        if ($LASTEXITCODE -ne 0) { throw 'Kconfig dependency setup failed.' }
    }
}
& 'V:/.platformio/penv/Scripts/platformio.exe' run -d $projectPath @PioArgs
exit $LASTEXITCODE
