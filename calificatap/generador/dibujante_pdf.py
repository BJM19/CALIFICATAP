"""
dibujante_pdf.py — Convierte la Maqueta en un archivo PDF con reportlab.

Este archivo NO decide posiciones: solo obedece a la maqueta.

Detalle importante: reportlab mide la 'y' desde ABAJO de la hoja,
pero nuestra maqueta la mide desde ARRIBA. La función _y() hace la
conversión y es el ÚNICO lugar donde ocurre.
"""

from __future__ import annotations

from pathlib import Path

from reportlab.pdfgen import canvas

from . import diseno as d
from .maqueta import Maqueta, Pagina


class DibujantePDF:
    def __init__(self, maqueta: Maqueta, ruta_pdf: str | Path, titulo: str = "Hoja de respuestas"):
        self.m = maqueta
        # ruta_pdf puede ser una ruta o un "archivo en memoria" (io.BytesIO),
        # que usa la vista previa de la interfaz para no escribir en el disco
        destino = ruta_pdf if hasattr(ruta_pdf, "write") else str(ruta_pdf)
        self.c = canvas.Canvas(destino, pagesize=(maqueta.ancho, maqueta.alto))
        self.c.setTitle(titulo)
        self.c.setAuthor("CalificaTAP")

    # ------------------------------------------------------------------
    # Conversión de coordenadas
    # ------------------------------------------------------------------
    def _y(self, y_maqueta: float) -> float:
        """y medida desde arriba (maqueta) → y medida desde abajo (PDF)."""
        return self.m.alto - y_maqueta

    # ------------------------------------------------------------------
    # Dibujo de cada tipo de elemento
    # ------------------------------------------------------------------
    def dibujar_rectangulos(self) -> None:
        for r in self.m.rectangulos:
            self.c.setLineWidth(r.grosor)
            relleno = r.relleno_gris is not None
            if relleno:
                self.c.setFillGray(r.relleno_gris)
            # En reportlab el rectángulo se define por su esquina INFERIOR izquierda
            self.c.rect(r.x, self._y(r.y + r.alto), r.ancho, r.alto,
                        stroke=1 if r.con_borde else 0, fill=1 if relleno else 0)
        self.c.setFillGray(0)

    def dibujar_lineas(self) -> None:
        for linea in self.m.lineas:
            self.c.setLineWidth(linea.grosor)
            self.c.line(linea.x1, self._y(linea.y1), linea.x2, self._y(linea.y2))

    def dibujar_textos(self, textos=None) -> None:
        for t in (self.m.textos if textos is None else textos):
            self.c.setFont(d.FUENTE_NEGRITA if t.negrita else d.FUENTE, t.tamano)
            self.c.setFillGray(t.gris)
            if t.alineacion == "centro":
                self.c.drawCentredString(t.x, self._y(t.y), t.texto)
            elif t.alineacion == "derecha":
                self.c.drawRightString(t.x, self._y(t.y), t.texto)
            else:
                self.c.drawString(t.x, self._y(t.y), t.texto)
        self.c.setFillGray(0)

    def dibujar_imagenes(self) -> None:
        for img in self.m.imagenes:
            self.c.drawImage(img.ruta, img.x, self._y(img.y + img.alto), img.ancho, img.alto,
                             preserveAspectRatio=True, mask="auto")

    def dibujar_burbujas(self) -> None:
        """Dibuja TODAS las burbujas, tomadas de los bloques de la maqueta."""
        for b in self.m.todas_las_burbujas():
            radio = b.diametro / 2
            # Círculo blanco con borde negro
            self.c.setLineWidth(d.GROSOR_BORDE_BURBUJA)
            self.c.setStrokeGray(0)
            self.c.setFillGray(1)
            self.c.circle(b.cx, self._y(b.cy), radio, stroke=1, fill=1)
            # Letra o dígito en gris claro dentro del círculo
            self.c.setFillGray(d.GRIS_LETRA_BURBUJA)
            self.c.setFont(d.FUENTE, d.TAMANO_LETRA_BURBUJA)
            # 0,35 * tamaño baja la letra para que quede centrada verticalmente
            self.c.drawCentredString(b.cx, self._y(b.cy) - 0.35 * d.TAMANO_LETRA_BURBUJA, b.valor)
        self.c.setFillGray(0)

    def dibujar_marcadores(self) -> None:
        """
        Cada marcador son 3 cuadrados concéntricos: negro, blanco, negro.
        Los tamaños salen de PROPORCIONES_MARCADOR (7-5-3), igual que la
        imagen omr_marker.jpg que genera plantilla_omr.py.
        """
        exterior = d.PROPORCIONES_MARCADOR[0]
        for mk in self.m.marcadores:
            for i, proporcion in enumerate(d.PROPORCIONES_MARCADOR):
                lado = mk.lado * proporcion / exterior
                self.c.setFillGray(0 if i % 2 == 0 else 1)  # alterna negro/blanco
                self.c.rect(mk.cx - lado / 2, self._y(mk.cy + lado / 2), lado, lado,
                            stroke=0, fill=1)
        self.c.setFillGray(0)

    def dibujar_ejemplos(self) -> None:
        """Burbujas de ejemplo de las instrucciones."""
        r = d.DIAMETRO_BURBUJA / 2
        for ej in self.m.ejemplos:
            x, y = ej.cx, self._y(ej.cy)
            self.c.setLineWidth(d.GROSOR_BORDE_BURBUJA)
            self.c.setFillGray(0 if ej.tipo == "correcto" else 1)
            self.c.circle(x, y, r, stroke=1, fill=1)
            self.c.setLineWidth(1.0)
            if ej.tipo == "x":
                self.c.line(x - r * 0.6, y - r * 0.6, x + r * 0.6, y + r * 0.6)
                self.c.line(x - r * 0.6, y + r * 0.6, x + r * 0.6, y - r * 0.6)
            elif ej.tipo == "chulo":
                self.c.line(x - r * 0.6, y, x - r * 0.1, y - r * 0.6)
                self.c.line(x - r * 0.1, y - r * 0.6, x + r * 0.7, y + r * 0.7)
            elif ej.tipo == "parcial":
                self.c.setFillGray(0)
                self.c.wedge(x - r, y - r, x + r, y + r, 0, 180, stroke=0, fill=1)
        self.c.setFillGray(0)

    def rellenar(self, marcas: dict[str, str]) -> None:
        """
        Rellena burbujas: el código del examen, los datos de las hojas
        personalizadas, o (en las pruebas) las respuestas de un estudiante.
        marcas = {"MAT_01": "B", "doc01": "1", ...}
        """
        self.c.setFillGray(0.1)
        for b in self.m.todas_las_burbujas():
            if marcas.get(b.etiqueta) == b.valor:
                self.c.circle(b.cx, self._y(b.cy), b.diametro / 2 * 0.95, stroke=0, fill=1)
        self.c.setFillGray(0)

    # ------------------------------------------------------------------
    def dibujar_pagina(self, pagina: Pagina) -> None:
        """Dibuja una hoja completa. El orden importa: lo de después queda encima."""
        self.dibujar_rectangulos()
        self.dibujar_lineas()
        self.dibujar_imagenes()
        self.dibujar_textos()
        self.dibujar_burbujas()
        self.dibujar_ejemplos()
        self.dibujar_marcadores()
        self.rellenar({**self.m.marcas_fijas, **pagina.marcas})
        self.dibujar_textos(pagina.textos)
        self.c.showPage()            # termina la página; la siguiente empieza en blanco

    def guardar(self, paginas: list[Pagina]) -> None:
        for pagina in paginas:
            self.dibujar_pagina(pagina)
        self.c.save()


def dibujar_pdf(maqueta: Maqueta, ruta_pdf: str | Path, titulo: str = "Hoja de respuestas",
                marcas: dict[str, str] | None = None,
                paginas: list[Pagina] | None = None) -> None:
    """
    Atajo para crear el PDF en una sola línea.
        - Sin 'paginas': una hoja en blanco (con 'marcas' opcionales, para pruebas).
        - Con 'paginas': una hoja por cada Pagina (hojas personalizadas).
    """
    if paginas is None:
        paginas = [Pagina(marcas=marcas or {})]
    DibujantePDF(maqueta, ruta_pdf, titulo).guardar(paginas)


def dibujar_pdf_hojas(pares: list[tuple[Maqueta, Pagina]], ruta_pdf, titulo: str = "Hoja de respuestas") -> None:
    """
    Para exámenes de VARIAS hojas: cada página del PDF puede usar una maqueta distinta.
    pares = [(maqueta_hoja1, pagina_de_Ana), (maqueta_hoja2, pagina_de_Ana), (maqueta_hoja1, ...)]
    """
    dibujante = DibujantePDF(pares[0][0], ruta_pdf, titulo)
    for maqueta, pagina in pares:
        dibujante.m = maqueta          # el mismo "lápiz", otro plano
        dibujante.dibujar_pagina(pagina)
    dibujante.c.save()
