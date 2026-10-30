"""
estudiantes.py — Importa la lista del curso desde Excel o CSV.

Cada colegio exporta las listas de forma distinta (SIMAT, plataforma propia,
una hoja de cálculo hecha a mano...). Por eso:
    1. Leemos el archivo tal cual.
    2. Adivinamos qué columna es el documento y cuál el nombre (por el título).
    3. El docente confirma o cambia esas columnas en pantalla.
    4. Guardamos una versión limpia: estudiantes.csv con documento, nombre, curso
       y "lista" (el N.º de lista: la posición del estudiante en el archivo).

El N.º de lista sirve para la hoja de respuestas "con N.º de lista": allí el
estudiante marca su número (7) en vez de su documento, y el programa busca en
la lista quién es el 7. Por eso el ORDEN de la lista importa.
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


def lista_limpia(tabla: pd.DataFrame, col_documento: str | None, col_nombre: str,
                 col_curso: str | None = None) -> pd.DataFrame:
    """
    Devuelve una tabla con columnas: documento, nombre, curso, lista.

    Cada fila con nombre recibe su N.º de lista (1, 2, 3... en el orden del
    archivo). Si un estudiante no tiene documento (o no se eligió esa columna)
    se le pone "L" + su número ("L07"): así igual se le reconoce en las hojas
    con N.º de lista.
    """
    limpia = pd.DataFrame({
        "documento": (tabla[col_documento].map(normalizar_documento) if col_documento
                      else ""),
        "nombre": tabla[col_nombre].str.strip(),
        "curso": tabla[col_curso].str.strip() if col_curso else "",
    })
    limpia = limpia[(limpia["nombre"] != "") | (limpia["documento"] != "")].reset_index(drop=True)
    limpia["lista"] = [str(i + 1) for i in range(len(limpia))]
    sin_doc = limpia["documento"] == ""
    limpia.loc[sin_doc, "documento"] = "L" + limpia.loc[sin_doc, "lista"].str.zfill(2)
    return limpia.drop_duplicates("documento")


def guardar_estudiantes(examen: Examen, lista: pd.DataFrame) -> None:
    lista.to_csv(examen.archivo_estudiantes, index=False, encoding="utf-8-sig")


def cargar_estudiantes(examen: Examen) -> pd.DataFrame:
    if not examen.archivo_estudiantes.exists():
        return pd.DataFrame(columns=["documento", "nombre", "curso", "lista"])
    lista = pd.read_csv(examen.archivo_estudiantes, dtype=str, encoding="utf-8-sig").fillna("")
    if "lista" not in lista.columns or (lista["lista"] == "").all():
        # Listas guardadas antes de esta función: el N.º es la posición en el archivo
        lista["lista"] = [str(i + 1) for i in range(len(lista))]
    return lista


# ---------------------------------------------------------------------------
# Hojas con N.º de lista: de "lo que se leyó en la hoja" al estudiante
# ---------------------------------------------------------------------------
def documento_por_numero(estudiantes: pd.DataFrame) -> dict[str, str]:
    """{"7": documento del estudiante N.º 7} según la columna "lista"."""
    if estudiantes.empty or "lista" not in estudiantes.columns:
        return {}
    return {normalizar_documento(n): d for n, d in zip(estudiantes["lista"], estudiantes["documento"])
            if normalizar_documento(n)}


def nombres_por_lectura(examen: Examen, estudiantes: pd.DataFrame) -> dict[str, str]:
    """
    {lo que se lee en la hoja: nombre}. En la hoja con documento la clave es el
    documento; en la hoja con N.º de lista, el número ("7").
    """
    if estudiantes.empty:
        return {}
    if examen.por_lista:
        nombres = dict(zip(estudiantes["documento"], estudiantes["nombre"]))
        return {n: nombres.get(d, "") for n, d in documento_por_numero(estudiantes).items()}
    return dict(zip(estudiantes["documento"], estudiantes["nombre"]))
