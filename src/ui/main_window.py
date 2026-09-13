"""Ventana principal de PDF Splitter."""

from __future__ import annotations

import re
import sys
from pathlib import Path

from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QKeySequence
from PySide6.QtUiTools import QUiLoader
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QHeaderView,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QWidget,
)

from core.pdf_splitter import PdfSplitterError, page_count, split_pdf

WINDOWS_RESERVED = {
    "CON", "PRN", "AUX", "NUL", "COM1", "COM2", "COM3", "COM4", "COM5",
    "COM6", "COM7", "COM8", "COM9", "LPT1", "LPT2", "LPT3", "LPT4", "LPT5",
    "LPT6", "LPT7", "LPT8", "LPT9",
}
INVALID_FILENAME = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


class MainWindow(QMainWindow):
    """Controla la interfaz sin mezclarla con el procesamiento del PDF."""

    def __init__(self) -> None:
        super().__init__()
        loader = QUiLoader()
        ui_path = self._resource_path("ui/forms/main_window.ui")
        self._ui = loader.load(str(ui_path), self)
        if self._ui is None:
            raise RuntimeError(f"No se pudo cargar la interfaz: {ui_path}")
        self.txt_pdf = self._widget(QLineEdit, "txtPdf")
        self.txt_destino = self._widget(QLineEdit, "txtDestino")
        self.table = self._widget(QTableWidget, "tblPaginas")
        self.progress = self._widget(QProgressBar, "progressBar")
        self.btn_pdf = self._widget(QPushButton, "btnSeleccionarPdf")
        self.btn_destino = self._widget(QPushButton, "btnDestino")
        self.btn_generate = self._widget(QPushButton, "btnGenerar")
        self.btn_sequence = self._widget(QPushButton, "btnCompletarSecuencia")
        self.status = self._ui.findChild(QWidget, "lblEstado")

        self.pdf_path: Path | None = None
        self.destination: Path | None = None
        self._configure_table()
        self.progress.setValue(0)
        self._ui.setAcceptDrops(True)
        self._ui.installEventFilter(self)
        self.btn_pdf.clicked.connect(self.select_pdf)
        self.btn_destino.clicked.connect(self.select_destination)
        self.btn_generate.clicked.connect(self.generate_pdfs)
        self.btn_sequence.clicked.connect(self.complete_sequence)

    def show(self) -> None:
        """Muestra la ventana cargada desde Qt Designer."""
        self._ui.show()

    @staticmethod
    def _resource_path(relative: str) -> Path:
        root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[1]))
        return root / relative

    def _widget(self, kind: type, name: str):
        widget = self._ui.findChild(kind, name)
        if widget is None:
            raise RuntimeError(f"Falta el control '{name}' en main_window.ui.")
        return widget

    def _set_status(self, message: str) -> None:
        self.status.setProperty("text", message)
        QApplication.processEvents()

    def _configure_table(self) -> None:
        self.table.setColumnCount(2)
        self.table.setHorizontalHeaderLabels(["Página", "Nombre del archivo"])
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.installEventFilter(self)

    def eventFilter(self, watched, event) -> bool:
        if watched is self.table and event.type() == QEvent.KeyPress:
            if event.matches(QKeySequence.StandardKey.Paste):
                self._paste_names()
                return True
        if watched is self._ui and event.type() == QEvent.DragEnter:
            self.dragEnterEvent(event)
            return event.isAccepted()
        if watched is self._ui and event.type() == QEvent.Drop:
            self.dropEvent(event)
            return event.isAccepted()
        return super().eventFilter(watched, event)

    def _paste_names(self) -> None:
        text = QApplication.clipboard().text()
        if not text:
            return
        row = max(0, self.table.currentRow())
        values = [line.split("\t", 1)[0].strip() for line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n")]
        values = [value for value in values if value]
        for offset, value in enumerate(values):
            target = row + offset
            if target >= self.table.rowCount():
                break
            item = self.table.item(target, 1)
            if item:
                item.setText(value)

    def select_pdf(self) -> None:
        file_name, _ = QFileDialog.getOpenFileName(self, "Seleccionar PDF", "", "Archivos PDF (*.pdf)")
        if file_name:
            self.load_pdf(Path(file_name))

    def load_pdf(self, path: Path) -> None:
        self._set_status("Leyendo PDF...")
        try:
            total = page_count(path)
        except PdfSplitterError as error:
            self._error(str(error))
            self._set_status("No se pudo cargar el PDF.")
            return
        self.pdf_path = path
        self.txt_pdf.setText(str(path))
        self.table.setRowCount(total)
        for row in range(total):
            page_item = QTableWidgetItem(str(row + 1))
            page_item.setFlags(page_item.flags() & ~Qt.ItemIsEditable)
            self.table.setItem(row, 0, page_item)
            self.table.setItem(row, 1, QTableWidgetItem())
        self.progress.setValue(0)
        self._set_status(f"PDF cargado. {total} páginas.")
        self.table.setCurrentCell(0, 1)

    def select_destination(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Seleccionar carpeta de destino")
        if folder:
            self.destination = Path(folder)
            self.txt_destino.setText(str(self.destination))
            self._set_status("Carpeta de destino seleccionada.")

    def _names(self) -> list[str] | None:
        names: list[str] = []
        seen: set[str] = set()
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 1)
            name = item.text().strip() if item else ""
            if name.lower().endswith(".pdf"):
                name = name[:-4].strip()
            if not name:
                self._error(f"Debe asignar un nombre a todas las páginas (falta la página {row + 1}).")
                return None
            if INVALID_FILENAME.search(name) or name.endswith((".", " ")) or name.upper() in WINDOWS_RESERVED:
                self._error(f"El nombre '{name}' contiene caracteres no válidos o está reservado por el sistema.")
                return None
            key = name.casefold()
            if key in seen:
                self._error(f"El nombre '{name}' está repetido.")
                return None
            seen.add(key)
            names.append(name)
        return names

    def generate_pdfs(self) -> None:
        if self.pdf_path is None:
            self._error("No se seleccionó ningún PDF.")
            return
        if self.destination is None or not self.destination.is_dir():
            self._error("No se seleccionó una carpeta de destino válida.")
            return
        names = self._names()
        if names is None:
            return
        existing = [f"{name}.pdf" for name in names if (self.destination / f"{name}.pdf").exists()]
        if existing:
            message = "Ya existen estos archivos:\n\n" + "\n".join(existing[:10])
            if len(existing) > 10:
                message += f"\n… y {len(existing) - 10} más."
            message += "\n\n¿Desea reemplazarlos?"
            answer = QMessageBox.question(self, "Confirmar reemplazo", message, QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if answer != QMessageBox.Yes:
                self._set_status("Proceso cancelado.")
                return
        self.progress.setRange(0, len(names))
        self.progress.setValue(0)
        self.btn_generate.setEnabled(False)
        try:
            self._set_status("Generando archivos...")
            def update(done: int, total: int, filename: str) -> None:
                self.progress.setValue(done)
                self._set_status(f"Generando {filename}..." if done < total else f"Generados {total} archivos.")
            created = split_pdf(self.pdf_path, self.destination, names, update)
            self._set_status(f"Proceso finalizado. {len(created)} archivos generados.")
            QMessageBox.information(self, "PDF Splitter", f"Se generaron {len(created)} archivos correctamente.")
        except PdfSplitterError as error:
            self._error(str(error))
            self._set_status("El proceso no pudo finalizar.")
        finally:
            self.btn_generate.setEnabled(True)

    def complete_sequence(self) -> None:
        start_row = self.table.currentRow()
        if start_row < 0 or self.table.currentColumn() != 1:
            start_row = 0
        item = self.table.item(start_row, 1)
        value = item.text().strip() if item else ""
        if not value.isdigit():
            self._error("Seleccione una celda de nombre que contenga el número inicial de la secuencia.")
            return
        populated = [row for row in range(start_row + 1, self.table.rowCount()) if self.table.item(row, 1).text().strip()]
        if populated:
            answer = QMessageBox.question(self, "Completar secuencia", "Hay nombres ya escritos que serán reemplazados. ¿Desea continuar?", QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if answer != QMessageBox.Yes:
                return
        number = int(value)
        width = len(value)
        for row in range(start_row, self.table.rowCount()):
            self.table.item(row, 1).setText(str(number + row - start_row).zfill(width))
        self._set_status("Secuencia completada.")

    def dragEnterEvent(self, event) -> None:
        if event.mimeData().hasUrls() and any(url.toLocalFile().lower().endswith(".pdf") for url in event.mimeData().urls()):
            event.acceptProposedAction()

    def dropEvent(self, event) -> None:
        for url in event.mimeData().urls():
            path = Path(url.toLocalFile())
            if path.suffix.lower() == ".pdf" and path.is_file():
                self.load_pdf(path)
                event.acceptProposedAction()
                return

    def _error(self, message: str) -> None:
        QMessageBox.critical(self, "PDF Splitter", message)
