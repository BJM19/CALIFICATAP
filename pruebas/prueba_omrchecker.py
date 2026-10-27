"""
prueba_omrchecker.py — Prueba de extremo a extremo del Módulo 1.

¿Qué hace?
    1. Genera la hoja a partir de un JSON de configuración.
    2. "Simula a un estudiante": rellena respuestas al azar (con algunas en blanco)
       y un número de documento, usando la MISMA maqueta.
    3. Convierte esa hoja en imagen de dos formas:
         - escaneo: derecha y limpia
         - foto:    girada, en perspectiva, con fondo, sombra y ruido (como un celular)
    4. Ejecuta OMRChecker con el template.json generado.
    5. Compara lo que leyó OMRChecker con lo que "marcó el estudiante".

Si todo coincide, el PDF y el template.json están bien sincronizados.

Uso:
    python pruebas/prueba_omrchecker.py --omrchecker externo/OMRChecker
"""

from __future__ import annotations

import argparse
import csv
import random
import subprocess
import sys
import tempfile
from pathlib import Path

import cv2
import numpy as np

# Permite importar 'calificatap' al ejecutar este archivo directamente
RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from calificatap.generador.configuracion import cargar_configuracion  # noqa: E402
from calificatap.generador.dibujante_pdf import dibujar_pdf  # noqa: E402
from calificatap.generador.maquetador import maquetar  # noqa: E402
from calificatap.generador.plantilla_omr import guardar_archivos_omr  # noqa: E402
from calificatap.generador.verificar import pdf_a_imagen  # noqa: E402


def respuestas_al_azar(maqueta, semilla: int, prob_blanco: float = 0.05) -> dict[str, str]:
    """Inventa las marcas de un estudiante: {etiqueta: valor}."""
    azar = random.Random(semilla)
    marcas = {}
    for bloque in maqueta.bloques:
        if bloque.nombre.startswith("Codigo"):
            continue          # el código del examen ya viene impreso
        for etiqueta in bloque.etiquetas:
            if bloque.nombre == "Documento" or azar.random() > prob_blanco:
                marcas[etiqueta] = azar.choice(bloque.valores)
    return marcas


def simular_foto(imagen: np.ndarray, semilla: int) -> np.ndarray:
    """Distorsiona una imagen limpia para que parezca una foto de celular."""
    azar = np.random.default_rng(semilla)
    h, w = imagen.shape
    # 1. Ponemos la hoja sobre un "pupitre" gris más grande
    fondo = np.full((int(h * 1.25), int(w * 1.25)), 110, np.uint8)
    dy, dx = (fondo.shape[0] - h) // 2, (fondo.shape[1] - w) // 2
    fondo[dy:dy + h, dx:dx + w] = imagen
    # 2. Perspectiva: movemos un poco cada esquina de la hoja
    esquinas = np.float32([[dx, dy], [dx + w, dy], [dx + w, dy + h], [dx, dy + h]])
    movidas = esquinas + azar.uniform(-0.03, 0.03, esquinas.shape).astype(np.float32) * w
    matriz = cv2.getPerspectiveTransform(esquinas, movidas)
    foto = cv2.warpPerspective(fondo, matriz, (fondo.shape[1], fondo.shape[0]), borderValue=110)
    # 3. Sombra suave (más oscuro hacia un lado) + desenfoque + ruido
    gradiente = np.linspace(0.75, 1.0, foto.shape[1])[None, :]
    foto = foto.astype(np.float32) * gradiente
    foto = cv2.GaussianBlur(foto, (5, 5), 0)
    foto += azar.normal(0, 6, foto.shape)
    return np.clip(foto, 0, 255).astype(np.uint8)


def leer_resultados(carpeta_salida: Path) -> list[dict]:
    archivos = sorted(carpeta_salida.rglob("Results_*.csv"))
    if not archivos:
        return []
    with open(archivos[-1], encoding="utf-8") as f:
        return list(csv.DictReader(f))


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser()
    parser.add_argument("--omrchecker", default=str(RAIZ / "externo" / "OMRChecker"),
                        help="carpeta donde está main.py de OMRChecker")
    parser.add_argument("--config", default=str(RAIZ / "configuracion" / "examen_ejemplo.json"))
    parser.add_argument("--semilla", type=int, default=7)
    parser.add_argument("--formas", type=int, default=0, help="probar con formas A, B...")
    parser.add_argument("--prefijo", default="", help="comando antes de python (ej. xvfb-run -a)")
    args = parser.parse_args()

    conf = cargar_configuracion(args.config)
    conf.codigo_examen = 613          # un código cualquiera para la prueba
    if args.formas:
        conf.formas = args.formas
    maqueta = maquetar(conf)
    marcas = respuestas_al_azar(maqueta, args.semilla)
    esperado_doc = "".join(marcas[e] for e in maqueta.etiquetas_documento)
    esperado_cod = format(conf.codigo_examen, "010b")
    esperada_forma = marcas.get("forma", "")

    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)

        # Hoja diligenciada → imagen limpia (escáner) y foto simulada (celular)
        dibujar_pdf(maqueta, tmp / "diligenciada.pdf", marcas=marcas)
        limpia = pdf_a_imagen(tmp / "diligenciada.pdf", escala=150 / 72)  # 150 DPI
        casos = {
            # nombre del caso: (imagen, plantilla que le corresponde)
            "escaneo": (limpia, "template.json"),
            "foto": (simular_foto(limpia, args.semilla), "template_fotos.json"),
        }

        todo_bien = True
        total = len(maqueta.etiquetas_preguntas)
        for caso, (imagen, plantilla) in casos.items():
            # Cada caso en su propia carpeta, con su plantilla llamada template.json
            entrada, salida = tmp / caso / "entrada", tmp / caso / "salida"
            entrada.mkdir(parents=True)
            guardar_archivos_omr(maqueta, entrada)
            # OMRChecker solo lee "template.json": ponemos ahí la plantilla de este caso
            (entrada / plantilla).replace(entrada / "template.json")
            (entrada / "template_fotos.json").unlink(missing_ok=True)
            cv2.imwrite(str(entrada / f"{caso}.jpg"), imagen)

            comando = args.prefijo.split() + [sys.executable, "main.py",
                                              "-i", str(entrada), "-o", str(salida)]
            proceso = subprocess.run(comando, cwd=args.omrchecker, capture_output=True, text=True)
            if proceso.returncode != 0:
                print(proceso.stdout[-3000:], proceso.stderr[-3000:])
                return 1

            filas = leer_resultados(salida)
            if not filas:
                print(f"{caso:8s} ✘ OMRChecker no pudo procesarla (¿no encontró las 4 marcas?)")
                todo_bien = False
                continue
            fila = filas[0]
            errores = [e for e in maqueta.etiquetas_preguntas
                       if fila.get(e, "") != marcas.get(e, "")]
            doc_ok = fila.get("documento") == esperado_doc
            cod_ok = fila.get("codigo_examen") == esperado_cod
            forma_ok = fila.get("forma", "") == esperada_forma
            print(f"{caso:8s} código {'✔' if cod_ok else '✘'}  forma {'✔' if forma_ok else '✘'}  "
                  f"documento {'✔' if doc_ok else '✘'} ({fila.get('documento')})  "
                  f"preguntas correctas: {total - len(errores)}/{total}")
            for e in errores[:10]:
                print(f"    {e}: esperado '{marcas.get(e, '')}', leído '{fila.get(e)}'")
            todo_bien &= doc_ok and cod_ok and forma_ok and not errores

        if todo_bien:
            print("✔ OMRChecker leyó exactamente lo que se marcó: PDF y template.json coinciden.")
        return 0 if todo_bien else 1


if __name__ == "__main__":
    sys.exit(main())
