"""
boletines.py — Un informe de una página para cada estudiante (PDF).

Cada boletín tiene:
    - los datos del colegio, del examen y del estudiante;
    - su nota, su porcentaje de aciertos y su puesto en el curso;
    - una tabla y un gráfico por materia, comparando con el promedio del curso;
    - las preguntas que debe repasar (las que falló o dejó en blanco),
      con lo que marcó y la respuesta correcta.

Todos los boletines van en un solo PDF (una página por estudiante), en orden
alfabético, listos para imprimir y entregar.

Se dibuja con reportlab "platypus" (bloques que se acomodan solos en la página)
y el gráfico con reportlab.graphics (rectángulos), que es mucho más rápido que
hacer un gráfico de matplotlib por cada estudiante.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd
from reportlab.graphics.shapes import Drawing, Line, Rect, String
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from .calificar import Resultados

VERDE = colors.HexColor("#1F7A4D")
VERDE_CLARO = colors.HexColor("#E3F1E9")
ROJO = colors.HexColor("#B3261E")
ROJO_CLARO = colors.HexColor("#FBE9E7")
GRIS = colors.HexColor("#5C6B64")
GRIS_CLARO = colors.HexColor("#E4E8E6")

_base = getSampleStyleSheet()
TITULO = ParagraphStyle("t", parent=_base["Title"], fontSize=15, textColor=VERDE, spaceAfter=2)
SUB = ParagraphStyle("s", parent=_base["Normal"], fontSize=9.5, textColor=GRIS, alignment=1)
H2 = ParagraphStyle("h2", parent=_base["Heading3"], fontSize=11, spaceBefore=8, spaceAfter=4,
                    textColor=colors.black)
TEXTO = ParagraphStyle("x", parent=_base["Normal"], fontSize=9, leading=12)
CHICO = ParagraphStyle("c", parent=TEXTO, fontSize=8, textColor=GRIS, leading=10)
GRANDE = ParagraphStyle("g", parent=_base["Normal"], fontSize=22, leading=26, alignment=1)
ETIQUETA = ParagraphStyle("e", parent=_base["Normal"], fontSize=8, textColor=GRIS, alignment=1)

ANCHO_UTIL = letter[0] - 3.6 * cm


def _tarjeta(valor: str, etiqueta: str, color=colors.black) -> list:
    estilo = ParagraphStyle("v", parent=GRANDE, textColor=color)
    return [Paragraph(f"<b>{valor}</b>", estilo), Paragraph(etiqueta, ETIQUETA)]


def _grafico_materias(filas: list[tuple[str, float, float]]) -> Drawing:
    """
    Barras horizontales: el % del estudiante (verde) y una rayita con el
    promedio del curso (gris), una fila por materia.
    """
    alto_fila, x0, ancho = (18 if len(filas) <= 5 else 14), 120, ANCHO_UTIL - 160
    alto = alto_fila * len(filas) + 22
    dibujo = Drawing(ANCHO_UTIL, alto)
    for i, (materia, pct_est, pct_curso) in enumerate(filas):
        y = alto - 14 - (i + 1) * alto_fila
        dibujo.add(String(x0 - 6, y + 4, materia[:24], fontName="Helvetica", fontSize=8,
                          textAnchor="end"))
        dibujo.add(Rect(x0, y, ancho, 11, fillColor=GRIS_CLARO, strokeColor=None))
        if not pd.isna(pct_est):
            dibujo.add(Rect(x0, y, ancho * pct_est / 100, 11, fillColor=VERDE, strokeColor=None))
            dibujo.add(String(x0 + ancho + 6, y + 2.5, f"{pct_est:.0f} %", fontName="Helvetica-Bold",
                              fontSize=8))
        if not pd.isna(pct_curso):
            xc = x0 + ancho * pct_curso / 100
            dibujo.add(Line(xc, y - 2, xc, y + 13, strokeColor=colors.black, strokeWidth=1.6))
    # Leyenda
    dibujo.add(Rect(x0, alto - 9, 10, 7, fillColor=VERDE, strokeColor=None))
    dibujo.add(String(x0 + 14, alto - 8, "Estudiante", fontName="Helvetica", fontSize=7.5))
    dibujo.add(Line(x0 + 75, alto - 10, x0 + 75, alto - 1, strokeColor=colors.black, strokeWidth=1.6))
    dibujo.add(String(x0 + 80, alto - 8, "Promedio del curso", fontName="Helvetica", fontSize=7.5))
    return dibujo


def _preguntas_para_repasar(r: Resultados, documento: str) -> list[tuple[str, list[str]]]:
    """
    [(materia, ["3 (B/D)", "7 (—/A)", ...]), ...]
    Entre paréntesis: lo que marcó / la respuesta correcta ("—" = en blanco).
    Se escribe corto para que el boletín quepa en una sola página.
    """
    if documento not in r.respuestas.index:
        return []
    forma = r.formas.get(documento, "A")
    clave = r.claves.get(forma, {})
    numeros = r.examen.numeros_impresos()
    resultado = []
    for m in r.examen.materias:
        falladas = []
        for e in m.etiquetas():
            acierto = r.aciertos.at[documento, e]
            if pd.isna(acierto) or acierto:
                continue
            marcada = r.respuestas.at[documento, e] or "—"
            falladas.append(f"{numeros[e]} ({marcada}/{clave.get(e, '?')})")
        if falladas:
            resultado.append((m.nombre, falladas))
    return resultado


def crear_boletines(r: Resultados, ruta: str | Path, documentos: list[str] | None = None) -> Path:
    """Crea el PDF con un boletín por estudiante (o solo los 'documentos' indicados)."""
    ruta = Path(ruta)
    ex, escala = r.examen, r.escala
    colegio = ex.datos.get("colegio", {})
    fecha = ex.datos.get("examen", {}).get("fecha", "")
    est = r.por_estudiante.copy()
    if documentos is not None:
        est = est[est["documento"].isin(documentos)]
    est = est.sort_values(["curso", "nombre", "documento"])
    total = len(r.por_estudiante)
    promedios = dict(zip(r.por_materia["materia"], r.por_materia["promedio"])) \
        if not r.por_materia.empty else {}
    materias = [m for m in ex.materias if m.nombre in r.por_estudiante]

    historia = []
    for n, (_, f) in enumerate(est.iterrows()):
        if n:
            historia.append(PageBreak())
        # --- Encabezado ---
        historia += [Paragraph(colegio.get("nombre", "").upper(), TITULO),
                     Paragraph(" · ".join(x for x in (colegio.get("municipio", ""), ex.nombre,
                                                      f"Grado {ex.grado}", fecha) if x), SUB),
                     Spacer(1, 6),
                     Paragraph("<b>INFORME DE RESULTADOS</b>", ParagraphStyle(
                         "i", parent=SUB, textColor=colors.black, fontSize=10.5)),
                     Spacer(1, 8)]
        # --- Datos del estudiante ---
        datos = [["Estudiante:", f["nombre"] or "—", "Documento:", f["documento"]],
                 ["Curso:", f["curso"] or "—", "Forma:" if "forma" in f else "",
                  f.get("forma", "") if "forma" in f else ""]]
        tabla = Table(datos, colWidths=[2.2 * cm, 7.6 * cm, 2.4 * cm, 4 * cm])
        tabla.setStyle(TableStyle([("FONT", (0, 0), (-1, -1), "Helvetica", 9.5),
                                   ("FONT", (0, 0), (0, -1), "Helvetica-Bold", 9.5),
                                   ("FONT", (2, 0), (2, -1), "Helvetica-Bold", 9.5),
                                   ("FONT", (1, 0), (1, 0), "Helvetica-Bold", 11),
                                   ("BOX", (0, 0), (-1, -1), 0.5, GRIS_CLARO),
                                   ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F7F9F8"))]))
        historia += [tabla, Spacer(1, 10)]

        # --- Tarjetas: nota, %, puesto, aprueba ---
        aprueba = bool(f["aprobado"])
        color_nota = VERDE if aprueba else ROJO
        if r.con_puntaje and not pd.isna(f["puntaje"]):
            # Simulacro tipo Saber 11: el puntaje de 0 a 500 en lugar del %
            segunda = _tarjeta(f"{int(f['puntaje'])}",
                               "Puntaje tipo Saber (de 500)")
        else:
            segunda = _tarjeta(f"{f['porcentaje']:.0f} %", f"Aciertos: {int(f['aciertos'])}")
        tarjetas = Table([[_tarjeta(f"{f['nota']:.1f}", f"Nota (de {escala.minima:.1f} a {escala.maxima:.1f})", color_nota),
                           segunda,
                           _tarjeta(f"{int(f['puesto'])} de {total}", "Puesto en el curso"),
                           _tarjeta("Sí" if aprueba else "No", f"Aprueba (desde {escala.aprobacion:.1f})",
                                    color_nota)]],
                         colWidths=[ANCHO_UTIL / 4] * 4)
        tarjetas.setStyle(TableStyle([("BOX", (0, 0), (-1, -1), 0.5, GRIS_CLARO),
                                      ("INNERGRID", (0, 0), (-1, -1), 0.5, GRIS_CLARO),
                                      ("BACKGROUND", (0, 0), (0, 0), VERDE_CLARO if aprueba else ROJO_CLARO),
                                      ("TOPPADDING", (0, 0), (-1, -1), 8),
                                      ("BOTTOMPADDING", (0, 0), (-1, -1), 8)]))
        historia += [tarjetas, Spacer(1, 6)]

        # --- Por materia ---
        historia.append(Paragraph("Resultados por materia", H2))
        filas = [["Materia", "Aciertos", "% del estudiante", "Nota", "Promedio del curso"]]
        datos_grafico = []
        for m in materias:
            pct = f[m.nombre]
            de_la_materia = (r.aciertos.loc[f["documento"], m.etiquetas()]
                             if f["documento"] in r.aciertos.index else pd.Series(dtype=float))
            correctas = de_la_materia.sum()
            cuentan = int(de_la_materia.notna().sum()) or m.preguntas   # sin las anuladas que no cuentan
            prom = promedios.get(m.nombre, float("nan"))
            filas.append([m.nombre, f"{int(correctas)} de {cuentan}",
                          "—" if pd.isna(pct) else f"{pct:.0f} %",
                          "—" if pd.isna(pct) else f"{escala.nota(pct / 100):.1f}",
                          "—" if pd.isna(prom) else f"{prom:.0f} %"])
            datos_grafico.append((m.nombre, pct, prom))
        tabla = Table(filas, colWidths=[5.6 * cm, 2.6 * cm, 3.2 * cm, 1.8 * cm, 3.2 * cm])
        tabla.setStyle(TableStyle([("FONT", (0, 0), (-1, -1), "Helvetica", 9),
                                   ("FONT", (0, 0), (-1, 0), "Helvetica-Bold", 9),
                                   ("BACKGROUND", (0, 0), (-1, 0), VERDE_CLARO),
                                   ("ALIGN", (1, 0), (-1, -1), "CENTER"),
                                   ("GRID", (0, 0), (-1, -1), 0.4, GRIS_CLARO)]))
        historia += [tabla, Spacer(1, 8), _grafico_materias(datos_grafico)]

        # --- Preguntas para repasar ---
        repasar = _preguntas_para_repasar(r, f["documento"])
        historia.append(Paragraph("Preguntas para repasar", H2))
        if repasar:
            historia.append(Paragraph("Número de la pregunta y, entre paréntesis, lo que marcó / "
                                      "la respuesta correcta (— = la dejó en blanco).", CHICO))
            historia.append(Spacer(1, 3))
            for materia, lista in repasar:
                historia.append(Paragraph(f"<b>{materia}:</b> " + ", ".join(lista), TEXTO))
                historia.append(Spacer(1, 3))
        else:
            historia.append(Paragraph("¡Ninguna! Respondió bien todas las preguntas.", TEXTO))

        # --- Pie ---
        historia += [Spacer(1, 14),
                     Table([["_______________________________", "_______________________________"],
                            ["Firma del docente", "Firma del acudiente"]],
                           colWidths=[ANCHO_UTIL / 2] * 2,
                           style=[("FONT", (0, 0), (-1, -1), "Helvetica", 8.5),
                                  ("TEXTCOLOR", (0, 1), (-1, 1), GRIS),
                                  ("ALIGN", (0, 0), (-1, -1), "CENTER")]),
                     Spacer(1, 8),
                     Paragraph(f"Generado con CalificaTAP el {date.today():%d/%m/%Y}.", CHICO)]

    if not historia:
        historia.append(Paragraph("No hay estudiantes calificados.", TEXTO))
    doc = SimpleDocTemplate(str(ruta), pagesize=letter, title=f"Boletines · {ex.nombre}",
                            author="CalificaTAP", leftMargin=1.8 * cm, rightMargin=1.8 * cm,
                            topMargin=1.2 * cm, bottomMargin=1.2 * cm)
    doc.build(historia)
    return ruta
