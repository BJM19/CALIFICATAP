"""
maqueta.py — El "plano" de la hoja de respuestas.

IDEA CLAVE DEL MÓDULO:
    La maqueta es la ÚNICA FUENTE DE VERDAD sobre dónde va cada cosa.
    - dibujante_pdf.py  LEE la maqueta y dibuja el PDF.
    - plantilla_omr.py  LEE la maqueta y escribe template.json.
    Ninguno de los dos calcula posiciones por su cuenta. Por eso el PDF y
    la plantilla no pueden quedar desalineados: salen del mismo plano.

Es como el plano de una casa: el albañil (PDF) y el electricista (OMRChecker)
trabajan con la misma hoja de planos, no cada uno con sus propias medidas.

Coordenadas: puntos, origen arriba a la izquierda, y hacia abajo (ver diseno.py).
"""

from __future__ import annotations

from dataclasses import dataclass, field


# ---------------------------------------------------------------------------
# Elementos que OMRChecker necesita conocer
# ---------------------------------------------------------------------------

@dataclass
class Marcador:
    """Marca de alineación cuadrada. (cx, cy) es su CENTRO."""
    cx: float
    cy: float
    lado: float


@dataclass
class Burbuja:
    """Un círculo para rellenar. (cx, cy) es su CENTRO."""
    cx: float
    cy: float
    diametro: float
    etiqueta: str   # a qué campo pertenece, ej. "MAT_03" o "doc05"
    valor: str      # qué significa si se rellena, ej. "B" o "7"


@dataclass
class BloqueCampos:
    """
    Un grupo rectangular de burbujas con el mismo patrón.
    Corresponde EXACTAMENTE a un "fieldBlock" de OMRChecker.

    Ejemplo: preguntas 1 a 8 de Matemáticas con opciones A-D:

        1. (A) (B) (C) (D)      ← un "campo" (etiqueta MAT_01)
        2. (A) (B) (C) (D)      ← otro campo (MAT_02)
        ...
           ↑    ↑
           |    paso_burbujas: distancia entre A y B (dentro del campo)
           origen: centro de la primera burbuja (1-A)
        paso_campos: distancia entre la fila 1 y la fila 2

    direccion:
        "horizontal" → las opciones de un campo van de izquierda a derecha
                       (preguntas), y los campos se apilan hacia abajo.
        "vertical"   → las opciones van de arriba a abajo (dígitos del
                       documento: 0..9) y los campos se ponen uno al lado del otro.
    """
    nombre: str
    direccion: str
    valores: list[str]
    etiquetas: list[str]
    origen_cx: float
    origen_cy: float
    paso_burbujas: float
    paso_campos: float
    diametro: float

    def burbujas(self) -> list[Burbuja]:
        """
        Genera todas las burbujas del bloque.

        ¡OJO! Este cálculo replica paso a paso el que hace OMRChecker
        (función generate_bubble_grid de su archivo template.py):
        se parte del origen, se avanza 'paso_burbujas' por cada opción
        y 'paso_campos' por cada campo. El PDF se dibuja con ESTAS burbujas,
        así que dibujamos exactamente donde OMRChecker va a buscar.
        """
        resultado = []
        for i, etiqueta in enumerate(self.etiquetas):
            for j, valor in enumerate(self.valores):
                if self.direccion == "horizontal":
                    cx = self.origen_cx + j * self.paso_burbujas
                    cy = self.origen_cy + i * self.paso_campos
                else:  # vertical
                    cx = self.origen_cx + i * self.paso_campos
                    cy = self.origen_cy + j * self.paso_burbujas
                resultado.append(Burbuja(cx, cy, self.diametro, etiqueta, valor))
        return resultado


# ---------------------------------------------------------------------------
# Elementos decorativos (solo el PDF los usa; OMRChecker no los necesita)
# ---------------------------------------------------------------------------

@dataclass
class Texto:
    x: float
    y: float               # línea base del texto
    texto: str
    tamano: float = 9.0
    negrita: bool = False
    alineacion: str = "izquierda"   # "izquierda", "centro" o "derecha"
    gris: float = 0.0               # 0 = negro


@dataclass
class Linea:
    x1: float
    y1: float
    x2: float
    y2: float
    grosor: float = 0.6


@dataclass
class Rectangulo:
    x: float               # esquina superior izquierda
    y: float
    ancho: float
    alto: float
    relleno_gris: float | None = None   # None = sin relleno
    grosor: float = 0.6
    con_borde: bool = True


@dataclass
class Imagen:
    ruta: str
    x: float
    y: float
    ancho: float
    alto: float


@dataclass
class EjemploRelleno:
    """Burbujas de ejemplo en las instrucciones (correcta / incorrectas)."""
    cx: float
    cy: float
    tipo: str   # "correcto", "x", "chulo" o "parcial"


@dataclass
class Pagina:
    """
    Lo que cambia de una hoja impresa a otra (hojas personalizadas):
    burbujas que se imprimen ya rellenas y textos extra (nombre, curso...).
    Una hoja en blanco es una Pagina vacía.
    """
    marcas: dict[str, str] = field(default_factory=dict)   # {"doc01": "1", "forma": "B"}
    textos: list[Texto] = field(default_factory=list)


# ---------------------------------------------------------------------------
# La maqueta completa
# ---------------------------------------------------------------------------

@dataclass
class Maqueta:
    ancho: float
    alto: float
    marcadores: list[Marcador] = field(default_factory=list)
    bloques: list[BloqueCampos] = field(default_factory=list)
    # Decoración
    textos: list[Texto] = field(default_factory=list)
    lineas: list[Linea] = field(default_factory=list)
    rectangulos: list[Rectangulo] = field(default_factory=list)
    imagenes: list[Imagen] = field(default_factory=list)
    ejemplos: list[EjemploRelleno] = field(default_factory=list)
    # Información útil para los módulos 2 y 3
    etiquetas_documento: list[str] = field(default_factory=list)
    etiquetas_preguntas: list[str] = field(default_factory=list)
    etiquetas_codigo: list[str] = field(default_factory=list)   # cod01..cod10
    etiquetas_hoja: list[str] = field(default_factory=list)     # hoj01..hoj02 (número de hoja)
    hoja: int = 1                       # qué hoja es (si el examen tiene varias)
    total_hojas: int = 1
    etiqueta_forma: str | None = None                           # "forma" si hay formas
    # Burbujas que van rellenas en TODAS las hojas (el código del examen)
    marcas_fijas: dict[str, str] = field(default_factory=dict)
    # Dónde escribir los datos de cada estudiante en las hojas personalizadas
    pos_nombre: tuple[float, float] = (0.0, 0.0)
    pos_curso: tuple[float, float] = (0.0, 0.0)
    pos_casillas_doc: list[tuple[float, float]] = field(default_factory=list)

    def todas_las_burbujas(self) -> list[Burbuja]:
        return [b for bloque in self.bloques for b in bloque.burbujas()]

    def marcador_superior_izquierdo(self) -> Marcador:
        """El marcador más arriba y más a la izquierda: origen de la plantilla OMR."""
        return min(self.marcadores, key=lambda m: m.cx + m.cy)
