"""
vista_previa.py — Dibuja la hoja como imagen para mostrarla en pantalla.

Usa EXACTAMENTE el mismo camino que la hoja real (configuración → maqueta → PDF),
pero el PDF se crea en memoria y se convierte en imagen. Así, lo que el docente
ve en la pantalla es lo mismo que se va a imprimir.
"""

from __future__ import annotations

import io
from pathlib import Path

from PIL import Image

try:
    import pymupdf as fitz
except ImportError:
    import fitz

from ..generador.configuracion import configuracion_desde_datos
from ..generador.dibujante_pdf import dibujar_pdf
from ..generador.maquetador import maquetar_examen, pagina_personalizada


def imagen_vista_previa(datos: dict, carpeta_base: str | Path, alto_px: int,
                        estudiante: dict | None = None,
                        hoja: int = 1) -> tuple[Image.Image, int]:
    """
    Devuelve una imagen (PIL) de la hoja con 'alto_px' píxeles de alto.
    Si se da 'estudiante' ({"documento", "nombre", "curso"}), se muestra su hoja
    personalizada (con nombre y documento ya marcados).
    Devuelve (imagen, total_de_hojas): si el examen no cabe en una hoja, 'hoja'
    dice cuál mostrar.
    Si la configuración tiene errores, lanza la misma excepción que el generador
    (ErrorDeConfiguracion o ErrorDeMaquetacion) para mostrar el mensaje.
    """
    conf = configuracion_desde_datos(datos, carpeta_base)
    hojas = maquetar_examen(conf)
    maqueta = hojas[max(1, min(hoja, len(hojas))) - 1]

    paginas = None
    if estudiante:
        forma = "A" if conf.formas > 1 else ""
        paginas = [pagina_personalizada(maqueta, estudiante["documento"], estudiante["nombre"],
                                        estudiante.get("curso", ""), forma)]

    memoria = io.BytesIO()                    # "archivo" que vive en la RAM
    dibujar_pdf(maqueta, memoria, titulo=conf.nombre_examen, paginas=paginas)

    with fitz.open(stream=memoria.getvalue(), filetype="pdf") as documento:
        pagina = documento[0]
        zoom = alto_px / pagina.rect.height
        pix = pagina.get_pixmap(matrix=fitz.Matrix(zoom, zoom))
        return Image.frombytes("RGB", (pix.width, pix.height), pix.samples), len(hojas)
