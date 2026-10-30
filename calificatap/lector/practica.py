"""
practica.py — Inventa un curso completo para practicar sin imprimir.

Crea, para un examen ya generado, en la carpeta indicada:
    curso_escaneado.pdf     ← todas las hojas "escaneadas" en un solo PDF
    clave_correcta.txt      ← la clave (por forma), para escribirla en Resultados
    lista_estudiantes.csv   ← lista del curso para importar

Los estudiantes son inventados. Cada uno tiene una "habilidad" distinta, así
los resultados se ven variados (unos ganan, otros pierden). Sirve para:
    - mostrarle el programa a otros docentes sin imprimir nada;
    - probar cambios en el código sin tener que escanear hojas reales.
"""

from __future__ import annotations

import csv
import io
import random
import zlib
from pathlib import Path


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


def _habilidad_base(documento: str) -> float:
    """
    Cada estudiante inventado tiene una habilidad fija (entre 0,35 y 0,90) que sale
    de su documento. Así, en varios exámenes de práctica, el mismo estudiante
    rinde parecido (y el seguimiento entre exámenes tiene sentido).
    """
    return 0.35 + 0.55 * (zlib.crc32(documento.encode()) % 1000) / 1000


def crear_curso_de_practica(examen: Examen, destino: str | Path, estudiantes: int = 24,
                            con_nombre: bool = True, semilla: int = 11,
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
    for viejo in destino.glob("foto_*.jpg"):     # fotos de versiones anteriores (ya no se usan)
        viejo.unlink()

    pdf_curso = fitz.open()
    lista = []
    if lista_fija:
        # (documento, nombre) o (documento, nombre, N.º de lista)
        candidatos = ([tuple(e) for e in lista_fija][:99] if conf.por_lista
                      else [tuple(e) for e in lista_fija if len(e[0]) <= digitos])
    else:
        candidatos = [(str(azar.randint(10**9, 1_199_999_999))[:max(digitos, 8)],
                       f"{azar.choice(NOMBRES)} {azar.choice(APELLIDOS)} {azar.choice(APELLIDOS)}")
                      for _ in range(estudiantes)]
    for i, (documento, nombre, *numero) in enumerate(candidatos):
        forma = formas[i % len(formas)]
        lista.append((documento, nombre))
        # Lo que va en la hoja: el documento, o el N.º de lista (su posición: 1, 2, 3...)
        en_la_hoja = (numero[0] if numero else str(i + 1)) if conf.por_lista else documento
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
                pagina = pagina_personalizada(h, en_la_hoja, nombre, f"{examen.grado}-01",
                                              forma if examen.letras_formas else "")
            else:
                # Hoja en blanco: el estudiante rellena su documento (o N.º) y su forma
                pagina = Pagina(marcas=dict(zip(
                    h.etiquetas_documento, en_la_hoja.zfill(len(h.etiquetas_documento)))))
                if examen.letras_formas:
                    pagina.marcas["forma"] = forma
            pagina.marcas.update({e: v for e, v in respuestas.items()
                                  if e in h.etiquetas_preguntas})
            pares.append((h, pagina))

        memoria = io.BytesIO()
        dibujar_pdf_hojas(pares, memoria)
        pdf_curso.insert_pdf(fitz.open(stream=memoria.getvalue(), filetype="pdf"))
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
