"""
clave.py — La clave de respuestas (las respuestas correctas).

Se guarda en clave.json, dentro de la carpeta del examen, una clave por forma:
    {"formas": {"A": {"MAT_01": "D", ...}, "B": {"MAT_01": "A", ...}}}
Si el examen no tiene formas, solo existe la forma "A".

Para que el docente la escriba rápido, en pantalla se escribe una línea por
materia con las letras seguidas:  "DDDBB DBADC ..."  (los espacios no importan).
"""

from __future__ import annotations

import json

from ..examenes import Examen, MateriaExamen


def texto_a_letras(texto: str) -> list[str]:
    """'dd db, a' → ['D', 'D', 'D', 'B', 'A'] (ignora espacios, comas y guiones)."""
    return [c for c in texto.upper() if c.isalpha()]


def revisar_texto(texto: str, materia: MateriaExamen) -> tuple[bool, str]:
    """
    Revisa la clave escrita para una materia.
    Devuelve (está_bien, mensaje corto para mostrar al lado).
    """
    letras = texto_a_letras(texto)
    validas = "ABCDEFGH"[: materia.opciones]
    malas = sorted({c for c in letras if c not in validas})
    if malas:
        return False, f"«{', '.join(malas)}» no es opción (solo {validas[0]}–{validas[-1]})"
    if len(letras) < materia.preguntas:
        return False, f"{len(letras)}/{materia.preguntas} · faltan {materia.preguntas - len(letras)}"
    if len(letras) > materia.preguntas:
        return False, f"{len(letras)}/{materia.preguntas} · sobran {len(letras) - materia.preguntas}"
    return True, f"{len(letras)}/{materia.preguntas} ✔"


def textos_a_clave(examen: Examen, textos: dict[str, str]) -> dict[str, str]:
    """{código_materia: texto} → {etiqueta: letra}. Solo incluye lo que esté completo."""
    clave = {}
    for m in examen.materias:
        letras = texto_a_letras(textos.get(m.codigo, ""))
        for etiqueta, letra in zip(m.etiquetas(), letras):
            clave[etiqueta] = letra
    return clave


def clave_a_textos(examen: Examen, clave: dict[str, str]) -> dict[str, str]:
    """{etiqueta: letra} → {código_materia: 'DDDBB DBADC ...'} (en grupos de 5)."""
    textos = {}
    for m in examen.materias:
        letras = "".join(clave.get(e, "") for e in m.etiquetas())
        textos[m.codigo] = " ".join(letras[i:i + 5] for i in range(0, len(letras), 5))
    return textos


def guardar_clave(examen: Examen, claves: dict[str, dict[str, str]]) -> None:
    """claves = {"A": {"MAT_01": "D", ...}, "B": {...}}  (sin formas: solo "A")."""
    examen.archivo_clave.write_text(json.dumps({"formas": claves}, indent=1), encoding="utf-8")


def cargar_clave(examen: Examen) -> dict[str, dict[str, str]]:
    """Devuelve {forma: {etiqueta: letra}}. Acepta también el formato antiguo (sin formas)."""
    try:
        datos = json.loads(examen.archivo_clave.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    if "formas" in datos:
        return datos["formas"]
    return {"A": datos} if datos else {}
