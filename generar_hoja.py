"""
generar_hoja.py — Punto de entrada del Módulo 1.

Uso (desde la carpeta del proyecto):

    python generar_hoja.py configuracion/examen_ejemplo.json

Opciones:
    --salidas CARPETA     dónde guardar los archivos (por defecto: salidas)
    --sin-verificar       no generar la imagen de verificación
"""

import argparse
import sys

from calificatap.generador import generar_hoja
from calificatap.generador.configuracion import ErrorDeConfiguracion
from calificatap.generador.maquetador import ErrorDeMaquetacion


def main() -> int:
    # En algunas consolas de Windows los símbolos ✔ y ✘ fallan; forzamos UTF-8
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="Genera la hoja de respuestas y su template.json")
    parser.add_argument("config", help="archivo JSON con la configuración del examen")
    parser.add_argument("--salidas", default="salidas", help="carpeta de salida")
    parser.add_argument("--sin-verificar", action="store_true", help="omitir la verificación")
    args = parser.parse_args()

    try:
        generar_hoja(args.config, args.salidas, verificar_resultado=not args.sin_verificar)
    except (ErrorDeConfiguracion, ErrorDeMaquetacion) as error:
        # Errores "esperados": mostramos solo el mensaje, sin el rastro técnico
        print(f"✘ {error}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
