"""
formas.py — Arma las formas A, B, C... a partir del banco y calcula sus claves.

    Forma A  = el banco tal cual (el orden en que el docente escribió las preguntas).
    Forma B… = el programa cambia, DENTRO DE CADA MATERIA:
                 - el orden de las preguntas (las de un mismo contexto se mueven juntas), y/o
                 - el orden de las opciones (salvo las marcadas como «Fija»).

Las materias no cambian de lugar: la hoja de respuestas es la misma para todas
las formas (Matemáticas siempre en las preguntas 1 a 25, por ejemplo).

Todo lo que se hizo queda en formas.json, el "mapa" de cada forma:

    {"semilla": 4821, "barajar_preguntas": true, "barajar_opciones": true,
     "formas": {"B": {"MAT_01": {"original": "MAT_07", "opciones": "CADB"}, ...}}}

    → la pregunta 1 de la forma B es la 7 del banco; su opción A es la C del
      banco, su B es la A, su C es la D y su D es la B.

Con ese mapa:
    - la clave de cada forma se calcula sola (no hay que digitarla);
    - en «Resultados» se pueden juntar las formas y ver cada pregunta UNA vez.
"""

from __future__ import annotations

import json
import random
from dataclasses import dataclass
from datetime import datetime

from ..examenes import Examen
from .banco import LETRAS, Banco

NOMBRE_MAPA = "formas.json"


@dataclass
class PreguntaEnForma:
    etiqueta: str        # posición en la forma (MAT_01 = la que se responde en la casilla 1)
    original: str        # la pregunta del banco que va ahí
    opciones: str        # "CADB": qué opción del banco va en A, B, C, D de esta forma


def _bloques(etiquetas: list[str], banco: Banco) -> list[list[str]]:
    """Agrupa las preguntas seguidas que comparten contexto (se mueven juntas)."""
    bloques: list[list[str]] = []
    for e in etiquetas:
        ctx = banco.preguntas[e].contexto
        if ctx and bloques and banco.preguntas[bloques[-1][-1]].contexto == ctx:
            bloques[-1].append(e)
        else:
            bloques.append([e])
    return bloques


def armar_formas(examen: Examen, banco: Banco, barajar_preguntas: bool = True,
                 barajar_opciones: bool = True, semilla: int | None = None
                 ) -> tuple[dict[str, list[PreguntaEnForma]], int]:
    """
    Devuelve ({forma: [PreguntaEnForma en el orden de la hoja de respuestas]}, semilla).
    Con la MISMA semilla y el mismo banco, el resultado es siempre el mismo:
    así se puede volver a generar sin cambiar los cuadernillos ya impresos.
    """
    if semilla is None:
        semilla = random.randint(1000, 999_999)
    formas = {}
    for k, letra in enumerate(examen.formas_para_clave):
        azar = random.Random(f"{semilla}-{letra}")
        lista = []
        for m in examen.materias:
            etiquetas = m.etiquetas()
            bloques = _bloques(etiquetas, banco)
            if k > 0 and barajar_preguntas and len(bloques) > 1:
                original = list(bloques)
                for _ in range(10):                 # que no quede igual a la forma A
                    azar.shuffle(bloques)
                    if bloques != original:
                        break
            orden = [e for b in bloques for e in b]
            for posicion, origen in zip(etiquetas, orden):
                p = banco.preguntas[origen]
                letras = LETRAS[:len(p.opciones)]
                if k > 0 and barajar_opciones and not p.fija and len(letras) > 1:
                    permutacion = list(letras)
                    for _ in range(10):
                        azar.shuffle(permutacion)
                        if "".join(permutacion) != letras:
                            break
                    letras = "".join(permutacion)
                lista.append(PreguntaEnForma(posicion, origen, letras))
        formas[letra] = lista
    return formas, semilla


def claves_de_formas(formas: dict[str, list[PreguntaEnForma]], banco: Banco
                     ) -> dict[str, dict[str, str]]:
    """La clave de cada forma: dónde quedó la opción correcta después de barajar."""
    claves = {}
    for letra, lista in formas.items():
        clave = {}
        for pf in lista:
            correcta = banco.preguntas[pf.original].correcta
            clave[pf.etiqueta] = LETRAS[pf.opciones.index(correcta)]
        claves[letra] = clave
    return claves


# ---------------------------------------------------------------------------
# El mapa (formas.json)
# ---------------------------------------------------------------------------
def guardar_mapa(examen: Examen, formas: dict[str, list[PreguntaEnForma]], semilla: int,
                 barajar_preguntas: bool, barajar_opciones: bool, **opciones) -> None:
    """Guarda formas.json (el mapa) y las opciones elegidas (tiempo, etc.) para la próxima vez."""
    datos = {"semilla": semilla, "barajar_preguntas": barajar_preguntas,
             "barajar_opciones": barajar_opciones, **opciones,
             "creado": datetime.now().isoformat(timespec="seconds"),
             "formas": {letra: {pf.etiqueta: {"original": pf.original, "opciones": pf.opciones}
                                for pf in lista}
                        for letra, lista in formas.items()}}
    examen.carpeta_cuadernillos.mkdir(parents=True, exist_ok=True)
    (examen.carpeta_cuadernillos / NOMBRE_MAPA).write_text(
        json.dumps(datos, indent=1, ensure_ascii=False), encoding="utf-8")


def cargar_mapa(examen: Examen) -> dict:
    """El contenido de formas.json, o {} si el examen no tiene cuadernillos del programa."""
    try:
        datos = json.loads((examen.carpeta_cuadernillos / NOMBRE_MAPA).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    # Solo sirve si corresponde a las preguntas actuales del examen
    todas = set(examen.todas_las_etiquetas())
    if not datos.get("formas") or any(set(f) != todas for f in datos["formas"].values()):
        return {}
    return datos


def a_letra_original(mapa_forma: dict, etiqueta: str, letra: str) -> str:
    """Traduce lo que marcó un estudiante en SU forma a la opción del banco."""
    if len(letra) != 1 or etiqueta not in mapa_forma:
        return letra                       # en blanco o doble marca: igual
    opciones = mapa_forma[etiqueta]["opciones"]
    i = LETRAS.find(letra)
    return opciones[i] if 0 <= i < len(opciones) else letra
