"""
diseno.py — Medidas y constantes de diseño de la hoja de respuestas.

Aquí están TODOS los "números mágicos" de la hoja en un solo lugar.
Si quieren burbujas más grandes, márgenes distintos o letra más pequeña,
este es el único archivo que deben tocar.

UNIDADES: todas las medidas están en PUNTOS tipográficos (pt).
    1 pt = 1/72 de pulgada ≈ 0,353 mm
    Una hoja carta mide 612 x 792 pt (8,5 x 11 pulgadas).

SISTEMA DE COORDENADAS DE LA MAQUETA:
    El origen (0, 0) está en la esquina SUPERIOR IZQUIERDA de la hoja.
    x crece hacia la derecha, y crece hacia ABAJO.
    (Es el mismo sentido que usan las imágenes y OpenCV. reportlab usa
    "y hacia arriba", pero esa conversión se hace en un solo lugar:
    dibujante_pdf.py.)
"""

# --- Página -------------------------------------------------------------
ANCHO_PAGINA = 612.0   # carta: 8,5 pulgadas * 72
ALTO_PAGINA = 792.0    # carta: 11 pulgadas * 72

# --- Marcas de alineación (las 4 esquinas) ------------------------------
# Cada marca es un cuadrado tipo "código QR": negro / blanco / negro.
LADO_MARCADOR = 22.0          # lado del cuadrado exterior (≈ 7,8 mm)
DISTANCIA_MARCADOR_BORDE = 20.0  # desde el borde de la hoja hasta la marca
# Proporciones de los 3 cuadrados concéntricos (como los códigos QR: 7-5-3).
# La usan el PDF y la imagen omr_marker.jpg, así ambos son idénticos.
PROPORCIONES_MARCADOR = (7, 5, 3)

# --- Zona de contenido --------------------------------------------------
# El contenido va dentro de este rectángulo, sin tocar las marcas.
MARGEN_IZQUIERDO = 50.0
MARGEN_DERECHO = 50.0
MARGEN_SUPERIOR = 46.0
LIMITE_INFERIOR = ALTO_PAGINA - 52.0  # nada de preguntas por debajo de esta y

# --- Burbujas -----------------------------------------------------------
DIAMETRO_BURBUJA = 11.0       # ≈ 3,9 mm, cómodo para rellenar con lápiz
GROSOR_BORDE_BURBUJA = 0.8
PASO_HORIZONTAL = 15.0        # distancia entre centros de burbujas vecinas (A→B)
PASO_VERTICAL = 14.5          # distancia entre centros de filas de preguntas

# --- Bloques de preguntas -----------------------------------------------
ANCHO_NUMERO_PREGUNTA = 22.0  # espacio a la izquierda para "12."
ESPACIO_DERECHO_COLUMNA = 5.0  # aire entre la última burbuja y el marco del bloque
ALTO_TITULO_MATERIA = 17.0    # franja gris con el nombre de la materia
SEPARACION_MIN_COLUMNAS = 12.0
MIN_PREGUNTAS_TRAS_TITULO = 3  # no dejar un título "huérfano" al final de columna

# --- Documento del estudiante -------------------------------------------
PASO_HORIZONTAL_DOC = 15.0
PASO_VERTICAL_DOC = 14.0
ALTO_CASILLA_DOC = 14.0       # casillas para escribir el número a mano

# --- Código del examen (franja inferior, preimpresa) ----------------------
# Cada examen recibe un número del 1 al 1022 que se imprime en binario:
# 10 parejas de burbujas (0 / 1) con una ya rellena. Así, al leer, el programa
# sabe a qué examen pertenece cada hoja. La franja está SIEMPRE en el mismo
# lugar, para poder leerla aunque la hoja sea de otro examen.
BITS_CODIGO = 10
Y_CODIGO = ALTO_PAGINA - 40.0      # centro de las burbujas del código
PASO_BIT_CODIGO = 27.0             # distancia entre una pareja y la siguiente
X_PRIMER_BIT = 178.0               # centro de la burbuja "0" del primer bit
# Después del código van 2 parejas más con el número de hoja (1 a 4), por si el
# examen no cabe en una sola hoja. También vienen rellenas de fábrica.
BITS_HOJA = 2
SEPARACION_HOJA = 10.0             # espacio extra entre el código y el número de hoja
MAX_HOJAS = 2 ** BITS_HOJA         # 4 hojas como máximo por estudiante

# --- Formas del examen (A, B, ...) ---------------------------------------
MAX_FORMAS = 4

# --- Letras ---------------------------------------------------------------
# Fuentes estándar de PDF: no necesitan instalarse (funciona sin internet)
# y sí aceptan tildes y eñes.
FUENTE = "Helvetica"
FUENTE_NEGRITA = "Helvetica-Bold"
TAMANO_LETRA_BURBUJA = 6.0
GRIS_LETRA_BURBUJA = 0.55     # 0 = negro, 1 = blanco. Gris claro para no confundir al lector
GRIS_FRANJA_TITULO = 0.88

# --- Conversión a píxeles para OMRChecker --------------------------------
# OMRChecker trabaja en píxeles. Usamos 2 px por cada punto (≈ 144 DPI).
# Con este valor una burbuja mide 22 px, suficiente para leerla bien.
PIXELES_POR_PUNTO = 2.0

# Letras de las opciones: A, B, C, ...
LETRAS_OPCIONES = "ABCDEFGH"
