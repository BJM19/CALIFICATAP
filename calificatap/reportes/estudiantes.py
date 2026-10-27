"""
estudiantes.py — Importa la lista del curso desde Excel o CSV.

Cada colegio exporta las listas de forma distinta (SIMAT, plataforma propia,
una hoja de cálculo hecha a mano...). Por eso:
    1. Leemos el archivo tal cual.
    2. Adivinamos qué columna es el documento y cuál el nombre (por el título).
    3. El docente confirma o cambia esas columnas en pantalla.
    4. Guardamos una versión limpia: estudiantes.csv con documento, nombre, curso.
"""

from __future__ import annotations

import unicodedata
from pathlib import Path

import pandas as pd

from ..examenes import Examen
from ..lector.hojas import normalizar_documento


def leer_tabla(ruta: str | Path) -> pd.DataFrame:
    """Lee un Excel (.xlsx/.xls) o un CSV (con coma o punto y coma) como texto."""
    ruta = Path(ruta)
    if ruta.suffix.lower() in (".xlsx", ".xlsm", ".xls"):
        tabla = pd.read_excel(ruta, dtype=str)
    else:
        # sep=None: pandas adivina si el separador es coma, punto y coma o tabulador
        tabla = pd.read_csv(ruta, dtype=str, sep=None, engine="python", encoding="utf-8-sig")
    tabla.columns = [str(c).strip() for c in tabla.columns]
    return tabla.dropna(how="all").fillna("")


def _sin_tildes(texto: str) -> str:
    return unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode().lower()


def adivinar_columnas(tabla: pd.DataFrame) -> dict[str, str | None]:
    """Busca las columnas por palabras clave en el título."""
    pistas = {
        "documento": ["documento", "identificacion", "doc", "cedula", "tarjeta", "nuip"],
        "nombre": ["nombre", "estudiante", "alumno", "apellido"],
        "curso": ["curso", "grupo", "grado", "seccion"],
    }
    encontradas: dict[str, str | None] = {}
    for campo, palabras in pistas.items():
        encontradas[campo] = next(
            (c for p in palabras for c in tabla.columns if p in _sin_tildes(c)), None)
    # Si no hay título de documento, la primera columna que sea casi toda de números
    if encontradas["documento"] is None:
        for c in tabla.columns:
            if tabla[c].str.fullmatch(r"\s*\d{5,}\s*").mean() > 0.8:
                encontradas["documento"] = c
                break
    return encontradas


def lista_limpia(tabla: pd.DataFrame, col_documento: str, col_nombre: str,
                 col_curso: str | None = None) -> pd.DataFrame:
    """Devuelve una tabla con columnas: documento, nombre, curso."""
    limpia = pd.DataFrame({
        "documento": tabla[col_documento].map(normalizar_documento),
        "nombre": tabla[col_nombre].str.strip(),
        "curso": tabla[col_curso].str.strip() if col_curso else "",
    })
    return limpia[limpia["documento"] != ""].drop_duplicates("documento")


def guardar_estudiantes(examen: Examen, lista: pd.DataFrame) -> None:
    lista.to_csv(examen.archivo_estudiantes, index=False, encoding="utf-8-sig")


def cargar_estudiantes(examen: Examen) -> pd.DataFrame:
    if not examen.archivo_estudiantes.exists():
        return pd.DataFrame(columns=["documento", "nombre", "curso"])
    return pd.read_csv(examen.archivo_estudiantes, dtype=str, encoding="utf-8-sig").fillna("")
