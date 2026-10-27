"""
Módulo 1 — Generador de hojas de respuestas.

Flujo:  examen.json → configuracion → maquetador → Maqueta ─┬→ dibujante_pdf → hoja_respuestas.pdf
                                                            └→ plantilla_omr → template.json (+ marcador)
"""
from .generar import generar_hoja  # noqa: F401

__all__ = ["generar_hoja"]
