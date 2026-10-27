"""
omr.py — Lee las hojas diligenciadas usando OMRChecker.

Pasos:
    1. Preparar las imágenes: cada página de un PDF se convierte en una imagen;
       las fotos se copian tal cual.
    2. Primera pasada con template.json (pensado para ESCÁNER).
    3. Las hojas que fallen se intentan otra vez con template_fotos.json
       (que primero recorta la hoja del fondo: pensado para FOTOS DE CELULAR).
    4. Se arma un HojaLeida por cada imagen, con lo que leyó OMRChecker.

OMRChecker se ejecuta como un programa aparte (subprocess). Así, si algo
falla dentro de él, la ventana de CalificaTAP no se cierra.
"""

from __future__ import annotations

import csv
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Callable

try:
    import pymupdf as fitz
except ImportError:
    import fitz

from ..examenes import Examen, listar_examenes
from ..generador.plantilla_omr import nombre_plantilla
from .hojas import ERROR, HojaLeida

EXTENSIONES_IMAGEN = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff", ".webp"}
EXTENSIONES_ADMITIDAS = EXTENSIONES_IMAGEN | {".pdf"}
DPI_PDF = 200   # resolución al convertir PDF escaneados en imágenes

# Tipo de la función que avisa el avance: avance(hechas, total, mensaje)
FuncionAvance = Callable[[int, int, str], None]


class ErrorDeLectura(Exception):
    """Problema que impide leer (por ejemplo, no está instalado OMRChecker)."""


def buscar_omrchecker(raiz_proyecto: Path) -> Path:
    carpeta = raiz_proyecto / "externo" / "OMRChecker"
    if not (carpeta / "main.py").exists():
        raise ErrorDeLectura(
            "No se encontró OMRChecker en la carpeta «externo\\OMRChecker».\n"
            "Pida ayuda para descargarlo (ver README) y ejecute Instalar.bat.")
    return carpeta


# ---------------------------------------------------------------------------
# 1. Preparar imágenes
# ---------------------------------------------------------------------------
def _nombre_libre(carpeta: Path, nombre: str) -> str:
    """Si ya existe 'hoja.jpg', devuelve 'hoja_2.jpg', 'hoja_3.jpg'..."""
    base, ext = Path(nombre).stem, Path(nombre).suffix
    candidato, n = nombre, 2
    while (carpeta / candidato).exists():
        candidato, n = f"{base}_{n}{ext}", n + 1
    return candidato


def preparar_imagenes(archivos: list[Path], destino: Path) -> dict[str, str]:
    """
    Copia/convierte los archivos a imágenes dentro de 'destino'.
    Devuelve {nombre_imagen: nombre_archivo_original}.
    """
    destino.mkdir(parents=True, exist_ok=True)
    origen_de = {}
    for archivo in archivos:
        ext = archivo.suffix.lower()
        if ext == ".pdf":
            with fitz.open(str(archivo)) as pdf:
                for n, pagina in enumerate(pdf, start=1):
                    nombre = _nombre_libre(destino, f"{archivo.stem}_pag{n:02d}.png")
                    pix = pagina.get_pixmap(dpi=DPI_PDF, colorspace=fitz.csGRAY)
                    pix.save(str(destino / nombre))
                    origen_de[nombre] = f"{archivo.name} (pág. {n})"
        elif ext in EXTENSIONES_IMAGEN:
            nombre = _nombre_libre(destino, archivo.name)
            shutil.copy(archivo, destino / nombre)
            origen_de[nombre] = archivo.name
    return origen_de


# ---------------------------------------------------------------------------
# 2. Ejecutar OMRChecker
# ---------------------------------------------------------------------------
def _ejecutar_omrchecker(omrchecker: Path, entrada: Path, salida: Path,
                         total: int, ya_hechas: int, total_global: int,
                         avance: FuncionAvance | None, mensaje: str) -> None:
    """Lanza OMRChecker y, mientras trabaja, cuenta las hojas que ya terminó."""
    salida.mkdir(parents=True, exist_ok=True)
    opciones = {}
    if sys.platform == "win32":
        opciones["creationflags"] = subprocess.CREATE_NO_WINDOW   # sin ventana negra
    # Python en modo "sin consola" (pythonw) no puede escribir en pantalla:
    # mandamos lo que imprime OMRChecker a un archivo de registro.
    ruta_registro = salida.parent / f"registro_{salida.name}.txt"
    registro = open(ruta_registro, "w", encoding="utf-8")
    proceso = subprocess.Popen(
        [sys.executable, "main.py", "-i", str(entrada.resolve()), "-o", str(salida.resolve())],
        cwd=omrchecker, stdout=registro, stderr=subprocess.STDOUT,
        env={**os.environ, "PYTHONIOENCODING": "utf-8"}, **opciones)

    revisadas = salida / "CheckedOMRs"
    while proceso.poll() is None:
        if avance:
            listas = len([p for p in revisadas.glob("*") if p.is_file()]) if revisadas.exists() else 0
            avance(ya_hechas + min(listas, total), total_global, mensaje)
        time.sleep(0.4)
    registro.close()

    if proceso.returncode != 0:
        # OMRChecker se detuvo con un error: mostramos el final de su registro
        final = ruta_registro.read_text(encoding="utf-8", errors="replace")[-1500:]
        raise ErrorDeLectura(f"OMRChecker se detuvo con un error:\n\n{final}")


def _leer_resultados(salida: Path) -> dict[str, dict]:
    """{nombre_imagen: fila_del_csv} con lo que OMRChecker sí pudo leer."""
    filas = {}
    for archivo in (salida / "Results").glob("Results_*.csv"):
        with open(archivo, newline="", encoding="utf-8") as f:
            for fila in csv.DictReader(f):
                filas[Path(fila["file_id"]).name] = fila
    return filas


def _de_otro_examen(examen: Examen, bits: str) -> str:
    """
    Compara el código leído en la hoja con el del examen.
    Devuelve "" si todo está bien, o un mensaje si la hoja es de otro examen.
    Si el código no se pudo leer (borroso, tachado) no se acusa a la hoja.
    """
    if not examen.codigo or not re.fullmatch(r"[01]{10}", bits or ""):
        return ""
    leido = int(bits, 2)
    if leido == examen.codigo:
        return ""
    for otro in listar_examenes(examen.carpeta.parent):
        if otro.codigo == leido:
            return f"Es una hoja de otro examen: «{otro.nombre_visible}»"
    return f"Es una hoja de otro examen (código N.º {leido})"


# ---------------------------------------------------------------------------
# 3. Función principal
# ---------------------------------------------------------------------------
def _leer_con_plantilla(examen: Examen, omrchecker: Path, trabajo: Path, todas: Path,
                        imagenes: list[str], hoja: int | str, etapa: str,
                        progreso: "Progreso") -> dict[str, tuple[dict, Path]]:
    """
    Lee 'imagenes' con la plantilla de una hoja (o la de "identificar"), en dos
    pasadas: primero la de escáner y, con las que fallen, la de fotos.
    Devuelve {imagen: (fila_del_csv, imagen_revisada)} con las que sí se leyeron.
    """
    leidas: dict[str, tuple[dict, Path]] = {}
    pendientes = list(imagenes)
    base = progreso.hechas                   # lo que ya se había avanzado antes de esta etapa
    for fotos, mensaje in ((False, "Leyendo hojas…"), (True, "Reintentando las fotos difíciles…")):
        if not pendientes:
            break
        nombre = f"{etapa}_{'fotos' if fotos else 'escaner'}"
        entrada, salida = trabajo / f"entrada_{nombre}", trabajo / f"salida_{nombre}"
        entrada.mkdir(parents=True)
        # OMRChecker busca estos archivos junto a las imágenes
        shutil.copy(examen.carpeta / nombre_plantilla(hoja, fotos), entrada / "template.json")
        shutil.copy(examen.carpeta / "config.json", entrada / "config.json")
        shutil.copy(examen.carpeta / "omr_marker.jpg", entrada / "omr_marker.jpg")
        for imagen in pendientes:
            shutil.copy(todas / imagen, entrada / imagen)

        ya_hechas = base + len(imagenes) - len(pendientes)
        _ejecutar_omrchecker(omrchecker, entrada, salida, len(pendientes),
                             ya_hechas, progreso.total, progreso.avance, mensaje)
        resultados = _leer_resultados(salida)
        for imagen in list(pendientes):
            if imagen in resultados:
                leidas[imagen] = (resultados[imagen], salida / "CheckedOMRs" / imagen)
                pendientes.remove(imagen)
    progreso.hechas = base + len(imagenes)   # leídas o no, esta etapa ya terminó
    return leidas


class Progreso:
    """Lleva la cuenta del avance total (puede haber varias etapas de lectura)."""

    def __init__(self, total: int, avance: FuncionAvance | None):
        self.total, self.avance, self.hechas = total, avance, 0


def _bits_a_numero(bits: str, cantidad: int) -> int | None:
    return int(bits, 2) if re.fullmatch(rf"[01]{{{cantidad}}}", bits or "") else None


def leer_hojas(examen: Examen, archivos: list[Path], raiz_proyecto: Path,
               avance: FuncionAvance | None = None) -> list[HojaLeida]:
    """
    Lee todas las hojas. Si el examen tiene UNA hoja por estudiante (lo normal),
    cada imagen se lee directamente con su plantilla.

    Si tiene VARIAS hojas, primero se averigua qué hoja es cada imagen leyendo
    solo la franja de abajo (plantilla "identificar"), y luego cada imagen se
    lee con la plantilla de su hoja.
    """
    omrchecker = buscar_omrchecker(raiz_proyecto)
    trabajo = examen.carpeta_lecturas / "_trabajo"
    shutil.rmtree(trabajo, ignore_errors=True)
    carpeta_imagenes = examen.carpeta_lecturas / "imagenes"
    carpeta_imagenes.mkdir(parents=True, exist_ok=True)

    if avance:
        avance(0, 1, "Preparando las imágenes…")
    todas = trabajo / "todas"
    origen_de = preparar_imagenes(archivos, todas)
    total = len(origen_de)
    if total == 0:
        raise ErrorDeLectura("Ninguno de los archivos es un PDF o una imagen.")

    imagenes = list(origen_de)
    n_hojas = examen.numero_hojas
    hoja_de: dict[str, int] = {}
    motivo_de: dict[str, str] = {}
    progreso = Progreso(total * (2 if n_hojas > 1 else 1), avance)

    if n_hojas == 1:
        hoja_de = {img: 1 for img in imagenes}
    else:
        # Etapa 1: ¿qué hoja es cada imagen?
        identificadas = _leer_con_plantilla(examen, omrchecker, trabajo, todas, imagenes,
                                            "identificar", "identificar", progreso)
        for img in imagenes:
            if img not in identificadas:
                continue                       # quedará como "no se pudo leer"
            fila = identificadas[img][0]
            otro = _de_otro_examen(examen, fila.get("codigo_examen", ""))
            numero = _bits_a_numero(fila.get("hoja", ""), 2)
            if otro:
                motivo_de[img] = otro
            elif numero is None or numero + 1 > n_hojas:
                motivo_de[img] = "No se pudo leer el número de hoja (franja de abajo)"
            else:
                hoja_de[img] = numero + 1

    # Etapa 2: leer cada imagen con la plantilla de su hoja
    leidas: dict[str, tuple[dict, Path]] = {}
    for k in range(1, n_hojas + 1):
        de_esta_hoja = [img for img in imagenes if hoja_de.get(img) == k]
        if de_esta_hoja:
            leidas.update(_leer_con_plantilla(examen, omrchecker, trabajo, todas, de_esta_hoja,
                                              k, f"hoja{k}", progreso))

    # Armar el resultado
    etiquetas = examen.todas_las_etiquetas()
    hojas = []
    for imagen, origen in origen_de.items():
        nombre_final = _nombre_libre(carpeta_imagenes, imagen)
        k = hoja_de.get(imagen, 1)
        if imagen in leidas:
            fila, revisada = leidas[imagen]
            shutil.copy(revisada if revisada.exists() else todas / imagen,
                        carpeta_imagenes / nombre_final)
            hoja = HojaLeida(archivo=nombre_final, origen=origen,
                             documento=fila.get("documento", ""),
                             respuestas={e: fila.get(e, "") or "" for e in etiquetas},
                             imagen=f"lecturas/imagenes/{nombre_final}",
                             forma=fila.get("forma", "") or "", hoja=k,
                             letras_forma=examen.letras_formas,
                             etiquetas_hoja=examen.etiquetas_de_hoja(k))
            hoja.actualizar_estado()
            # ¿La hoja es de este examen? (código impreso en la franja inferior)
            otro = _de_otro_examen(examen, fila.get("codigo_examen", ""))
            if otro:
                hoja.estado, hoja.motivo = ERROR, otro
        else:
            shutil.copy(todas / imagen, carpeta_imagenes / nombre_final)
            hoja = HojaLeida(archivo=nombre_final, origen=origen, estado=ERROR,
                             respuestas={e: "" for e in etiquetas},
                             imagen=f"lecturas/imagenes/{nombre_final}", hoja=k,
                             motivo=motivo_de.get(imagen, ""),
                             letras_forma=examen.letras_formas,
                             etiquetas_hoja=examen.etiquetas_de_hoja(k))
        hojas.append(hoja)

    if avance:
        avance(progreso.total, progreso.total, "Lectura terminada")
    shutil.rmtree(trabajo, ignore_errors=True)
    return hojas
