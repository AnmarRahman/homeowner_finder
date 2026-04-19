param(
    [string]$PythonPath = ".\.venv\Scripts\python.exe"
)

if (-not (Test-Path $PythonPath)) {
    Write-Error "Python executable not found at $PythonPath"
    exit 1
}

& $PythonPath -m pip install pyinstaller
if ($LASTEXITCODE -ne 0) {
    Write-Error "Failed to install pyinstaller."
    exit 1
}

& $PythonPath -m PyInstaller --noconfirm --onefile --windowed --name TrustBridgeLeadBuilder run_gui.py
if ($LASTEXITCODE -ne 0) {
    Write-Error "PyInstaller build failed."
    exit 1
}

Write-Host "Build completed."
Write-Host "Executable: dist\\TrustBridgeLeadBuilder.exe"
