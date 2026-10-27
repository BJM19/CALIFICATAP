"""
verificar.py — Comprueba que el PDF y el template.json coinciden.

Hace lo mismo que haría OMRChecker con una hoja perfectamente escaneada:
    1. Convierte el PDF en imagen (a PIXELES_POR_PUNTO px por punto).
    2. Recorta la zona entre los centros de las 4 marcas.
    3. Lee template.json y dibuja encima un cuadro por cada burbuja,
       calculado con la misma regla que usa OMRChecker.
    4. Mide cuántos píxeles se desvía cada círculo impreso de su cuadro.

Resultado: una imagen 'verificacion.png' para revisar a ojo, y un número
(la desviación máxima) para revisarlo automáticamente.

Usa PyMuPDF para convertir el PDF en imagen (se instala con pip y no
necesita programas adicionales en Windows).
"""

from __future__ import annotations

import json
from pathlib import Path

import cv2
import numpy as np

try:
    import pymupdf as fitz      # versiones nuevas de PyMuPDF
except ImportError:             # versiones anteriores
    import fitz

from . import diseno as d
from .maqueta import Maqueta


def pdf_a_imagen(ruta_pdf: str | Path, escala: float = d.PIXELES_POR_PUNTO,
                 indice: int = 0) -> np.ndarray:
    """Una página del PDF (la primera por defecto) como imagen en escala de grises."""
    with fitz.open(str(ruta_pdf)) as documento:
        pagina = documento[indice]
        pix = pagina.get_pixmap(matrix=fitz.Matrix(escala, escala), colorspace=fitz.csGRAY)
        return np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width).copy()


def cuadros_desde_template(template: dict) -> list[tuple[str, str, int, int, int, int]]:
    """
    Lee template.json y calcula el cuadro (x, y, ancho, alto) de cada burbuja,
    siguiendo la MISMA regla que OMRChecker (generate_bubble_grid).
    Ojo: aquí no usamos la maqueta a propósito, solo el JSON, para comprobarlo
    de forma independiente.
    """
    ancho, alto = template["bubbleDimensions"]
    cuadros = []
    for bloque in template["fieldBlocks"].values():
        x0, y0 = bloque["origin"]
        for i, etiqueta in enumerate(bloque["fieldLabels"]):
            for j, valor in enumerate(bloque["bubbleValues"]):
                if bloque["direction"] == "horizontal":
                    x = x0 + j * bloque["bubblesGap"]
                    y = y0 + i * bloque["labelsGap"]
                else:
                    x = x0 + i * bloque["labelsGap"]
                    y = y0 + j * bloque["bubblesGap"]
                cuadros.append((etiqueta, valor, round(x), round(y), ancho, alto))
    return cuadros


def verificar(ruta_pdf: str | Path, ruta_template: str | Path, maqueta: Maqueta,
              ruta_salida: str | Path, indice: int = 0) -> float:
    """Genera la imagen de verificación y devuelve la desviación máxima en píxeles.
    'indice' es la página del PDF que corresponde a esa maqueta (0 = primera)."""
    escala = d.PIXELES_POR_PUNTO
    imagen = pdf_a_imagen(ruta_pdf, escala, indice)
    template = json.loads(Path(ruta_template).read_text(encoding="utf-8"))

    # Recorte entre los centros de las marcas (lo que "ve" OMRChecker)
    xs = [mk.cx for mk in maqueta.marcadores]
    ys = [mk.cy for mk in maqueta.marcadores]
    x0, y0 = round(min(xs) * escala), round(min(ys) * escala)
    ancho_pag, alto_pag = template["pageDimensions"]
    recorte = imagen[y0:y0 + alto_pag, x0:x0 + ancho_pag]

    salida = cv2.cvtColor(recorte, cv2.COLOR_GRAY2BGR)
    desviacion_maxima = 0.0
    margen = 4  # buscamos el círculo un poco más allá del cuadro

    for etiqueta, valor, x, y, w, h in cuadros_desde_template(template):
        # Píxeles oscuros (el borde negro del círculo) cerca del cuadro
        zona = recorte[y - margen:y + h + margen, x - margen:x + w + margen]
        filas, columnas = np.nonzero(zona < 100)
        if len(filas) == 0:
            desviacion = float("inf")   # ¡no hay círculo donde debería!
        else:
            # Centro del círculo impreso vs. centro del cuadro de OMRChecker.
            # (+0,5 porque el píxel número i ocupa desde i hasta i+1: su centro es i+0,5)
            centro_impreso = (columnas.mean() + 0.5 - margen, filas.mean() + 0.5 - margen)
            desviacion = float(np.hypot(centro_impreso[0] - w / 2, centro_impreso[1] - h / 2))
        desviacion_maxima = max(desviacion_maxima, desviacion)
        color = (0, 170, 0) if desviacion <= 1.0 else (0, 0, 255)  # verde bien, rojo mal
        cv2.rectangle(salida, (x, y), (x + w, y + h), color, 1)

    cv2.putText(salida, f"Desviacion maxima: {desviacion_maxima:.2f} px", (10, alto_pag - 10),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200, 0, 0), 2)
    cv2.imwrite(str(ruta_salida), salida)
    return desviacion_maxima
