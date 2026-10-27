"""
ventana_importar.py — Ventana para importar la lista de estudiantes (Excel o CSV).

La usan dos pantallas:
    - "Crear hoja": para imprimir hojas con el nombre de cada estudiante.
    - "Resultados": para ver nombres y saber quién no entregó hoja.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from ..reportes.estudiantes import adivinar_columnas, leer_tabla, lista_limpia
from . import estilos


def importar_lista(padre, al_aceptar) -> None:
    """Pide el archivo y abre la ventana para elegir las columnas.
    Cuando el docente acepta, llama al_aceptar(lista) con un DataFrame limpio
    (columnas: documento, nombre, curso)."""
    ruta = filedialog.askopenfilename(
        parent=padre, title="Elegir la lista de estudiantes",
        filetypes=[("Excel o CSV", "*.xlsx *.xls *.csv *.txt"), ("Todos", "*.*")])
    if not ruta:
        return
    try:
        tabla = leer_tabla(ruta)
    except Exception as error:
        messagebox.showerror("No se pudo abrir", f"No se pudo leer el archivo.\n\n{error}",
                             parent=padre)
        return
    VentanaImportar(padre, tabla, al_aceptar)


class VentanaImportar(tk.Toplevel):
    """Muestra el archivo importado y deja elegir qué columna es cada cosa."""

    def __init__(self, padre, tabla, al_aceptar):
        super().__init__(padre)
        self.title("Importar lista de estudiantes")
        self.configure(bg=estilos.FONDO, padx=14, pady=12)
        self.transient(padre.winfo_toplevel())
        self.tabla, self.al_aceptar = tabla, al_aceptar

        ttk.Label(self, text=f"Se encontraron {len(tabla)} filas. Así se ve el archivo:",
                  font=(estilos.FAMILIA, 11, "bold")).pack(anchor="w")
        vista = ttk.Treeview(self, columns=list(tabla.columns), show="headings", height=6)
        for c in tabla.columns:
            vista.heading(c, text=c)
            vista.column(c, width=140)
        for _, fila in tabla.head(6).iterrows():
            vista.insert("", "end", values=list(fila))
        vista.pack(fill="x", pady=8)

        ttk.Label(self, text="¿Qué columna es cada cosa?",
                  font=(estilos.FAMILIA, 10, "bold")).pack(anchor="w", pady=(6, 2))
        adivinadas = adivinar_columnas(tabla)
        opciones = list(tabla.columns)
        caja = ttk.Frame(self)
        caja.pack(fill="x")
        self.vars = {}
        for i, (campo, texto) in enumerate([("documento", "Documento"), ("nombre", "Nombre"),
                                            ("curso", "Curso (opcional)")]):
            ttk.Label(caja, text=texto + ":").grid(row=i, column=0, sticky="w", pady=3)
            var = tk.StringVar(value=adivinadas.get(campo) or "")
            ttk.Combobox(caja, textvariable=var, state="readonly", width=35,
                         values=([""] if campo == "curso" else []) + opciones).grid(
                row=i, column=1, sticky="w", padx=8)
            self.vars[campo] = var

        ttk.Button(self, text="Importar", style="Primario.TButton",
                   command=self.aceptar).pack(anchor="e", pady=(12, 0))
        self.grab_set()

    def aceptar(self) -> None:
        doc, nombre = self.vars["documento"].get(), self.vars["nombre"].get()
        if not doc or not nombre:
            messagebox.showwarning("Faltan columnas", "Elija la columna del documento y la del nombre.",
                                   parent=self)
            return
        lista = lista_limpia(self.tabla, doc, nombre, self.vars["curso"].get() or None)
        self.al_aceptar(lista)
        self.destroy()
