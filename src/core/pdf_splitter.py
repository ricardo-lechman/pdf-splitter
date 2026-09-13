"""Operaciones locales para leer y dividir documentos PDF."""

from collections.abc import Callable, Sequence
from pathlib import Path

from pypdf import PdfReader, PdfWriter


class PdfSplitterError(Exception):
    """Error controlado al procesar un PDF."""


def page_count(pdf_path: str | Path) -> int:
    """Devuelve el número de páginas de un PDF legible y sin contraseña."""
    try:
        reader = PdfReader(str(pdf_path))
        if reader.is_encrypted:
            raise PdfSplitterError("El PDF está protegido con contraseña.")
        return len(reader.pages)
    except PdfSplitterError:
        raise
    except Exception as error:
        raise PdfSplitterError("El PDF no pudo ser leído.") from error


def split_pdf(pdf_path: str | Path, destination: str | Path, names: Sequence[str], progress: Callable[[int, int, str], None] | None = None) -> list[Path]:
    """Crea un PDF por página y devuelve las rutas que se generaron."""
    try:
        reader = PdfReader(str(pdf_path))
        if reader.is_encrypted:
            raise PdfSplitterError("El PDF está protegido con contraseña.")
        if len(reader.pages) != len(names):
            raise PdfSplitterError("La cantidad de nombres no coincide con las páginas.")
        output_dir = Path(destination)
        created: list[Path] = []
        for index, (page, name) in enumerate(zip(reader.pages, names), start=1):
            output_path = output_dir / f"{name}.pdf"
            if progress:
                progress(index - 1, len(names), output_path.name)
            writer = PdfWriter()
            writer.add_page(page)
            with output_path.open("wb") as output_file:
                writer.write(output_file)
            created.append(output_path)
            if progress:
                progress(index, len(names), output_path.name)
        return created
    except PdfSplitterError:
        raise
    except OSError as error:
        raise PdfSplitterError(f"No se pudo guardar el archivo: {error}") from error
    except Exception as error:
        raise PdfSplitterError("No se pudieron generar los PDFs.") from error
