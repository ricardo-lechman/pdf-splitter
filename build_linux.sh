#!/usr/bin/env bash
# Ejecutar en Linux: bash build_linux.sh
set -euo pipefail
python3 -m PyInstaller --noconfirm --clean --windowed --onefile --name PDF-Splitter --add-data "src/ui/forms/main_window.ui:ui/forms" src/main.py
echo "Ejecutable creado: dist/PDF-Splitter"
