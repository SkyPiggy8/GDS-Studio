$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$workspacePath = [System.IO.Path]::GetFullPath($PSScriptRoot)
$packagePath = [System.IO.Path]::GetFullPath((Join-Path $workspacePath 'dist\GDS Studio'))
if (-not $packagePath.StartsWith($workspacePath + [System.IO.Path]::DirectorySeparatorChar)) { throw 'Invalid package path.' }
$backupPath = Join-Path $workspacePath ('userdata\package-backups\' + (Get-Date -Format 'yyyyMMdd-HHmmss'))
if (Test-Path -LiteralPath $packagePath) {
    New-Item -ItemType Directory -Path $backupPath -Force | Out-Null
    Get-ChildItem -LiteralPath $packagePath | Where-Object { $_.Name -notin @('_internal','GDS Studio.exe','docs','licenses','source','third_party_sources','README.md','LICENSE','LICENSE-DISTRIBUTION.txt','THIRD_PARTY.md') } | ForEach-Object {
        Copy-Item -LiteralPath $_.FullName -Destination $backupPath -Recurse -Force
    }
}
& '.\.venv\Scripts\python.exe' -m PyInstaller --noconfirm --windowed --onedir --name 'GDS Studio' --collect-all gdstk --collect-all klayout --exclude-module PySide6.QtWebEngineCore --exclude-module PySide6.QtWebEngineWidgets --exclude-module PySide6.QtQml main.py
if ($LASTEXITCODE -ne 0) { throw 'Desktop build failed.' }
Copy-Item -LiteralPath 'examples' -Destination 'dist\GDS Studio\examples' -Recurse -Force
Copy-Item -LiteralPath 'user_plugins' -Destination 'dist\GDS Studio\user_plugins' -Recurse -Force
Copy-Item -LiteralPath 'docs' -Destination 'dist\GDS Studio\docs' -Recurse -Force
Copy-Item -LiteralPath 'README.md','THIRD_PARTY.md','LICENSE' -Destination 'dist\GDS Studio' -Force
Copy-Item -LiteralPath 'LICENSE-DISTRIBUTION.txt' -Destination 'dist\GDS Studio' -Force
New-Item -ItemType Directory -Path 'dist\GDS Studio\source' -Force | Out-Null
Copy-Item -LiteralPath 'gds_studio','tests','tools','main.py','pyproject.toml','requirements.txt','requirements-lock.txt','构建桌面版.ps1' -Destination 'dist\GDS Studio\source' -Recurse -Force
if (Test-Path -LiteralPath 'third_party_sources') { Copy-Item -LiteralPath 'third_party_sources' -Destination 'dist\GDS Studio' -Recurse -Force }
if (Test-Path -LiteralPath $backupPath) {
    Get-ChildItem -LiteralPath $backupPath | ForEach-Object { Copy-Item -LiteralPath $_.FullName -Destination $packagePath -Recurse -Force }
}
& '.\.venv\Scripts\python.exe' 'tools\collect_licenses.py' 'dist\GDS Studio\licenses'
if ($LASTEXITCODE -ne 0) { throw 'License collection failed.' }
Write-Host 'Desktop package: dist\GDS Studio\GDS Studio.exe'
