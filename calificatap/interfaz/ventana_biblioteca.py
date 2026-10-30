"""
ventana_biblioteca.py — Ventanas de la biblioteca de preguntas del colegio.

    VentanaBiblioteca         → buscar preguntas (por materia, grado, tema o texto),
                                verlas como saldrán en el cuadernillo y traerlas al
                                examen (o borrarlas de la biblioteca).
    VentanaGuardarBiblioteca  → guardar en la biblioteca una pregunta, una materia
                                o el examen completo, con su tema y grado.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk

from PIL import Image, ImageTk

from ..cuadernillos.banco import problemas_de_pregunta
from ..cuadernillos.biblioteca import Biblioteca, Entrada
from ..cuadernillos.pdf import vista_previa_suelta
from . import estilos

TODAS = "(todas)"
TODOS = "(todos)"


class VentanaBiblioteca(tk.Toplevel):
    def __init__(self, padre, biblioteca: Biblioteca, materia: str = "", al_elegir=None,
                 destino: str = ""):
        """
        al_elegir(lista_de_entradas): si se pasa, aparece el botón para traerlas al examen.
        destino: texto que explica dónde quedarán (ej. «desde la pregunta 12 de Matemáticas»).
        """
        super().__init__(padre)
        self.title("Biblioteca de preguntas del colegio")
        self.geometry("1180x720")
        self.minsize(950, 560)
        self.configure(bg=estilos.FONDO, padx=12, pady=10)
        self.transient(padre.winfo_toplevel())
        self.biblioteca, self.al_elegir = biblioteca, al_elegir
        self._foto = None
        self._resultados: list[Entrada] = []

        # --- Filtros ---
        filtros = ttk.Frame(self)
        filtros.pack(fill="x")
        self.var_materia = tk.StringVar(value=materia if materia in biblioteca.materias() else TODAS)
        self.var_grado = tk.StringVar(value=TODOS)
        self.var_tema = tk.StringVar(value=TODOS)
        self.var_texto = tk.StringVar()
        for etiqueta, var, valores, ancho in [
                ("Materia:", self.var_materia, [TODAS] + biblioteca.materias(), 22),
                ("Grado:", self.var_grado, [TODOS] + biblioteca.grados(), 7),
                ("Tema:", self.var_tema, [TODOS] + biblioteca.temas(), 22)]:
            ttk.Label(filtros, text=etiqueta).pack(side="left", padx=(0, 4))
            combo = ttk.Combobox(filtros, textvariable=var, values=valores, width=ancho,
                                 state="readonly")
            combo.pack(side="left", padx=(0, 12))
            combo.bind("<<ComboboxSelected>>", lambda e: self._filtrar())
            if var is self.var_tema:
                self.combo_tema = combo
        ttk.Label(filtros, text="Buscar:").pack(side="left", padx=(0, 4))
        entrada = ttk.Entry(filtros, textvariable=self.var_texto, width=24)
        entrada.pack(side="left")
        self.var_texto.trace_add("write", lambda *_: self._filtrar())

        # --- Botones (abajo) ---
        abajo = ttk.Frame(self)
        abajo.pack(side="bottom", fill="x", pady=(8, 0))
        self.lbl_cuenta = ttk.Label(abajo, style="Subtitulo.TLabel")
        self.lbl_cuenta.pack(side="left")
        ttk.Button(abajo, text="Cerrar", command=self.destroy).pack(side="right")
        if al_elegir:
            ttk.Button(abajo, text="Traer al examen", style="Primario.TButton",
                       command=self.traer).pack(side="right", padx=8)
        ttk.Button(abajo, text="Borrar de la biblioteca", command=self.borrar).pack(side="right")
        if destino:
            ttk.Label(self, style="Subtitulo.TLabel", text=destino).pack(side="bottom", anchor="w")

        # --- Lista y vista previa ---
        division = ttk.PanedWindow(self, orient="horizontal")
        division.pack(fill="both", expand=True, pady=(8, 0))
        marco = ttk.Frame(division)
        division.add(marco, weight=1)
        columnas = ("materia", "grado", "tema", "pregunta", "usada")
        self.tabla = ttk.Treeview(marco, columns=columnas, show="headings", selectmode="extended")
        for col, titulo, ancho in [("materia", "Materia", 120), ("grado", "Grado", 50),
                                   ("tema", "Tema", 130), ("pregunta", "Pregunta", 330),
                                   ("usada", "Usada en", 140)]:
            self.tabla.heading(col, text=titulo)
            self.tabla.column(col, width=ancho, minwidth=40, stretch=col == "pregunta")
        barra = ttk.Scrollbar(marco, orient="vertical", command=self.tabla.yview)
        self.tabla.configure(yscrollcommand=barra.set)
        self.tabla.pack(side="left", fill="both", expand=True)
        barra.pack(side="left", fill="y")
        self.tabla.bind("<<TreeviewSelect>>", lambda e: self._mostrar())
        self.tabla.bind("<Double-Button-1>", lambda e: self.traer() if al_elegir else None)

        derecha = tk.Frame(division, bg="white", highlightthickness=1,
                           highlightbackground=estilos.BORDE, width=440)
        division.add(derecha, weight=0)
        derecha.pack_propagate(False)
        self.lbl_vista = tk.Label(derecha, bg="white", anchor="n", justify="left",
                                  wraplength=400, fg=estilos.TEXTO_SUAVE,
                                  text="Elija una pregunta para verla.")
        self.lbl_vista.pack(fill="both", expand=True, padx=6, pady=6)

        self._filtrar()
        self.grab_set()

    # ----------------------------------------------------------------------
    def _filtrar(self) -> None:
        materia = "" if self.var_materia.get() == TODAS else self.var_materia.get()
        self.combo_tema.configure(values=[TODOS] + self.biblioteca.temas(materia or None))
        self._resultados = self.biblioteca.buscar(
            materia, "" if self.var_grado.get() == TODOS else self.var_grado.get(),
            "" if self.var_tema.get() == TODOS else self.var_tema.get(), self.var_texto.get())
        self.tabla.delete(*self.tabla.get_children())
        for e in self._resultados:
            resumen = " ".join(e.enunciado.split())[:80] or "(imagen)"
            if e.contexto:
                resumen = "📄 " + resumen               # tiene texto compartido
            self.tabla.insert("", "end", iid=e.id, values=(
                e.materia, e.grado, e.tema or "—", resumen, ", ".join(e.usada_en[-2:]) or "—"))
        total = len(self.biblioteca.entradas)
        self.lbl_cuenta.configure(
            text=f"{len(self._resultados)} de {total} preguntas · Ctrl o Shift para elegir varias · "
                 "📄 = tiene texto compartido" if total else
            "La biblioteca está vacía. En el editor de preguntas use «📚 Guardar en la biblioteca».")

    def _elegidas(self) -> list[Entrada]:
        return [self.biblioteca.entradas[i] for i in self.tabla.selection()
                if i in self.biblioteca.entradas]

    def _mostrar(self) -> None:
        elegidas = self._elegidas()
        if not elegidas:
            return
        e = elegidas[0]
        p, contexto = self.biblioteca.a_pregunta(e, "X_01")
        imagen = vista_previa_suelta(p, 1, contexto)
        if imagen is None:
            self.lbl_vista.configure(image="", text="(no se pudo dibujar)")
            return
        ancho = max(200, self.lbl_vista.winfo_width() - 6)
        if imagen.width > ancho:
            imagen = imagen.resize((ancho, int(imagen.height * ancho / imagen.width)), Image.LANCZOS)
        self._foto = ImageTk.PhotoImage(imagen)
        self.lbl_vista.configure(image=self._foto, text="")

    def traer(self) -> None:
        elegidas = self._elegidas()
        if not elegidas:
            messagebox.showinfo("Biblioteca", "Elija una o varias preguntas.", parent=self)
            return
        # Las que comparten un texto van siempre juntas
        lista, vistos = [], set()
        for e in self._resultados:                      # en el orden de la lista
            if e in elegidas:
                for otra in self.biblioteca.del_mismo_texto(e):
                    if otra.id not in vistos:
                        vistos.add(otra.id)
                        lista.append(otra)
        if self.al_elegir(lista):
            self.destroy()

    def borrar(self) -> None:
        elegidas = self._elegidas()
        if not elegidas:
            return
        if not messagebox.askyesno("Borrar", f"¿Borrar {len(elegidas)} pregunta(s) de la "
                                   "biblioteca? (No se borran de los exámenes donde ya están.)",
                                   parent=self):
            return
        self.biblioteca.eliminar([e.id for e in elegidas])
        self.biblioteca.guardar()
        self._filtrar()


class VentanaGuardarBiblioteca(tk.Toplevel):
    """Guardar preguntas del examen en la biblioteca (con tema y grado)."""

    def __init__(self, padre, biblioteca: Biblioteca, examen, banco, etiqueta_actual: str):
        super().__init__(padre)
        self.title("Guardar en la biblioteca")
        self.configure(bg=estilos.FONDO, padx=16, pady=12)
        self.transient(padre.winfo_toplevel())
        self.biblioteca, self.examen, self.banco = biblioteca, examen, banco
        materias = {m.codigo: m for m in examen.materias}
        self.materia = materias[etiqueta_actual.split("_")[0]]
        numeros = examen.numeros_impresos()

        def listas(etiquetas):
            return [e for e in etiquetas if not problemas_de_pregunta(
                banco.preguntas[e], materias[e.split("_")[0]], banco.contextos)]
        self.opciones = {
            "una": [etiqueta_actual] if listas([etiqueta_actual]) else [],
            "materia": listas(self.materia.etiquetas()),
            "todo": listas(examen.todas_las_etiquetas()),
        }
        ttk.Label(self, text="¿Qué preguntas guardar?", font=(estilos.FAMILIA, 11, "bold")).pack(
            anchor="w")
        self.var_alcance = tk.StringVar(value="una" if self.opciones["una"] else "materia")
        for clave, texto in [
                ("una", f"Solo la pregunta {numeros[etiqueta_actual]}"),
                ("materia", f"Las preguntas listas de {self.materia.nombre} "
                            f"({len(self.opciones['materia'])})"),
                ("todo", f"Todas las preguntas listas del examen ({len(self.opciones['todo'])})")]:
            boton = ttk.Radiobutton(self, text=texto, value=clave, variable=self.var_alcance,
                                    command=self._alcance_cambio)
            boton.pack(anchor="w", pady=1)
            if not self.opciones[clave]:
                boton.state(["disabled"])
        cuadro = ttk.Frame(self)
        cuadro.pack(fill="x", pady=(10, 0))
        ttk.Label(cuadro, text="Tema:").grid(row=0, column=0, sticky="w")
        self.var_tema = tk.StringVar()
        self.combo_tema = ttk.Combobox(cuadro, textvariable=self.var_tema, width=34,
                                       values=biblioteca.temas(self.materia.nombre))
        self.combo_tema.grid(row=0, column=1, sticky="w", padx=6, pady=2)
        ttk.Label(cuadro, text="Grado:").grid(row=1, column=0, sticky="w")
        self.var_grado = tk.StringVar(value=examen.grado)
        ttk.Entry(cuadro, textvariable=self.var_grado, width=8).grid(row=1, column=1, sticky="w",
                                                                    padx=6, pady=2)
        ttk.Label(self, style="Ayuda.TLabel", wraplength=420, justify="left",
                  text="El tema es opcional (ej. «Fracciones», «Lectura inferencial») y sirve "
                       "para encontrarlas después. Solo se guardan las preguntas completas; las "
                       "repetidas no se duplican.").pack(anchor="w", pady=(6, 0))
        fila = ttk.Frame(self)
        fila.pack(fill="x", pady=(12, 0))
        ttk.Button(fila, text="Guardar", style="Primario.TButton",
                   command=self.guardar).pack(side="right")
        ttk.Button(fila, text="Cancelar", command=self.destroy).pack(side="right", padx=6)
        self._alcance_cambio()
        self.grab_set()

    def _alcance_cambio(self) -> None:
        # Con el examen completo, el tema se deja vacío (cada materia tiene los suyos)
        if self.var_alcance.get() == "todo":
            self.combo_tema.state(["disabled"])
        else:
            self.combo_tema.state(["!disabled"])

    def guardar(self) -> None:
        etiquetas = self.opciones[self.var_alcance.get()]
        if not etiquetas:
            return
        materias = {m.codigo: m for m in self.examen.materias}
        tema = "" if self.var_alcance.get() == "todo" else self.var_tema.get().strip()
        nuevas = 0
        for e in etiquetas:
            p = self.banco.preguntas[e]
            contexto = self.banco.contextos.get(p.contexto) if p.contexto else None
            _, es_nueva = self.biblioteca.agregar(
                p, materias[e.split("_")[0]].nombre, self.var_grado.get().strip(), tema,
                self.examen.nombre_visible, contexto)
            nuevas += es_nueva
        try:
            self.biblioteca.guardar()
        except OSError as error:
            messagebox.showerror("Biblioteca", f"No se pudo guardar: {error}", parent=self)
            return
        repetidas = len(etiquetas) - nuevas
        messagebox.showinfo("Biblioteca", f"Se guardaron {nuevas} pregunta(s) en la biblioteca."
                            + (f"\n{repetidas} ya estaban." if repetidas else ""), parent=self)
        self.destroy()
