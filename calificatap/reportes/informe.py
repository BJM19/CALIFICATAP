"""
informe.py — Informe de un examen para coordinación / consejo académico (PDF).

Dos páginas con lo que una coordinación necesita para tomar decisiones:

    Página 1 — ¿Cómo le fue al grupo?
        - cifras principales (estudiantes, nota promedio, aprueban, puntaje tipo Saber);
        - niveles de desempeño (Superior, Alto, Básico, Bajo);
        - distribución de las notas (cuántos estudiantes en cada rango);
        - resultados por materia (tabla y gráfico).

    Página 2 — ¿Dónde hay que reforzar?
        - comparación entre cursos (11-01, 11-02...) si hay más de uno;
        - las preguntas más difíciles y la opción errada que más eligieron;
        - preguntas para revisar (mal redactadas o con posible error en la clave);
        - resumen de alertas y espacio para observaciones y firmas.

Los gráficos se dibujan con reportlab.graphics (rectángulos y textos), igual
que en los boletines: no hace falta matplotlib y el PDF queda liviano.
"""

from __future__ import annotations

from collections import Counter
from datetime import date
from pathlib import Path

import pandas as pd
from reportlab.graphics.shapes import Drawing, Line, Rect, String
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import cm
from reportlab.platypus import (KeepTogether, PageBreak, Paragraph, SimpleDocTemplate, Spacer,
                                Table, TableStyle)

from .boletines import (ANCHO_UTIL, CHICO, GRIS, GRIS_CLARO, H2, ROJO, SUB, TEXTO, TITULO,
                        VERDE, VERDE_CLARO, _tarjeta)
from .calificar import Resultados

AMARILLO = colors.HexColor("#E0A100")
AZUL = colors.HexColor("#2E6DA4")

# Niveles de desempeño (Decreto 1290). Los rangos exactos los define el SIEE de
# cada colegio; aquí se usan los más comunes en la escala de 1,0 a 5,0:
#   Bajo < nota de aprobación ≤ Básico < 4,0 ≤ Alto < 4,6 ≤ Superior
# Con otra escala, los cortes de Alto y Superior se ubican en el 75 % y el 90 %.
NIVELES = [("Superior", VERDE), ("Alto", AZUL), ("Básico", AMARILLO), ("Bajo", ROJO)]


def cortes_de_nivel(escala) -> dict[str, float]:
    """Nota mínima de cada nivel de desempeño."""
    rango = escala.maxima - escala.minima
    return {"Superior": round(escala.minima + 0.90 * rango, 1),
            "Alto": round(escala.minima + 0.75 * rango, 1),
            "Básico": escala.aprobacion,
            "Bajo": escala.minima}


def nivel_de(nota: float, cortes: dict[str, float]) -> str:
    for nombre, _ in NIVELES:
        if nota >= cortes[nombre]:
            return nombre
    return "Bajo"


def _estilo_tabla(encabezado_verde: bool = True) -> list:
    estilo = [("FONT", (0, 0), (-1, -1), "Helvetica", 8.5),
              ("FONT", (0, 0), (-1, 0), "Helvetica-Bold", 8.5),
              ("ALIGN", (1, 0), (-1, -1), "CENTER"),
              ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
              ("GRID", (0, 0), (-1, -1), 0.4, GRIS_CLARO),
              ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3)]
    if encabezado_verde:
        estilo.append(("BACKGROUND", (0, 0), (-1, 0), VERDE_CLARO))
    return estilo


# ---------------------------------------------------------------------------
# Gráficos
# ---------------------------------------------------------------------------
def _barra_niveles(conteo: dict[str, int], total: int) -> Drawing:
    """Una barra horizontal partida en colores: qué parte del grupo está en cada nivel."""
    alto, ancho = 34, ANCHO_UTIL
    dibujo = Drawing(ancho, alto)
    x = 0.0
    for nombre, color in NIVELES:
        n = conteo.get(nombre, 0)
        if not n:
            continue
        w = ancho * n / total
        dibujo.add(Rect(x, 12, w, 20, fillColor=color, strokeColor=colors.white, strokeWidth=1))
        if w > 46:
            dibujo.add(String(x + w / 2, 18.5, f"{nombre} {n / total * 100:.0f} %",
                              fontName="Helvetica-Bold", fontSize=8, fillColor=colors.white,
                              textAnchor="middle"))
        x += w
    return dibujo


def _histograma(notas: pd.Series, escala) -> Drawing:
    """Cuántos estudiantes sacaron cada rango de nota (de media en media unidad)."""
    paso = 0.5 if escala.maxima - escala.minima <= 10 else (escala.maxima - escala.minima) / 8
    bordes = []
    inicio = escala.minima
    while inicio < escala.maxima - 1e-9:
        bordes.append(inicio)
        inicio = round(inicio + paso, 2)
    conteos = []
    for i, b in enumerate(bordes):
        fin = bordes[i + 1] if i + 1 < len(bordes) else escala.maxima + 0.001
        conteos.append(int(((notas >= b) & (notas < fin)).sum()))
    alto, ancho = 120, ANCHO_UTIL
    x0, y0, alto_barras = 28, 22, 80
    dibujo = Drawing(ancho, alto)
    maximo = max(conteos) or 1
    ancho_barra = (ancho - x0 - 10) / len(bordes)
    for i, (b, n) in enumerate(zip(bordes, conteos)):
        x = x0 + i * ancho_barra
        h = alto_barras * n / maximo
        color = VERDE if b >= escala.aprobacion else ROJO
        dibujo.add(Rect(x + 3, y0, ancho_barra - 6, h, fillColor=color, strokeColor=None))
        if n:
            dibujo.add(String(x + ancho_barra / 2, y0 + h + 3, str(n), fontName="Helvetica-Bold",
                              fontSize=8, textAnchor="middle"))
        fin = bordes[i + 1] if i + 1 < len(bordes) else escala.maxima
        etiqueta = f"{b:.1f}–{fin - 0.1:.1f}" if i + 1 < len(bordes) else f"{b:.1f}–{fin:.1f}"
        dibujo.add(String(x + ancho_barra / 2, y0 - 11, etiqueta, fontName="Helvetica",
                          fontSize=7, fillColor=GRIS, textAnchor="middle"))
    dibujo.add(Line(x0, y0, ancho - 10, y0, strokeColor=GRIS, strokeWidth=0.6))
    dibujo.add(String(0, y0 + alto_barras / 2, "Est.", fontName="Helvetica", fontSize=7,
                      fillColor=GRIS))
    return dibujo


def _barras_materias(filas: list[tuple[str, float]], aprobacion_pct: float) -> Drawing:
    """Promedio de aciertos de cada materia, con una raya en el % que equivale a aprobar."""
    alto_fila, x0 = 16, 125
    ancho = ANCHO_UTIL - x0 - 40
    alto = alto_fila * len(filas) + 8
    dibujo = Drawing(ANCHO_UTIL, alto)
    for i, (materia, pct) in enumerate(filas):
        y = alto - (i + 1) * alto_fila
        dibujo.add(String(x0 - 6, y + 3, materia[:26], fontName="Helvetica", fontSize=8,
                          textAnchor="end"))
        dibujo.add(Rect(x0, y, ancho, 10, fillColor=GRIS_CLARO, strokeColor=None))
        color = VERDE if pct >= aprobacion_pct else ROJO
        dibujo.add(Rect(x0, y, ancho * pct / 100, 10, fillColor=color, strokeColor=None))
        dibujo.add(String(x0 + ancho + 5, y + 2, f"{pct:.0f} %", fontName="Helvetica-Bold",
                          fontSize=8))
    xa = x0 + ancho * aprobacion_pct / 100
    dibujo.add(Line(xa, 0, xa, alto, strokeColor=colors.black, strokeWidth=0.8,
                    strokeDashArray=[3, 2]))
    return dibujo


# ---------------------------------------------------------------------------
# El informe
# ---------------------------------------------------------------------------
def crear_informe(r: Resultados, ruta: str | Path) -> Path:
    ruta = Path(ruta)
    ex, escala = r.examen, r.escala
    est = r.por_estudiante.copy()
    n = len(est)
    colegio = ex.datos.get("colegio", {})
    fecha = ex.datos.get("examen", {}).get("fecha", "")
    cortes = cortes_de_nivel(escala)
    est["nivel"] = [nivel_de(nota, cortes) for nota in est["nota"]]
    est["curso"] = est["curso"].replace("", "Sin curso").fillna("Sin curso")
    # % de aciertos que equivale a la nota de aprobación (3,0 → 50 % en la escala 1–5)
    aprob_pct = (escala.aprobacion - escala.minima) / (escala.maxima - escala.minima) * 100
    materias = [m for m in ex.materias if m.nombre in est]
    preguntas = r.preguntas_analisis           # con las formas juntas, si se puede
    vigentes = preguntas[preguntas["anulada"] == ""] if "anulada" in preguntas else preguntas
    sin_hoja = sum(1 for tipo, _ in r.alertas if tipo == "Sin hoja")

    historia = []
    # ===================== PÁGINA 1 =====================
    historia += [
        Paragraph(colegio.get("nombre", "Institución educativa").upper(), TITULO),
        Paragraph(" · ".join(x for x in (colegio.get("municipio", ""), ex.nombre,
                                          f"Grado {ex.grado}" if ex.grado else "", fecha) if x), SUB),
        Spacer(1, 2),
        Paragraph("<b>INFORME DE RESULTADOS PARA COORDINACIÓN</b>",
                  SUB.clone("s2", fontSize=11, textColor=colors.black)),
        Spacer(1, 10)]

    promedio_pct = est["porcentaje"].mean()
    nota_prom = escala.nota(promedio_pct / 100)
    aprueban = int(est["aprobado"].sum())
    tarjetas = [
        _tarjeta(f"{n}", "Estudiantes calificados" + (f" ({sin_hoja} sin hoja)" if sin_hoja else "")),
        _tarjeta(f"{nota_prom:.1f}", f"Nota promedio · {promedio_pct:.0f} % de aciertos",
                 VERDE if nota_prom >= escala.aprobacion else ROJO),
        _tarjeta(f"{aprueban / n * 100:.0f} %", f"Aprueban ({aprueban} de {n})"),
    ]
    if r.con_puntaje:
        tarjetas.append(_tarjeta(f"{est['puntaje'].mean():.0f}", "Puntaje tipo Saber (de 500)"))
    tabla = Table([tarjetas], colWidths=[ANCHO_UTIL / len(tarjetas)] * len(tarjetas))
    tabla.setStyle(TableStyle([("BOX", (0, 0), (-1, -1), 0.5, GRIS_CLARO),
                               ("INNERGRID", (0, 0), (-1, -1), 0.5, GRIS_CLARO),
                               ("TOPPADDING", (0, 0), (-1, -1), 8),
                               ("BOTTOMPADDING", (0, 0), (-1, -1), 8)]))
    historia += [tabla, Spacer(1, 4)]

    # --- Niveles de desempeño ---
    conteo = Counter(est["nivel"])
    historia.append(Paragraph("Niveles de desempeño", H2))
    filas = [["Nivel", "Rango de nota", "Estudiantes", "% del grupo"]]
    limites = [escala.maxima, cortes["Superior"], cortes["Alto"], cortes["Básico"]]
    for i, (nombre, _) in enumerate(NIVELES):
        desde = cortes[nombre]
        hasta = limites[i] if i == 0 else round(limites[i] - 0.1, 1)
        filas.append([nombre, f"{desde:.1f} a {hasta:.1f}", conteo.get(nombre, 0),
                      f"{conteo.get(nombre, 0) / n * 100:.0f} %"])
    tabla = Table(filas, colWidths=[3.5 * cm, 3.5 * cm, 3 * cm, 3 * cm])
    estilo = _estilo_tabla()
    for i, (_, color) in enumerate(NIVELES, start=1):
        estilo += [("TEXTCOLOR", (0, i), (0, i), color), ("FONT", (0, i), (0, i), "Helvetica-Bold", 8.5)]
    tabla.setStyle(TableStyle(estilo))
    historia += [tabla, Spacer(1, 4), _barra_niveles(conteo, n),
                 Paragraph("Rangos habituales del Decreto 1290; si el SIEE del colegio usa otros, "
                           "téngalo en cuenta al leer esta tabla.", CHICO)]

    # --- Distribución de notas ---
    historia += [Paragraph("Distribución de las notas", H2), _histograma(est["nota"], escala),
                 Paragraph(f"En rojo, los rangos por debajo de la nota de aprobación "
                           f"({escala.aprobacion:.1f}).", CHICO)]

    # --- Por materia ---
    historia.append(Paragraph("Resultados por materia", H2))
    filas = [["Materia", "Preguntas", "Promedio", "Nota prom.", "Mejor", "Más bajo",
              "Aprueban"]]
    for _, m in r.por_materia.iterrows():
        filas.append([m["materia"], m["preguntas"], f"{m['promedio']:.0f} %",
                      f"{m['nota_promedio']:.1f}", f"{m['maximo']:.0f} %", f"{m['minimo']:.0f} %",
                      f"{m['aprueban'] / n * 100:.0f} %"])
    tabla = Table(filas, colWidths=[4.6 * cm, 1.8 * cm, 1.9 * cm, 1.9 * cm, 1.7 * cm, 1.9 * cm,
                                    2.0 * cm])
    estilo = _estilo_tabla()
    for i, (_, m) in enumerate(r.por_materia.iterrows(), start=1):
        if m["nota_promedio"] < escala.aprobacion:
            estilo.append(("TEXTCOLOR", (3, i), (3, i), ROJO))
    tabla.setStyle(TableStyle(estilo))
    historia += [tabla, Spacer(1, 6),
                 _barras_materias(list(zip(r.por_materia["materia"], r.por_materia["promedio"])),
                                  aprob_pct),
                 Paragraph(f"Promedio de aciertos. La raya punteada marca el {aprob_pct:.0f} %, "
                           "que equivale a la nota de aprobación.", CHICO)]

    # ===================== PÁGINA 2 =====================
    historia.append(PageBreak())

    # --- Comparación entre cursos ---
    cursos = sorted(est["curso"].unique())
    historia.append(Paragraph("Comparación entre cursos", H2))
    if len(cursos) > 1:
        codigos = [m.codigo for m in materias]
        filas = [["Curso", "Est.", *codigos, "Nota prom.", "Aprueban"]
                 + (["Puntaje"] if r.con_puntaje else [])]
        for curso in cursos + ["Todos"]:
            grupo = est if curso == "Todos" else est[est["curso"] == curso]
            fila = [curso, len(grupo)]
            fila += [f"{grupo[m.nombre].mean():.0f} %" for m in materias]
            fila += [f"{escala.nota(grupo['porcentaje'].mean() / 100):.1f}",
                     f"{grupo['aprobado'].mean() * 100:.0f} %"]
            if r.con_puntaje:
                fila.append(f"{grupo['puntaje'].mean():.0f}")
            filas.append(fila)
        ancho_otros = (ANCHO_UTIL - 2.4 * cm - 1.2 * cm) / (len(filas[0]) - 2)
        tabla = Table(filas, colWidths=[2.4 * cm, 1.2 * cm] + [ancho_otros] * (len(filas[0]) - 2))
        estilo = _estilo_tabla() + [("FONT", (0, len(filas) - 1), (-1, len(filas) - 1),
                                     "Helvetica-Bold", 8.5),
                                    ("BACKGROUND", (0, len(filas) - 1), (-1, len(filas) - 1),
                                     colors.HexColor("#F3F5F4"))]
        # En cada materia, el mejor curso en verde y el más bajo en rojo
        for j, m in enumerate(materias, start=2):
            valores = {i: est[est["curso"] == c][m.nombre].mean() for i, c in enumerate(cursos, 1)}
            if len(set(round(v) for v in valores.values())) > 1:
                estilo += [("TEXTCOLOR", (j, max(valores, key=valores.get)),
                            (j, max(valores, key=valores.get)), VERDE),
                           ("TEXTCOLOR", (j, min(valores, key=valores.get)),
                            (j, min(valores, key=valores.get)), ROJO)]
        tabla.setStyle(TableStyle(estilo))
        historia += [tabla, Paragraph("Promedio de aciertos por materia. En verde, el curso con el "
                                      "mejor resultado en cada materia; en rojo, el más bajo.",
                                      CHICO)]
    else:
        historia.append(Paragraph(
            f"Todos los estudiantes son del curso {cursos[0]}." if cursos[0] != "Sin curso" else
            "No se cargó la lista de estudiantes con el curso, así que no se pueden comparar cursos.",
            TEXTO))

    # --- Preguntas más difíciles ---
    historia.append(Paragraph("Las 10 preguntas más difíciles", H2))
    if r.formas_juntas:
        historia.append(Paragraph("Con todas las formas juntas; los números son los de la "
                                  "forma A.", CHICO))
    hay_formas = bool(ex.letras_formas) and not r.formas_juntas
    dificiles = vigentes.sort_values("acierto").head(10)
    filas = [["N.º"] + (["Forma"] if hay_formas else []) +
             ["Materia", "Acertó", "Clave", "Errada más elegida", "¿Discrimina?"]]
    for _, p in dificiles.iterrows():
        errada = "—"
        if p["distractor"]:
            veces = p.get(p["distractor"], "")
            pct = f" ({veces / p['respondieron'] * 100:.0f} %)" if veces != "" and p["respondieron"] else ""
            errada = f"{p['distractor']}{pct}"
        filas.append([p["pregunta"]] + ([p["forma"]] if hay_formas else []) +
                     [p["materia"], f"{p['acierto']:.0f} %", p["clave"], errada,
                      p["calidad"] or "—"])
    anchos = [1.2 * cm] + ([1.3 * cm] if hay_formas else []) + \
             [5.0 * cm, 1.8 * cm, 1.6 * cm, 3.6 * cm, 2.6 * cm]
    tabla = Table(filas, colWidths=anchos)
    col_materia = 2 if hay_formas else 1
    tabla.setStyle(TableStyle(_estilo_tabla() + [("ALIGN", (col_materia, 0), (col_materia, -1),
                                                   "LEFT")]))
    historia += [tabla, Paragraph("«Errada más elegida»: si muchos eligieron la misma opción "
                                  "equivocada, puede haber un error de concepto común que vale la "
                                  "pena trabajar en clase.", CHICO)]

    # --- Preguntas para revisar ---
    revisar = vigentes[(vigentes["calidad"] == "Revisar") | (vigentes["sospecha_clave"] != "")]
    anuladas = preguntas[preguntas["anulada"] != ""] if "anulada" in preguntas else preguntas.iloc[0:0]
    historia.append(Paragraph("Preguntas para revisar en el cuadernillo", H2))
    lineas = []
    sospechas = revisar[revisar["sospecha_clave"] != ""]
    if not sospechas.empty:
        lineas.append("<b>Posible error en la clave:</b> " + ", ".join(
            f"{p['pregunta']}{' (' + p['forma'] + ')' if p['forma'] not in ('', '*') else ''} "
            f"(clave {p['clave']}, los mejores marcaron {p['sospecha_clave']})"
            for _, p in sospechas.iterrows()))
    no_discriminan = revisar[revisar["sospecha_clave"] == ""]
    if not no_discriminan.empty:
        numeros = [str(p["pregunta"]) + (f" ({p['forma']})" if p["forma"] not in ("", "*") else "")
                   for _, p in no_discriminan.iterrows()]
        resto = f" y {len(numeros) - 30} más (ver el Excel)" if len(numeros) > 30 else ""
        lineas.append(f"<b>No distinguen a quienes saben de quienes no</b> ({len(numeros)}; "
                      "pueden estar mal redactadas o ser ambiguas): "
                      + ", ".join(numeros[:30]) + resto)
    if not anuladas.empty:
        lineas.append("<b>Anuladas por el docente:</b> " + ", ".join(
            f"{p['pregunta']} ({'buena para todos' if p['anulada'] == 'bien' else 'no cuenta'})"
            for _, p in anuladas.iterrows()))
    if preguntas["calidad"].eq("").all():
        lineas.append("Con menos de 10 estudiantes no se calcula si las preguntas discriminan.")
    for linea in lineas or ["No hay preguntas para revisar."]:
        historia += [Paragraph(linea, TEXTO), Spacer(1, 3)]

    # --- Alertas ---
    if r.alertas:
        historia.append(Paragraph("Alertas", H2))
        # (sin el símbolo ⚠: la letra del PDF no lo tiene)
        resumen = Counter(tipo.replace("⚠", "").strip() for tipo, _ in r.alertas)
        historia.append(Paragraph(" · ".join(f"{tipo}: {c}" for tipo, c in resumen.items()), TEXTO))

    # --- Observaciones y firmas ---
    historia.append(KeepTogether([
        Paragraph("Observaciones", H2),
        Table([[""], [""], [""]], colWidths=[ANCHO_UTIL], rowHeights=[16] * 3,
              style=[("LINEBELOW", (0, 0), (-1, -1), 0.5, GRIS_CLARO)]),
        Spacer(1, 26),
        Table([["_______________________________", "_______________________________"],
               ["Docente", "Coordinación académica"]],
              colWidths=[ANCHO_UTIL / 2] * 2,
              style=[("FONT", (0, 0), (-1, -1), "Helvetica", 8.5),
                     ("TEXTCOLOR", (0, 1), (-1, 1), GRIS),
                     ("ALIGN", (0, 0), (-1, -1), "CENTER")]),
        Spacer(1, 8),
        Paragraph(f"Generado con CalificaTAP el {date.today():%d/%m/%Y}. Escala de notas "
                  f"{escala.minima:.1f} a {escala.maxima:.1f}; aprueba con {escala.aprobacion:.1f}."
                  + (" El puntaje tipo Saber es una aproximación (cada materia = % de aciertos)."
                     if r.con_puntaje else ""), CHICO)]))

    def pie(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 7.5)
        canvas.setFillColor(GRIS)
        canvas.drawRightString(letter[0] - 1.8 * cm, 0.8 * cm,
                               f"{ex.nombre} · página {doc.page}")
        canvas.restoreState()

    doc = SimpleDocTemplate(str(ruta), pagesize=letter, title=f"Informe · {ex.nombre}",
                            author="CalificaTAP", leftMargin=1.8 * cm, rightMargin=1.8 * cm,
                            topMargin=1.2 * cm, bottomMargin=1.3 * cm)
    doc.build(historia, onFirstPage=pie, onLaterPages=pie)
    return ruta
