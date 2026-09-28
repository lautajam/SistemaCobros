"""
pdf_utils.py
------------
Motor de plantillas (Jinja2) + conversión HTML -> PDF (wkhtmltopdf vía pdfkit).

Este módulo NO conoce reglas de negocio (números de boleto, clientes, etc.):
solo sabe cómo tomar una plantilla HTML + un diccionario de datos y producir
un PDF, y cómo armar nombres de archivo normalizados. La lógica de negocio
vive en documentos.py.
"""

import os
import re
import shutil
import unicodedata

import jinja2
import pdfkit

from . import formatos

# Rutas donde el instalador oficial de wkhtmltopdf suele dejar el ejecutable,
# por si no quedó agregado al PATH del sistema (muy común en Windows).
_RUTAS_COMUNES_WKHTMLTOPDF = [
    r"C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe",
    r"C:\Program Files (x86)\wkhtmltopdf\bin\wkhtmltopdf.exe",
    "/usr/local/bin/wkhtmltopdf",
    "/usr/bin/wkhtmltopdf",
    "/opt/homebrew/bin/wkhtmltopdf",
]

MENSAJE_WKHTMLTOPDF_NO_ENCONTRADO = (
    "No se encontró el programa 'wkhtmltopdf', necesario para generar los PDF.\n\n"
    "Este programa NO se instala con 'pip install' (pdfkit es solo un conector): "
    "hay que instalarlo aparte:\n"
    "  - Windows/macOS: descargarlo de https://wkhtmltopdf.org/downloads.html "
    "e instalarlo (aceptar las opciones por defecto).\n"
    "  - Debian/Ubuntu: sudo apt-get install wkhtmltopdf\n"
    "  - Fedora: sudo dnf install wkhtmltopdf\n\n"
    "Después de instalarlo, CERRÁ Y VOLVÉ A ABRIR la terminal (o reiniciá el "
    "equipo) para que el sistema reconozca el programa, y volvé a ejecutar "
    "'python run.py'.\n\n"
    "Si ya lo instalaste y sigue sin encontrarlo, copiá la ruta completa al "
    "archivo wkhtmltopdf.exe y definila como variable de entorno "
    "WKHTMLTOPDF_PATH antes de iniciar la app, por ejemplo en Windows (CMD):\n"
    '  set WKHTMLTOPDF_PATH=C:\\Program Files\\wkhtmltopdf\\bin\\wkhtmltopdf.exe\n'
    "  python run.py"
)


def _buscar_wkhtmltopdf():
    """Intenta ubicar el ejecutable de wkhtmltopdf en, por orden:
    1) la variable de entorno WKHTMLTOPDF_PATH,
    2) el PATH del sistema,
    3) ubicaciones típicas de instalación (sobre todo en Windows).
    Devuelve la ruta si la encuentra, o None."""
    desde_env = os.environ.get("WKHTMLTOPDF_PATH")
    if desde_env and os.path.isfile(desde_env):
        return desde_env

    desde_path = shutil.which("wkhtmltopdf") or shutil.which("wkhtmltopdf.exe")
    if desde_path:
        return desde_path

    for ruta in _RUTAS_COMUNES_WKHTMLTOPDF:
        if os.path.isfile(ruta):
            return ruta

    return None


def normalizar_nombre_archivo(texto: str) -> str:
    """Convierte un nombre de cliente en algo apto para un nombre de archivo:
    sin tildes, sin espacios (reemplazados por '_') y sin caracteres
    especiales. El nombre original en clientes.csv NUNCA se modifica; esta
    función solo se usa para construir el nombre del PDF.
    """
    texto = (texto or "cliente").strip()
    # Quitar tildes/diacríticos (Pérez -> Perez)
    descompuesto = unicodedata.normalize("NFKD", texto)
    sin_tildes = "".join(c for c in descompuesto if not unicodedata.combining(c))
    # Espacios -> guion bajo
    con_guiones = re.sub(r"\s+", "_", sin_tildes)
    # Quitar cualquier caracter no alfanumérico salvo '_' y '-'
    limpio = re.sub(r"[^A-Za-z0-9_\-]", "", con_guiones)
    limpio = re.sub(r"_+", "_", limpio).strip("_-")
    return limpio or "cliente"


def nombre_pdf_boleto(fecha_ddmmyyyy: str, nombre_cliente: str, numero: str) -> str:
    return f"boleto_recepcion_{fecha_ddmmyyyy}_{normalizar_nombre_archivo(nombre_cliente)}_{numero}.pdf"


def nombre_pdf_recibo(fecha_ddmmyyyy: str, nombre_cliente: str, numero: str) -> str:
    return f"recibo_{fecha_ddmmyyyy}_{normalizar_nombre_archivo(nombre_cliente)}_{numero}.pdf"


def unique_path(path: str) -> str:
    """Si `path` ya existe, agrega _1, _2, ... para no sobrescribirlo
    accidentalmente (usado para los documentos en blanco)."""
    if not os.path.exists(path):
        return path
    base, ext = os.path.splitext(path)
    i = 1
    while True:
        candidato = f"{base}_{i}{ext}"
        if not os.path.exists(candidato):
            return candidato
        i += 1


def _blanco_o_valor(valor, largo=18):
    """Filtro Jinja: si el valor está vacío, dibuja una línea para completar
    a mano (usado en los documentos en blanco y en campos opcionales)."""
    if valor:
        return valor
    return "_" * largo


def _get_env(template_dir: str) -> jinja2.Environment:
    env = jinja2.Environment(
        loader=jinja2.FileSystemLoader(template_dir),
        autoescape=jinja2.select_autoescape(["html"]),
    )
    env.filters["blanco"] = _blanco_o_valor
    env.filters["pesos"] = formatos.pesos
    return env


def render_html_template(template_dir: str, template_name: str, contexto: dict) -> str:
    env = _get_env(template_dir)
    plantilla = env.get_template(template_name)
    return plantilla.render(**contexto)


def _wkhtmltopdf_options():
    return {
        "page-size": "A4",
        "margin-top": "12mm",
        "margin-bottom": "12mm",
        "margin-left": "12mm",
        "margin-right": "12mm",
        "encoding": "UTF-8",
        "quiet": "",
        "enable-local-file-access": "",
    }


def html_to_pdf(html: str, output_path: str) -> None:
    directorio = os.path.dirname(output_path)
    if directorio:
        os.makedirs(directorio, exist_ok=True)

    ruta_wkhtmltopdf = _buscar_wkhtmltopdf()
    if not ruta_wkhtmltopdf:
        raise RuntimeError(MENSAJE_WKHTMLTOPDF_NO_ENCONTRADO)

    configuracion = pdfkit.configuration(wkhtmltopdf=ruta_wkhtmltopdf)
    pdfkit.from_string(html, output_path, options=_wkhtmltopdf_options(), configuration=configuracion)
