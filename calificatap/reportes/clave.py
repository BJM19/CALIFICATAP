"""
clave.py — La clave de respuestas (las respuestas correctas).

Se guarda en clave.json, dentro de la carpeta del examen, una clave por forma:
    {"formas": {"A": {"MAT_01": "D", ...}, "B": {"MAT_01": "A", ...}}}
Si el examen no tiene formas, solo existe la forma "A".

También guarda las preguntas ANULADAS (por ejemplo, una pregunta mal
redactada o con dos respuestas válidas), por forma:
    {"formas": {...}, "anuladas": {"A": {"MAT_05": "bien"}, "B": {"MAT_12": "excluir"}}}
        "bien"     → se le da por buena a todos los estudiantes
        "excluir"  → no cuenta: se califica sobre las demás preguntas

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


MODOS_ANULACION = {
    "bien": "Se le da por buena a todos",
    "excluir": "No cuenta (se califica sobre las demás)",
}


def _leer_archivo(examen: Examen) -> dict:
    try:
        return json.loads(examen.archivo_clave.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _escribir_archivo(examen: Examen, claves: dict, anuladas: dict) -> None:
    datos = {"formas": claves}
    if any(anuladas.values()):
        datos["anuladas"] = {f: a for f, a in anuladas.items() if a}
    examen.archivo_clave.write_text(json.dumps(datos, indent=1), encoding="utf-8")


def guardar_clave(examen: Examen, claves: dict[str, dict[str, str]]) -> None:
    """claves = {"A": {"MAT_01": "D", ...}, "B": {...}}  (sin formas: solo "A").
    Las preguntas anuladas que ya había se conservan."""
    _escribir_archivo(examen, claves, cargar_anuladas(examen))


def cargar_clave(examen: Examen) -> dict[str, dict[str, str]]:
    """Devuelve {forma: {etiqueta: letra}}. Acepta también el formato antiguo (sin formas)."""
    datos = _leer_archivo(examen)
    if "formas" in datos:
        return datos["formas"]
    return {"A": datos} if datos else {}


def cargar_anuladas(examen: Examen) -> dict[str, dict[str, str]]:
    """Devuelve {forma: {etiqueta: "bien" | "excluir"}} (vacío si no hay anuladas)."""
    anuladas = _leer_archivo(examen).get("anuladas", {})
    return {f: {e: m for e, m in a.items() if m in MODOS_ANULACION}
            for f, a in anuladas.items() if isinstance(a, dict)}


def anular_pregunta(examen: Examen, forma: str, etiqueta: str, modo: str | None) -> None:
    """Anula una pregunta de una forma (modo "bien" o "excluir"), o la restaura (modo None)."""
    anuladas = cargar_anuladas(examen)
    de_la_forma = anuladas.setdefault(forma, {})
    if modo:
        if modo not in MODOS_ANULACION:
            raise ValueError(f"Modo desconocido: {modo}")
        de_la_forma[etiqueta] = modo
    else:
        de_la_forma.pop(etiqueta, None)
    _escribir_archivo(examen, cargar_clave(examen), anuladas)
