"""
generar.py — Une todas las piezas del Módulo 1.

    examen.json
        │  configuracion.cargar_configuracion()
        ▼
    ConfiguracionExamen
        │  maquetador.maquetar()
        ▼
    Maqueta  (única fuente de verdad)
        ├── dibujante_pdf.dibujar_pdf()            → hoja_respuestas.pdf
        └── plantilla_omr.guardar_archivos_omr()   → template.json, template_fotos.json,
                                                     config.json, omr_marker.jpg
        │
        └── verificar.verificar()                  → verificacion.png
"""

from __future__ import annotations

import csv
import json
import random
import re
import shutil
import unicodedata
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from . import diseno as d
from .configuracion import ErrorDeConfiguracion, cargar_configuracion, configuracion_desde_datos
from .dibujante_pdf import dibujar_pdf_hojas
from .maqueta import Pagina
from .maquetador import maquetar_examen, pagina_personalizada
from .plantilla_omr import guardar_archivos_omr, nombre_plantilla
from .verificar import verificar


def nombre_de_carpeta(texto: str) -> str:
    """'Simulacro Saber 11°' → 'simulacro_saber_11' (sin tildes ni símbolos)."""
    texto = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "_", texto.lower()).strip("_")


@dataclass
class ResultadoGeneracion:
    """Lo que devuelve la generación, para mostrarlo en consola o en la interfaz."""
    carpeta: Path
    ruta_pdf: Path
    total_preguntas: int
    desviacion: float | None   # None si no se verificó
    codigo_examen: int = 0
    ruta_personalizadas: Path | None = None
    hojas_personalizadas: int = 0
    archivado_en: Path | None = None   # dónde quedaron las lecturas viejas (si se movieron)
    hojas: int = 1                     # hojas por estudiante

    @property
    def verificacion_ok(self) -> bool:
        return self.desviacion is None or self.desviacion <= 1.0


def estructura(datos: dict) -> tuple:
    """
    Lo que define DÓNDE están las burbujas: si cambia, las hojas ya impresas
    (y lo que ya se leyó) dejan de corresponder a la hoja nueva.
    El nombre del colegio, la fecha o el logo no cuentan.
    """
    opciones = datos.get("opciones", {})
    return (datos.get("documento", {}).get("digitos", 10),
            int(opciones.get("formas", 1) or 1),
            tuple((m.get("codigo", "").upper(), m.get("preguntas"), m.get("opciones"))
                  for m in datos.get("materias", [])))


def _examen_anterior(carpeta: Path) -> dict | None:
    try:
        return json.loads((carpeta / "examen.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _archivar_lecturas(carpeta: Path) -> Path | None:
    """
    Mueve lo leído y la clave del examen anterior a una carpeta aparte
    ("anterior_2026-10-09_1530"), para que no se mezcle con el examen nuevo.
    No se borra nada.
    """
    cosas = [carpeta / n for n in ("lecturas", "clave.json", "resultados.xlsx", "hojas_con_nombre.pdf")
             if (carpeta / n).exists()]
    if not cosas:
        return None
    destino = carpeta / f"anterior_{datetime.now():%Y-%m-%d_%H%M}"
    destino.mkdir(exist_ok=True)
    for cosa in cosas:
        shutil.move(str(cosa), str(destino / cosa.name))
    return destino


def _asignar_codigo(carpeta: Path, carpeta_salidas: Path, mismo_diseno: bool) -> int:
    """
    Cada examen tiene un código único (1 a 1022) que se imprime en la hoja.
    - Si el examen ya existía con el MISMO diseño, conserva su código
      (las hojas ya impresas siguen sirviendo).
    - Si es nuevo, o cambió el diseño, se elige al azar uno que no use otro examen.
      Así, una hoja impresa con el diseño viejo se reconoce como "de otro examen".
    """
    anterior = _examen_anterior(carpeta)
    if mismo_diseno and anterior and anterior.get("codigo_examen"):
        return int(anterior["codigo_examen"])
    usados = set()
    for otro in Path(carpeta_salidas).glob("*/examen.json"):
        try:
            usados.add(int(json.loads(otro.read_text(encoding="utf-8")).get("codigo_examen") or 0))
        except (OSError, ValueError):
            continue
    return random.choice([c for c in range(1, 1023) if c not in usados])


def _solo_digitos(texto: str) -> str:
    return re.sub(r"\D", "", str(texto)).lstrip("0")


def preparar_estudiantes(estudiantes: list[dict], digitos: int) -> list[dict]:
    """Limpia la lista y revisa que cada documento quepa en la hoja."""
    limpios, largos = [], []
    for e in estudiantes:
        doc = _solo_digitos(e.get("documento", ""))
        if not doc:
            continue
        if len(doc) > digitos:
            largos.append(f"{e.get('nombre', '')} ({doc})")
        limpios.append({"documento": doc, "nombre": str(e.get("nombre", "")).strip(),
                        "curso": str(e.get("curso", "") or "").strip()})
    if largos:
        raise ErrorDeConfiguracion(
            f"{len(largos)} documento(s) tienen más de {digitos} cifras, por ejemplo "
            f"{largos[0]}. Aumente «Dígitos del documento».")
    return limpios


def generar_desde_datos(datos: dict, carpeta_base: str | Path = ".",
                        carpeta_salidas: str | Path = "salidas",
                        verificar_resultado: bool = True,
                        estudiantes: list[dict] | None = None,
                        repartir_formas: bool = True) -> ResultadoGeneracion:
    """
    Genera todos los archivos del examen a partir de un diccionario.
    (La interfaz gráfica llama esta función directamente.)

    estudiantes: lista opcional de {"documento", "nombre", "curso"}. Si se da,
    además se crea hojas_con_nombre.pdf: una hoja por estudiante, con su nombre
    y su documento ya marcados. Con repartir_formas, las formas se asignan
    alternadas (A, B, A, B...).
    """
    datos = {k: v for k, v in datos.items() if k != "codigo_examen"}
    conf = configuracion_desde_datos(datos, carpeta_base)

    carpeta = Path(carpeta_salidas) / nombre_de_carpeta(f"{conf.nombre_examen}_grado_{conf.grado}")
    lista = preparar_estudiantes(estudiantes, conf.digitos_documento) if estudiantes else []
    anterior = _examen_anterior(carpeta)
    mismo_diseno = anterior is not None and estructura(anterior) == estructura(datos)
    conf.codigo_examen = _asignar_codigo(carpeta, Path(carpeta_salidas), mismo_diseno)
    hojas = maquetar_examen(conf)        # casi siempre una sola hoja
    # Si el diseño cambió, lo que se leyó con el diseño viejo ya no sirve: se aparta
    archivado_en = _archivar_lecturas(carpeta) if anterior and not mismo_diseno else None
    carpeta.mkdir(parents=True, exist_ok=True)

    # Hoja(s) en blanco: un PDF con una página por cada hoja del examen
    ruta_pdf = carpeta / "hoja_respuestas.pdf"
    dibujar_pdf_hojas([(h, Pagina()) for h in hojas], ruta_pdf, titulo=conf.nombre_examen)
    for vieja in carpeta.glob("template*_hoja*.json"):   # por si antes tenía más hojas
        vieja.unlink()
    guardar_archivos_omr(hojas, carpeta)
    # Guardamos una copia de la configuración (con su código): los módulos 2 y 3 la usan
    (carpeta / "examen.json").write_text(
        json.dumps({**datos, "codigo_examen": conf.codigo_examen,
                    # fecha de creación (se conserva al regenerar): ordena el seguimiento
                    "creado": (anterior or {}).get("creado") or datetime.now().isoformat(
                        timespec="seconds"),
                    # qué preguntas van en cada hoja (si el examen tiene varias)
                    "hojas": [h.etiquetas_preguntas for h in hojas]},
                   indent=2, ensure_ascii=False),
        encoding="utf-8")

    # Hojas personalizadas: todas las hojas de cada estudiante, una tras otra
    ruta_personalizadas = None
    if lista:
        letras = d.LETRAS_OPCIONES[: conf.formas] if conf.formas > 1 else ""
        pares = []
        for i, e in enumerate(lista):
            forma = letras[i % len(letras)] if letras and repartir_formas else ""
            for h in hojas:
                pares.append((h, pagina_personalizada(h, e["documento"], e["nombre"],
                                                      e["curso"], forma)))
        ruta_personalizadas = carpeta / "hojas_con_nombre.pdf"
        dibujar_pdf_hojas(pares, ruta_personalizadas, titulo=conf.nombre_examen)
        # La misma lista sirve después en "Resultados" (nombres y quién no entregó)
        with open(carpeta / "estudiantes.csv", "w", newline="", encoding="utf-8-sig") as f:
            escritor = csv.DictWriter(f, fieldnames=["documento", "nombre", "curso"])
            escritor.writeheader()
            escritor.writerows(lista)

    # Verificación: cada hoja del PDF contra su plantilla
    desviacion = None
    if verificar_resultado:
        desviaciones = []
        for k, h in enumerate(hojas):
            sufijo = "" if k == 0 else f"_hoja{k + 1}"
            desviaciones.append(verificar(ruta_pdf, carpeta / nombre_plantilla(h.hoja), h,
                                          carpeta / f"verificacion{sufijo}.png", indice=k))
        desviacion = max(desviaciones)
    return ResultadoGeneracion(carpeta, ruta_pdf, conf.total_preguntas, desviacion,
                               conf.codigo_examen, ruta_personalizadas, len(lista), archivado_en,
                               len(hojas))


def generar_hoja(ruta_config: str | Path, carpeta_salidas: str | Path = "salidas",
                 verificar_resultado: bool = True) -> ResultadoGeneracion:
    """Versión para la consola: lee el JSON, genera e imprime el resultado."""
    ruta_config = Path(ruta_config)
    cargar_configuracion(ruta_config)   # valida el archivo con mensajes claros
    datos = json.loads(ruta_config.read_text(encoding="utf-8"))
    r = generar_desde_datos(datos, ruta_config.parent, carpeta_salidas, verificar_resultado)

    hojas = f" en {r.hojas} hojas por estudiante" if r.hojas > 1 else ""
    print(f"✔ Hoja generada: {r.total_preguntas} preguntas{hojas} · "
          f"código del examen N.º {r.codigo_examen}.")
    print(f"  Archivos en: {r.carpeta}")
    if r.desviacion is not None:
        if r.verificacion_ok:
            print(f"✔ Verificación: PDF y template.json coinciden "
                  f"(desviación máxima {r.desviacion:.2f} px).")
        else:
            print(f"✘ ATENCIÓN: desviación de {r.desviacion:.2f} px. Revisen verificacion.png")
    return r
