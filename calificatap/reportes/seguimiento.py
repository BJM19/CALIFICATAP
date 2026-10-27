"""
seguimiento.py — Compara varios exámenes para ver cómo avanza el curso.

Por ejemplo: Simulacro 1 (marzo), Simulacro 2 (junio), Simulacro 3 (septiembre).
Cada examen se califica igual que en la pestaña Resultados (con su clave, su
lista y su escala), y luego se juntan los resultados:

    curso        → promedio general y por materia en cada examen
    estudiantes  → % de aciertos de cada estudiante en cada examen, y cuánto cambió
    detalle(doc) → la evolución de UN estudiante, materia por materia

Los estudiantes se reconocen por su documento (así se juntan aunque el nombre
esté escrito distinto en dos listas). Las materias, por su nombre.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from ..examenes import Examen
from ..lector.hojas import cargar_hojas
from .calificar import Resultados, calificar, cargar_escala
from .clave import cargar_clave
from .estudiantes import cargar_estudiantes


def calificar_examen(examen: Examen) -> Resultados | None:
    """Califica un examen con lo que tenga guardado. None si no tiene hojas o clave."""
    hojas = cargar_hojas(examen)
    claves = cargar_clave(examen)
    if not hojas or not any(claves.values()):
        return None
    r = calificar(examen, hojas, claves, cargar_estudiantes(examen), cargar_escala(examen))
    return r if r.hay_datos else None


def etiqueta_corta(examen: Examen) -> str:
    """Nombre corto para los ejes de los gráficos: 'Simulacro 1 (2026-03-15)'."""
    fecha = examen.datos.get("examen", {}).get("fecha", "")
    nombre = examen.nombre if len(examen.nombre) <= 28 else examen.nombre[:26] + "…"
    return f"{nombre} ({fecha})" if fecha else nombre


@dataclass
class Seguimiento:
    examenes: list[str]                          # etiquetas, en orden
    curso: pd.DataFrame                          # filas: exámenes; columnas: General + materias
    estudiantes: pd.DataFrame                    # filas: documento; columnas: nombre, exámenes, cambio
    _por_examen: dict[str, Resultados] = field(default_factory=dict)

    @property
    def hay_datos(self) -> bool:
        return len(self.examenes) > 0

    def detalle(self, documento: str) -> pd.DataFrame:
        """Evolución de un estudiante: filas = exámenes; columnas = Total + materias (%)."""
        filas = {}
        for etiqueta, r in self._por_examen.items():
            est = r.por_estudiante.set_index("documento")
            if documento not in est.index:
                continue
            fila = {"Total": est.at[documento, "porcentaje"]}
            for m in r.examen.materias:
                if m.nombre in est.columns:
                    fila[m.nombre] = est.at[documento, m.nombre]
            filas[etiqueta] = fila
        return pd.DataFrame.from_dict(filas, orient="index").reindex(
            [e for e in self.examenes if e in filas])


def construir_seguimiento(examenes: list[Examen]) -> Seguimiento:
    """Junta los resultados de varios exámenes (ordenados por fecha de creación)."""
    examenes = sorted(examenes, key=lambda e: e.creado)
    por_examen: dict[str, Resultados] = {}
    for e in examenes:
        r = calificar_examen(e)
        if r is not None:
            etiqueta = etiqueta_corta(e)
            while etiqueta in por_examen:         # dos exámenes con el mismo nombre
                etiqueta += " "
            por_examen[etiqueta] = r

    # --- Curso: promedios por examen ---
    filas_curso = {}
    for etiqueta, r in por_examen.items():
        fila = {"General": r.por_estudiante["porcentaje"].mean(),
                "Estudiantes": len(r.por_estudiante),
                "Nota promedio": r.escala.nota(r.por_estudiante["porcentaje"].mean() / 100),
                "Aprueban %": r.por_estudiante["aprobado"].mean() * 100}
        for _, m in r.por_materia.iterrows():
            fila[m["materia"]] = m["promedio"]
        filas_curso[etiqueta] = fila
    curso = pd.DataFrame.from_dict(filas_curso, orient="index").round(1)

    # --- Estudiantes: % total en cada examen ---
    nombres: dict[str, str] = {}
    columnas = {}
    for etiqueta, r in por_examen.items():
        est = r.por_estudiante
        columnas[etiqueta] = est.set_index("documento")["porcentaje"]
        for doc, nombre in zip(est["documento"], est["nombre"]):
            if nombre and not nombres.get(doc):
                nombres[doc] = nombre
    estudiantes = pd.DataFrame(columnas)
    # Las hojas sin documento no se pueden seguir de un examen a otro
    estudiantes = estudiantes[~estudiantes.index.astype(str).str.startswith("(sin documento)")]
    if not estudiantes.empty:
        estudiantes.insert(0, "nombre", [nombres.get(d, "") for d in estudiantes.index])
        valores = estudiantes[list(por_examen)]
        # Cambio = último examen presentado − primer examen presentado
        primero = valores.apply(lambda f: f.dropna().iloc[0] if f.notna().any() else None, axis=1)
        ultimo = valores.apply(lambda f: f.dropna().iloc[-1] if f.notna().any() else None, axis=1)
        estudiantes["presentados"] = valores.notna().sum(axis=1)
        estudiantes["cambio"] = (ultimo - primero).where(estudiantes["presentados"] > 1).round(1)
        estudiantes = estudiantes.sort_values("nombre")

    return Seguimiento(list(por_examen), curso, estudiantes, por_examen)
