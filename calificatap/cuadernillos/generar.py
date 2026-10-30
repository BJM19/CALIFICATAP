"""
generar.py — Une todo el Módulo 0:

    banco_preguntas.xlsx ──► leer_banco() ──► armar_formas() ──┬─► cuadernillo_A.pdf, _B.pdf...
                                                               ├─► formas.json (el mapa)
                                                               └─► clave.json (clave de cada forma)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from ..examenes import Examen
from ..reportes.clave import cargar_clave, guardar_clave
from .banco import NOMBRE_BANCO, Banco, leer_banco
from .formas import armar_formas, cargar_mapa, claves_de_formas, guardar_mapa
from .pdf import dibujar_cuadernillo


@dataclass
class ResultadoCuadernillos:
    archivos: dict[str, Path] = field(default_factory=dict)   # {forma: pdf}
    claves: dict[str, dict[str, str]] = field(default_factory=dict)
    semilla: int = 0
    clave_cambio: bool = False      # la clave que había en «Resultados» era distinta


def ruta_banco(examen: Examen) -> Path:
    return examen.carpeta_cuadernillos / NOMBRE_BANCO


def nombre_cuadernillo(forma: str) -> str:
    return f"cuadernillo_{forma}.pdf"


def generar_cuadernillos(examen: Examen, banco: Banco | None = None,
                         barajar_preguntas: bool = True, barajar_opciones: bool = True,
                         nueva_semilla: bool = False, tiempo: str = "",
                         pagina_por_materia: bool = True) -> ResultadoCuadernillos:
    """
    Crea un cuadernillo por forma y guarda la clave de cada una.
    Si ya se habían generado, se usa la MISMA semilla (los mismos órdenes), salvo que
    se pida 'nueva_semilla'. Así, corregir un error de digitación en el banco y
    volver a generar no cambia el orden de lo que ya se imprimió.
    """
    if banco is None:
        banco = leer_banco(examen, ruta_banco(examen))
    if not banco.completo:
        raise ValueError("El banco tiene problemas:\n" + "\n".join(banco.problemas[:10]))

    anterior = cargar_mapa(examen)
    semilla = None if nueva_semilla else anterior.get("semilla")
    formas, semilla = armar_formas(examen, banco, barajar_preguntas, barajar_opciones, semilla)

    carpeta = examen.carpeta_cuadernillos
    carpeta.mkdir(parents=True, exist_ok=True)
    for viejo in carpeta.glob("cuadernillo_*.pdf"):       # por si antes había más formas
        if viejo.stem.split("_")[-1] not in formas:
            viejo.unlink()
    resultado = ResultadoCuadernillos(semilla=semilla)
    con_formas = bool(examen.letras_formas)
    for letra, lista in formas.items():
        ruta = carpeta / nombre_cuadernillo(letra)
        dibujar_cuadernillo(examen, banco, letra, lista, ruta, tiempo, mostrar_forma=con_formas,
                            pagina_por_materia=pagina_por_materia)
        resultado.archivos[letra] = ruta

    guardar_mapa(examen, formas, semilla, barajar_preguntas, barajar_opciones,
                 tiempo=tiempo, pagina_por_materia=pagina_por_materia)
    resultado.claves = claves_de_formas(formas, banco)
    previa = cargar_clave(examen)
    resultado.clave_cambio = bool(previa) and any(previa.get(f) and previa.get(f) != c
                                                   for f, c in resultado.claves.items())
    guardar_clave(examen, resultado.claves)
    return resultado
