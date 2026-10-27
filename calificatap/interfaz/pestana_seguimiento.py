"""
pestana_seguimiento.py — Pantalla "Seguimiento": compara varios exámenes.

    ┌───────────────────────────┬──────────────────────────────────────────┐
    │ Grado: [11 ▼]             │ ┌ Curso │ Estudiantes ┐                  │
    │ Exámenes a comparar:      │ │  gráfico de líneas: promedio general │ │
    │  ☑ Simulacro 1 (marzo)    │ │  y por materia en cada examen        │ │
    │  ☑ Simulacro 2 (junio)    │ │  tabla con los números               │ │
    │  ☑ Simulacro 3 (sept.)    │ └──────────────────────────────────────┘ │
    │ [Exportar a Excel]        │                                          │
    └───────────────────────────┴──────────────────────────────────────────┘

Solo aparecen los exámenes que ya tienen hojas leídas y clave.
"""

from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk

import pandas as pd
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

from ..examenes import listar_examenes
from ..reportes.seguimiento import construir_seguimiento, etiqueta_corta
from . import estilos
from .utilidades import abrir_con_el_sistema

# Colores para las materias (paleta categórica validada para daltonismo, en orden fijo)
COLORES_MATERIAS = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300",
                    "#4a3aa7", "#e34948"]
COLOR_GENERAL = "#1D2522"


class PestanaSeguimiento(ttk.Frame):
    def __init__(self, padre, raiz_proyecto: Path, var_examen: tk.StringVar):
        super().__init__(padre)
        self.raiz = raiz_proyecto
        self.var_examen = var_examen
        self.examenes = []          # exámenes con resultados (los de la lista)
        self.seguimiento = None
        self._orden = (None, False)
        self._construir()

    # ======================================================================
    # Construcción
    # ======================================================================
    def _construir(self) -> None:
        division = ttk.PanedWindow(self, orient="horizontal")
        division.pack(fill="both", expand=True)
        izquierda = ttk.Frame(division, padding=(14, 10, 6, 10))
        derecha = ttk.Frame(division, padding=(6, 10, 14, 10))
        division.add(izquierda, weight=0)
        division.add(derecha, weight=1)

        ttk.Label(izquierda, text="Seguimiento", style="Titulo.TLabel").pack(anchor="w")
        ttk.Label(izquierda, style="Subtitulo.TLabel", wraplength=330, justify="left",
                  text="Compare varios exámenes del mismo curso para ver si mejora, "
                       "en general y en cada materia.").pack(anchor="w", pady=(0, 10))

        fila = ttk.Frame(izquierda)
        fila.pack(fill="x")
        ttk.Label(fila, text="Grado:", font=(estilos.FAMILIA, 10, "bold")).pack(side="left")
        self.var_grado = tk.StringVar(value="Todos")
        self.combo_grado = ttk.Combobox(fila, textvariable=self.var_grado, state="readonly", width=10)
        self.combo_grado.pack(side="left", padx=8)
        self.combo_grado.bind("<<ComboboxSelected>>", lambda e: self._llenar_lista())

        ttk.Label(izquierda, text="Exámenes a comparar:",
                  font=(estilos.FAMILIA, 10, "bold")).pack(anchor="w", pady=(12, 4))
        self.lista = tk.Listbox(izquierda, selectmode="multiple", height=10, width=44,
                                activestyle="none", exportselection=False,
                                selectbackground=estilos.VERDE_CLARO,
                                selectforeground=estilos.TEXTO, relief="flat",
                                highlightthickness=1, highlightbackground=estilos.BORDE)
        self.lista.pack(fill="x")
        self.lista.bind("<<ListboxSelect>>", lambda e: self._programar())
        ttk.Label(izquierda, style="Subtitulo.TLabel", wraplength=330, justify="left",
                  text="Clic para marcar o desmarcar. Solo aparecen los exámenes que ya "
                       "tienen hojas leídas y clave.").pack(anchor="w", pady=(4, 0))
        botones = ttk.Frame(izquierda)
        botones.pack(fill="x", pady=6)
        ttk.Button(botones, text="Todos", style="Pequeno.TButton",
                   command=lambda: (self.lista.select_set(0, "end"), self._programar())).pack(side="left")
        ttk.Button(botones, text="Ninguno", style="Pequeno.TButton",
                   command=lambda: (self.lista.select_clear(0, "end"), self._programar())).pack(
            side="left", padx=6)

        ttk.Button(izquierda, text="📊 Exportar a Excel", style="Primario.TButton",
                   command=self.exportar).pack(anchor="w", pady=(16, 0))

        self.lbl_aviso = ttk.Label(derecha, style="Subtitulo.TLabel")
        self.lbl_aviso.pack(anchor="w")
        self.pestanas = ttk.Notebook(derecha)
        self.pestanas.pack(fill="both", expand=True, pady=(6, 0))

        # --- Curso ---
        pagina = ttk.Frame(self.pestanas, padding=6)
        self.pestanas.add(pagina, text="  Curso  ")
        self.fig_curso = Figure(figsize=(6, 3.3), dpi=96)
        self.lienzo_curso = FigureCanvasTkAgg(self.fig_curso, master=pagina)
        self.lienzo_curso.get_tk_widget().pack(fill="both", expand=True)
        self.marco_tabla_curso = ttk.Frame(pagina)
        self.marco_tabla_curso.pack(fill="x", pady=(6, 0))

        # --- Estudiantes ---
        pagina = ttk.Frame(self.pestanas, padding=6)
        self.pestanas.add(pagina, text="  Estudiantes  ")
        self.marco_tabla_est = ttk.Frame(pagina)
        self.marco_tabla_est.pack(fill="both", expand=True)
        self.lbl_estudiante = ttk.Label(pagina, style="Subtitulo.TLabel",
                                        text="Seleccione un estudiante para ver su evolución.")
        self.lbl_estudiante.pack(anchor="w", pady=(6, 0))
        self.fig_est = Figure(figsize=(6, 2.4), dpi=96)
        self.lienzo_est = FigureCanvasTkAgg(self.fig_est, master=pagina)
        self.lienzo_est.get_tk_widget().pack(fill="x")
        self.tabla_est = None

    # ======================================================================
    # Lista de exámenes
    # ======================================================================
    def al_mostrar(self) -> None:
        """Al abrir la pestaña: busca los exámenes que ya tienen resultados."""
        todos = listar_examenes(self.raiz / "salidas")
        self.todos = [e for e in todos
                      if e.archivo_respuestas.exists() and e.archivo_clave.exists()]
        self.todos.sort(key=lambda e: e.creado)
        grados = sorted({e.grado for e in self.todos}, key=lambda g: (len(g), g))
        self.combo_grado.configure(values=["Todos"] + grados)
        # Por defecto, el grado del examen que se está trabajando en las otras pestañas
        actual = next((e for e in self.todos if e.carpeta.name == self.var_examen.get()), None)
        if actual and self.var_grado.get() == "Todos":
            self.var_grado.set(actual.grado)
        self._llenar_lista()

    def _llenar_lista(self) -> None:
        grado = self.var_grado.get()
        self.examenes = [e for e in self.todos if grado == "Todos" or e.grado == grado]
        self.lista.delete(0, "end")
        for e in self.examenes:
            self.lista.insert("end", f"  {etiqueta_corta(e)} · Grado {e.grado}")
        self.lista.select_set(0, "end")       # todos marcados al empezar
        self._programar()

    def _programar(self) -> None:
        if getattr(self, "_id", None):
            self.after_cancel(self._id)
        self._id = self.after(300, self.actualizar)

    # ======================================================================
    # Calcular y mostrar
    # ======================================================================
    def actualizar(self) -> None:
        self._id = None
        elegidos = [self.examenes[i] for i in self.lista.curselection()]
        if not self.todos:
            self._aviso("Todavía no hay exámenes con hojas leídas y clave.")
            self.seguimiento = None
            self._limpiar()
            return
        if not elegidos:
            self._aviso("Marque a la izquierda los exámenes que quiere comparar.")
            self.seguimiento = None
            self._limpiar()
            return
        self.winfo_toplevel().configure(cursor="watch")
        self.update_idletasks()
        try:
            self.seguimiento = construir_seguimiento(elegidos)
        finally:
            self.winfo_toplevel().configure(cursor="")
        s = self.seguimiento
        if len(s.examenes) < 2:
            self._aviso("Con un solo examen no hay con qué comparar: marque al menos dos.")
        else:
            self._aviso(f"Comparando {len(s.examenes)} exámenes, del más antiguo al más reciente.")
        self._dibujar_curso(s)
        self._tabla_curso(s)
        self._tabla_estudiantes(s)
        self._dibujar_estudiante(None)

    def _aviso(self, texto: str) -> None:
        self.lbl_aviso.configure(text=texto)

    def _limpiar(self) -> None:
        for fig, lienzo in ((self.fig_curso, self.lienzo_curso), (self.fig_est, self.lienzo_est)):
            fig.clear()
            lienzo.draw()
        for marco in (self.marco_tabla_curso, self.marco_tabla_est):
            for hijo in marco.winfo_children():
                hijo.destroy()

    def _estilo_ejes(self, ax) -> None:
        for lado in ("top", "right"):
            ax.spines[lado].set_visible(False)
        for lado in ("left", "bottom"):
            ax.spines[lado].set_color("#B9C2BE")
        ax.tick_params(colors="#5C6B64", labelsize=8)
        ax.grid(axis="y", color="#E4E8E6", linewidth=0.8)
        ax.set_axisbelow(True)
        ax.set_ylim(0, 100)
        ax.set_ylabel("% de aciertos", fontsize=9, color="#5C6B64")

    def _lineas(self, ax, tabla: pd.DataFrame, columnas: list[str], general: str) -> None:
        """Una línea por columna: la general gruesa y oscura, las materias de colores."""
        x = range(len(tabla))
        for i, col in enumerate(columnas):
            es_general = col == general
            ax.plot(x, tabla[col], marker="o", markersize=6 if es_general else 4,
                    linewidth=3 if es_general else 1.6,
                    color=COLOR_GENERAL if es_general else COLORES_MATERIAS[i % len(COLORES_MATERIAS)],
                    label=col, zorder=3 if es_general else 2)
        ax.set_xticks(list(x))
        ax.set_xticklabels([e.replace(" (", "\n(") for e in tabla.index], fontsize=8)
        ax.legend(fontsize=8, frameon=False, loc="upper left", bbox_to_anchor=(1.0, 1.0))

    def _dibujar_curso(self, s) -> None:
        fig = self.fig_curso
        fig.clear()
        ax = fig.add_subplot(111)
        materias = [c for c in s.curso.columns
                    if c not in ("General", "Estudiantes", "Nota promedio", "Aprueban %")]
        self._lineas(ax, s.curso, ["General"] + materias, "General")
        # El valor del promedio general, escrito sobre cada punto
        for i, v in enumerate(s.curso["General"]):
            ax.annotate(f"{v:.0f} %", (i, v), textcoords="offset points", xytext=(0, 8),
                        ha="center", fontsize=9, fontweight="bold", color=COLOR_GENERAL)
        ax.set_title("Promedio del curso en cada examen", loc="left", fontsize=11,
                     fontweight="bold", color=estilos.TEXTO)
        self._estilo_ejes(ax)
        fig.tight_layout()
        self.lienzo_curso.draw()

    def _tabla_simple(self, marco, columnas, filas, alto: int, ordenable=True) -> ttk.Treeview:
        for hijo in marco.winfo_children():
            hijo.destroy()
        tabla = ttk.Treeview(marco, columns=[c[0] for c in columnas], show="headings", height=alto)
        for col, titulo, ancho in columnas:
            tabla.heading(col, text=titulo,
                          command=(lambda c=col: self._ordenar(tabla, c)) if ordenable else "")
            tabla.column(col, width=ancho, minwidth=40, anchor="w" if ancho >= 150 else "center")
        barra = ttk.Scrollbar(marco, orient="vertical", command=tabla.yview)
        tabla.configure(yscrollcommand=barra.set)
        tabla.pack(side="left", fill="both", expand=True)
        barra.pack(side="left", fill="y")
        for valores, tags in filas:
            tabla.insert("", "end", values=valores, tags=tags)
        return tabla

    def _tabla_curso(self, s) -> None:
        cols = [("examen", "Examen", 210)] + [(c, c[:14], 80) for c in s.curso.columns]
        filas = [([etiqueta] + ["—" if pd.isna(v) else (f"{v:.0f}" if c == "Estudiantes" else f"{v:.1f}")
                                for c, v in fila.items()], ())
                 for etiqueta, fila in s.curso.iterrows()]
        self._tabla_simple(self.marco_tabla_curso, cols, filas, alto=min(len(filas), 5),
                           ordenable=False)

    def _tabla_estudiantes(self, s) -> None:
        est = s.estudiantes
        cols = ([("nombre", "Nombre", 190), ("documento", "Documento", 95)]
                + [(e, f"Ex. {i + 1} %", 70) for i, e in enumerate(s.examenes)]
                + [("cambio", "Cambio", 80)])
        filas = []
        for doc, f in est.iterrows():
            cambio = f["cambio"]
            if pd.isna(cambio):
                texto, tag = "—", ()
            elif cambio >= 5:
                texto, tag = f"↑ +{cambio:.0f}", ("mejora",)
            elif cambio <= -5:
                texto, tag = f"↓ {cambio:.0f}", ("baja",)
            else:
                texto, tag = f"= {cambio:+.0f}", ()
            valores = ([f["nombre"] or "—", doc]
                       + ["—" if pd.isna(f[e]) else f"{f[e]:.0f}" for e in s.examenes] + [texto])
            filas.append((valores, tag))
        self.tabla_est = self._tabla_simple(self.marco_tabla_est, cols, filas, alto=9)
        self.tabla_est.tag_configure("mejora", background=estilos.VERDE_CLARO)
        self.tabla_est.tag_configure("baja", background=estilos.ROJO_CLARO)
        self.tabla_est.bind("<<TreeviewSelect>>", lambda e: self._estudiante_elegido())
        leyenda = " · ".join(f"Ex. {i + 1} = {e}" for i, e in enumerate(s.examenes))
        self.lbl_estudiante.configure(text=f"{leyenda}.   Seleccione un estudiante para ver "
                                           "su evolución. Verde: subió 5 puntos o más · Rojo: bajó.")

    def _estudiante_elegido(self) -> None:
        seleccion = self.tabla_est.selection()
        if seleccion:
            doc = str(self.tabla_est.set(seleccion[0], "documento"))
            self._dibujar_estudiante(doc)

    def _dibujar_estudiante(self, documento: str | None) -> None:
        fig = self.fig_est
        fig.clear()
        if documento and self.seguimiento:
            detalle = self.seguimiento.detalle(documento)
            if not detalle.empty:
                ax = fig.add_subplot(111)
                self._lineas(ax, detalle, list(detalle.columns), "Total")
                nombre = self.seguimiento.estudiantes.at[documento, "nombre"] or documento
                ax.set_title(f"Evolución de {nombre}", loc="left", fontsize=10,
                             fontweight="bold", color=estilos.TEXTO)
                self._estilo_ejes(ax)
                fig.tight_layout()
        self.lienzo_est.draw()

    def _ordenar(self, tabla: ttk.Treeview, columna: str) -> None:
        """Ordena la tabla al hacer clic en el título de una columna."""
        def valor(texto):
            limpio = str(texto).replace("↑", "").replace("↓", "").replace("=", "").replace("+", "")
            try:
                return (0, float(limpio))
            except ValueError:
                return (1, str(texto).lower())
        filas = [(tabla.set(i, columna), i) for i in tabla.get_children("")]
        descendente = self._orden == (columna, False)
        filas.sort(key=lambda f: valor(f[0]), reverse=descendente)
        for pos, (_, i) in enumerate(filas):
            tabla.move(i, "", pos)
        self._orden = (columna, descendente)

    # ======================================================================
    # Exportar
    # ======================================================================
    def exportar(self) -> None:
        if not self.seguimiento or not self.seguimiento.hay_datos:
            messagebox.showinfo("Sin datos", "Marque los exámenes que quiere comparar.", parent=self)
            return
        from ..reportes.excel import exportar_seguimiento
        grado = self.var_grado.get()
        nombre = f"seguimiento_grado_{grado}.xlsx" if grado != "Todos" else "seguimiento.xlsx"
        ruta = self.raiz / "salidas" / nombre
        try:
            exportar_seguimiento(self.seguimiento, ruta)
        except PermissionError:
            messagebox.showerror("Archivo abierto", f"Cierre {nombre} en Excel y vuelva a intentar.",
                                 parent=self)
            return
        if messagebox.askyesno("Excel listo", f"Se guardó {nombre} en la carpeta «salidas».\n\n"
                               "¿Desea abrirlo ahora?", parent=self):
            abrir_con_el_sistema(ruta)
