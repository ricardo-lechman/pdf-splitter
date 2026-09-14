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
    QButtonGroup,
    QFileDialog,
    QHeaderView,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QRadioButton,
    QTableWidget,
    QTableWidgetItem,
    QWidget,
)

from core.pdf_splitter import PdfSplitterError, merge_pdfs, page_count, split_pdf

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
        self.rdo_correlativos = self._widget(QRadioButton, "rdoCorrelativos")
        self.rdo_lista_manual = self._widget(QRadioButton, "rdoListaManual")
        self.txt_inicio = self._widget(QLineEdit, "txtInicioSecuencia")
        self.txt_lista = self._widget(QLineEdit, "txtListaManual")
        self.btn_aplicar_lista = self._widget(QPushButton, "btnAplicarLista")
        self.btn_select_merge = self._widget(QPushButton, "btnSeleccionarParaUnir")
        self.btn_merge = self._widget(QPushButton, "btnUnirPdfs")
        self.merge_label = self._ui.findChild(QWidget, "lblUnirArchivos")
        self.status = self._ui.findChild(QWidget, "lblEstado")

        self.pdf_path: Path | None = None
        self.destination: Path | None = None
        self.merge_paths: list[Path] = []
        self.assignment_mode = QButtonGroup(self)
        self.assignment_mode.addButton(self.rdo_correlativos)
        self.assignment_mode.addButton(self.rdo_lista_manual)
        self._configure_table()
        self.progress.setValue(0)
        self._ui.setAcceptDrops(True)
        self._ui.installEventFilter(self)
        self.btn_pdf.clicked.connect(self.select_pdf)
        self.btn_destino.clicked.connect(self.select_destination)
        self.btn_generate.clicked.connect(self.generate_pdfs)
        self.btn_sequence.clicked.connect(self.complete_sequence)
        self.btn_aplicar_lista.clicked.connect(self.apply_manual_list)
        self.btn_select_merge.clicked.connect(self.select_pdfs_to_merge)
        self.btn_merge.clicked.connect(self.merge_selected_pdfs)

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
        self.rdo_correlativos.setChecked(True)
        if self.table.rowCount() == 0:
            self._error("Primero seleccione un PDF para cargar sus páginas.")
            return
        value = self.txt_inicio.text().strip()
        if not value.isdigit():
            self._error("Ingrese un número inicial para la secuencia correlativa.")
            return
        populated = [row for row in range(self.table.rowCount()) if self.table.item(row, 1).text().strip()]
        if populated:
            answer = QMessageBox.question(self, "Completar secuencia", "Hay nombres ya escritos que serán reemplazados. ¿Desea continuar?", QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if answer != QMessageBox.Yes:
                return
        number = int(value)
        width = len(value)
        for row in range(self.table.rowCount()):
            self.table.item(row, 1).setText(str(number + row).zfill(width))
        self._set_status("Secuencia completada.")

    def apply_manual_list(self) -> None:
        """Aplica una lista de nombres separados por punto y coma a la tabla."""
        self.rdo_lista_manual.setChecked(True)
        if self.table.rowCount() == 0:
            self._error("Primero seleccione un PDF para cargar sus páginas.")
            return
        raw_values = self.txt_lista.text().split(";")
        values = [value.strip() for value in raw_values]
        if not self.txt_lista.text().strip() or any(not value for value in values):
            self._error("Ingrese nombres separados por ';' sin valores vacíos.")
            return
        if len(values) > self.table.rowCount():
            self._error(f"La lista tiene {len(values)} nombres, pero el PDF solo tiene {self.table.rowCount()} páginas.")
            return
        for row in range(self.table.rowCount()):
            self.table.item(row, 1).setText(values[row] if row < len(values) else "")
        if len(values) < self.table.rowCount():
            self._set_status(f"Lista aplicada: {len(values)} nombres. Faltan {self.table.rowCount() - len(values)} por completar.")
        else:
            self._set_status("Lista manual aplicada.")

    def select_pdfs_to_merge(self) -> None:
        files, _ = QFileDialog.getOpenFileNames(self, "Seleccionar PDFs para unir", "", "Archivos PDF (*.pdf)")
        if not files:
            return
        self.merge_paths = [Path(file_name) for file_name in files]
        preview = ", ".join(path.name for path in self.merge_paths[:3])
        if len(self.merge_paths) > 3:
            preview += f" y {len(self.merge_paths) - 3} más"
        self.merge_label.setProperty("text", f"{len(self.merge_paths)} archivos seleccionados: {preview}")
        self._set_status(f"{len(self.merge_paths)} PDFs preparados para unir.")

    def merge_selected_pdfs(self) -> None:
        if not self.merge_paths:
            self._error("Seleccione los PDFs que desea unir.")
            return
        default_name = "PDF_unido.pdf"
        file_name, _ = QFileDialog.getSaveFileName(self, "Guardar PDF unido", default_name, "Archivos PDF (*.pdf)")
        if not file_name:
            return
        output = Path(file_name)
        if output.suffix.lower() != ".pdf":
            output = output.with_suffix(".pdf")
        if output.exists():
            answer = QMessageBox.question(self, "Confirmar reemplazo", f"El archivo {output.name} ya existe. ¿Desea reemplazarlo?", QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if answer != QMessageBox.Yes:
                return
        if any(path.resolve() == output.resolve() for path in self.merge_paths):
            self._error("El archivo de salida no puede ser uno de los PDFs seleccionados.")
            return
        try:
            self._set_status("Uniendo PDFs...")
            result = merge_pdfs(self.merge_paths, output)
            self._set_status(f"PDF unido creado: {result.name}")
            QMessageBox.information(self, "PDF Splitter", f"PDF unido creado correctamente:\n{result}")
        except PdfSplitterError as error:
            self._error(str(error))
            self._set_status("No se pudieron unir los PDFs.")

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
