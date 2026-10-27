"""
crear_hojas_de_prueba.py — Inventa un curso completo para practicar sin imprimir.
(Lo mismo que el botón «Hojas de práctica» de la pestaña «Leer hojas».)

Uso:
    python pruebas/crear_hojas_de_prueba.py                 (usa el examen más reciente)
    python pruebas/crear_hojas_de_prueba.py --estudiantes 30 --sin-nombre
"""

import argparse
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from calificatap.examenes import listar_examenes  # noqa: E402
from calificatap.lector.practica import crear_curso_de_practica  # noqa: E402


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser()
    parser.add_argument("--estudiantes", type=int, default=24)
    parser.add_argument("--fotos", type=int, default=3, help="cuántas hojas van como foto")
    parser.add_argument("--semilla", type=int, default=11)
    parser.add_argument("--sin-nombre", action="store_true",
                        help="hojas en blanco (sin nombre ni documento impresos)")
    args = parser.parse_args()

    examenes = listar_examenes(RAIZ / "salidas")
    if not examenes:
        print("Primero genere una hoja de respuestas.")
        return 1
    examen = examenes[0]
    destino, _, _ = crear_curso_de_practica(examen, RAIZ / "escaneos" / f"practica_{examen.carpeta.name}",
                                      args.estudiantes, args.fotos, not args.sin_nombre, args.semilla)
    print(f"✔ Curso de práctica creado en: {destino}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
