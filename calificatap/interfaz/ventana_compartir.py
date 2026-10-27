"""
ventana_compartir.py — Ventanas para exportar e importar un examen (.zip).
"""

from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from ..compartir import (ErrorAlCompartir, ExamenYaExiste, exportar_examen, importar_examen,
                         leer_info)
from ..examenes import listar_examenes
from . import estilos
from .utilidades import abrir_con_el_sistema


class VentanaExportar(tk.Toplevel):
    """Elegir el examen y qué incluir; luego, dónde guardar el .zip."""

    def __init__(self, padre, carpeta_salidas: Path, carpeta_actual: str = ""):
        super().__init__(padre)
        self.title("Exportar un examen")
        self.configure(bg=estilos.FONDO, padx=18, pady=14)
        self.transient(padre)
        self.resizable(False, False)
        self.examenes = listar_examenes(carpeta_salidas)
        if not self.examenes:
            messagebox.showinfo("Exportar", "Todavía no hay exámenes creados.", parent=padre)
            self.destroy()
            return

        ttk.Label(self, text="Exportar un examen", style="Titulo.TLabel").pack(anchor="w")
        ttk.Label(self, style="Subtitulo.TLabel", wraplength=440, justify="left",
                  text="Se guarda todo el examen en un solo archivo .zip, para pasarlo a otro "
                       "computador (por ejemplo, en una USB) o como copia de seguridad.").pack(
            anchor="w", pady=(0, 10))

        ttk.Label(self, text="Examen:", font=(estilos.FAMILIA, 10, "bold")).pack(anchor="w")
        self.combo = ttk.Combobox(self, state="readonly", width=55,
                                  values=[e.nombre_visible for e in self.examenes])
        nombres = [e.carpeta.name for e in self.examenes]
        self.combo.current(nombres.index(carpeta_actual) if carpeta_actual in nombres else 0)
        self.combo.pack(anchor="w", pady=(2, 10))

        self.var_clave = tk.BooleanVar(value=True)
        self.var_resultados = tk.BooleanVar(value=True)
        ttk.Checkbutton(self, variable=self.var_clave,
                        text="Incluir la clave, la lista de estudiantes y la escala").pack(anchor="w")
        ttk.Checkbutton(self, variable=self.var_resultados,
                        text="Incluir las hojas leídas y los resultados (pesa más, por las imágenes)"
                        ).pack(anchor="w", pady=(2, 0))
        ttk.Label(self, style="Subtitulo.TLabel", wraplength=440, justify="left",
                  text="El diseño de la hoja siempre se incluye: con él, el otro computador "
                       "puede leer las hojas impresas de este examen.").pack(anchor="w", pady=(8, 0))

        botones = ttk.Frame(self)
        botones.pack(fill="x", pady=(14, 0))
        ttk.Button(botones, text="Exportar…", style="Primario.TButton",
                   command=self.exportar).pack(side="right")
        ttk.Button(botones, text="Cancelar", command=self.destroy).pack(side="right", padx=8)
        self.grab_set()

    def exportar(self) -> None:
        examen = self.examenes[self.combo.current()]
        ruta = filedialog.asksaveasfilename(
            parent=self, title="Guardar el examen como", defaultextension=".zip",
            initialfile=f"{examen.carpeta.name}.zip", filetypes=[("Examen de CalificaTAP", "*.zip")])
        if not ruta:
            return
        self.configure(cursor="watch")
        self.update_idletasks()
        try:
            exportar_examen(examen, ruta, self.var_clave.get(), self.var_resultados.get())
        except OSError as error:
            messagebox.showerror("No se pudo exportar", str(error), parent=self)
            return
        finally:
            self.configure(cursor="")
        tamano = Path(ruta).stat().st_size / 1_000_000
        if messagebox.askyesno("Examen exportado",
                               f"Se guardó «{Path(ruta).name}» ({tamano:.1f} MB).\n\n"
                               "En el otro computador use «Compartir examen ▸ Importar».\n\n"
                               "¿Abrir la carpeta donde quedó?", parent=self):
            abrir_con_el_sistema(Path(ruta).parent)
        self.destroy()


def importar_con_dialogos(padre, carpeta_salidas: Path) -> Path | None:
    """Pide el .zip, pregunta qué hacer si el examen ya existe e importa."""
    ruta = filedialog.askopenfilename(parent=padre, title="Importar un examen",
                                      filetypes=[("Examen de CalificaTAP", "*.zip")])
    if not ruta:
        return None
    try:
        info = leer_info(ruta)
        try:
            carpeta, avisos = importar_examen(ruta, carpeta_salidas)
        except ExamenYaExiste:
            respuesta = messagebox.askyesnocancel(
                "El examen ya existe",
                f"Ya tiene un examen «{info['examen']}» (grado {info['grado']}).\n\n"
                "• Sí: reemplazarlo por el del archivo (el actual se guarda en "
                "«salidas/_respaldos»).\n"
                "• No: importarlo como una copia aparte.\n"
                "• Cancelar: no hacer nada.", parent=padre)
            if respuesta is None:
                return None
            carpeta, avisos = importar_examen(ruta, carpeta_salidas,
                                              "reemplazar" if respuesta else "copia")
    except ErrorAlCompartir as error:
        messagebox.showerror("No se pudo importar", str(error), parent=padre)
        return None
    texto = f"Se importó «{info['examen']}» (grado {info['grado']})."
    if avisos:
        texto += "\n\n" + "\n".join(avisos)
    messagebox.showinfo("Examen importado", texto, parent=padre)
    return carpeta
