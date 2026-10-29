"""
plantilla_omr.py — Convierte la Maqueta en los archivos que necesita OMRChecker:

    template.json        → dónde está cada burbuja y qué significa
                           (las hojas se leen desde el PDF del ESCÁNER)
    omr_marker.jpg  → imagen de la marca de alineación (para encontrarla en el escaneo)
    config.json     → ajustes de procesamiento de OMRChecker

¿CÓMO VE OMRChecker LA HOJA?
    1. Busca las 4 marcas de las esquinas en el escaneo.
    2. "Endereza" la imagen tomando como esquinas los CENTROS de esas 4 marcas
       (corrige si la hoja entró un poco torcida al escáner).
    3. Estira esa imagen enderezada al tamaño 'pageDimensions'.
    4. Busca cada burbuja en las coordenadas (en píxeles) del template.json.

    Por eso, para OMRChecker el punto (0, 0) NO es la esquina de la hoja,
    sino el CENTRO DE LA MARCA SUPERIOR IZQUIERDA. Y el ancho de su "página"
    es la distancia entre los centros de las marcas, no el ancho de la hoja.

    ┌──────────────────────────────┐  ← borde de la hoja
    │ ■(0,0)────────────────────■  │
    │ │   zona que ve OMRChecker │  │
    │ │                          │  │
    │ ■────────────────────────■ │  │
    └──────────────────────────────┘

La conversión de la maqueta (puntos) a OMRChecker (píxeles) es:

    px = (x_maqueta - x_marca_sup_izq) * PIXELES_POR_PUNTO
    py = (y_maqueta - y_marca_sup_izq) * PIXELES_POR_PUNTO
"""

from __future__ import annotations

import json
from pathlib import Path

import cv2
import numpy as np

from . import diseno as d
from .maqueta import BloqueCampos, Maqueta

NOMBRE_IMAGEN_MARCADOR = "omr_marker.jpg"


class ConversorCoordenadas:
    """Traduce puntos de la maqueta a píxeles del sistema de OMRChecker."""

    def __init__(self, maqueta: Maqueta, escala: float = d.PIXELES_POR_PUNTO):
        self.escala = escala
        marca = maqueta.marcador_superior_izquierdo()
        self.x0, self.y0 = marca.cx, marca.cy

    def a_pixeles(self, x: float, y: float) -> tuple[float, float]:
        return (x - self.x0) * self.escala, (y - self.y0) * self.escala

    def longitud(self, distancia_pt: float) -> float:
        """Para distancias (pasos, diámetros) no se resta el origen, solo se escala."""
        return distancia_pt * self.escala


def _bloque_a_omr(bloque: BloqueCampos, conv: ConversorCoordenadas) -> dict:
    """
    Convierte un BloqueCampos en un fieldBlock de OMRChecker.

    OMRChecker ubica cada burbuja por su esquina SUPERIOR IZQUIERDA,
    no por su centro. Por eso restamos el radio al centro de la primera burbuja.
    """
    radio = bloque.diametro / 2
    ox, oy = conv.a_pixeles(bloque.origen_cx - radio, bloque.origen_cy - radio)
    return {
        "origin": [round(ox), round(oy)],   # OMRChecker exige enteros aquí
        "bubbleValues": bloque.valores,
        "direction": bloque.direccion,
        "fieldLabels": bloque.etiquetas,
        # Los pasos sí pueden tener decimales: así no se acumula error fila tras fila
        "bubblesGap": round(conv.longitud(bloque.paso_burbujas), 3),
        "labelsGap": round(conv.longitud(bloque.paso_campos), 3),
    }


def construir_template(maqueta: Maqueta, solo_identificar: bool = False) -> dict:
    """
    Arma el diccionario que se guardará como template.json.

    (Antes había una segunda plantilla para fotos de celular, con un paso extra
    "CropPage" que recorta la hoja del fondo. En las pruebas reales las fotos no
    funcionaron bien, así que CalificaTAP lee solo PDF del escáner.)

    solo_identificar=True arma una plantilla que lee ÚNICAMENTE la franja de
    abajo (código del examen y número de hoja). Sirve, en exámenes de varias
    hojas, para saber primero qué hoja es cada imagen.
    """
    conv = ConversorCoordenadas(maqueta)

    # Tamaño de la "página" de OMRChecker = distancia entre centros de marcas
    xs = [mk.cx for mk in maqueta.marcadores]
    ys = [mk.cy for mk in maqueta.marcadores]
    ancho_px = round(conv.longitud(max(xs) - min(xs)))
    alto_px = round(conv.longitud(max(ys) - min(ys)))

    diametro_px = round(conv.longitud(d.DIAMETRO_BURBUJA))

    # Preprocesadores: pasos que OMRChecker aplica a la imagen antes de leerla
    preprocesadores = [{
        "name": "CropOnMarkers",
        "options": {
            "relativePath": NOMBRE_IMAGEN_MARCADOR,
            # Cuántas veces cabe la marca en el ancho de la hoja. OMRChecker lo usa
            # para saber de qué tamaño buscar la marca.
            "sheetToMarkerWidthRatio": round(d.ANCHO_PAGINA / d.LADO_MARCADOR),
            # Busca la marca entre el 40 % y el 110 % de ese tamaño
            # (por si el escáner o la impresora cambiaron un poco la escala)
            "marker_rescale_range": [40, 110],
            "marker_rescale_steps": 14,
        },
    }]

    franja = set(maqueta.etiquetas_codigo + maqueta.etiquetas_hoja)
    bloques = {b.nombre: _bloque_a_omr(b, conv) for b in maqueta.bloques
               if not solo_identificar or set(b.etiquetas) <= franja}

    template = {
        "pageDimensions": [ancho_px, alto_px],
        "bubbleDimensions": [diametro_px, diametro_px],
        "preProcessors": preprocesadores,
        # customLabels une varios campos en una sola columna:
        #   doc01..doc10 → columna "documento" con el número completo
        #   cod01..cod10 → columna "codigo_examen" con los 10 bits ("0000000101")
        #   hoj01..hoj02 → columna "hoja" con 2 bits ("01" = hoja 2)
        "customLabels": ({"documento": maqueta.etiquetas_documento} if not solo_identificar else {})
                        | {"codigo_examen": maqueta.etiquetas_codigo,
                           "hoja": maqueta.etiquetas_hoja},
        "fieldBlocks": bloques,
        # Orden de las columnas en el CSV: documento, código, hoja, forma y luego las preguntas
        "outputColumns": (["codigo_examen", "hoja"] if solo_identificar else
                          ["documento", "codigo_examen", "hoja"]
                          + ([maqueta.etiqueta_forma] if maqueta.etiqueta_forma else [])
                          + maqueta.etiquetas_preguntas),
        "emptyValue": "",
    }

    _verificar_dentro_de_pagina(maqueta, conv, ancho_px, alto_px)
    return template


def _verificar_dentro_de_pagina(maqueta: Maqueta, conv: ConversorCoordenadas,
                                ancho_px: float, alto_px: float) -> None:
    """Toda burbuja debe quedar DENTRO del rectángulo formado por las marcas."""
    for b in maqueta.todas_las_burbujas():
        px, py = conv.a_pixeles(b.cx, b.cy)
        if not (0 < px < ancho_px and 0 < py < alto_px):
            raise ValueError(f"La burbuja {b.etiqueta}={b.valor} queda fuera de las marcas.")


def construir_config_omr() -> dict:
    """
    config.json de OMRChecker. Le decimos que la imagen de trabajo tenga
    la misma proporción de una hoja carta (ancho x 792/612).
    """
    ancho = 900
    alto = round(ancho * d.ALTO_PAGINA / d.ANCHO_PAGINA)
    return {
        "dimensions": {"processing_width": ancho, "processing_height": alto},
        "outputs": {"show_image_level": 0},
    }


def guardar_imagen_marcador(ruta: str | Path, pixeles_por_modulo: int = 20) -> None:
    """
    Dibuja la marca de alineación como imagen, con las MISMAS proporciones
    (7-5-3) que en el PDF. OMRChecker buscará esta figura en el escaneo.
    """
    exterior = d.PROPORCIONES_MARCADOR[0]
    lado = exterior * pixeles_por_modulo
    imagen = np.full((lado, lado), 255, dtype=np.uint8)   # fondo blanco
    for i, proporcion in enumerate(d.PROPORCIONES_MARCADOR):
        margen = (exterior - proporcion) * pixeles_por_modulo // 2
        color = 0 if i % 2 == 0 else 255                  # negro, blanco, negro
        imagen[margen:lado - margen, margen:lado - margen] = color
    cv2.imwrite(str(ruta), imagen)


def nombre_plantilla(hoja: int | str = 1) -> str:
    """
    Nombres de los archivos de plantilla:
        hoja 1 → template.json
        hoja 2 → template_hoja2.json
        "identificar" → template_identificar.json
    """
    sufijo = "" if hoja == 1 else (f"_hoja{hoja}" if isinstance(hoja, int) else f"_{hoja}")
    return f"template{sufijo}.json"


def _escribir(ruta: Path, contenido: dict) -> None:
    ruta.write_text(json.dumps(contenido, indent=2, ensure_ascii=False), encoding="utf-8")


def guardar_archivos_omr(maqueta: Maqueta | list[Maqueta], carpeta: str | Path) -> dict:
    """
    Escribe las plantillas (una por cada hoja, más la de identificar),
    config.json y omr_marker.jpg. Acepta una hoja o la lista de hojas.
    """
    carpeta = Path(carpeta)
    hojas = maqueta if isinstance(maqueta, list) else [maqueta]
    for vieja in carpeta.glob("template_fotos*.json"):   # de versiones que leían fotos
        vieja.unlink()
    for h in hojas:
        _escribir(carpeta / nombre_plantilla(h.hoja), construir_template(h))
    _escribir(carpeta / nombre_plantilla("identificar"),
              construir_template(hojas[0], solo_identificar=True))
    template = construir_template(hojas[0])
    (carpeta / "config.json").write_text(
        json.dumps(construir_config_omr(), indent=2), encoding="utf-8")
    guardar_imagen_marcador(carpeta / NOMBRE_IMAGEN_MARCADOR)
    return template
