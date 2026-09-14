# PDF Splitter — instalación en Ubuntu

Estas instrucciones permiten preparar la aplicación en una computadora con
Ubuntu usando la carpeta copiada desde un pendrive. La primera preparación
requiere conexión a Internet para descargar las dependencias. Luego el
ejecutable funciona sin Internet.

## 1. Copiar el proyecto

Copie la carpeta completa `aplicacion pdf pyton` desde el pendrive a una
carpeta personal, por ejemplo `Documentos`. No se recomienda compilar ni usar
la aplicación directamente desde el pendrive.

Abra una Terminal dentro de la carpeta copiada. Una forma sencilla es abrir la
carpeta en el explorador de archivos, hacer clic derecho en un espacio vacío y
elegir **Abrir en una terminal**.

## 2. Instalar Python y herramientas necesarias

Ejecute estos comandos en la Terminal:

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip
```

## 3. Crear el entorno de la aplicación

Desde la carpeta del proyecto, ejecute:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install PySide6==6.11.1 pypdf==6.14.2 pyinstaller==6.19.0
```

La Terminal debe mostrar `(.venv)` al inicio de la línea mientras el entorno
esté activado.

## 4. Probar la aplicación

```bash
python src/main.py
```

Seleccione un PDF, una carpeta de destino, escriba o pegue los nombres y
presione **Generar PDFs**.

Para cerrar la aplicación, cierre su ventana. Para salir del entorno virtual,
ejecute:

```bash
deactivate
```

## 5. Crear el ejecutable portable para Linux

Active otra vez el entorno virtual y ejecute el script:

```bash
source .venv/bin/activate
bash build_linux.sh
chmod +x dist/PDF-Splitter
```

El resultado queda en:

```text
dist/PDF-Splitter
```

Puede copiar ese único archivo a un pendrive. En otra computadora Linux
compatible, cópielo al disco, dele permiso de ejecución si hace falta y ábralo:

```bash
chmod +x PDF-Splitter
./PDF-Splitter
```

El ejecutable no requiere Python ni Internet, pero debe generarse en Linux.
Para una mejor compatibilidad, genere el ejecutable en la versión más antigua
de Ubuntu donde se vaya a utilizar.

## Si aparece un error relacionado con Qt

En algunas instalaciones mínimas de Ubuntu puede hacer falta esta biblioteca:

```bash
sudo apt install -y libegl1
```

Después vuelva a probar `python src/main.py`.
