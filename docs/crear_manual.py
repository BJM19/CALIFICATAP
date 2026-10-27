"""
crear_manual.py — Arma el «Manual CalificaTAP.pdf» para docentes.

El texto está aquí mismo y las imágenes en docs/capturas/. Si cambian la
aplicación, actualicen las capturas y el texto, y vuelvan a ejecutar:

    python docs/crear_manual.py

Usa reportlab "platypus": en lugar de dibujar cada línea en una posición, se
arma una lista de bloques (títulos, párrafos, imágenes, tablas) y reportlab
los acomoda en las páginas solo.
"""

from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (Image, KeepTogether, ListFlowable, ListItem, PageBreak,
                                Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle)

RAIZ = Path(__file__).resolve().parent.parent
CAPTURAS = Path(__file__).resolve().parent / "capturas"
SALIDA = RAIZ / "Manual CalificaTAP.pdf"

VERDE = colors.HexColor("#1F7A4D")
VERDE_CLARO = colors.HexColor("#E3F1E9")
AMARILLO = colors.HexColor("#FFF4D6")
ROJO_CLARO = colors.HexColor("#FBE9E7")
GRIS = colors.HexColor("#5C6B64")

# --- Estilos de texto -----------------------------------------------------
base = getSampleStyleSheet()
TITULO = ParagraphStyle("titulo", parent=base["Title"], fontSize=30, textColor=VERDE,
                        spaceAfter=10)
SUB = ParagraphStyle("sub", parent=base["Normal"], fontSize=14, textColor=GRIS,
                     alignment=TA_CENTER, leading=18)
H1 = ParagraphStyle("h1", parent=base["Heading1"], fontSize=18, textColor=VERDE,
                    spaceBefore=6, spaceAfter=8)
H2 = ParagraphStyle("h2", parent=base["Heading2"], fontSize=13, textColor=colors.black,
                    spaceBefore=10, spaceAfter=4)
TEXTO = ParagraphStyle("texto", parent=base["Normal"], fontSize=10.5, leading=15, spaceAfter=6)
NOTA = ParagraphStyle("nota", parent=TEXTO, fontSize=9.5, textColor=GRIS, leading=13)
PIE = ParagraphStyle("pie", parent=NOTA, alignment=TA_CENTER, spaceAfter=10)


def p(texto, estilo=TEXTO):
    return Paragraph(texto, estilo)


def lista(items, numerada=False):
    return ListFlowable([ListItem(p(t), leftIndent=14) for t in items],
                        bulletType="1" if numerada else "bullet", start="1" if numerada else None,
                        leftIndent=14, bulletFontSize=9)


def captura(nombre, ancho_cm=16.5, pie=""):
    ruta = CAPTURAS / nombre
    img = Image(str(ruta))
    proporcion = img.imageHeight / img.imageWidth
    img.drawWidth, img.drawHeight = ancho_cm * cm, ancho_cm * cm * proporcion
    bloque = [img]
    if pie:
        bloque.append(p(pie, PIE))
    return KeepTogether(bloque)


def recuadro(texto, fondo=VERDE_CLARO):
    """Un consejo o advertencia dentro de un recuadro de color."""
    t = Table([[p(texto)]], colWidths=[16.5 * cm])
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), fondo),
                           ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#D5DDD9")),
                           ("LEFTPADDING", (0, 0), (-1, -1), 10),
                           ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                           ("TOPPADDING", (0, 0), (-1, -1), 6),
                           ("BOTTOMPADDING", (0, 0), (-1, -1), 6)]))
    return t


def tabla(filas, anchos, colores_filas=None):
    datos = [[p(f"<b>{c}</b>") for c in filas[0]]] + [[p(c) for c in f] for f in filas[1:]]
    t = Table(datos, colWidths=[a * cm for a in anchos])
    estilo = [("BACKGROUND", (0, 0), (-1, 0), VERDE_CLARO),
              ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#D5DDD9")),
              ("VALIGN", (0, 0), (-1, -1), "TOP")]
    for i, color in (colores_filas or {}).items():
        estilo.append(("BACKGROUND", (0, i), (0, i), color))
    t.setStyle(TableStyle(estilo))
    return t


def numero_de_pagina(canvas, doc):
    canvas.saveState()
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(GRIS)
    canvas.drawCentredString(letter[0] / 2, 1.2 * cm,
                             f"CalificaTAP · Manual para docentes · página {doc.page}")
    canvas.restoreState()


# =========================================================================
# Contenido
# =========================================================================
h = []   # "historia": la lista de bloques del documento

# --- Portada ---
h += [Spacer(1, 2.5 * cm), p("CalificaTAP", TITULO),
      p("Hojas de respuestas que se califican solas", SUB), Spacer(1, 0.6 * cm),
      p("Manual para docentes", SUB), Spacer(1, 1.2 * cm),
      captura("00_hoja_con_nombre.png", 9),
      Spacer(1, 0.8 * cm),
      p("Media Técnica en Desarrollo de Software · IESTAP · Puerto López, Meta", PIE),
      PageBreak()]

# --- 1. Qué es ---
h += [p("1. ¿Qué hace CalificaTAP?", H1),
      p("CalificaTAP crea hojas de respuestas para sus exámenes, las <b>lee</b> a partir de un "
        "escaneo o de fotos, y le entrega las <b>notas</b>, los resultados por materia y por "
        "pregunta, y un archivo de Excel. Funciona <b>sin internet</b>."),
      tabla([["Pestaña", "Para qué sirve"],
             ["1. Crear hoja", "Diseñar la hoja (materias, preguntas, opciones) e imprimirla, "
                               "en blanco o con el nombre de cada estudiante."],
             ["2. Leer hojas", "Cargar el PDF del escáner o las fotos. El programa lee cada hoja "
                               "y le muestra lo que detectó."],
             ["3. Resultados", "Escribir la clave y ver notas, gráficos y alertas. Exportar a Excel."],
             ["4. Seguimiento", "Comparar varios exámenes para ver si el curso mejora."]],
            [4, 12.5]),
      Spacer(1, 0.4 * cm),
      p("1.1 Instalación (una sola vez, con internet)", H2),
      lista(["Instale Python desde <i>python.org</i>. Al instalar, marque la casilla "
             "<b>«Add python.exe to PATH»</b>.",
             "En la carpeta de CalificaTAP, haga doble clic en <b>Instalar.bat</b> y espere a "
             "que diga «Listo».",
             "Para abrir el programa, cada vez: doble clic en <b>Abrir CalificaTAP.bat</b>."],
            numerada=True),
      recuadro("La carpeta <b>externo\\OMRChecker</b> debe estar dentro de la carpeta de "
               "CalificaTAP: es el «motor» que lee las burbujas. Si falta, pida ayuda a quien "
               "le instaló el programa."),
      PageBreak()]

# --- 2. Crear la hoja ---
h += [p("2. Crear la hoja de respuestas", H1),
      lista(["<b>Colegio y examen:</b> nombre, municipio, logo (opcional), nombre del examen, "
             "grado y fecha.",
             "<b>Materias:</b> con «+ Agregar» se añade una materia; en la parte de abajo se "
             "escribe su nombre, cuántas preguntas tiene y cuántas opciones (A–D, A–E...). El "
             "botón «Plantilla Saber 11» carga las cinco materias de una vez.",
             "Mire la <b>vista previa</b> a la derecha: se actualiza sola. Si algo no cabe, una "
             "franja roja le dice qué corregir."], numerada=True),
      captura("01_crear_arriba.png", pie="Pestaña «Crear hoja»: formulario a la izquierda, "
                                         "vista previa a la derecha."),
      p("2.1 Opciones", H2),
      lista(["<b>Dígitos del documento:</b> las cifras del documento más largo del curso.",
             "<b>Numeración:</b> seguida en toda la hoja (1 a 105) o empezando en 1 en cada materia.",
             "<b>Formas (opcional):</b> para hacer un cuadernillo A y otro B (ver sección 2.3)."]),
      p("2.2 Hojas con nombre (recomendado)", H2),
      p("En la sección 5 pulse <b>«Importar lista»</b> y elija el Excel o CSV del curso (por "
        "ejemplo, el del SIMAT). El programa le pregunta cuál columna es el documento y cuál el "
        "nombre. Al generar, además de la hoja en blanco, se crea <b>hojas_con_nombre.pdf</b>: "
        "una hoja por estudiante con su nombre y su documento <b>ya marcados</b>. Así nadie se "
        "equivoca al rellenar el documento, que es el error más común."),
      captura("02_crear_abajo.png", pie="Opciones, formas y hojas con nombre. La vista previa "
                                        "muestra la hoja del primer estudiante."),
      p("2.3 Formas A y B (opcional)", H2),
      p("Si elige 2 formas, la hoja trae la casilla <b>FORMA</b>. La hoja de respuestas es la "
        "misma para todos; lo que cambia es el <b>cuadernillo de preguntas</b>: en el cuadernillo "
        "B usted cambia el orden de las opciones, así la respuesta correcta queda en otra letra. "
        "En «Resultados» escribirá una clave para cada forma. Con hojas con nombre, las formas se "
        "reparten en orden (A, B, A, B...) y ya vienen marcadas."),
      p("2.4 Generar e imprimir", H2),
      p("Pulse <b>«Generar hoja de respuestas»</b>. Se abre una ventana con el botón para abrir "
        "el PDF."),
      recuadro("<b>Al imprimir, elija «Tamaño real» o «100 %»</b>, nunca «Ajustar a la página». "
               "Si la hoja se encoge, las marcas negras de las esquinas cambian de lugar y el "
               "programa no la podrá leer.", AMARILLO),
      Spacer(1, 0.3 * cm),
      p("Cada examen recibe un <b>código</b> que se imprime en la franja de abajo de la hoja. "
        "Sirve para que, si se cuela una hoja de otro examen, el programa lo detecte. Si vuelve "
        "a generar el mismo examen sin cambiar el diseño, el código se conserva y las hojas ya "
        "impresas siguen sirviendo. Si cambia el diseño (materias, preguntas, opciones, dígitos o "
        "formas), el programa le avisa antes.", NOTA),
      p("2.5 Exámenes de varias hojas", H2),
      p("Si las preguntas no caben en una hoja, el programa las reparte <b>solo</b> en 2, 3 o 4 "
        "hojas (la vista previa muestra «Hoja 1 de 2» con flechas para pasar de una a otra). Cada hoja dice arriba «HOJA 1 DE 2» y "
        "trae marcado su número en la franja de abajo, así que al escanear el orden da igual: el "
        "programa reconoce qué hoja es y junta las hojas de cada estudiante por su documento."),
      lista(["Cada hoja lleva el documento del estudiante: con hojas con nombre ya viene marcado "
             "en todas.",
             "Si a un estudiante le falta una hoja, aparece en «Alertas» como «Falta una hoja».",
             "Siempre que se pueda, el programa evita partir una materia entre dos hojas."]),
      PageBreak()]

# --- 3. Día del examen y escaneo ---
h += [p("3. El día del examen", H1),
      lista(["Entregue a cada estudiante su hoja (y, si usa formas, el cuadernillo de la misma "
             "forma que dice su hoja).",
             "Pida <b>lápiz No. 2 o lapicero negro</b> y que <b>rellenen completamente</b> un solo "
             "círculo por pregunta. Una X o un chulo no se lee bien.",
             "Si se equivocan, que borren muy bien. Sin corrector.",
             "Que no doblen la hoja ni escriban sobre las marcas negras de las esquinas."]),
      p("3.1 Escanear o fotografiar", H2),
      tabla([["", "Escáner (recomendado)", "Foto de celular"],
             ["Cómo", "Todas las hojas en un solo PDF. Blanco y negro o escala de grises, "
                      "200 a 300 ppp.",
              "Desde arriba, con la hoja completa, plana y bien iluminada. Que se vean las "
              "cuatro marcas negras."],
             ["Orden", "Da igual: el programa identifica a cada estudiante por su documento.",
              "Da igual."]], [2.5, 7, 7]),
      Spacer(1, 0.6 * cm),

      p("4. Leer las hojas", H1),
      lista(["En la pestaña <b>«2. Leer hojas»</b> elija el examen arriba.",
             "Pulse <b>«Agregar PDF o fotos»</b> (o «Agregar carpeta») y elija los archivos. Puede "
             "mezclar PDF y fotos.",
             "Pulse <b>«Leer hojas»</b> y espere: la barra muestra el avance (unos segundos por hoja).",
             "Haga clic en una hoja de la lista para ver, a la derecha, lo que detectó el programa. "
             "Con la rueda del ratón se acerca."], numerada=True),
      captura("03_leer.png", pie="Pestaña «Leer hojas»: lista de hojas leídas e imagen con las "
                                 "marcas detectadas."),
      p("4.1 ¿Qué significan los colores?", H2),
      tabla([["Estado", "Qué hacer"],
             ["Lista", "Nada: se leyó bien."],
             ["Revisar (amarillo)", "Algo merece una mirada: doble marca, documento incompleto, "
                                    "no marcó la forma. Haga doble clic para revisarla."],
             ["No se leyó (rojo)", "No se encontraron las 4 marcas (foto cortada, torcida u oscura), "
                                   "o es una hoja de OTRO examen. Tome la foto de nuevo, léala en "
                                   "el examen correcto o corríjala a mano."]],
            [4, 12.5], {2: AMARILLO, 3: ROJO_CLARO}),
      p("4.2 Corregir una hoja a mano", H2),
      p("Doble clic sobre la hoja: a la izquierda verá la imagen y a la derecha el documento, la "
        "forma y cada respuesta. Las preguntas con doble marca salen en amarillo y las que están en "
        "blanco, en gris. Corrija y pulse <b>«Guardar corrección»</b>."),
      captura("04_corregir.png", 15, "Ventana de corrección."),
      p("4.3 Otros botones", H2),
      lista(["<b>Eliminar:</b> quita las hojas seleccionadas (con Ctrl o Shift se eligen varias).",
             "<b>Borrar todas:</b> empieza de cero en ese examen. Los PDF y fotos originales no se borran.",
             "Si vuelve a leer la hoja de un estudiante, la nueva <b>reemplaza</b> a la anterior: "
             "no se duplica.",
             "<b>Hojas de práctica:</b> crea hojas llenadas al azar para probar el programa sin imprimir. "
             "Ideal para aprender a usarlo o mostrárselo a otro docente."]),
      PageBreak()]

# --- 5. Resultados ---
h += [p("5. Ver los resultados", H1),
      lista(["<b>Clave de respuestas:</b> escriba una línea por materia con las respuestas correctas "
             "seguidas, por ejemplo <i>ABDCA BBCDA</i> (los espacios no importan). Al lado verá si "
             "está completa (25/25). Si el examen tiene formas, hay un bloque para cada forma.",
             "<b>Truco:</b> llene una hoja con las respuestas correctas, léala con las demás y use "
             "«Tomar la clave de una hoja leída».",
             "<b>Lista de estudiantes</b> (opcional si ya la cargó al crear la hoja): para ver los "
             "nombres y saber quién no entregó.",
             "<b>Escala de notas:</b> por defecto de 1,0 a 5,0 y aprueba con 3,0."], numerada=True),
      captura("05_resultados.png", pie="Pestaña «Resultados»: clave a la izquierda; tablero a la "
                                       "derecha. Todo se recalcula solo."),
      p("En el tablero verá cuatro cuadros (estudiantes, nota promedio, cuántos aprueban y la "
        "pregunta más difícil) y cuatro pestañas:"),
      tabla([["Pestaña", "Qué muestra"],
             ["Estudiantes", "Puesto, porcentaje por materia, nota y si aprueba. Clic en un "
                             "título para ordenar."],
             ["Materias", "Promedio de cada materia en un gráfico y en una tabla."],
             ["Preguntas", "Qué tanto acertó el curso en cada pregunta (verde fácil, amarillo "
                           "media, rojo difícil), la opción errada más elegida y si la pregunta "
                           "<b>discrimina</b>: «Buena» si la aciertan más los mejores estudiantes; "
                           "«Revisar» si puede estar mal redactada o ser ambigua."],
             ["Alertas", "Hojas sin leer, estudiantes sin hoja, documentos repetidos o que no "
                         "están en la lista, y posibles errores en la clave."]], [3.5, 13]),
      Spacer(1, 0.3 * cm),
      captura("07_preguntas.png", pie="Pestaña «Preguntas»: en amarillo, una pregunta con "
                                      "posible error en la clave."),
      recuadro("<b>Posible error en la clave.</b> Si casi nadie acertó una pregunta y la mayoría de "
               "los MEJORES estudiantes marcó la misma otra opción, lo más probable es que la clave "
               "esté mal. El programa lo avisa en rojo arriba y en «Alertas». Revise esa pregunta "
               "en su cuadernillo: si la clave estaba mal, corríjala y las notas se recalculan solas.",
               AMARILLO),
      Spacer(1, 0.3 * cm),
      p("5.1 Exportar a Excel", H2),
      p("El botón <b>«Exportar a Excel»</b> crea <b>resultados.xlsx</b> en la carpeta del examen, con "
        "las hojas Resumen (con gráfico), Estudiantes, Materias, Preguntas, Respuestas (verde bien, "
        "rojo mal) y Alertas. Si Excel muestra un error al exportar, cierre el archivo y vuelva a "
        "intentar."),
      p("5.2 Boletines para los estudiantes", H2),
      p("El botón <b>«Boletines (PDF)»</b> crea <b>boletines.pdf</b>: una página por estudiante "
        "con su nota, su porcentaje, su puesto, el resultado de cada materia comparado con el "
        "promedio del curso y las <b>preguntas para repasar</b> (lo que marcó y la respuesta "
        "correcta). Se puede imprimir y entregar, o enviar al acudiente."),
      PageBreak()]

# --- 6. Seguimiento ---
h += [p("6. Seguimiento entre exámenes", H1),
      p("En la pestaña <b>«4. Seguimiento»</b> elija el grado y marque los exámenes que quiere "
        "comparar (por ejemplo, los tres simulacros del año). Solo aparecen los que ya tienen hojas "
        "leídas y clave. Los estudiantes se reconocen por su documento."),
      captura("09_seguimiento.png", pie="Promedio del curso en cada examen: la línea negra es el "
                                        "promedio general; las de colores, cada materia."),
      captura("10_seguimiento_est.png", pie="Pestaña «Estudiantes»: porcentaje en cada examen y "
                                            "cambio. Verde: subió 5 puntos o más; rojo: bajó. Al "
                                            "elegir un estudiante se ve su evolución por materia."),
      p("El botón «Exportar a Excel» guarda el seguimiento en la carpeta «salidas»."),
      PageBreak()]

# --- 7. Compartir ---
h += [p("7. Compartir un examen con otro computador", H1),
      p("Con el menú <b>«Compartir examen»</b> (arriba a la derecha) un examen completo se "
        "guarda en un solo archivo <b>.zip</b>. Sirve para pasarlo a otro docente, llevarlo en una "
        "USB a la sala de sistemas o guardar una copia de seguridad."),
      lista(["<b>Exportar:</b> elija el examen y qué incluir: siempre va el diseño de la hoja; "
             "puede agregar la clave y la lista, y las hojas leídas con los resultados.",
             "<b>Importar:</b> elija el .zip. Si ese examen ya existe, el programa pregunta si lo "
             "reemplaza (el anterior se guarda en «salidas\\_respaldos») o si lo importa como copia.",
             "El examen importado conserva su código, así que las hojas ya impresas sirven en el "
             "otro computador."]),
      recuadro("Si el otro docente solo va a <b>calificar</b>, exporte con la clave y la lista. "
               "Si solo va a <b>imprimir</b>, basta con el diseño."),
      Spacer(1, 0.6 * cm)]

# --- 8. Preguntas frecuentes ---
h += [p("8. Problemas frecuentes", H1),
      tabla([["Problema", "Solución"],
             ["Una hoja sale «No se leyó».",
              "Revise que se vean las 4 marcas negras completas. En fotos: desde arriba, sin sombras "
              "fuertes y con la hoja plana. Si no se puede repetir, corríjala a mano con doble clic."],
             ["«Es una hoja de otro examen».",
              "Esa hoja se imprimió para otro examen (o con un diseño anterior). Léala en el examen "
              "que le corresponde."],
             ["Muchas hojas con «Documento incompleto».",
              "Los estudiantes no rellenaron bien el documento. Use hojas con nombre la próxima vez."],
             ["Doble marca en varias preguntas.",
              "El estudiante borró mal o marcó dos opciones. Revise la imagen y corrija a mano: "
              "deje vacía la pregunta si de verdad marcó dos."],
             ["Cambié el diseño después de imprimir.",
              "Las hojas viejas ya no sirven para el diseño nuevo. Lo leído antes queda guardado en "
              "una carpeta «anterior_...» dentro del examen."],
             ["No aparece el nombre de un estudiante.",
              "Su documento no está en la lista (o está escrito distinto). Revise la lista o corrija "
              "el documento de la hoja."],
             ["«Falta una hoja» (examen de varias hojas).",
              "No se escaneó una de las hojas de ese estudiante, o el documento de esa hoja quedó "
              "mal marcado. Búsquela en «Leer hojas» y corrija el documento."],
             ["Las notas parecen muy bajas en una pregunta.",
              "Mire la pestaña «Alertas»: puede ser un error en la clave."]], [5.5, 11]),
      Spacer(1, 0.6 * cm),
      p("¿Dónde quedan los archivos?", H2),
      p("Todo se guarda en la carpeta <b>salidas</b>, una carpeta por examen: la hoja en PDF, "
        "las hojas con nombre, las hojas leídas (carpeta «lecturas»), la clave, la lista y el Excel "
        "de resultados. Para hacer una copia de seguridad, copie la carpeta «salidas» o use "
        "«Compartir examen → Exportar»."),
      Spacer(1, 1 * cm),
      p("CalificaTAP es un proyecto de los estudiantes de la Media Técnica en Desarrollo de "
        "Software de la IESTAP. Funciona con OMRChecker (software libre).", PIE)]


def main() -> None:
    doc = SimpleDocTemplate(str(SALIDA), pagesize=letter, title="Manual CalificaTAP",
                            author="CalificaTAP", leftMargin=2.5 * cm, rightMargin=2.5 * cm,
                            topMargin=2 * cm, bottomMargin=2 * cm)
    doc.build(h, onLaterPages=numero_de_pagina)
    print(f"Manual creado: {SALIDA}")


if __name__ == "__main__":
    main()
