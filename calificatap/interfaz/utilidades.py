"""
utilidades.py — Piezas reutilizables de la interfaz.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
import tkinter as tk
import unicodedata
from pathlib import Path
from tkinter import ttk

from . import estilos


class MarcoDesplazable(ttk.Frame):
    """
    Un marco con barra de desplazamiento vertical.
    Todo lo que se ponga dentro de `self.interior` se puede desplazar
    con la rueda del ratón cuando no cabe en la ventana.

    Truco: tkinter no tiene un "Frame con scroll", así que se mete un Frame
    dentro de un Canvas (que sí se puede desplazar).
    """

    def __init__(self, padre, **kwargs):
        super().__init__(padre, **kwargs)
        self.lienzo = tk.Canvas(self, bg=estilos.FONDO, highlightthickness=0)
        barra = ttk.Scrollbar(self, orient="vertical", command=self.lienzo.yview)
        self.lienzo.configure(yscrollcommand=barra.set)
        self.interior = ttk.Frame(self.lienzo)
        self._ventana = self.lienzo.create_window((0, 0), window=self.interior, anchor="nw")

        self.lienzo.pack(side="left", fill="both", expand=True)
        barra.pack(side="right", fill="y")

        # Cuando cambia el tamaño del contenido, se actualiza la zona desplazable
        self.interior.bind("<Configure>", lambda e: self.lienzo.configure(
            scrollregion=self.lienzo.bbox("all")))
        # El contenido ocupa todo el ancho disponible
        self.lienzo.bind("<Configure>", lambda e: self.lienzo.itemconfigure(
            self._ventana, width=e.width))
        # La rueda del ratón solo actúa mientras el puntero está encima
        self.bind("<Enter>", lambda e: self._activar_rueda(True))
        self.bind("<Leave>", lambda e: self._activar_rueda(False))

    def _activar_rueda(self, activar: bool) -> None:
        if activar:
            self.bind_all("<MouseWheel>", self._rueda)              # Windows y Mac
            self.bind_all("<Button-4>", lambda e: self.lienzo.yview_scroll(-1, "units"))  # Linux
            self.bind_all("<Button-5>", lambda e: self.lienzo.yview_scroll(1, "units"))
        else:
            for evento in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
                self.unbind_all(evento)

    def _rueda(self, evento) -> None:
        # Solo desplazar si el contenido es más alto que la ventana
        if self.interior.winfo_height() > self.lienzo.winfo_height():
            paso = -1 if evento.delta > 0 else 1   # rueda hacia arriba → subir
            self.lienzo.yview_scroll(paso * 2, "units")


def abrir_con_el_sistema(ruta: str | Path) -> None:
    """Abre un archivo o carpeta con el programa predeterminado (lector de PDF, explorador...)."""
    ruta = str(ruta)
    if sys.platform == "win32":
        os.startfile(ruta)  # noqa: S606 — solo existe en Windows
    elif sys.platform == "darwin":
        subprocess.Popen(["open", ruta])
    else:
        subprocess.Popen(["xdg-open", ruta])


def sugerir_codigo(nombre: str, codigos_usados: set[str]) -> str:
    """
    Propone un código corto para una materia a partir de su nombre:
        "Matemáticas" → "MAT",  "Ciencias Naturales" → "CIE"
    Si ya existe, le agrega un número: "MAT2", "MAT3"...
    """
    sin_tildes = unicodedata.normalize("NFKD", nombre).encode("ascii", "ignore").decode()
    letras = re.sub(r"[^A-Za-z]", "", sin_tildes).upper()
    base = (letras[:3] or "MAT")
    codigo, n = base, 2
    while codigo in codigos_usados:
        codigo, n = f"{base}{n}", n + 1
    return codigo


class VisorImagen(tk.Canvas):
    """
    Muestra una imagen ajustada al espacio disponible.
    - Rueda del ratón: acercar / alejar.
    - Arrastrar con el ratón: mover la imagen.
    - Doble clic: volver a ajustar.
    """

    def __init__(self, padre, **kwargs):
        super().__init__(padre, bg=estilos.FONDO_VISTA_PREVIA, highlightthickness=0, **kwargs)
        self._original = None      # imagen PIL completa
        self._foto = None          # versión que se está mostrando (ImageTk)
        self._zoom = None          # None = ajustar a la ventana
        self._mensaje = ""
        self.bind("<Configure>", lambda e: self._dibujar())
        self.bind("<MouseWheel>", lambda e: self._acercar(1.2 if e.delta > 0 else 1 / 1.2, e))
        self.bind("<Button-4>", lambda e: self._acercar(1.2, e))
        self.bind("<Button-5>", lambda e: self._acercar(1 / 1.2, e))
        self.bind("<ButtonPress-1>", lambda e: self.scan_mark(e.x, e.y))
        self.bind("<B1-Motion>", lambda e: self.scan_dragto(e.x, e.y, gain=1))
        self.bind("<Double-Button-1>", lambda e: self.ajustar())

    def mostrar(self, ruta: str | Path | None, mensaje: str = "") -> None:
        from PIL import Image
        self._mensaje = mensaje
        self._original = None
        if ruta and Path(ruta).exists():
            self._original = Image.open(ruta)
            self._original.load()
        self.ajustar()

    def ajustar(self) -> None:
        self._zoom = None
        self.xview_moveto(0)
        self.yview_moveto(0)
        self._dibujar()

    def _escala_ajustada(self) -> float:
        ancho, alto = max(self.winfo_width(), 50), max(self.winfo_height(), 50)
        return min(ancho / self._original.width, alto / self._original.height) * 0.97

    def _acercar(self, factor: float, evento) -> None:
        if self._original is None:
            return
        actual = self._zoom or self._escala_ajustada()
        self._zoom = max(0.1, min(actual * factor, 3.0))
        self._dibujar()

    def _dibujar(self) -> None:
        from PIL import ImageTk
        self.delete("all")
        if self._original is None:
            self.create_text(self.winfo_width() // 2, self.winfo_height() // 2,
                             text=self._mensaje or "Seleccione una hoja para verla aquí",
                             fill=estilos.TEXTO_SUAVE, font=(estilos.FAMILIA, 11),
                             justify="center")
            return
        escala = self._zoom or self._escala_ajustada()
        tamano = (max(1, int(self._original.width * escala)),
                  max(1, int(self._original.height * escala)))
        self._foto = ImageTk.PhotoImage(self._original.resize(tamano))
        x = max(self.winfo_width() // 2, tamano[0] // 2)
        self.create_image(x, 6, image=self._foto, anchor="n")
        self.configure(scrollregion=(0, 0, max(tamano[0], self.winfo_width()), tamano[1] + 12))


class SelectorExamen(ttk.Frame):
    """
    Lista desplegable con los exámenes ya generados.
    Comparte la variable 'var_carpeta' con las demás pestañas, así al cambiar
    de pestaña se conserva el examen elegido.
    """

    def __init__(self, padre, carpeta_salidas: Path, var_carpeta: tk.StringVar, al_cambiar):
        from ..examenes import listar_examenes
        super().__init__(padre)
        self._listar = lambda: listar_examenes(carpeta_salidas)
        self.var_carpeta = var_carpeta
        self.al_cambiar = al_cambiar
        self.examenes = []
        ttk.Label(self, text="Examen:", font=(estilos.FAMILIA, 11, "bold")).pack(side="left")
        self.combo = ttk.Combobox(self, state="readonly", width=55)
        self.combo.pack(side="left", padx=8)
        self.combo.bind("<<ComboboxSelected>>", lambda e: self._elegido())
        self.lbl_info = ttk.Label(self, style="Subtitulo.TLabel")
        self.lbl_info.pack(side="left", padx=6)

    def actualizar(self) -> None:
        """Vuelve a buscar los exámenes (por si se generó uno nuevo)."""
        self.examenes = self._listar()
        self.combo.configure(values=[e.nombre_visible for e in self.examenes])
        nombres = [e.carpeta.name for e in self.examenes]
        if self.var_carpeta.get() in nombres:
            self.combo.current(nombres.index(self.var_carpeta.get()))
        elif self.examenes:
            self.combo.current(0)
            self.var_carpeta.set(nombres[0])
        else:
            self.combo.set("(todavía no hay exámenes: créelos en la pestaña 1)")
        self._mostrar_info()

    def _elegido(self) -> None:
        self.var_carpeta.set(self.examenes[self.combo.current()].carpeta.name)
        self._mostrar_info()
        self.al_cambiar()

    def _mostrar_info(self) -> None:
        e = self.examen
        self.lbl_info.configure(
            text=f"{e.total_preguntas} preguntas · {len(e.materias)} materias" if e else "")

    @property
    def examen(self):
        i = self.combo.current()
        return self.examenes[i] if 0 <= i < len(self.examenes) else None


class Tarjeta(tk.Frame):
    """Cuadro con un número grande y un título pequeño (para el tablero de resultados)."""

    def __init__(self, padre, titulo: str):
        super().__init__(padre, bg=estilos.FONDO_PANEL, highlightthickness=1,
                         highlightbackground=estilos.BORDE, padx=10, pady=8)
        tk.Label(self, text=titulo, bg=estilos.FONDO_PANEL, fg=estilos.TEXTO_SUAVE,
                 font=(estilos.FAMILIA, 9)).pack(anchor="w")
        self.lbl_valor = tk.Label(self, text="—", bg=estilos.FONDO_PANEL, fg=estilos.TEXTO,
                                  font=(estilos.FAMILIA, 20, "bold"))
        self.lbl_valor.pack(anchor="w")
        self.lbl_detalle = tk.Label(self, text="", bg=estilos.FONDO_PANEL,
                                    fg=estilos.TEXTO_SUAVE, font=(estilos.FAMILIA, 9))
        self.lbl_detalle.pack(anchor="w")

    def poner(self, valor: str, detalle: str = "", color: str | None = None) -> None:
        self.lbl_valor.configure(text=valor, fg=color or estilos.TEXTO)
        self.lbl_detalle.configure(text=detalle)
