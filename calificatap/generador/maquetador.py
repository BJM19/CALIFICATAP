"""
maquetador.py — Calcula DÓNDE va cada elemento de la hoja.

Recibe la configuración del examen y devuelve una Maqueta (ver maqueta.py).
Aquí no se dibuja nada: solo se hacen cuentas de posiciones.

Orden de trabajo (de arriba hacia abajo en la hoja):
    1. Marcas de alineación en las 4 esquinas.
    2. Encabezado del colegio y datos del examen.
    3. Datos del estudiante: nombre, instrucciones y cuadrícula del documento.
    4. Bloques de preguntas por materia, repartidos en columnas.
"""

from __future__ import annotations

import math

from reportlab.pdfbase.pdfmetrics import stringWidth

from . import diseno as d
from .configuracion import ConfiguracionExamen, Materia
from .maqueta import (BloqueCampos, EjemploRelleno, Imagen, Linea, Maqueta,
                      Marcador, Pagina, Rectangulo, Texto)


class ErrorDeMaquetacion(Exception):
    """Las preguntas no caben en una hoja carta."""


# ---------------------------------------------------------------------------
# Utilidad: achicar un texto hasta que quepa en un ancho
# ---------------------------------------------------------------------------

def _tamano_que_cabe(texto: str, ancho_max: float, tamano: float,
                     negrita: bool = True, minimo: float = 5.0) -> float:
    fuente = d.FUENTE_NEGRITA if negrita else d.FUENTE
    while tamano > minimo and stringWidth(texto, fuente, tamano) > ancho_max:
        tamano -= 0.25
    return tamano


# ---------------------------------------------------------------------------
# 1. Marcas de alineación
# ---------------------------------------------------------------------------

def _agregar_marcadores(m: Maqueta) -> None:
    # Centro de la marca = distancia al borde + medio lado
    desde_borde = d.DISTANCIA_MARCADOR_BORDE + d.LADO_MARCADOR / 2
    izquierda, derecha = desde_borde, m.ancho - desde_borde
    arriba, abajo = desde_borde, m.alto - desde_borde
    for cx, cy in [(izquierda, arriba), (derecha, arriba),
                   (izquierda, abajo), (derecha, abajo)]:
        m.marcadores.append(Marcador(cx, cy, d.LADO_MARCADOR))


# ---------------------------------------------------------------------------
# 2. Encabezado
# ---------------------------------------------------------------------------

def _agregar_encabezado_compacto(m: Maqueta, conf: ConfiguracionExamen) -> float:
    """
    Encabezado más bajito (versión con N.º de lista): colegio, examen y una
    sola línea de detalle con municipio, grado, fecha y preguntas.
    """
    y = d.MARGEN_SUPERIOR
    centro_x = m.ancho / 2
    if conf.ruta_logo:
        m.imagenes.append(Imagen(str(conf.ruta_logo), d.MARGEN_IZQUIERDO, y - 2, 40, 40))
    ancho_titulo = m.ancho - 2 * (d.MARGEN_IZQUIERDO + 48)
    tam = _tamano_que_cabe(conf.nombre_colegio.upper(), ancho_titulo, 12)
    m.textos.append(Texto(centro_x, y + 11, conf.nombre_colegio.upper(), tam,
                          negrita=True, alineacion="centro"))
    tam = _tamano_que_cabe(conf.nombre_examen, ancho_titulo, 10.5)
    m.textos.append(Texto(centro_x, y + 24, conf.nombre_examen, tam,
                          negrita=True, alineacion="centro"))
    partes = [conf.municipio] if conf.municipio else []
    partes.append(f"Grado: {conf.grado}")
    if conf.fecha:
        partes.append(f"Fecha: {conf.fecha}")
    partes.append(f"Preguntas: {conf.total_preguntas}")
    detalle = "     ·     ".join(partes)
    # Más angosto, para no chocar con el recuadro "HOJA 2 DE 3" de la derecha
    tam = _tamano_que_cabe(detalle, m.ancho - 2 * (d.MARGEN_IZQUIERDO + 78), 8.5, negrita=False)
    m.textos.append(Texto(centro_x, y + 35, detalle, tam, alineacion="centro"))
    y_fin = y + 41
    m.lineas.append(Linea(d.MARGEN_IZQUIERDO, y_fin, m.ancho - d.MARGEN_DERECHO, y_fin, 1.0))
    return y_fin + 7


def _agregar_encabezado(m: Maqueta, conf: ConfiguracionExamen) -> float:
    """Dibuja el encabezado y devuelve la 'y' donde termina."""
    if conf.por_lista:
        return _agregar_encabezado_compacto(m, conf)
    y = d.MARGEN_SUPERIOR
    centro_x = m.ancho / 2

    if conf.ruta_logo:
        m.imagenes.append(Imagen(str(conf.ruta_logo), d.MARGEN_IZQUIERDO, y, 52, 52))

    ancho_titulo = m.ancho - 2 * (d.MARGEN_IZQUIERDO + 60)
    tam = _tamano_que_cabe(conf.nombre_colegio.upper(), ancho_titulo, 13)
    m.textos.append(Texto(centro_x, y + 13, conf.nombre_colegio.upper(), tam,
                          negrita=True, alineacion="centro"))
    if conf.municipio:
        m.textos.append(Texto(centro_x, y + 25, conf.municipio, 9, alineacion="centro"))

    tam = _tamano_que_cabe(conf.nombre_examen, ancho_titulo, 11)
    m.textos.append(Texto(centro_x, y + 42, conf.nombre_examen, tam,
                          negrita=True, alineacion="centro"))

    detalle = f"Grado: {conf.grado}"
    if conf.fecha:
        detalle += f"        Fecha: {conf.fecha}"
    detalle += f"        Preguntas: {conf.total_preguntas}"
    m.textos.append(Texto(centro_x, y + 55, detalle, 9, alineacion="centro"))

    y_fin = y + 62
    m.lineas.append(Linea(d.MARGEN_IZQUIERDO, y_fin, m.ancho - d.MARGEN_DERECHO, y_fin, 1.0))
    return y_fin + 8


# ---------------------------------------------------------------------------
# 3. Datos del estudiante
# ---------------------------------------------------------------------------

def _agregar_documento(m: Maqueta, conf: ConfiguracionExamen, y: float) -> tuple[float, float]:
    """
    Cuadrícula del número de documento, alineada a la derecha.

        [1][0][2][3]...      ← casillas para escribir a mano
        (0)(0)(0)(0)
        (1)(1)(1)(1)         ← cada COLUMNA es un campo (doc01, doc02, ...)
        ...                    y sus valores van de 0 a 9 hacia ABAJO
        (9)(9)(9)(9)           (por eso la dirección es "vertical")

    Devuelve (x donde empieza el recuadro, y donde termina).
    """
    n = conf.digitos_documento
    relleno = 6.0
    ancho = n * d.PASO_HORIZONTAL_DOC + 2 * relleno
    x = m.ancho - d.MARGEN_DERECHO - ancho

    titulo_alto = 15.0
    y_casillas = y + titulo_alto
    y_primera_burbuja = y_casillas + d.ALTO_CASILLA_DOC + 4 + d.DIAMETRO_BURBUJA / 2
    y_fin = y_primera_burbuja + 9 * d.PASO_VERTICAL_DOC + d.DIAMETRO_BURBUJA / 2 + 5

    # Marco y título
    m.rectangulos.append(Rectangulo(x, y, ancho, y_fin - y))
    m.rectangulos.append(Rectangulo(x, y, ancho, titulo_alto - 2,
                                    relleno_gris=d.GRIS_FRANJA_TITULO))
    tam = _tamano_que_cabe("NÚMERO DE DOCUMENTO", ancho - 6, 8)
    m.textos.append(Texto(x + ancho / 2, y + 9.5, "NÚMERO DE DOCUMENTO", tam,
                          negrita=True, alineacion="centro"))

    # Casillas para escribir el número a mano
    x_primera = x + relleno + d.PASO_HORIZONTAL_DOC / 2
    for i in range(n):
        cx = x_primera + i * d.PASO_HORIZONTAL_DOC
        m.rectangulos.append(Rectangulo(cx - 6.5, y_casillas, 13, d.ALTO_CASILLA_DOC, grosor=0.5))
        m.pos_casillas_doc.append((cx, y_casillas + 10.5))   # para las hojas con nombre

    # El bloque de burbujas: esto SÍ lo lee OMRChecker
    etiquetas = [f"doc{i + 1:02d}" for i in range(n)]
    m.bloques.append(BloqueCampos(
        nombre="Documento",
        direccion="vertical",
        valores=[str(v) for v in range(10)],
        etiquetas=etiquetas,
        origen_cx=x_primera,
        origen_cy=y_primera_burbuja,
        paso_burbujas=d.PASO_VERTICAL_DOC,     # de 0 a 1 a 2... (hacia abajo)
        paso_campos=d.PASO_HORIZONTAL_DOC,     # de una columna a la siguiente
        diametro=d.DIAMETRO_BURBUJA,
    ))
    m.etiquetas_documento = etiquetas
    return x, y_fin


def _agregar_datos_e_instrucciones(m: Maqueta, conf: ConfiguracionExamen,
                                   x_derecha: float, y: float, y_fin: float) -> None:
    """Nombre, curso, firma, forma (si hay) e instrucciones (a la izquierda del documento)."""
    x = d.MARGEN_IZQUIERDO
    ancho = x_derecha - 12 - x

    # Campos para escribir
    m.textos.append(Texto(x, y + 9, "NOMBRE Y APELLIDOS:", 8, negrita=True))
    m.lineas.append(Linea(x, y + 30, x + ancho, y + 30, 0.6))
    m.pos_nombre = (x + 2, y + 26)
    m.textos.append(Texto(x, y + 44, "CURSO:", 8, negrita=True))
    m.lineas.append(Linea(x + 34, y + 46, x + 110, y + 46, 0.6))
    m.pos_curso = (x + 38, y + 43)

    # Si el examen tiene formas (A, B...), el estudiante marca la suya aquí
    fin_firma = x + ancho
    if conf.formas > 1:
        letras = list(d.LETRAS_OPCIONES[: conf.formas])
        x_primera = x + ancho - (len(letras) - 0.5) * d.PASO_HORIZONTAL
        m.textos.append(Texto(x_primera - 10, y + 44, "FORMA:", 8, negrita=True,
                              alineacion="derecha"))
        m.bloques.append(BloqueCampos(
            nombre="Forma", direccion="horizontal", valores=letras, etiquetas=["forma"],
            origen_cx=x_primera, origen_cy=y + 41, paso_burbujas=d.PASO_HORIZONTAL,
            paso_campos=d.PASO_VERTICAL, diametro=d.DIAMETRO_BURBUJA))
        m.etiqueta_forma = "forma"
        fin_firma = x_primera - 52
    m.textos.append(Texto(x + 122, y + 44, "FIRMA:", 8, negrita=True))
    m.lineas.append(Linea(x + 154, y + 46, fin_firma, y + 46, 0.6))

    # Recuadro de instrucciones
    y_ins = y + 56
    m.rectangulos.append(Rectangulo(x, y_ins, ancho, y_fin - y_ins))
    m.rectangulos.append(Rectangulo(x, y_ins, ancho, 13, relleno_gris=d.GRIS_FRANJA_TITULO))
    m.textos.append(Texto(x + ancho / 2, y_ins + 9.5, "INSTRUCCIONES", 8,
                          negrita=True, alineacion="centro"))
    instrucciones = [
        "• Use lápiz No. 2 o lapicero de tinta negra.",
        "• Rellene COMPLETAMENTE un solo círculo por pregunta.",
        "• Escriba su documento en las casillas y rellene el dígito",
        "   correspondiente en cada columna.",
        "• Si se equivoca, borre muy bien. No use corrector.",
        "• No doble ni arrugue la hoja y no escriba sobre las",
        "   marcas negras de las esquinas.",
    ]
    for i, linea in enumerate(instrucciones):
        m.textos.append(Texto(x + 6, y_ins + 25 + i * 10.5, linea, 7.5))

    # Ejemplos de cómo SÍ y cómo NO rellenar
    y_ej = y_fin - 11
    m.textos.append(Texto(x + 6, y_ej + 2.5, "Así SÍ:", 7.5, negrita=True))
    m.ejemplos.append(EjemploRelleno(x + 45, y_ej, "correcto"))
    m.textos.append(Texto(x + 70, y_ej + 2.5, "Así NO:", 7.5, negrita=True))
    for k, tipo in enumerate(["x", "chulo", "parcial"]):
        m.ejemplos.append(EjemploRelleno(x + 112 + k * 18, y_ej, tipo))


# ---------------------------------------------------------------------------
# 3b. Versión con N.º de lista (más preguntas por hoja)
# ---------------------------------------------------------------------------

ALTO_FRANJA_LISTA = 52.0


def _agregar_numero_lista(m: Maqueta, y: float) -> float:
    """
    Recuadro del N.º de lista, alineado a la derecha. Ocupa solo 2 filas:

        N.º DE LISTA
        [0]  (0)(1)(2)(3)(4)(5)(6)(7)(8)(9)     ← 1.ª cifra (campo lis01)
        [7]  (0)(1)(2)(3)(4)(5)(6)(7)(8)(9)     ← 2.ª cifra (campo lis02)

    Aquí cada FILA es un campo y sus valores van de 0 a 9 hacia la DERECHA
    (dirección "horizontal", igual que las preguntas). Por eso es tan bajito.
    Devuelve la x donde empieza el recuadro.
    """
    relleno = 6.0
    ancho_casilla = 14.0
    ancho = relleno + ancho_casilla + 8 + 10 * d.PASO_HORIZONTAL + relleno - 3
    x = m.ancho - d.MARGEN_DERECHO - ancho
    titulo_alto = 13.0

    m.rectangulos.append(Rectangulo(x, y, ancho, ALTO_FRANJA_LISTA))
    m.rectangulos.append(Rectangulo(x, y, ancho, titulo_alto, relleno_gris=d.GRIS_FRANJA_TITULO))
    m.textos.append(Texto(x + ancho / 2, y + 9.3, "N.º DE LISTA   (ejemplo: el 7 es 0 7)", 7.5,
                          negrita=True, alineacion="centro"))

    x_casilla = x + relleno
    x_primera = x_casilla + ancho_casilla + 8 + d.PASO_HORIZONTAL / 2 - 3
    cy_primera = y + titulo_alto + 3 + d.DIAMETRO_BURBUJA / 2 + 1.5
    etiquetas = ["lis01", "lis02"]
    for i in range(2):
        cy = cy_primera + i * d.PASO_VERTICAL
        m.rectangulos.append(Rectangulo(x_casilla, cy - 7, ancho_casilla, 14, grosor=0.5))
        m.pos_casillas_doc.append((x_casilla + ancho_casilla / 2, cy + 3.5))
    m.bloques.append(BloqueCampos(
        nombre="Lista",
        direccion="horizontal",
        valores=[str(v) for v in range(10)],
        etiquetas=etiquetas,
        origen_cx=x_primera,
        origen_cy=cy_primera,
        paso_burbujas=d.PASO_HORIZONTAL,       # de 0 a 1 a 2... (hacia la derecha)
        paso_campos=d.PASO_VERTICAL,           # de la 1.ª cifra a la 2.ª (hacia abajo)
        diametro=d.DIAMETRO_BURBUJA,
    ))
    # Se guardan como "etiquetas del documento": así la lectura, la plantilla
    # de OMRChecker y las hojas con nombre funcionan igual en las dos versiones.
    m.etiquetas_documento = etiquetas
    return x


def _agregar_datos_compactos(m: Maqueta, conf: ConfiguracionExamen,
                             x_derecha: float, y: float) -> None:
    """Nombre, curso, firma, forma e instrucciones resumidas en 3 renglones."""
    x = d.MARGEN_IZQUIERDO
    ancho = x_derecha - 12 - x
    fin = x + ancho

    # Renglón 1: nombre
    m.textos.append(Texto(x, y + 12, "NOMBRE Y APELLIDOS:", 8, negrita=True))
    m.lineas.append(Linea(x + 96, y + 14, fin, y + 14, 0.6))
    m.pos_nombre = (x + 99, y + 11.5)

    # Renglón 2: curso, firma y forma
    m.textos.append(Texto(x, y + 31, "CURSO:", 8, negrita=True))
    m.lineas.append(Linea(x + 34, y + 33, x + 92, y + 33, 0.6))
    m.pos_curso = (x + 38, y + 30)
    fin_firma = fin
    if conf.formas > 1:
        letras = list(d.LETRAS_OPCIONES[: conf.formas])
        x_primera = fin - (len(letras) - 0.5) * d.PASO_HORIZONTAL
        m.textos.append(Texto(x_primera - 10, y + 31, "FORMA:", 8, negrita=True,
                              alineacion="derecha"))
        m.bloques.append(BloqueCampos(
            nombre="Forma", direccion="horizontal", valores=letras, etiquetas=["forma"],
            origen_cx=x_primera, origen_cy=y + 28, paso_burbujas=d.PASO_HORIZONTAL,
            paso_campos=d.PASO_VERTICAL, diametro=d.DIAMETRO_BURBUJA))
        m.etiqueta_forma = "forma"
        fin_firma = x_primera - 52
    m.textos.append(Texto(x + 100, y + 31, "FIRMA:", 8, negrita=True))
    m.lineas.append(Linea(x + 132, y + 33, fin_firma, y + 33, 0.6))

    # Renglón 3: instrucciones resumidas, con los ejemplos de relleno
    y_ins = y + 39
    m.rectangulos.append(Rectangulo(x, y_ins, ancho, ALTO_FRANJA_LISTA - 39,
                                    relleno_gris=0.94, grosor=0.5))
    texto = "Lápiz No. 2. Un solo círculo por pregunta. No use corrector."
    x_ej = fin - 150
    tam = _tamano_que_cabe(texto, x_ej - x - 10, 7, negrita=False, minimo=5.5)
    m.textos.append(Texto(x + 4, y_ins + 9, texto, tam))
    cy = y_ins + 6.5
    m.textos.append(Texto(x_ej, y_ins + 9, "Así SÍ:", 7, negrita=True))
    m.ejemplos.append(EjemploRelleno(x_ej + 33, cy, "correcto"))
    m.textos.append(Texto(x_ej + 48, y_ins + 9, "Así NO:", 7, negrita=True))
    for k, tipo in enumerate(["x", "chulo", "parcial"]):
        m.ejemplos.append(EjemploRelleno(x_ej + 90 + k * 16, cy, tipo))


# ---------------------------------------------------------------------------
# 4. Bloques de preguntas
# ---------------------------------------------------------------------------

def _repartir_en_columnas(conf: ConfiguracionExamen, y_inicio: float, y_limite: float,
                          n_columnas: int, evitar_partir: bool) -> list[tuple] | None:
    """
    Planea en qué hoja y en qué columna va cada grupo de preguntas, SIN dibujar nada.
    Las preguntas se acomodan de arriba hacia abajo y de izquierda a derecha
    (como se lee un periódico). Si una materia no cabe completa en la columna,
    continúa en la siguiente con el título "(cont.)". Cuando se acaban las
    columnas de una hoja, se sigue en la hoja siguiente (máximo MAX_HOJAS).

    Con evitar_partir=True, una materia que no cabe en el espacio restante
    se pasa completa a una columna nueva (se ve más ordenado, pero gasta
    más espacio).

    Devuelve una lista de tuplas (hoja, columna, y, materia, numeros, es_continuacion),
    o None si ni con MAX_HOJAS alcanza.
    """
    plan = []
    hoja, columna, y = 1, 0, y_inicio
    for materia in conf.materias:
        pendientes = list(range(1, materia.preguntas + 1))
        es_continuacion = False
        while pendientes:
            # ¿Cuántas filas de preguntas caben en lo que queda de la columna?
            espacio = y_limite - y - d.ALTO_TITULO_MATERIA
            caben = max(0, math.floor(espacio / d.PASO_VERTICAL))
            minimo = min(d.MIN_PREGUNTAS_TRAS_TITULO, len(pendientes))

            # Si la materia no cabe completa aquí pero SÍ cabría completa en una
            # columna nueva (y quedan columnas en esta hoja), mejor empezarla allá.
            filas_columna_nueva = math.floor(
                (y_limite - y_inicio - d.ALTO_TITULO_MATERIA) / d.PASO_VERTICAL)
            if (evitar_partir and not es_continuacion and y > y_inicio and caben < len(pendientes)
                    and len(pendientes) <= filas_columna_nueva
                    and columna + 1 < n_columnas):
                caben = 0

            # Evitar que la continuación quede con 1 o 2 preguntas sueltas
            sobran = len(pendientes) - caben
            if 0 < sobran < d.MIN_PREGUNTAS_TRAS_TITULO:
                caben -= d.MIN_PREGUNTAS_TRAS_TITULO - sobran

            if caben < minimo:
                # No cabe: pasamos a la siguiente columna (o a la hoja siguiente)
                columna, y = columna + 1, y_inicio
                if columna >= n_columnas:
                    hoja, columna = hoja + 1, 0
                    if hoja > d.MAX_HOJAS:
                        return None
                continue

            numeros, pendientes = pendientes[:caben], pendientes[caben:]
            plan.append((hoja, columna, y, materia, numeros, es_continuacion))
            y += d.ALTO_TITULO_MATERIA + len(numeros) * d.PASO_VERTICAL + 7
            es_continuacion = True
    return plan


def _geometria_columnas(conf: ConfiguracionExamen) -> tuple[list[float], float]:
    """¿Cuántas columnas caben y dónde empieza cada una? (x de cada columna, ancho)"""
    max_opciones = max(mat.opciones_max for mat in conf.materias)
    ancho_columna = (d.ANCHO_NUMERO_PREGUNTA + max_opciones * d.PASO_HORIZONTAL
                     + d.ESPACIO_DERECHO_COLUMNA)
    ancho_util = d.ANCHO_PAGINA - d.MARGEN_IZQUIERDO - d.MARGEN_DERECHO
    n_columnas = int((ancho_util + d.SEPARACION_MIN_COLUMNAS)
                     // (ancho_columna + d.SEPARACION_MIN_COLUMNAS))
    # Repartimos el espacio sobrante entre las columnas
    separacion = (ancho_util - n_columnas * ancho_columna) / max(n_columnas - 1, 1)
    xs = [d.MARGEN_IZQUIERDO + i * (ancho_columna + separacion) for i in range(n_columnas)]
    return xs, ancho_columna


def _ancho_para(opciones: int) -> float:
    return d.ANCHO_NUMERO_PREGUNTA + opciones * d.PASO_HORIZONTAL + d.ESPACIO_DERECHO_COLUMNA


def _geometria_mixta(opciones_por_columna: list[int]) -> tuple[list[float], list[float]] | None:
    """Columnas de distinto ancho (ej. 3 angostas de A-D y 1 ancha de A-H). None si no caben."""
    anchos = [_ancho_para(o) for o in opciones_por_columna]
    ancho_util = d.ANCHO_PAGINA - d.MARGEN_IZQUIERDO - d.MARGEN_DERECHO
    sobra = ancho_util - sum(anchos)
    if sobra < d.SEPARACION_MIN_COLUMNAS * (len(anchos) - 1):
        return None
    separacion = sobra / max(len(anchos) - 1, 1)
    xs, x = [], d.MARGEN_IZQUIERDO
    for a in anchos:
        xs.append(x)
        x += a + separacion
    return xs, anchos


def _elegir_columnas(conf: ConfiguracionExamen, y_inicio: float):
    """
    Decide cuántas columnas, de qué ancho y qué va en cada una.
    Lo normal: todas iguales (tan anchas como la pregunta con más opciones).
    Pero si UNA materia tiene muchas más opciones (Inglés con A-H), hacer todas las
    columnas así de anchas cambia todas las materias y gasta espacio; entonces se dejan
    anchas solo las ÚLTIMAS columnas de cada hoja, siempre que no gaste más hojas.
    Devuelve (xs, anchos, plan).
    """
    xs, ancho = _geometria_columnas(conf)
    plan = _planear_preguntas(conf, y_inicio, len(xs))
    mejor = (plan[-1][0], xs, [ancho] * len(xs), plan)

    maximo = max(m.opciones_max for m in conf.materias)
    menores = [o for m in conf.materias for o in
               [m.opciones] + [p[2] for p in m.partes] if o < maximo]
    if not menores:
        return mejor[1:]
    mixta = False
    angosta = max(menores)
    for anchas in range(1, 3):
        for n in range(8, anchas, -1):
            geometria = _geometria_mixta([angosta] * (n - anchas) + [maximo] * anchas)
            if geometria is None:
                continue
            try:
                otro = _planear_preguntas(conf, y_inicio, n)
            except ErrorDeMaquetacion:
                break
            # ¿Cada bloque quedó en una columna con espacio para sus opciones?
            valido = all(max(materia.opciones_de(k) for k in numeros)
                         <= (maximo if columna >= n - anchas else angosta)
                         for _, columna, _, materia, numeros, _ in otro)
            # Columnas mixtas siempre que NO gasten más hojas: así solo la materia
            # con más opciones queda en columna ancha y las demás no cambian
            if valido and (otro[-1][0] < mejor[0] or (not mixta and otro[-1][0] == mejor[0])):
                mejor = (otro[-1][0], geometria[0], geometria[1], otro)
                mixta = True
            break                       # con este número de anchas, ya se probó el máximo n
    return mejor[1:]


def _planear_preguntas(conf: ConfiguracionExamen, y_inicio: float, n_columnas: int) -> list[tuple]:
    """
    Elige el mejor reparto: el que use MENOS hojas; entre dos con las mismas hojas,
    el que no parte las materias.
    """
    partiendo = _repartir_en_columnas(conf, y_inicio, d.LIMITE_INFERIOR, n_columnas, False)
    if partiendo is None:
        raise ErrorDeMaquetacion(
            f"Las {conf.total_preguntas} preguntas no caben ni en {d.MAX_HOJAS} hojas por "
            f"estudiante. Quite preguntas o use menos opciones por pregunta.")
    sin_partir = _repartir_en_columnas(conf, y_inicio, d.LIMITE_INFERIOR, n_columnas, True)
    if sin_partir and sin_partir[-1][0] <= partiendo[-1][0]:
        return sin_partir
    return partiendo


def _agregar_bloque_materia(m: Maqueta, conf: ConfiguracionExamen, materia: Materia,
                            numeros: list[int], primer_numero_global: int,
                            x: float, ancho: float, y: float,
                            es_continuacion: bool) -> float:
    """Agrega un bloque (título + filas de preguntas). Devuelve la y final."""
    # Franja del título
    titulo = materia.nombre.upper() + (" (cont.)" if es_continuacion else "")
    alto_franja = d.ALTO_TITULO_MATERIA - 4
    m.rectangulos.append(Rectangulo(x, y, ancho, alto_franja, relleno_gris=d.GRIS_FRANJA_TITULO))
    tam = _tamano_que_cabe(titulo, ancho - 6, 7.5)
    m.textos.append(Texto(x + ancho / 2, y + 9, titulo, tam, negrita=True, alineacion="centro"))

    # Centro de la primera burbuja (pregunta numeros[0], opción A)
    origen_cx = x + d.ANCHO_NUMERO_PREGUNTA + d.PASO_HORIZONTAL / 2
    origen_cy = y + d.ALTO_TITULO_MATERIA + d.PASO_VERTICAL / 2

    # Números impresos a la izquierda de cada fila
    for fila, numero in enumerate(numeros):
        if conf.numeracion == "continua":
            impreso = primer_numero_global + fila
        else:
            impreso = numero
        cy = origen_cy + fila * d.PASO_VERTICAL
        m.textos.append(Texto(x + d.ANCHO_NUMERO_PREGUNTA - 3, cy + 2.6,
                              f"{impreso}.", 7.5, negrita=True, alineacion="derecha"))

    # Los bloques que leerá OMRChecker. Normalmente es UNO; si la materia tiene
    # partes con distinto número de opciones (ej. Inglés: A-H y luego A-C), se hace
    # un bloque por cada tramo seguido de preguntas con las mismas opciones.
    inicio = 0
    while inicio < len(numeros):
        letras = materia.letras_de(numeros[inicio])
        fin = inicio
        while fin + 1 < len(numeros) and materia.letras_de(numeros[fin + 1]) == letras:
            fin += 1
        tramo = numeros[inicio:fin + 1]
        etiquetas = [materia.etiqueta(n) for n in tramo]
        m.bloques.append(BloqueCampos(
            nombre=f"{materia.codigo}_{tramo[0]:02d}_a_{tramo[-1]:02d}",
            direccion="horizontal",
            valores=letras,
            etiquetas=etiquetas,
            origen_cx=origen_cx,
            origen_cy=origen_cy + inicio * d.PASO_VERTICAL,
            paso_burbujas=d.PASO_HORIZONTAL,
            paso_campos=d.PASO_VERTICAL,
            diametro=d.DIAMETRO_BURBUJA,
        ))
        m.etiquetas_preguntas.extend(etiquetas)
        inicio = fin + 1

    # Marco alrededor del bloque
    y_fin = y + d.ALTO_TITULO_MATERIA + len(numeros) * d.PASO_VERTICAL
    m.rectangulos.append(Rectangulo(x, y, ancho, y_fin - y + 1, grosor=0.5))
    return y_fin


# ---------------------------------------------------------------------------
# Función principal
# ---------------------------------------------------------------------------

def _agregar_codigo_examen(m: Maqueta, conf: ConfiguracionExamen) -> None:
    """
    Franja inferior con el código del examen y el número de hoja, en binario.

    Ejemplo: código 5, hoja 2 (código en 10 cifras: 0000000101; hoja-1 en 2 cifras: 01):
        código: 1    2    3   ...   8    9   10      hoja:  1    2
               ●○   ●○   ●○  ...   ●○   ○●   ●○           ●○   ○●     (● = rellena de fábrica)
               0 1  0 1  0 1       0 1  0 1  0 1          0 1  0 1

    Cada pareja es un campo de OMRChecker con valores "0" y "1".
    Al leer, los valores se unen ("0000000101") y se convierten a número.
    La franja está SIEMPRE en el mismo lugar, en todas las hojas de todos los
    exámenes: por eso se puede leer aunque no se sepa todavía qué hoja es.
    """
    m.textos.append(Texto(d.X_PRIMER_BIT - 14, d.Y_CODIGO + 2.6,
                          "Código del examen (no marcar):", 6.5, alineacion="derecha",
                          gris=0.35))
    for i in range(d.BITS_CODIGO + d.BITS_HOJA):
        es_hoja = i >= d.BITS_CODIGO
        etiqueta = f"hoj{i - d.BITS_CODIGO + 1:02d}" if es_hoja else f"cod{i + 1:02d}"
        x = d.X_PRIMER_BIT + i * d.PASO_BIT_CODIGO + (d.SEPARACION_HOJA if es_hoja else 0)
        m.bloques.append(BloqueCampos(
            nombre=f"Hoja_{etiqueta[3:]}" if es_hoja else f"Codigo_{etiqueta[3:]}",
            direccion="horizontal", valores=["0", "1"], etiquetas=[etiqueta],
            origen_cx=x, origen_cy=d.Y_CODIGO, paso_burbujas=d.PASO_HORIZONTAL - 2,
            paso_campos=d.PASO_VERTICAL, diametro=d.DIAMETRO_BURBUJA))
        (m.etiquetas_hoja if es_hoja else m.etiquetas_codigo).append(etiqueta)

    x_texto = (d.X_PRIMER_BIT + (d.BITS_CODIGO + d.BITS_HOJA) * d.PASO_BIT_CODIGO
               + d.SEPARACION_HOJA - 7)
    bits_hoja = format(m.hoja - 1, f"0{d.BITS_HOJA}b")
    m.marcas_fijas.update(dict(zip(m.etiquetas_hoja, bits_hoja)))
    if conf.codigo_examen is not None:
        bits = format(conf.codigo_examen, f"0{d.BITS_CODIGO}b")
        m.marcas_fijas.update(dict(zip(m.etiquetas_codigo, bits)))
        texto = f"N.º {conf.codigo_examen} · hoja {m.hoja}"
    else:
        texto = "(se asigna al generar)"     # en la vista previa todavía no hay código
    m.textos.append(Texto(x_texto, d.Y_CODIGO + 2.6, texto, 6.5, gris=0.35))


def pagina_personalizada(m: Maqueta, documento: str, nombre: str, curso: str = "",
                         forma: str = "") -> Pagina:
    """
    Datos de UN estudiante para imprimir su hoja ya llena: nombre y curso
    escritos, documento escrito en las casillas y con sus burbujas rellenas,
    y la forma (si hay) también rellena.
    """
    digitos = len(m.etiquetas_documento)
    documento = documento.zfill(digitos)        # 8 cifras en 10 casillas → "00" delante
    pagina = Pagina()
    pagina.textos.append(Texto(*m.pos_nombre, nombre, 10, negrita=True))
    if curso:
        pagina.textos.append(Texto(*m.pos_curso, curso, 9))
    for (cx, cy), digito, etiqueta in zip(m.pos_casillas_doc, documento, m.etiquetas_documento):
        pagina.textos.append(Texto(cx, cy, digito, 9, negrita=True, alineacion="centro"))
        pagina.marcas[etiqueta] = digito
    if forma and m.etiqueta_forma:
        pagina.marcas[m.etiqueta_forma] = forma
    return pagina


def _hoja_base(conf: ConfiguracionExamen, hoja: int, total: int) -> tuple[Maqueta, float]:
    """Lo que se repite en todas las hojas: marcas, encabezado, documento, datos, código."""
    m = Maqueta(ancho=d.ANCHO_PAGINA, alto=d.ALTO_PAGINA, hoja=hoja, total_hojas=total)
    _agregar_marcadores(m)
    y = _agregar_encabezado(m, conf)
    if total > 1:
        # "HOJA 2 DE 3" bien visible, para no confundir las hojas
        # (a la derecha, justo encima de la línea del encabezado)
        m.rectangulos.append(Rectangulo(m.ancho - d.MARGEN_DERECHO - 72, y - 26, 72, 15,
                                        relleno_gris=0.15))
        m.textos.append(Texto(m.ancho - d.MARGEN_DERECHO - 36, y - 15.5,
                              f"HOJA {hoja} DE {total}", 8.5, negrita=True,
                              alineacion="centro", gris=1.0))
    if conf.por_lista:
        # Versión con N.º de lista: todo en una franja bajita → caben más preguntas
        x_lista = _agregar_numero_lista(m, y)
        _agregar_datos_compactos(m, conf, x_lista, y)
        y_fin_datos = y + ALTO_FRANJA_LISTA
    else:
        x_doc, y_fin_datos = _agregar_documento(m, conf, y)
        _agregar_datos_e_instrucciones(m, conf, x_doc, y, y_fin_datos)
    _agregar_codigo_examen(m, conf)
    # Pie de página (debajo de las marcas inferiores)
    pie = "Hoja de respuestas generada con CalificaTAP"
    if total > 1:
        pie = f"Hoja {hoja} de {total}  ·  " + pie
    m.textos.append(Texto(m.ancho / 2, m.alto - 20, pie, 6.5, alineacion="centro", gris=0.45))
    return m, y_fin_datos + 12


def maquetar_examen(conf: ConfiguracionExamen) -> list[Maqueta]:
    """
    Construye TODAS las hojas del examen (casi siempre es una sola).
    Cada hoja trae el encabezado, el documento y la forma, para que se pueda
    saber de quién es aunque se separe de las demás.
    """
    primera, y_inicio = _hoja_base(conf, 1, 1)
    xs_columnas, anchos_columnas, plan = _elegir_columnas(conf, y_inicio)
    total = plan[-1][0]

    hojas = [primera] if total == 1 else [_hoja_base(conf, k, total)[0]
                                          for k in range(1, total + 1)]
    numero_global = 1  # para la numeración "continua"
    for hoja, columna, y, materia, numeros, es_continuacion in plan:
        _agregar_bloque_materia(hojas[hoja - 1], conf, materia, numeros, numero_global,
                                xs_columnas[columna], anchos_columnas[columna], y,
                                es_continuacion)
        numero_global += len(numeros)
    return hojas


def maquetar(conf: ConfiguracionExamen) -> Maqueta:
    """La primera hoja del examen (atajo para exámenes de una sola hoja)."""
    return maquetar_examen(conf)[0]
