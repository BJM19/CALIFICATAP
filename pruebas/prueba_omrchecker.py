"""
prueba_omrchecker.py — Prueba de extremo a extremo del Módulo 1.

¿Qué hace?
    1. Genera la hoja a partir de un JSON de configuración.
    2. "Simula a un estudiante": rellena respuestas al azar (con algunas en blanco)
       y un número de documento, usando la MISMA maqueta.
    3. Convierte esa hoja en imagen de dos formas:
         - escaneo: derecha y limpia
         - torcido: girada un poco y con algo de ruido (la hoja entró torcida al escáner)
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
            if bloque.nombre in ("Documento", "Lista") or azar.random() > prob_blanco:
                marcas[etiqueta] = azar.choice(bloque.valores)
    return marcas


def simular_escaneo_torcido(imagen: np.ndarray, semilla: int) -> np.ndarray:
    """Gira un poco la hoja y le agrega ruido, como si entrara torcida al escáner."""
    azar = np.random.default_rng(semilla)
    h, w = imagen.shape
    angulo = azar.uniform(1.0, 2.0) * azar.choice([-1, 1])        # grados
    matriz = cv2.getRotationMatrix2D((w / 2, h / 2), angulo, 1.0)
    torcida = cv2.warpAffine(imagen, matriz, (w, h), borderValue=255)
    torcida = torcida.astype(np.float32) + azar.normal(0, 4, torcida.shape)
    return np.clip(torcida, 0, 255).astype(np.uint8)


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

        # Hoja diligenciada → imagen limpia y otra torcida (las dos, como de escáner)
        dibujar_pdf(maqueta, tmp / "diligenciada.pdf", marcas=marcas)
        limpia = pdf_a_imagen(tmp / "diligenciada.pdf", escala=150 / 72)  # 150 DPI
        casos = {
            "escaneo": limpia,
            "torcido": simular_escaneo_torcido(limpia, args.semilla),
        }

        todo_bien = True
        total = len(maqueta.etiquetas_preguntas)
        for caso, imagen in casos.items():
            # Cada caso en su propia carpeta, con template.json, config.json y la marca
            entrada, salida = tmp / caso / "entrada", tmp / caso / "salida"
            entrada.mkdir(parents=True)
            guardar_archivos_omr(maqueta, entrada)
            (entrada / "template_identificar.json").unlink(missing_ok=True)
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
