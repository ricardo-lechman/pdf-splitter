# Ejecutar desde PowerShell en Windows: .\build_windows.ps1
$ErrorActionPreference = "Stop"
& .\.venv\Scripts\python.exe -m PyInstaller --noconfirm --clean --windowed --onefile --name "PDF-Splitter" --add-data "src/ui/forms/main_window.ui;ui/forms" src/main.py
Write-Host "Ejecutable creado: dist\PDF-Splitter.exe"
