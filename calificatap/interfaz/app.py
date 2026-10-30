"""
app.py — Ventana principal de CalificaTAP.

Tiene un encabezado y cinco pestañas:
    1. Crear hoja     (Módulo 1: generador de la hoja de respuestas)
    2. Cuadernillos   (Módulo 0: banco de preguntas → cuadernillos por forma y claves)
    3. Leer hojas     (Módulo 2: lector con OMRChecker)
    4. Resultados     (Módulo 3: calificación, gráficos y Excel)
    5. Seguimiento    (compara varios exámenes: ¿el curso mejora?)
"""

from __future__ import annotations

import sys
import tkinter as tk
from pathlib import Path
from tkinter import ttk

from . import estilos
from .pestana_cuadernillos import PestanaCuadernillos
from .pestana_generador import PestanaGenerador
from .pestana_lector import PestanaLector
from .pestana_resultados import PestanaResultados
from .pestana_seguimiento import PestanaSeguimiento
from .ventana_compartir import VentanaExportar, importar_con_dialogos

# Carpeta raíz del proyecto (dos niveles arriba de este archivo).
# Se calcula así, y no con la carpeta actual, porque al abrir el programa con
# doble clic la "carpeta actual" puede ser cualquiera.
RAIZ_PROYECTO = Path(__file__).resolve().parents[2]


def _nitidez_en_windows() -> None:
    """En pantallas con escala (125 %, 150 %) Windows ve borrosas las ventanas
    de tkinter. Esta línea le pide a Windows que las dibuje nítidas."""
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            pass


class AplicacionCalificaTAP(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("CalificaTAP — Calificación automática de hojas de respuestas")
        self.geometry("1280x820")
        self.minsize(1000, 640)
        estilos.aplicar_estilos(self)

        # Encabezado verde
        encabezado = ttk.Frame(self, style="Encabezado.TFrame", padding=(18, 10))
        encabezado.pack(fill="x")
        ttk.Label(encabezado, text="CalificaTAP", style="Encabezado.TLabel").pack(side="left")
        ttk.Label(encabezado, style="EncabezadoSub.TLabel",
                  text="   Hojas de respuestas que se califican solas").pack(side="left")
        ttk.Button(encabezado, text="❓ Manual", command=self._abrir_manual).pack(side="right")
        # Menú para pasar exámenes de un computador a otro (o hacer copias de seguridad)
        boton = ttk.Menubutton(encabezado, text="📦 Compartir examen ▾")
        menu = tk.Menu(boton, tearoff=False)
        menu.add_command(label="Exportar un examen (.zip)…",
                         command=lambda: VentanaExportar(self, RAIZ_PROYECTO / "salidas",
                                                         self.var_examen.get()))
        menu.add_command(label="Importar un examen (.zip)…", command=self._importar)
        boton["menu"] = menu
        boton.pack(side="right", padx=8)

        # Pestañas. "var_examen" guarda el examen elegido y la comparten las
        # pestañas 2 y 3, para no tener que elegirlo dos veces.
        self.var_examen = tk.StringVar()
        self.pestanas = ttk.Notebook(self)
        self.pestanas.pack(fill="both", expand=True, pady=(6, 0))

        self.generador = PestanaGenerador(self.pestanas, RAIZ_PROYECTO,
                                          al_generar=self._examen_generado)
        self.cuadernillos = PestanaCuadernillos(self.pestanas, RAIZ_PROYECTO, self.var_examen)
        self.lector = PestanaLector(self.pestanas, RAIZ_PROYECTO, self.var_examen)
        self.resultados = PestanaResultados(self.pestanas, RAIZ_PROYECTO, self.var_examen)
        self.seguimiento = PestanaSeguimiento(self.pestanas, RAIZ_PROYECTO, self.var_examen)
        self.pestanas.add(self.generador, text="  1. Crear hoja  ")
        self.pestanas.add(self.cuadernillos, text="  2. Cuadernillos  ")
        self.pestanas.add(self.lector, text="  3. Leer hojas  ")
        self.pestanas.add(self.resultados, text="  4. Resultados  ")
        self.pestanas.add(self.seguimiento, text="  5. Seguimiento  ")
        self.pestanas.bind("<<NotebookTabChanged>>", lambda e: self._cambio_de_pestana())

        # Al cerrar, recordar lo que había en pantalla
        self.protocol("WM_DELETE_WINDOW", self._al_cerrar)

    def _cambio_de_pestana(self) -> None:
        """Al abrir una pestaña, se actualiza (por si hay exámenes u hojas nuevas)."""
        actual = self.nametowidget(self.pestanas.select())
        if hasattr(actual, "al_mostrar"):
            actual.al_mostrar()

    def _examen_generado(self, carpeta: Path) -> None:
        """Cuando se genera una hoja, ese examen queda elegido en las pestañas 2 y 3."""
        self.var_examen.set(carpeta.name)

    def _importar(self) -> None:
        carpeta = importar_con_dialogos(self, RAIZ_PROYECTO / "salidas")
        if carpeta:
            self.var_examen.set(carpeta.name)     # queda elegido en las pestañas 2, 3 y 4
            self._cambio_de_pestana()

    def _abrir_manual(self) -> None:
        """Abre el manual para docentes (PDF en la carpeta del programa)."""
        from tkinter import messagebox
        from .utilidades import abrir_con_el_sistema
        manual = RAIZ_PROYECTO / "Manual CalificaTAP.pdf"
        if manual.exists():
            abrir_con_el_sistema(manual)
        else:
            messagebox.showinfo("Manual", "No se encontró «Manual CalificaTAP.pdf» en la carpeta "
                                "del programa.", parent=self)

    def _al_cerrar(self) -> None:
        self.generador.guardar_sesion()
        self.destroy()


def main() -> None:
    _nitidez_en_windows()
    app = AplicacionCalificaTAP()
    app.mainloop()


if __name__ == "__main__":
    main()
