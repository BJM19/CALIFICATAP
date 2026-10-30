"""
configuracion.py — Lee y valida el archivo JSON de configuración del examen.

¿Por qué validar? Porque un error en el JSON (por ejemplo "preguntas": "veinte")
debe detectarse ANTES de imprimir 300 hojas, con un mensaje claro en español.

El resultado es un objeto ConfiguracionExamen con datos ya revisados,
así el resto del programa puede confiar en ellos.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from . import diseno


class ErrorDeConfiguracion(Exception):
    """Error en el archivo JSON. El mensaje explica qué corregir."""


@dataclass
class Materia:
    codigo: str        # código corto, ej. "MAT". Se usa en las etiquetas: MAT_01, MAT_02...
    nombre: str        # nombre que se imprime, ej. "Matemáticas"
    preguntas: int     # cuántas preguntas tiene
    opciones: int      # cuántas opciones por pregunta (A, B, C, D...)
    # Opcional: partes con OTRO número de opciones, como en Inglés del ICFES
    # (preguntas 1-5 con A-H, 6-10 con A-C...). Lista de (desde, hasta, opciones),
    # contando desde 1 dentro de la materia.
    partes: list[tuple[int, int, int]] = field(default_factory=list)

    def opciones_de(self, numero: int) -> int:
        """Cuántas opciones tiene la pregunta 'numero' (1, 2... dentro de la materia)."""
        for desde, hasta, opciones in self.partes:
            if desde <= numero <= hasta:
                return opciones
        return self.opciones

    def letras_de(self, numero: int) -> list[str]:
        """Opciones de una pregunta, ej. ['A', 'B', 'C'] si tiene 3."""
        return list(diseno.LETRAS_OPCIONES[: self.opciones_de(numero)])

    @property
    def letras(self) -> list[str]:
        """Lista de opciones, ej. ['A', 'B', 'C', 'D'] si opciones = 4."""
        return list(diseno.LETRAS_OPCIONES[: self.opciones])

    @property
    def opciones_max(self) -> int:
        """La pregunta con más opciones (define el ancho de la columna)."""
        return max([self.opciones] + [o for _, _, o in self.partes])

    def etiqueta(self, numero: int) -> str:
        """Nombre único de una pregunta: etiqueta(3) → 'MAT_03'.
        Ese nombre es la columna que aparecerá en los resultados de OMRChecker."""
        return f"{self.codigo}_{numero:02d}"


@dataclass
class ConfiguracionExamen:
    nombre_colegio: str
    municipio: str
    ruta_logo: Path | None
    nombre_examen: str
    grado: str
    fecha: str
    digitos_documento: int
    numeracion: str                  # "continua" (1..N en toda la hoja) o "por_materia"
    formas: int = 1                  # 1 = sin formas; 2 = A y B; 3 = A, B y C...
    codigo_examen: int | None = None # número que identifica el examen (lo asigna generar.py)
    materias: list[Materia] = field(default_factory=list)
    # Cómo se identifica al estudiante en la hoja:
    #   "documento" → cuadrícula con el número de documento (4 a 12 cifras)
    #   "lista"     → solo su N.º en la lista del curso (2 cifras): la parte de
    #                 arriba de la hoja se achica y caben MÁS preguntas
    identificacion: str = "documento"

    @property
    def por_lista(self) -> bool:
        return self.identificacion == "lista"

    @property
    def total_preguntas(self) -> int:
        return sum(m.preguntas for m in self.materias)


# ---------------------------------------------------------------------------
# Funciones auxiliares de validación
# ---------------------------------------------------------------------------

def _exigir(condicion: bool, mensaje: str) -> None:
    """Si la condición es falsa, detiene el programa con un mensaje claro."""
    if not condicion:
        raise ErrorDeConfiguracion(mensaje)


def _texto(datos: dict, clave: str, donde: str, obligatorio: bool = True) -> str:
    valor = datos.get(clave, "")
    _exigir(isinstance(valor, (str, int)), f"En {donde}, '{clave}' debe ser un texto.")
    valor = str(valor).strip()
    if obligatorio:
        _exigir(valor != "", f"En {donde}, falta el campo '{clave}'.")
    return valor


def _entero(datos: dict, clave: str, donde: str, minimo: int, maximo: int) -> int:
    valor = datos.get(clave)
    # bool es subclase de int en Python, por eso lo excluimos aparte
    _exigir(isinstance(valor, int) and not isinstance(valor, bool),
            f"En {donde}, '{clave}' debe ser un número entero (sin comillas).")
    _exigir(minimo <= valor <= maximo,
            f"En {donde}, '{clave}' debe estar entre {minimo} y {maximo} (llegó {valor}).")
    return valor


def texto_a_partes(texto: str) -> list[dict]:
    """
    Lo que escribe el docente → lista de partes.
        "1-5: 8, 6-10: 3"  →  [{"desde": 1, "hasta": 5, "opciones": 8},
                                {"desde": 6, "hasta": 10, "opciones": 3}]
    Lanza ValueError con un mensaje claro si no se entiende.
    """
    partes = []
    for trozo in [t.strip() for t in re.split(r"[,;]", texto) if t.strip()]:
        coincide = re.fullmatch(r"(\d+)\s*(?:-|a|al|–)\s*(\d+)\s*[:=]\s*(\d+)|(\d+)\s*[:=]\s*(\d+)",
                                trozo)
        if not coincide:
            raise ValueError(f"No se entiende «{trozo}». Escriba, por ejemplo: 1-5: 8, 6-10: 3")
        if coincide.group(1):
            desde, hasta, opciones = map(int, coincide.group(1, 2, 3))
        else:
            desde = hasta = int(coincide.group(4))
            opciones = int(coincide.group(5))
        partes.append({"desde": desde, "hasta": hasta, "opciones": opciones})
    return partes


def partes_a_texto(partes: list[dict]) -> str:
    return ", ".join(f"{p['desde']}-{p['hasta']}: {p['opciones']}" if p["desde"] != p["hasta"]
                     else f"{p['desde']}: {p['opciones']}" for p in partes or [])


def _leer_partes(m: dict, donde: str, preguntas: int) -> list[tuple[int, int, int]]:
    """Valida las partes de una materia (si tiene)."""
    partes = m.get("partes") or []
    _exigir(isinstance(partes, list), f"En {donde}, 'partes' debe ser una lista.")
    resultado, usadas = [], set()
    for p in partes:
        _exigir(isinstance(p, dict), f"En {donde}, cada parte debe ser un objeto {{ ... }}.")
        desde = _entero(p, "desde", donde, 1, preguntas)
        hasta = _entero(p, "hasta", donde, desde, preguntas)
        opciones = _entero(p, "opciones", donde, 2, len(diseno.LETRAS_OPCIONES))
        rango = set(range(desde, hasta + 1))
        cruce = rango & usadas
        _exigir(not cruce, f"En {donde}, las partes se cruzan (la pregunta "
                           f"{min(cruce) if cruce else ''} está en dos partes).")
        usadas |= rango
        resultado.append((desde, hasta, opciones))
    return sorted(resultado)


# ---------------------------------------------------------------------------
# Función principal
# ---------------------------------------------------------------------------

def cargar_configuracion(ruta_json: str | Path) -> ConfiguracionExamen:
    """Lee el JSON, revisa cada campo y devuelve un ConfiguracionExamen."""
    ruta_json = Path(ruta_json)
    _exigir(ruta_json.exists(), f"No existe el archivo de configuración: {ruta_json}")

    try:
        datos = json.loads(ruta_json.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise ErrorDeConfiguracion(
            f"El JSON tiene un error de escritura en la línea {error.lineno}, "
            f"columna {error.colno}: {error.msg}. Revisen comas, comillas y llaves."
        ) from error
    # La ruta del logo se interpreta relativa a la carpeta del JSON
    return configuracion_desde_datos(datos, ruta_json.parent)


def configuracion_desde_datos(datos: dict, carpeta_base: str | Path = ".") -> ConfiguracionExamen:
    """
    Revisa un diccionario con la configuración (el mismo contenido del JSON)
    y devuelve un ConfiguracionExamen. La usa la interfaz gráfica, que arma
    el diccionario a partir de lo que el docente escribe en pantalla.
    """
    _exigir(isinstance(datos, dict), "La configuración debe ser un objeto { ... }.")

    # --- Sección "colegio" ---
    colegio = datos.get("colegio", {})
    _exigir(isinstance(colegio, dict), "La sección 'colegio' debe ser un objeto { ... }.")
    ruta_logo = None
    if colegio.get("logo"):
        ruta_logo = (Path(carpeta_base) / colegio["logo"]).resolve()
        _exigir(ruta_logo.exists(), f"No se encontró el logo en: {ruta_logo}")

    # --- Sección "examen" ---
    examen = datos.get("examen", {})
    _exigir(isinstance(examen, dict), "La sección 'examen' debe ser un objeto { ... }.")

    # --- Sección "documento" (opcional) ---
    documento = datos.get("documento", {"digitos": 10})
    _exigir(isinstance(documento, dict), "La sección 'documento' debe ser un objeto { ... }.")
    identificacion = documento.get("tipo", "documento") or "documento"
    _exigir(identificacion in ("documento", "lista"),
            "En 'documento', 'tipo' debe ser \"documento\" o \"lista\".")

    # --- Sección "opciones" (opcional) ---
    opciones = datos.get("opciones", {})
    numeracion = opciones.get("numeracion", "continua")
    _exigir(numeracion in ("continua", "por_materia"),
            "En 'opciones', 'numeracion' debe ser \"continua\" o \"por_materia\".")

    configuracion = ConfiguracionExamen(
        nombre_colegio=_texto(colegio, "nombre", "'colegio'"),
        municipio=_texto(colegio, "municipio", "'colegio'", obligatorio=False),
        ruta_logo=ruta_logo,
        nombre_examen=_texto(examen, "nombre", "'examen'"),
        grado=_texto(examen, "grado", "'examen'"),
        fecha=_texto(examen, "fecha", "'examen'", obligatorio=False),
        # Con N.º de lista siempre son 2 cifras (hasta 99 estudiantes)
        digitos_documento=(2 if identificacion == "lista"
                           else _entero(documento, "digitos", "'documento'", 4, 12)),
        identificacion=identificacion,
        numeracion=numeracion,
        formas=_entero({"formas": opciones.get("formas", 1)}, "formas", "'opciones'",
                       1, diseno.MAX_FORMAS),
        codigo_examen=(_entero(datos, "codigo_examen", "la configuración", 1, 1022)
                       if datos.get("codigo_examen") is not None else None),
    )

    # --- Sección "materias" ---
    materias = datos.get("materias")
    _exigir(isinstance(materias, list) and len(materias) > 0,
            "Debe haber una lista 'materias' con al menos una materia.")

    codigos_vistos = set()
    for i, m in enumerate(materias, start=1):
        donde = f"la materia #{i}"
        _exigir(isinstance(m, dict), f"{donde} debe ser un objeto {{ ... }}.")
        codigo = _texto(m, "codigo", donde).upper()
        # Solo letras y números: el código termina siendo nombre de columna
        _exigir(re.fullmatch(r"[A-Z][A-Z0-9]{0,7}", codigo) is not None,
                f"En {donde}, el código '{codigo}' debe empezar con letra y tener "
                f"solo letras/números (máx. 8), ej. \"MAT\".")
        _exigir(codigo not in codigos_vistos, f"El código '{codigo}' está repetido.")
        codigos_vistos.add(codigo)

        preguntas = _entero(m, "preguntas", donde, 1, 200)
        configuracion.materias.append(Materia(
            codigo=codigo,
            nombre=_texto(m, "nombre", donde),
            preguntas=preguntas,
            opciones=_entero(m, "opciones", donde, 2, len(diseno.LETRAS_OPCIONES)),
            partes=_leer_partes(m, f"«{m.get('nombre', codigo)}»", preguntas),
        ))

    return configuracion
