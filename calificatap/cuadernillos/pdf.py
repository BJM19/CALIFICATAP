"""
pdf.py — Dibuja el cuadernillo de preguntas de una forma, con un estilo parecido
al de las pruebas Saber:

    - portada con la FORMA en grande, las materias con sus números de pregunta
      y las instrucciones;
    - el cuerpo a DOS COLUMNAS, con una línea en medio;
    - cada materia empieza en una página nueva, con una franja de color;
    - los textos compartidos van precedidos de
      «RESPONDA LAS PREGUNTAS 26 A 28 DE ACUERDO CON LA SIGUIENTE INFORMACIÓN»;
    - las opciones van una debajo de otra: A. ... B. ... C. ... D. ...

Se usa reportlab "platypus": cada pregunta es un bloque que se acomoda solo en
la columna; si no cabe, pasa entera a la siguiente (KeepTogether).
"""

from __future__ import annotations

import io
from pathlib import Path
from xml.sax.saxutils import escape

from PIL import Image as ImagenPIL
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (BaseDocTemplate, CondPageBreak, Frame, Image, KeepTogether,
                                NextPageTemplate,
                                PageBreak, PageTemplate, Paragraph, Spacer, Table, TableStyle)

from ..examenes import Examen
from .banco import LETRAS, Banco
from .formas import PreguntaEnForma

VERDE = colors.HexColor("#1F7A4D")
VERDE_CLARO = colors.HexColor("#E3F1E9")
GRIS = colors.HexColor("#5C6B64")
GRIS_LINEA = colors.HexColor("#B9C2BE")

ANCHO, ALTO = letter
MARGEN = 1.6 * cm
SEPARACION = 0.9 * cm                       # entre las dos columnas
ANCHO_COLUMNA = (ANCHO - 2 * MARGEN - SEPARACION) / 2


# ---------------------------------------------------------------------------
# Letra: Arial (Windows) o una parecida. Así salen bien símbolos como ≤, π, √.
# ---------------------------------------------------------------------------
_CANDIDATAS = [
    ("C:/Windows/Fonts/arial.ttf", "C:/Windows/Fonts/arialbd.ttf",
     "C:/Windows/Fonts/ariali.ttf", "C:/Windows/Fonts/arialbi.ttf"),
    ("/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
     "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
     "/usr/share/fonts/truetype/liberation/LiberationSans-Italic.ttf",
     "/usr/share/fonts/truetype/liberation/LiberationSans-BoldItalic.ttf"),
    ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
     "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
     "/usr/share/fonts/truetype/dejavu/DejaVuSans-Oblique.ttf",
     "/usr/share/fonts/truetype/dejavu/DejaVuSans-BoldOblique.ttf"),
]


def _registrar_letra() -> tuple[str, str]:
    """Devuelve (normal, negrita). Si no encuentra ninguna, usa Helvetica."""
    for rutas in _CANDIDATAS:
        if all(Path(r).exists() for r in rutas):
            try:
                nombres = ["CT-Normal", "CT-Negrita", "CT-Cursiva", "CT-NegritaCursiva"]
                for nombre, ruta in zip(nombres, rutas):
                    pdfmetrics.registerFont(TTFont(nombre, ruta))
                pdfmetrics.registerFontFamily("CT-Normal", normal="CT-Normal", bold="CT-Negrita",
                                              italic="CT-Cursiva", boldItalic="CT-NegritaCursiva")
                return "CT-Normal", "CT-Negrita"
            except Exception:
                continue
    return "Helvetica", "Helvetica-Bold"


def _estilos(normal: str, negrita: str) -> dict[str, ParagraphStyle]:
    return {
        "texto": ParagraphStyle("texto", fontName=normal, fontSize=9.5, leading=12.5,
                                alignment=TA_JUSTIFY, spaceAfter=4),
        "instruccion": ParagraphStyle("instr", fontName=negrita, fontSize=8.3, leading=10.5,
                                      spaceBefore=6, spaceAfter=5),
        "pregunta": ParagraphStyle("preg", fontName=normal, fontSize=9.5, leading=12.5,
                                   leftIndent=17, firstLineIndent=-17,
                                   spaceAfter=4),
        "opcion": ParagraphStyle("opc", fontName=normal, fontSize=9.5, leading=12.3,
                                 leftIndent=31, firstLineIndent=-14, spaceAfter=2),
        "franja": ParagraphStyle("franja", fontName=negrita, fontSize=11, leading=13,
                                 textColor=colors.white),
        "franja_sub": ParagraphStyle("franja2", fontName=normal, fontSize=8.5, leading=10,
                                     textColor=colors.white),
        "titulo": ParagraphStyle("tit", fontName=negrita, fontSize=17, leading=21,
                                 alignment=TA_CENTER, textColor=VERDE),
        "sub": ParagraphStyle("sub", fontName=normal, fontSize=10.5, leading=14,
                              alignment=TA_CENTER, textColor=GRIS),
        "grande": ParagraphStyle("gr", fontName=negrita, fontSize=15, leading=19,
                                 alignment=TA_CENTER),
        "forma": ParagraphStyle("forma", fontName=negrita, fontSize=64, leading=70,
                                alignment=TA_CENTER, textColor=VERDE),
        "celda": ParagraphStyle("celda", fontName=normal, fontSize=9.5, leading=12),
        "aviso": ParagraphStyle("aviso", fontName=normal, fontSize=9, leading=12.5),
    }


def _parrafos(texto: str) -> str:
    """Texto del Excel → texto para el PDF (respeta los saltos de línea)."""
    return escape(texto).replace("\n", "<br/>")


def _imagen(datos: bytes, ancho_max: float, alto_max: float = 9 * cm) -> Image | None:
    """Una imagen ajustada al ancho de la columna (sin deformarla)."""
    try:
        with ImagenPIL.open(io.BytesIO(datos)) as im:
            ancho_px, alto_px = im.size
            ppp = (im.info.get("dpi") or (96, 96))[0] or 96
    except Exception:
        return None
    # tamaño real según los ppp de la imagen (las fórmulas se guardan a 200 ppp);
    # capturas de pantalla sin ese dato: 96 ppp
    ancho = min(ancho_max, ancho_px * 72 / max(72, float(ppp)))
    alto = ancho * alto_px / ancho_px
    if alto > alto_max:
        alto, ancho = alto_max, alto_max * ancho_px / alto_px
    imagen = Image(io.BytesIO(datos), width=ancho, height=alto)
    imagen.hAlign = "CENTER"
    return imagen


# ---------------------------------------------------------------------------
# El cuadernillo
# ---------------------------------------------------------------------------
def dibujar_cuadernillo(examen: Examen, banco: Banco, forma: str,
                        preguntas: list[PreguntaEnForma], ruta: str | Path,
                        tiempo: str = "", mostrar_forma: bool = True,
                        pagina_por_materia: bool = True) -> Path:
    """
    pagina_por_materia=True: cada prueba empieza en una página nueva (como en el ICFES).
    False: sigue en la misma columna si queda espacio (ahorra papel).
    """
    ruta = Path(ruta)
    normal, negrita = _registrar_letra()
    est = _estilos(normal, negrita)
    numeros = examen.numeros_impresos()
    colegio = examen.datos.get("colegio", {})
    datos_examen = examen.datos.get("examen", {})
    texto_forma = f"Forma {forma}" if mostrar_forma else ""

    # --- Encabezado y pie de cada página del cuerpo ---
    def pagina_cuerpo(canvas, doc):
        canvas.saveState()
        arriba = ALTO - MARGEN + 0.35 * cm
        canvas.setFont(negrita, 8.5)
        canvas.setFillColor(GRIS)
        canvas.drawString(MARGEN, arriba, examen.nombre.upper())
        if texto_forma:
            # recuadro con la forma, a la derecha
            canvas.setFillColor(VERDE)
            canvas.roundRect(ANCHO - MARGEN - 2.2 * cm, arriba - 0.18 * cm, 2.2 * cm, 0.55 * cm,
                             3, stroke=0, fill=1)
            canvas.setFillColor(colors.white)
            canvas.drawCentredString(ANCHO - MARGEN - 1.1 * cm, arriba, texto_forma.upper())
        canvas.setStrokeColor(GRIS_LINEA)
        canvas.setLineWidth(0.6)
        canvas.line(MARGEN, arriba - 0.3 * cm, ANCHO - MARGEN, arriba - 0.3 * cm)
        # línea entre columnas
        x = MARGEN + ANCHO_COLUMNA + SEPARACION / 2
        canvas.line(x, MARGEN, x, arriba - 0.5 * cm)
        # pie
        canvas.setFont(normal, 8)
        canvas.setFillColor(GRIS)
        canvas.drawCentredString(ANCHO / 2, MARGEN - 0.7 * cm, str(doc.page))
        canvas.restoreState()

    alto_cuerpo = ALTO - 2 * MARGEN - 0.6 * cm
    columnas = [Frame(MARGEN, MARGEN, ANCHO_COLUMNA, alto_cuerpo, id="izq",
                      leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0),
                Frame(MARGEN + ANCHO_COLUMNA + SEPARACION, MARGEN, ANCHO_COLUMNA, alto_cuerpo,
                      id="der", leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)]
    portada = Frame(MARGEN, MARGEN, ANCHO - 2 * MARGEN, ALTO - 2 * MARGEN, id="portada")
    doc = BaseDocTemplate(str(ruta), pagesize=letter,
                          title=f"Cuadernillo · {examen.nombre} · {texto_forma}",
                          author="CalificaTAP")
    doc.addPageTemplates([PageTemplate("portada", [portada]),
                          PageTemplate("cuerpo", columnas, onPage=pagina_cuerpo)])

    historia = _portada(examen, forma, preguntas, numeros, colegio, datos_examen, tiempo,
                        mostrar_forma, est)
    historia.append(NextPageTemplate("cuerpo"))

    # --- Cuerpo: materia por materia ---
    por_materia: dict[str, list[PreguntaEnForma]] = {}
    for pf in preguntas:
        por_materia.setdefault(pf.etiqueta.split("_")[0], []).append(pf)
    primera = True
    for m in examen.materias:
        lista = por_materia.get(m.codigo, [])
        if not lista:
            continue
        if primera or pagina_por_materia:
            historia.append(PageBreak())
        else:
            historia += [Spacer(1, 10), CondPageBreak(7 * cm)]
        primera = False
        historia.append(_franja(m.nombre, numeros[lista[0].etiqueta],
                                numeros[lista[-1].etiqueta], est))
        historia.append(Spacer(1, 8))
        i = 0
        while i < len(lista):
            pf = lista[i]
            ctx = banco.preguntas[pf.original].contexto
            if ctx:
                # Todas las preguntas seguidas de este contexto
                grupo = [pf]
                while (i + len(grupo) < len(lista)
                       and banco.preguntas[lista[i + len(grupo)].original].contexto == ctx):
                    grupo.append(lista[i + len(grupo)])
                bloque = _bloque_contexto(banco.contextos[ctx], numeros[grupo[0].etiqueta],
                                          numeros[grupo[-1].etiqueta], est)
                # El contexto y su primera pregunta, juntos (si caben)
                historia.append(KeepTogether(bloque + _pregunta(pf, banco, numeros, est)))
                for otra in grupo[1:]:
                    historia.append(KeepTogether(_pregunta(otra, banco, numeros, est)))
                i += len(grupo)
            else:
                historia.append(KeepTogether(_pregunta(pf, banco, numeros, est)))
                i += 1

    historia += [Spacer(1, 14), Paragraph("FIN DEL CUADERNILLO", est["instruccion"].clone(
        "fin", alignment=TA_CENTER, textColor=GRIS))]
    doc.build(historia)
    return ruta


def _franja(materia: str, desde: int, hasta: int, est) -> Table:
    """Franja verde al comenzar cada materia: «MATEMÁTICAS · Preguntas 1 a 25»."""
    tabla = Table([[Paragraph(materia.upper(), est["franja"])],
                   [Paragraph(f"Preguntas {desde} a {hasta}", est["franja_sub"])]],
                  colWidths=[ANCHO_COLUMNA])
    tabla.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), VERDE),
                               ("LEFTPADDING", (0, 0), (-1, -1), 8),
                               ("TOPPADDING", (0, 0), (0, 0), 6),
                               ("BOTTOMPADDING", (0, -1), (-1, -1), 6),
                               ("TOPPADDING", (0, 1), (0, 1), 0)]))
    return tabla


def _bloque_contexto(contexto, desde: int, hasta: int, est) -> list:
    """«RESPONDA LAS PREGUNTAS 26 A 29 ...» + el texto y/o la imagen compartidos."""
    if desde == hasta:
        instruccion = f"RESPONDA LA PREGUNTA {desde} DE ACUERDO CON LA SIGUIENTE INFORMACIÓN"
    else:
        instruccion = (f"RESPONDA LAS PREGUNTAS {desde} A {hasta} DE ACUERDO CON LA "
                       "SIGUIENTE INFORMACIÓN")
    bloque = [Paragraph(instruccion, est["instruccion"])]
    if contexto.texto:
        bloque += [Paragraph(_parrafos(p), est["texto"]) for p in contexto.texto.split("\n\n")]
    if contexto.imagen:
        imagen = _imagen(contexto.imagen, ANCHO_COLUMNA, alto_max=12 * cm)
        if imagen:
            bloque += [Spacer(1, 3), imagen, Spacer(1, 5)]
    return bloque


def vista_previa_pregunta(examen: Examen, banco: Banco, etiqueta: str, zoom: float = 1.6):
    """
    Imagen (PIL) de UNA pregunta tal como saldrá en el cuadernillo (forma A),
    con su texto compartido si tiene. La usa el editor de preguntas.
    """
    from reportlab.platypus import SimpleDocTemplate
    try:
        import pymupdf as fitz
    except ImportError:
        import fitz
    normal, negrita = _registrar_letra()
    est = _estilos(normal, negrita)
    numeros = examen.numeros_impresos()
    p = banco.preguntas[etiqueta]
    opciones = list(p.opciones)
    while opciones and not opciones[-1]:
        opciones.pop()
    pf = PreguntaEnForma(etiqueta, etiqueta, LETRAS[:len(opciones)])
    historia = []
    if p.contexto and p.contexto in banco.contextos:
        # el rango de preguntas que comparten este texto
        mismas = [e for e in examen.todas_las_etiquetas()
                  if e in banco.preguntas and banco.preguntas[e].contexto == p.contexto]
        historia += _bloque_contexto(banco.contextos[p.contexto], numeros[mismas[0]],
                                     numeros[mismas[-1]], est)
    historia += _pregunta(pf, banco, numeros, est)
    memoria = io.BytesIO()
    alto = 60 * cm
    doc = SimpleDocTemplate(memoria, pagesize=(ANCHO_COLUMNA + 24, alto), leftMargin=12,
                            rightMargin=12, topMargin=12, bottomMargin=12)
    try:
        doc.build(historia)
    except Exception:                      # una imagen o texto raro: que no se caiga el editor
        return None
    with fitz.open(stream=memoria.getvalue(), filetype="pdf") as pdf:
        pix = pdf[0].get_pixmap(matrix=fitz.Matrix(zoom, zoom))
        imagen = ImagenPIL.frombytes("RGB", (pix.width, pix.height), pix.samples)
    # recortar el espacio en blanco de abajo
    gris = imagen.convert("L").point(lambda v: 255 if v > 245 else 0)
    caja = ImagenPIL.eval(gris, lambda v: 255 - v).getbbox()
    if caja:
        imagen = imagen.crop((0, 0, imagen.width, min(imagen.height, caja[3] + 14)))
    return imagen


def _pregunta(pf: PreguntaEnForma, banco: Banco, numeros: dict, est) -> list:
    """Número + enunciado + imagen + opciones (ya en el orden de esta forma)."""
    p = banco.preguntas[pf.original]
    bloque = [Paragraph(f"<b>{numeros[pf.etiqueta]}.</b>&nbsp;&nbsp;" + _parrafos(p.enunciado),
                        est["pregunta"])]
    if p.imagen:
        imagen = _imagen(p.imagen, ANCHO_COLUMNA - 17)
        if imagen:
            bloque += [Spacer(1, 2), imagen, Spacer(1, 4)]
    for posicion, letra_banco in zip(LETRAS, pf.opciones):
        texto = p.opciones[LETRAS.index(letra_banco)]
        bloque.append(Paragraph(f"<b>{posicion}.</b>&nbsp;&nbsp;{_parrafos(texto)}", est["opcion"]))
    bloque.append(Spacer(1, 9))
    return bloque


def _portada(examen, forma, preguntas, numeros, colegio, datos_examen, tiempo,
             mostrar_forma, est) -> list:
    """Portada: colegio, examen, la FORMA en grande, materias e instrucciones."""
    ancho = ANCHO - 2 * MARGEN
    historia = [Spacer(1, 0.6 * cm),
                Paragraph(escape(colegio.get("nombre", "").upper()), est["titulo"]),
                Paragraph(escape(colegio.get("municipio", "")), est["sub"]),
                Spacer(1, 0.7 * cm),
                Paragraph("CUADERNILLO DE PREGUNTAS", est["grande"]),
                Paragraph(escape(" · ".join(x for x in (examen.nombre,
                                                         f"Grado {examen.grado}",
                                                         datos_examen.get("fecha", "")) if x)),
                          est["sub"]),
                Spacer(1, 0.7 * cm)]
    if mostrar_forma:
        caja = Table([[Paragraph("FORMA", est["sub"])], [Paragraph(forma, est["forma"])]],
                     colWidths=[5 * cm], rowHeights=[0.8 * cm, 2.6 * cm])
        caja.setStyle(TableStyle([("BOX", (0, 0), (-1, -1), 2, VERDE),
                                  ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                                  ("BACKGROUND", (0, 0), (-1, -1), VERDE_CLARO)]))
        historia += [caja, Spacer(1, 0.7 * cm)]

    # Materias y números de pregunta
    filas = [[Paragraph("<b>Prueba</b>", est["celda"]), Paragraph("<b>Preguntas</b>", est["celda"])]]
    por_materia: dict[str, list[str]] = {}
    for pf in preguntas:
        por_materia.setdefault(pf.etiqueta.split("_")[0], []).append(pf.etiqueta)
    for m in examen.materias:
        etiquetas = por_materia.get(m.codigo, [])
        if etiquetas:
            filas.append([Paragraph(escape(m.nombre), est["celda"]),
                          Paragraph(f"{numeros[etiquetas[0]]} a {numeros[etiquetas[-1]]}",
                                    est["celda"])])
    tabla = Table(filas, colWidths=[8 * cm, 4 * cm])
    tabla.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), VERDE_CLARO),
                               ("GRID", (0, 0), (-1, -1), 0.5, GRIS_LINEA),
                               ("TOPPADDING", (0, 0), (-1, -1), 4),
                               ("BOTTOMPADDING", (0, 0), (-1, -1), 4)]))
    historia += [tabla, Spacer(1, 0.7 * cm)]

    # Instrucciones
    instrucciones = [
        "Marque sus respuestas ÚNICAMENTE en la hoja de respuestas, rellenando "
        "completamente el círculo de la opción que elija. Una sola opción por pregunta.",
        "Use lápiz No. 2 o lapicero de tinta negra. Si se equivoca, borre muy bien.",
        "No escriba ni haga marcas en este cuadernillo.",
    ]
    if mostrar_forma:
        instrucciones.insert(0, f"Este cuadernillo es la <b>FORMA {forma}</b>. Verifique que en su "
                                f"hoja de respuestas esté marcada la forma {forma}.")
    if tiempo:
        instrucciones.append(f"Tiempo para responder: <b>{escape(tiempo)}</b>.")
    caja = Table([[Paragraph("<b>INSTRUCCIONES</b>", est["aviso"])]]
                 + [[Paragraph(f"•&nbsp;&nbsp;{t}", est["aviso"])] for t in instrucciones],
                 colWidths=[ancho - 2 * cm])
    caja.setStyle(TableStyle([("BOX", (0, 0), (-1, -1), 0.8, GRIS_LINEA),
                              ("BACKGROUND", (0, 0), (-1, 0), VERDE_CLARO),
                              ("LEFTPADDING", (0, 0), (-1, -1), 10),
                              ("TOPPADDING", (0, 0), (-1, -1), 3),
                              ("BOTTOMPADDING", (0, 0), (-1, -1), 3)]))
    historia += [caja, Spacer(1, 1.2 * cm),
                 Paragraph("Nombre: ______________________________________________&nbsp;&nbsp; "
                           "Curso: __________", est["aviso"])]
    return historia
