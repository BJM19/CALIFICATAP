"""
practica.py — Inventa un curso completo para practicar sin imprimir.

Crea, para un examen ya generado, en la carpeta indicada:
    curso_escaneado.pdf     ← varias hojas "escaneadas" en un solo PDF
    foto_*.jpg              ← algunas hojas como "fotos de celular" (torcidas, con sombra)
    clave_correcta.txt      ← la clave (por forma), para escribirla en Resultados
    lista_estudiantes.csv   ← lista del curso para importar

Los estudiantes son inventados. Cada uno tiene una "habilidad" distinta, así
los resultados se ven variados (unos ganan, otros pierden). Sirve para:
    - mostrarle el programa a otros docentes sin imprimir nada;
    - probar cambios en el código (los estudiantes de Media Técnica).
"""

from __future__ import annotations

import csv
import io
import random
import zlib
from pathlib import Path

import cv2
import numpy as np

try:
    import pymupdf as fitz
except ImportError:
    import fitz

from ..examenes import Examen
from ..generador.configuracion import configuracion_desde_datos
from ..generador.dibujante_pdf import dibujar_pdf_hojas
from ..generador.maqueta import Pagina
from ..generador.maquetador import maquetar_examen, pagina_personalizada

NOMBRES = ["Ana", "Luis", "Camila", "Andrés", "Valentina", "Santiago", "Daniela", "Juan",
           "Mariana", "Sebastián", "Laura", "Mateo", "Sara", "Nicolás", "Paula", "Felipe",
           "Isabela", "Tomás", "Gabriela", "Samuel", "Juliana", "David", "Sofía", "Kevin"]
APELLIDOS = ["Rojas", "Gómez", "Rodríguez", "Martínez", "Torres", "Ramírez", "Vargas",
             "Castro", "Moreno", "Herrera", "Medina", "Suárez", "Parra", "Cárdenas"]


def simular_foto(imagen: np.ndarray, azar: np.random.Generator) -> np.ndarray:
    """Pone la hoja sobre un fondo, en perspectiva, con sombra y ruido."""
    h, w = imagen.shape
    fondo = np.full((int(h * 1.25), int(w * 1.25)), 105, np.uint8)
    dy, dx = (fondo.shape[0] - h) // 2, (fondo.shape[1] - w) // 2
    fondo[dy:dy + h, dx:dx + w] = imagen
    esquinas = np.float32([[dx, dy], [dx + w, dy], [dx + w, dy + h], [dx, dy + h]])
    movidas = esquinas + azar.uniform(-0.025, 0.025, esquinas.shape).astype(np.float32) * w
    foto = cv2.warpPerspective(fondo, cv2.getPerspectiveTransform(esquinas, movidas),
                               (fondo.shape[1], fondo.shape[0]), borderValue=105)
    foto = foto.astype(np.float32) * np.linspace(0.78, 1.0, foto.shape[1])[None, :]
    foto = cv2.GaussianBlur(foto, (5, 5), 0) + azar.normal(0, 5, foto.shape)
    return np.clip(foto, 0, 255).astype(np.uint8)


def _habilidad_base(documento: str) -> float:
    """
    Cada estudiante inventado tiene una habilidad fija (entre 0,35 y 0,90) que sale
    de su documento. Así, en varios exámenes de práctica, el mismo estudiante
    rinde parecido (y el seguimiento entre exámenes tiene sentido).
    """
    return 0.35 + 0.55 * (zlib.crc32(documento.encode()) % 1000) / 1000


def crear_curso_de_practica(examen: Examen, destino: str | Path, estudiantes: int = 24,
                            fotos: int = 3, con_nombre: bool = True, semilla: int = 11,
                            lista_fija: list[tuple[str, str]] | None = None,
                            mejora: float = 0.0):
    """
    Crea las hojas de práctica. Devuelve (carpeta, claves, lista):
        claves = {"A": {"MAT_01": "D", ...}, ...}
        lista  = [(documento, nombre), ...]

    lista_fija: usar estos estudiantes (por ejemplo, la lista real del curso)
                en lugar de inventarlos.
    mejora:     se suma a la habilidad de todos (0,1 = el curso mejoró 10 puntos).
    """
    azar = random.Random(semilla)
    azar_np = np.random.default_rng(semilla)

    conf = configuracion_desde_datos(examen.datos, examen.carpeta)
    hojas = maquetar_examen(conf)                # casi siempre una sola hoja
    valores_de = {e: b.valores for h in hojas for b in h.bloques for e in b.etiquetas}
    todas_preguntas = [e for h in hojas for e in h.etiquetas_preguntas]
    digitos = conf.digitos_documento
    formas = examen.formas_para_clave            # "A" si no hay formas; "AB" si hay dos

    # Una clave inventada por cada forma
    claves = {f: {e: azar.choice(valores_de[e]) for e in todas_preguntas} for f in formas}

    destino = Path(destino)
    destino.mkdir(parents=True, exist_ok=True)
    for viejo in destino.glob("foto_*.jpg"):     # quitar fotos de una práctica anterior
        viejo.unlink()

    pdf_curso = fitz.open()
    lista = []
    if lista_fija:
        candidatos = [(d, n) for d, n in lista_fija if len(d) <= digitos]
    else:
        candidatos = [(str(azar.randint(10**9, 1_199_999_999))[:digitos],
                       f"{azar.choice(NOMBRES)} {azar.choice(APELLIDOS)} {azar.choice(APELLIDOS)}")
                      for _ in range(estudiantes)]
    fotos = min(fotos, len(candidatos))
    for i, (documento, nombre) in enumerate(candidatos):
        forma = formas[i % len(formas)]
        lista.append((documento, nombre))
        habilidad = min(0.97, _habilidad_base(documento) + mejora + azar.uniform(-0.05, 0.05))

        # Lo que "marcó" este estudiante en todo el examen
        respuestas = {}
        for e in todas_preguntas:
            if azar.random() < 0.03:
                continue                                   # la dejó en blanco
            respuestas[e] = claves[forma][e] if azar.random() < habilidad else azar.choice(valores_de[e])

        pares = []
        for h in hojas:
            if con_nombre:
                # Hoja personalizada: nombre, documento y forma ya vienen impresos
                pagina = pagina_personalizada(h, documento, nombre, f"{examen.grado}-01",
                                              forma if examen.letras_formas else "")
            else:
                # Hoja en blanco: el estudiante rellena su documento y su forma
                pagina = Pagina(marcas={f"doc{k + 1:02d}": d
                                        for k, d in enumerate(documento.zfill(digitos))})
                if examen.letras_formas:
                    pagina.marcas["forma"] = forma
            pagina.marcas.update({e: v for e, v in respuestas.items()
                                  if e in h.etiquetas_preguntas})
            pares.append((h, pagina))

        memoria = io.BytesIO()
        dibujar_pdf_hojas(pares, memoria)
        paginas_pdf = fitz.open(stream=memoria.getvalue(), filetype="pdf")
        if i < fotos:
            for k, pagina_pdf in enumerate(paginas_pdf):
                pix = pagina_pdf.get_pixmap(dpi=150, colorspace=fitz.csGRAY)
                imagen = np.frombuffer(pix.samples, np.uint8).reshape(pix.height, pix.width)
                sufijo = f"_hoja{k + 1}" if len(hojas) > 1 else ""
                cv2.imwrite(str(destino / f"foto_{i + 1:02d}{sufijo}.jpg"),
                            simular_foto(imagen, azar_np))
        else:
            pdf_curso.insert_pdf(paginas_pdf)
    pdf_curso.save(str(destino / "curso_escaneado.pdf"))

    # Clave como texto, materia por materia (y forma por forma)
    with open(destino / "clave_correcta.txt", "w", encoding="utf-8") as f:
        for forma, clave in claves.items():
            if examen.letras_formas:
                f.write(f"--- Forma {forma} ---\n")
            for m in examen.materias:
                f.write(f"{m.nombre}: {''.join(clave[e] for e in m.etiquetas())}\n")
    # Lista del curso (como la exportaría el SIMAT, más o menos)
    with open(destino / "lista_estudiantes.csv", "w", newline="", encoding="utf-8-sig") as f:
        escritor = csv.writer(f, delimiter=";")
        escritor.writerow(["Número de documento", "Nombre completo", "Curso"])
        for documento, nombre in lista:
            escritor.writerow([documento, nombre, f"{examen.grado}-01"])

    return destino, claves, lista
