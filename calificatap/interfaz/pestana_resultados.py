"""
pestana_resultados.py — Pantalla "Resultados" (Módulo 3).

    ┌──────────────────────────┬────────────────────────────────────────┐
    │ 1. Clave de respuestas   │ [Estudiantes 24] [Promedio 3,7] [...]  │
    │   Matemáticas  DDDBB ... │ ┌ Estudiantes │ Materias │ Preguntas ┐ │
    │ 2. Lista de estudiantes  │ │  tabla o gráfico                    │ │
    │ 3. Escala de notas       │ │                                     │ │
    │                          │ └─────────────────────────────────────┘ │
    │                          │                    [Exportar a Excel]   │
    └──────────────────────────┴────────────────────────────────────────┘

Todo se recalcula solo cuando cambia la clave, la lista o la escala.
Los gráficos se hacen con matplotlib dentro de la ventana de tkinter.
"""

from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk

import pandas as pd
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
from matplotlib.patches import Patch

from ..lector.hojas import ERROR, cargar_hojas, guardar_hojas
from ..reportes.calificar import (Escala, calificar, cargar_escala, guardar_escala,
                                  pesos_saber, usa_puntaje_saber)
from ..reportes.clave import (MODOS_ANULACION, anular_pregunta, cargar_clave, clave_a_textos,
                              guardar_clave, revisar_texto, textos_a_clave)
from ..reportes.estudiantes import cargar_estudiantes, guardar_estudiantes
from ..reportes.excel import exportar_excel
from . import estilos
from .utilidades import MarcoDesplazable, SelectorExamen, Tarjeta, abrir_con_el_sistema
from .ventana_importar import importar_lista

COLOR_DIFICULTAD = {"Fácil": "#3A9D6A", "Media": "#E0A100", "Difícil": "#C8463D"}
FUENTE_CLAVE = ("Consolas", 11) if estilos.FAMILIA == "Segoe UI" else ("DejaVu Sans Mono", 10)


class PestanaResultados(ttk.Frame):
    def __init__(self, padre, raiz_proyecto: Path, var_examen: tk.StringVar):
        super().__init__(padre)
        self.raiz = raiz_proyecto
        self.resultados = None
        self.vars_clave: dict[str, tk.StringVar] = {}
        self._id_recalculo = None
        self._cargando = False
        self._orden = ("puesto", False)
        # Puntaje tipo Saber 11: None = automático; pesos = {código_materia: peso}
        self._puntaje_saber: bool | None = None
        self._pesos: dict[str, float] = {}
        self._construir(var_examen)

    # ======================================================================
    # Construcción
    # ======================================================================
    def _construir(self, var_examen) -> None:
        arriba = ttk.Frame(self, padding=(14, 10, 14, 4))
        arriba.pack(fill="x")
        self.selector = SelectorExamen(arriba, self.raiz / "salidas", var_examen,
                                       al_cambiar=self.cargar_examen)
        self.selector.pack(side="left")
        self.btn_excel = ttk.Button(arriba, text="📊 Exportar a Excel", style="Primario.TButton",
                                    command=self.exportar)
        self.btn_excel.pack(side="right")
        ttk.Button(arriba, text="📄 Boletines (PDF)", command=self.boletines).pack(
            side="right", padx=8)

        division = ttk.PanedWindow(self, orient="horizontal")
        division.pack(fill="both", expand=True)
        izquierda = ttk.Frame(division, padding=(14, 4, 6, 10))
        derecha = ttk.Frame(division, padding=(6, 4, 14, 10))
        division.add(izquierda, weight=0)
        division.add(derecha, weight=1)

        desplazable = MarcoDesplazable(izquierda, width=430)
        desplazable.pack(fill="both", expand=True)
        formulario = desplazable.interior

        # --- 1. Clave ---
        self.marco_clave = ttk.LabelFrame(formulario, text="1. Clave de respuestas",
                                          style="Seccion.TLabelframe")
        self.marco_clave.pack(fill="x", pady=(0, 6))
        self.contenedor_clave = ttk.Frame(self.marco_clave, style="Panel.TFrame")
        self.contenedor_clave.pack(fill="x")
        ttk.Label(self.marco_clave, style="Ayuda.TLabel", wraplength=380, justify="left",
                  text="Escriba las respuestas correctas seguidas, por ejemplo «ABDCA BBCDA». "
                       "Los espacios no importan.").pack(anchor="w", pady=(6, 4))
        ttk.Button(self.marco_clave, text="Tomar la clave de una hoja leída…",
                   command=self.clave_desde_hoja).pack(anchor="w")

        # --- 2. Estudiantes ---
        marco = ttk.LabelFrame(formulario, text="2. Lista de estudiantes (opcional)",
                               style="Seccion.TLabelframe")
        marco.pack(fill="x", pady=6)
        self.lbl_estudiantes = ttk.Label(marco, style="Panel.TLabel", wraplength=380)
        self.lbl_estudiantes.pack(anchor="w")
        fila = ttk.Frame(marco, style="Panel.TFrame")
        fila.pack(fill="x", pady=(6, 0))
        ttk.Button(fila, text="Importar Excel o CSV…", command=self.importar_estudiantes).pack(side="left")
        ttk.Button(fila, text="Quitar lista", style="Pequeno.TButton",
                   command=self.quitar_estudiantes).pack(side="left", padx=6)
        ttk.Label(marco, style="Ayuda.TLabel", wraplength=380, justify="left",
                  text="Sirve para ver los nombres y saber quién no entregó hoja. "
                       "Puede ser la lista del SIMAT.").pack(anchor="w", pady=(6, 0))

        # --- 3. Escala ---
        marco = ttk.LabelFrame(formulario, text="3. Escala de notas", style="Seccion.TLabelframe")
        marco.pack(fill="x", pady=6)
        self.var_min, self.var_max, self.var_aprueba = (tk.StringVar(value="1.0"),
                                                        tk.StringVar(value="5.0"),
                                                        tk.StringVar(value="3.0"))
        for i, (texto, var) in enumerate([("Nota mínima", self.var_min), ("Nota máxima", self.var_max),
                                          ("Aprueba desde", self.var_aprueba)]):
            ttk.Label(marco, text=texto, style="Panel.TLabel").grid(row=0, column=i, sticky="w", padx=4)
            ttk.Spinbox(marco, from_=0, to=100, increment=0.1, width=7, textvariable=var).grid(
                row=1, column=i, sticky="w", padx=4)
            var.trace_add("write", lambda *_: self._programar_recalculo())

        # Puntaje tipo Saber 11 (0–500)
        self.var_puntaje = tk.BooleanVar(value=False)
        fila_p = ttk.Frame(marco, style="Panel.TFrame")
        fila_p.grid(row=2, column=0, columnspan=3, sticky="ew", pady=(10, 0))
        ttk.Checkbutton(fila_p, text="Puntaje tipo Saber 11 (0 a 500)", variable=self.var_puntaje,
                        command=self._cambio_puntaje).pack(side="left")
        ttk.Button(fila_p, text="Pesos…", style="Pequeno.TButton",
                   command=self.editar_pesos).pack(side="left", padx=6)
        self.lbl_pesos = ttk.Label(marco, style="Ayuda.TLabel", wraplength=380, justify="left")
        self.lbl_pesos.grid(row=3, column=0, columnspan=3, sticky="w", pady=(4, 0))

        # --- Tablero (derecha) ---
        tarjetas = ttk.Frame(derecha)
        tarjetas.pack(fill="x")
        self.t_estudiantes = Tarjeta(tarjetas, "Estudiantes")
        self.t_promedio = Tarjeta(tarjetas, "Nota promedio")
        self.t_aprueban = Tarjeta(tarjetas, "Aprueban")
        self.t_puntaje = Tarjeta(tarjetas, "Puntaje (0–500)")
        self.t_dificil = Tarjeta(tarjetas, "Más difícil")
        self.marco_tarjetas = tarjetas
        self._ubicar_tarjetas(con_puntaje=False)

        self.lbl_aviso = tk.Label(derecha, anchor="w", justify="left", padx=10, pady=6,
                                  wraplength=780,
                                  font=(estilos.FAMILIA, 10), bg=estilos.FONDO)
        self.lbl_aviso.pack(fill="x", pady=(8, 0))

        self.pestanas = ttk.Notebook(derecha)
        self.pestanas.pack(fill="both", expand=True, pady=(6, 0))
        self._pestana_estudiantes()
        self._pestana_materias()
        self._pestana_preguntas()
        self._pestana_alertas()

    def _tabla(self, padre, columnas: list[tuple[str, str, int]]) -> ttk.Treeview:
        marco = ttk.Frame(padre)
        marco.pack(fill="both", expand=True)
        tabla = ttk.Treeview(marco, columns=[c[0] for c in columnas], show="headings")
        for col, titulo, ancho in columnas:
            tabla.heading(col, text=titulo, command=lambda c=col: self._ordenar(tabla, c))
            tabla.column(col, width=ancho, minwidth=40,
                         anchor="w" if ancho > 120 else "center")
        barra = ttk.Scrollbar(marco, orient="vertical", command=tabla.yview)
        tabla.configure(yscrollcommand=barra.set)
        tabla.pack(side="left", fill="both", expand=True)
        barra.pack(side="left", fill="y")
        return tabla

    def _pestana_estudiantes(self) -> None:
        self.pag_estudiantes = ttk.Frame(self.pestanas, padding=6)
        self.pestanas.add(self.pag_estudiantes, text="  Estudiantes  ")
        self.tabla_est = None   # se crea al calcular (las columnas dependen de las materias)

    def _pestana_materias(self) -> None:
        pagina = ttk.Frame(self.pestanas, padding=6)
        self.pestanas.add(pagina, text="  Materias  ")
        self.fig_materias = Figure(figsize=(6, 2.8), dpi=96)
        self.lienzo_materias = FigureCanvasTkAgg(self.fig_materias, master=pagina)
        self.lienzo_materias.get_tk_widget().pack(fill="both", expand=True)
        self.tabla_mat = self._tabla(pagina, [
            ("materia", "Materia", 180), ("preguntas", "Preguntas", 75),
            ("promedio", "Promedio %", 85), ("nota_promedio", "Nota promedio", 100),
            ("maximo", "Máximo %", 80), ("minimo", "Mínimo %", 80), ("aprueban", "Aprueban", 80)])
        self.tabla_mat.configure(height=6)
        self.tabla_mat.master.pack_configure(expand=False, pady=(6, 0))

    def _pestana_preguntas(self) -> None:
        pagina = ttk.Frame(self.pestanas, padding=6)
        self.pestanas.add(pagina, text="  Preguntas  ")
        # Si hay formas, la pregunta 5 de la forma A y la de la B pueden ser distintas:
        # se ve una forma a la vez
        self.fila_forma = ttk.Frame(pagina)
        ttk.Label(self.fila_forma, text="Ver la forma:").pack(side="left")
        self.var_forma_preg = tk.StringVar(value="A")
        combo = ttk.Combobox(self.fila_forma, textvariable=self.var_forma_preg, width=4,
                             state="readonly")
        combo.pack(side="left", padx=6)
        combo.bind("<<ComboboxSelected>>", lambda e: self.resultados and self._mostrar_preguntas(self.resultados))
        self.combo_forma_preg = combo
        self.pagina_preguntas = pagina
        self.fig_preguntas = Figure(figsize=(6, 2.3), dpi=96)
        self.lienzo_preguntas = FigureCanvasTkAgg(self.fig_preguntas, master=pagina)
        self.lienzo_preguntas.get_tk_widget().pack(fill="x")
        self.tabla_preg = self._tabla(pagina, [
            ("pregunta", "N.º", 45), ("materia", "Materia", 135), ("clave", "Clave", 95),
            ("acierto", "% acierto", 70), ("dificultad", "Dificultad", 75),
            ("calidad", "¿Discrimina?", 90), ("distractor", "Errada + elegida", 110),
            ("en_blanco", "Blanco", 55), ("doble_marca", "Doble", 50)])
        # Preguntas con posible error en la clave: en amarillo; anuladas: en gris
        self.tabla_preg.tag_configure("sospecha", background="#FFE08A")
        self.tabla_preg.tag_configure("anulada", foreground=estilos.TEXTO_SUAVE,
                                      background="#ECEFED")
        self.tabla_preg.configure(selectmode="browse")
        botones = ttk.Frame(pagina)
        # Abajo y empacado ANTES que la tabla, para que la tabla no lo tape
        botones.pack(side="bottom", fill="x", pady=(6, 0), before=self.tabla_preg.master)
        ttk.Button(botones, text="⊘ Anular pregunta…", command=self.anular).pack(side="left")
        ttk.Button(botones, text="Quitar anulación", command=self.quitar_anulacion).pack(
            side="left", padx=6)
        self.lbl_anuladas = ttk.Label(botones, style="Subtitulo.TLabel")
        self.lbl_anuladas.pack(side="left", padx=8)
        ttk.Label(pagina, style="Subtitulo.TLabel", wraplength=700, justify="left",
                  text="¿Discrimina?: Buena = la aciertan más los mejores que los más flojos. "
                       "Revisar = puede estar mal redactada o ser ambigua. "
                       "En amarillo: posible error en la clave. En gris: pregunta anulada.").pack(
            anchor="w", pady=(0, 4), before=self.tabla_preg.master)

    def _pestana_alertas(self) -> None:
        self.pag_alertas = ttk.Frame(self.pestanas, padding=6)
        self.pestanas.add(self.pag_alertas, text="  Alertas  ")
        self.tabla_alertas = self._tabla(self.pag_alertas, [("tipo", "Tipo", 160),
                                                            ("detalle", "Detalle", 560)])
        # El detalle completo de la alerta elegida (en la tabla puede no caber)
        self.lbl_alerta = tk.Label(self.pag_alertas, anchor="w", justify="left", wraplength=760,
                                   bg=estilos.FONDO, fg=estilos.TEXTO, font=(estilos.FAMILIA, 10),
                                   text="Seleccione una alerta para leerla completa aquí.")
        self.lbl_alerta.pack(fill="x", pady=(6, 0), before=self.tabla_alertas.master)
        self.tabla_alertas.bind("<<TreeviewSelect>>", lambda e: self.lbl_alerta.configure(
            text=" — ".join(self.tabla_alertas.item(self.tabla_alertas.selection()[0], "values"))
            if self.tabla_alertas.selection() else ""))

    # ======================================================================
    # Cargar el examen elegido
    # ======================================================================
    def al_mostrar(self) -> None:
        self.selector.actualizar()
        self.cargar_examen()

    def cargar_examen(self) -> None:
        examen = self.selector.examen
        for hijo in self.contenedor_clave.winfo_children():
            hijo.destroy()
        self.vars_clave.clear()
        self.lbls_clave = {}
        if not examen:
            return

        # La escala de notas guardada para este examen
        escala = cargar_escala(examen)
        self.var_min.set(f"{escala.minima:.1f}")
        self.var_max.set(f"{escala.maxima:.1f}")
        self.var_aprueba.set(f"{escala.aprobacion:.1f}")
        self._puntaje_saber, self._pesos = escala.puntaje_saber, dict(escala.pesos)
        self.var_puntaje.set(usa_puntaje_saber(examen, escala))
        self._actualizar_lbl_pesos()

        # Una fila por materia (nombre, caja de texto y estado "25/25 ✔").
        # Si el examen tiene formas, se repite el bloque para cada forma.
        self._cargando = True
        claves = cargar_clave(examen)
        fila = 0
        for forma in examen.formas_para_clave:
            if examen.letras_formas:
                tk.Label(self.contenedor_clave, text=f"Forma {forma}", bg=estilos.VERDE_CLARO,
                         fg=estilos.VERDE_OSCURO, anchor="w", padx=6,
                         font=(estilos.FAMILIA, 10, "bold")).grid(
                    row=fila, column=0, columnspan=2, sticky="ew", pady=(10 if fila else 0, 0))
                fila += 1
            textos = clave_a_textos(examen, claves.get(forma, {}))
            for m in examen.materias:
                ttk.Label(self.contenedor_clave, text=f"{m.nombre} ({m.preguntas})",
                          style="Panel.TLabel", font=(estilos.FAMILIA, 10, "bold")).grid(
                    row=fila, column=0, sticky="w", pady=(6, 0))
                lbl = tk.Label(self.contenedor_clave, bg=estilos.FONDO_PANEL,
                               font=(estilos.FAMILIA, 9))
                lbl.grid(row=fila, column=1, sticky="e", pady=(6, 0))
                var = tk.StringVar(value=textos.get(m.codigo, ""))
                ttk.Entry(self.contenedor_clave, textvariable=var, font=FUENTE_CLAVE).grid(
                    row=fila + 1, column=0, columnspan=2, sticky="ew")
                fila += 2
                clave_var = (forma, m.codigo)
                var.trace_add("write", lambda *_, f=forma, materia=m: self._clave_cambio(f, materia))
                self.vars_clave[clave_var] = var
                self.lbls_clave[clave_var] = lbl
                self._clave_cambio(forma, m, guardar=False)
        self.contenedor_clave.columnconfigure(0, weight=1)
        self._cargando = False
        self._preparar_filtro_formas(examen)
        self._actualizar_lbl_estudiantes()
        self.recalcular()

    def _clave_cambio(self, forma: str, materia, guardar: bool = True) -> None:
        ok, texto = revisar_texto(self.vars_clave[(forma, materia.codigo)].get(), materia)
        self.lbls_clave[(forma, materia.codigo)].configure(
            text=texto, fg=estilos.VERDE_OSCURO if ok else estilos.ROJO)
        if guardar and not self._cargando:
            examen = self.selector.examen
            claves = {}
            for f in examen.formas_para_clave:
                textos = {c: v.get() for (ff, c), v in self.vars_clave.items() if ff == f}
                claves[f] = textos_a_clave(examen, textos)
            guardar_clave(examen, claves)
            self._programar_recalculo()

    # ======================================================================
    # Clave desde una hoja leída
    # ======================================================================
    def clave_desde_hoja(self) -> None:
        examen = self.selector.examen
        hojas = [h for h in cargar_hojas(examen) if h.estado != ERROR] if examen else []
        if not hojas:
            messagebox.showinfo("No hay hojas", "Primero lea las hojas en la pestaña 2.\n\n"
                                "Truco: llene una hoja con las respuestas correctas, "
                                "léala junto con las demás y elíjala aquí.", parent=self)
            return
        ventana = tk.Toplevel(self)
        ventana.title("Elegir la hoja con la clave")
        ventana.transient(self.winfo_toplevel())
        ventana.configure(bg=estilos.FONDO, padx=14, pady=12)
        ttk.Label(ventana, text="¿Cuál hoja tiene las respuestas correctas?",
                  font=(estilos.FAMILIA, 11, "bold")).pack(anchor="w")
        lista = tk.Listbox(ventana, width=60, height=12)
        for h in hojas:
            forma = f"  ·  forma {h.forma}" if examen.letras_formas and h.forma else ""
            lista.insert("end", f"{h.documento or '(sin documento)'}  —  {h.origen}{forma}")
        lista.pack(fill="both", expand=True, pady=8)

        var_forma = tk.StringVar(value=examen.formas_para_clave[0])
        if examen.letras_formas:
            fila = ttk.Frame(ventana)
            fila.pack(anchor="w", pady=(0, 6))
            ttk.Label(fila, text="Usarla como clave de la forma:").pack(side="left")
            ttk.Combobox(fila, textvariable=var_forma, values=list(examen.letras_formas),
                         state="readonly", width=4).pack(side="left", padx=6)
            # Al elegir una hoja, se propone la forma que el estudiante marcó en ella
            lista.bind("<<ListboxSelect>>", lambda e: lista.curselection() and
                       hojas[lista.curselection()[0]].forma in examen.letras_formas and
                       var_forma.set(hojas[lista.curselection()[0]].forma))
        var_quitar = tk.BooleanVar(value=True)
        ttk.Checkbutton(ventana, variable=var_quitar,
                        text="Quitar esa hoja de las hojas de estudiantes").pack(anchor="w")

        def usar():
            if not lista.curselection():
                return
            h = hojas[lista.curselection()[0]]
            clave = {e: v for e, v in h.respuestas.items() if len(v) == 1}
            textos = clave_a_textos(examen, clave)
            forma = var_forma.get()
            for (f, codigo), var in self.vars_clave.items():
                if f == forma:
                    var.set(textos.get(codigo, ""))
            if var_quitar.get():
                todas = cargar_hojas(examen)
                guardar_hojas(examen, [x for x in todas if x.archivo != h.archivo])
                self.recalcular()
            ventana.destroy()

        ttk.Button(ventana, text="Usar como clave", style="Primario.TButton",
                   command=usar).pack(anchor="e", pady=(8, 0))
        ventana.grab_set()

    # ======================================================================
    # Lista de estudiantes
    # ======================================================================
    def _actualizar_lbl_estudiantes(self) -> None:
        examen = self.selector.examen
        n = len(cargar_estudiantes(examen)) if examen else 0
        self.lbl_estudiantes.configure(
            text=f"✔ {n} estudiantes cargados." if n else "No hay lista cargada.")

    def quitar_estudiantes(self) -> None:
        examen = self.selector.examen
        if examen and examen.archivo_estudiantes.exists():
            examen.archivo_estudiantes.unlink()
            self._actualizar_lbl_estudiantes()
            self.recalcular()

    def importar_estudiantes(self) -> None:
        examen = self.selector.examen
        if not examen:
            return
        importar_lista(self, al_aceptar=lambda lista: (
            guardar_estudiantes(examen, lista), self._actualizar_lbl_estudiantes(),
            self.recalcular()))

    # ======================================================================
    # Calcular y mostrar
    # ======================================================================
    def _escala(self) -> Escala | None:
        try:
            e = Escala(float(self.var_min.get().replace(",", ".")),
                       float(self.var_max.get().replace(",", ".")),
                       float(self.var_aprueba.get().replace(",", ".")),
                       self._puntaje_saber, dict(self._pesos))
        except ValueError:
            return None
        return e if e.minima < e.maxima and e.minima <= e.aprobacion <= e.maxima else None

    def _programar_recalculo(self) -> None:
        if self._id_recalculo:
            self.after_cancel(self._id_recalculo)
        self._id_recalculo = self.after(500, self.recalcular)

    def _aviso(self, texto: str, tipo: str = "info") -> None:
        colores = {"info": (estilos.TEXTO_SUAVE, estilos.FONDO),
                   "ok": (estilos.VERDE_OSCURO, estilos.VERDE_CLARO),
                   "error": (estilos.ROJO, estilos.ROJO_CLARO)}
        fg, bg = colores[tipo]
        self.lbl_aviso.configure(text=texto, fg=fg, bg=bg)

    def recalcular(self) -> None:
        self._id_recalculo = None
        examen = self.selector.examen
        self.resultados = None
        if not examen:
            self._aviso("Primero cree un examen en la pestaña 1.")
            return
        escala = self._escala()
        if escala is None:
            self._aviso("Revise la escala de notas: la mínima debe ser menor que la máxima.", "error")
            return
        guardar_escala(examen, escala)
        claves = cargar_clave(examen)
        hojas = cargar_hojas(examen)
        if not hojas:
            self._aviso("Aún no hay hojas leídas para este examen. Léalas en la pestaña 2.")
            self._limpiar()
            return
        if not any(claves.values()):
            self._aviso("Escriba la clave de respuestas (a la izquierda) para ver los resultados.")
            self._limpiar()
            return

        r = calificar(examen, hojas, claves, cargar_estudiantes(examen), escala)
        self.resultados = r
        if not r.hay_datos:
            self._aviso("No hay hojas que se puedan calificar.", "error")
            self._limpiar()
            return
        faltan = {f: examen.total_preguntas - len(claves.get(f, {}))
                  for f in examen.formas_para_clave}
        faltan = {f: n for f, n in faltan.items() if n}
        if faltan:
            partes = [f"{'forma ' + f + ': ' if examen.letras_formas else ''}"
                      f"{n} {'pregunta' if n == 1 else 'preguntas'}" for f, n in faltan.items()]
            self._aviso(f"⚠ A la clave le faltan {', '.join(partes)}. "
                        "Mientras tanto, esas no se califican.", "error")
        else:
            self._aviso("✔ Resultados al día. Se actualizan solos cuando cambia algo.", "ok")
        # Lo más urgente primero: una clave equivocada cambia las notas de todos
        sospechas = r.por_pregunta[r.por_pregunta["sospecha_clave"] != ""]
        if not sospechas.empty:
            lista = ", ".join(
                f"{p['pregunta']}{' (' + p['forma'] + ')' if p['forma'] else ''}"
                for _, p in sospechas.head(5).iterrows())
            self._aviso(f"⚠ Posible error en la clave de la(s) pregunta(s) {lista}: la mayoría "
                        "de los mejores estudiantes marcó otra opción. Revísela(s): si la "
                        "clave estaba mal, corríjala; si la pregunta tenía un problema, "
                        "anúlela en la pestaña «Preguntas».", "error")
        self._mostrar(r)

    def _limpiar(self) -> None:
        for t in (self.t_estudiantes, self.t_promedio, self.t_aprueban, self.t_puntaje,
                  self.t_dificil):
            t.poner("—")
        for tabla in (self.tabla_preg, self.tabla_alertas, self.tabla_est, self.tabla_mat):
            if tabla is not None:
                tabla.delete(*tabla.get_children())
        self.fig_materias.clear()
        self.lienzo_materias.draw()
        self.fig_preguntas.clear()
        self.lienzo_preguntas.draw()

    def _mostrar(self, r) -> None:
        est, esc = r.por_estudiante, r.escala
        n = len(est)
        aprueban = int(est["aprobado"].sum())
        promedio = est["porcentaje"].mean()
        nota_prom = esc.nota(promedio / 100)
        self.t_estudiantes.poner(str(n))
        self.t_promedio.poner(f"{nota_prom:.1f}", f"{promedio:.0f} % de aciertos",
                              estilos.VERDE_OSCURO if nota_prom >= esc.aprobacion else estilos.ROJO)
        self.t_aprueban.poner(f"{aprueban} de {n}", f"{aprueban / n * 100:.0f} % del grupo")
        self._ubicar_tarjetas(r.con_puntaje)
        if r.con_puntaje:
            puntajes = est["puntaje"].dropna()
            self.t_puntaje.poner(f"{puntajes.mean():.0f}",
                                 f"de {puntajes.min():.0f} a {puntajes.max():.0f}")
        # La más difícil, sin contar las anuladas
        vigentes = r.por_pregunta[r.por_pregunta["anulada"] == ""]
        peor = (vigentes if not vigentes.empty else r.por_pregunta).sort_values("acierto").iloc[0]
        forma = f" ({peor['forma']})" if peor["forma"] else ""
        codigo = {m.nombre: m.codigo for m in r.examen.materias}.get(peor["materia"], "")
        self.t_dificil.poner(f"N.º {peor['pregunta']}{forma}",
                             f"{codigo} · {peor['acierto']:.0f} % acertó")

        self._llenar_estudiantes(r)
        self._dibujar_materias(r)
        self._mostrar_preguntas(r)

        self.tabla_mat.delete(*self.tabla_mat.get_children())
        for _, m in r.por_materia.iterrows():
            self.tabla_mat.insert("", "end", values=(
                m["materia"], m["preguntas"], f"{m['promedio']:.0f}", f"{m['nota_promedio']:.1f}",
                f"{m['maximo']:.0f}", f"{m['minimo']:.0f}", f"{m['aprueban']} de {n}"))

        self.tabla_alertas.delete(*self.tabla_alertas.get_children())
        for tipo, detalle in r.alertas:
            self.tabla_alertas.insert("", "end", values=(tipo, detalle))
        self.pestanas.tab(self.pag_alertas,
                          text=f"  Alertas ({len(r.alertas)})  " if r.alertas else "  Alertas  ")

    def _ubicar_tarjetas(self, con_puntaje: bool) -> None:
        """Pone las tarjetas del tablero en columnas del mismo ancho
        (la del puntaje solo si se está calculando el puntaje tipo Saber)."""
        visibles = [self.t_estudiantes, self.t_promedio, self.t_aprueban]
        visibles += [self.t_puntaje] if con_puntaje else []
        visibles.append(self.t_dificil)
        for t in (self.t_estudiantes, self.t_promedio, self.t_aprueban, self.t_puntaje,
                  self.t_dificil):
            t.grid_forget()
        for i in range(5):
            self.marco_tarjetas.columnconfigure(i, weight=1 if i < len(visibles) else 0,
                                                uniform="tarjeta" if i < len(visibles) else "")
        for i, t in enumerate(visibles):
            t.grid(row=0, column=i, sticky="nsew", padx=(0, 8))

    def _preparar_filtro_formas(self, examen) -> None:
        """Muestra "Ver la forma: [A]" solo si el examen tiene formas."""
        if examen.letras_formas:
            self.combo_forma_preg.configure(values=list(examen.letras_formas))
            if self.var_forma_preg.get() not in examen.letras_formas:
                self.var_forma_preg.set("A")
            self.fila_forma.pack(anchor="w", pady=(0, 4), before=self.lienzo_preguntas.get_tk_widget())
        else:
            self.fila_forma.pack_forget()

    def _preguntas_visibles(self, r):
        """Las filas de 'por_pregunta' de la forma elegida (o todas si no hay formas)."""
        p = r.por_pregunta
        if r.examen.letras_formas:
            p = p[p["forma"] == self.var_forma_preg.get()]
        return p

    def _mostrar_preguntas(self, r) -> None:
        p = self._preguntas_visibles(r)
        self._dibujar_preguntas(p)
        self.tabla_preg.delete(*self.tabla_preg.get_children())
        for _, fila in p.iterrows():
            clave = fila["clave"] + (f" → ¿{fila['sospecha_clave']}?" if fila["sospecha_clave"] else "")
            if fila["anulada"]:
                clave = f"{fila['clave']} ⊘ " + ("todos" if fila["anulada"] == "bien"
                                                 else "excluida")
            etiqueta_fila = "anulada" if fila["anulada"] else (
                "sospecha" if fila["sospecha_clave"] else "")
            # iid = "forma|etiqueta": así se sabe qué pregunta anular
            self.tabla_preg.insert("", "end", iid=f"{fila['forma'] or 'A'}|{fila['etiqueta']}",
                values=(fila["pregunta"], fila["materia"], clave, f"{fila['acierto']:.0f} %",
                        fila["dificultad"], fila["calidad"] or "—", fila["distractor"] or "—",
                        fila["en_blanco"], fila["doble_marca"]),
                tags=(etiqueta_fila,) if etiqueta_fila else ())
        n_anuladas = sum(len(a) for a in r.anuladas.values())
        self.lbl_anuladas.configure(
            text=f"{n_anuladas} pregunta(s) anulada(s)" if n_anuladas
            else "Elija una pregunta de la tabla para anularla.")

    def _llenar_estudiantes(self, r) -> None:
        # Las columnas dependen de las materias: se vuelve a crear la tabla
        for hijo in self.pag_estudiantes.winfo_children():
            hijo.destroy()
        # Para que quepan, cada materia se titula con su código (MAT, LEC...)
        materias = [m.nombre for m in r.examen.materias if m.nombre in r.por_estudiante]
        codigos = {m.nombre: m.codigo for m in r.examen.materias}
        con_forma = "forma" in r.por_estudiante
        columnas = ([("puesto", "#", 34), ("documento", "Documento", 92),
                     ("nombre", "Nombre", 160 if con_forma else 180)]
                    + ([("forma", "Forma", 46)] if con_forma else [])
                    + [(m, f"{codigos[m]} %", 54) for m in materias]
                    + [("porcentaje", "Total %", 62)]
                    + ([("puntaje", "Puntaje", 62)] if r.con_puntaje else [])
                    + [("nota", "Nota", 50), ("aprobado", "Aprueba", 66)])
        self.tabla_est = self._tabla(self.pag_estudiantes, columnas)
        self.tabla_est.tag_configure("pierde", background=estilos.ROJO_CLARO)
        for _, f in r.por_estudiante.iterrows():
            valores = ([f["puesto"], f["documento"], f["nombre"] or "—"]
                       + ([f["forma"]] if con_forma else [])
                       + ["—" if pd.isna(f[m]) else f"{f[m]:.0f}" for m in materias]
                       + [f"{f['porcentaje']:.0f}"]
                       + (["—" if pd.isna(f["puntaje"]) else f"{f['puntaje']:.0f}"]
                          if r.con_puntaje else [])
                       + [f"{f['nota']:.1f}",
                          "✔ Sí" if f["aprobado"] else "✘ No"])
            self.tabla_est.insert("", "end", values=valores,
                                  tags=() if f["aprobado"] else ("pierde",))

    def _ordenar(self, tabla: ttk.Treeview, columna: str) -> None:
        """Ordena una tabla al hacer clic en el título de la columna."""
        filas = [(tabla.set(i, columna), i) for i in tabla.get_children("")]

        def clave(valor):
            try:
                return (0, float(str(valor[0]).replace("%", "").replace("✔ Sí", "1").replace("✘ No", "0")))
            except ValueError:
                return (1, str(valor[0]).lower())

        descendente = self._orden == (columna, False)
        filas.sort(key=clave, reverse=descendente)
        for pos, (_, i) in enumerate(filas):
            tabla.move(i, "", pos)
        self._orden = (columna, descendente)

    def _estilo_ejes(self, ax) -> None:
        for lado in ("top", "right"):
            ax.spines[lado].set_visible(False)
        ax.spines["left"].set_color("#B9C2BE")
        ax.spines["bottom"].set_color("#B9C2BE")
        ax.tick_params(colors="#5C6B64", labelsize=9)
        ax.grid(axis="x" if ax.get_label() == "h" else "y", color="#E4E8E6", linewidth=0.8)
        ax.set_axisbelow(True)

    def _dibujar_materias(self, r) -> None:
        """Barras horizontales: promedio de aciertos (%) por materia, con el valor al final."""
        fig = self.fig_materias
        fig.clear()
        ax = fig.add_subplot(111, label="h")
        datos = r.por_materia.iloc[::-1]       # la primera materia queda arriba
        barras = ax.barh(datos["materia"], datos["promedio"], color=estilos.VERDE, height=0.55)
        for barra, valor in zip(barras, datos["promedio"]):
            ax.text(barra.get_width() + 1.5, barra.get_y() + barra.get_height() / 2,
                    f"{valor:.0f} %", va="center", fontsize=9, color=estilos.TEXTO)
        ax.set_xlim(0, 105)
        ax.set_title("Promedio de aciertos por materia", loc="left", fontsize=11,
                     color=estilos.TEXTO, fontweight="bold")
        self._estilo_ejes(ax)
        fig.tight_layout()
        self.lienzo_materias.draw()

    def _dibujar_preguntas(self, p) -> None:
        """Barras por pregunta coloreadas por dificultad (con leyenda en palabras)."""
        fig = self.fig_preguntas
        fig.clear()
        if p.empty:
            self.lienzo_preguntas.draw()
            return
        ax = fig.add_subplot(111)
        # Las anuladas en gris (ya no cuentan como difíciles)
        colores = ["#B9C2BE" if a else COLOR_DIFICULTAD[d]
                   for d, a in zip(p["dificultad"], p["anulada"])]
        ax.bar(range(len(p)), p["acierto"], color=colores, width=0.8)
        paso = max(1, len(p) // 20)
        ax.set_xticks(range(0, len(p), paso))
        ax.set_xticklabels(p["pregunta"].iloc[::paso], fontsize=8)
        ax.set_ylim(0, 100)
        ax.set_ylabel("% que acertó", fontsize=9, color="#5C6B64")
        ax.set_title("Acierto por pregunta", loc="left", fontsize=11,
                     color=estilos.TEXTO, fontweight="bold")
        leyenda = [Patch(color=c, label=f"{d}") for d, c in COLOR_DIFICULTAD.items()]
        if (p["anulada"] != "").any():
            leyenda.append(Patch(color="#B9C2BE", label="Anulada"))
        ax.legend(handles=leyenda, loc="upper right", ncol=len(leyenda), fontsize=8, frameon=False, bbox_to_anchor=(1, 1.18))
        self._estilo_ejes(ax)
        fig.tight_layout()
        self.lienzo_preguntas.draw()

    # ======================================================================
    # Exportar
    # ======================================================================
    # ======================================================================
    # Puntaje tipo Saber 11
    # ======================================================================
    def _actualizar_lbl_pesos(self) -> None:
        examen = self.selector.examen
        if not examen or not self.var_puntaje.get():
            self.lbl_pesos.configure(text="Promedio ponderado de las materias × 5, como el ICFES.")
            return
        pesos = pesos_saber(examen, Escala(pesos=self._pesos))
        self.lbl_pesos.configure(text="Pesos: " + " · ".join(
            f"{m.codigo} ×{pesos[m.codigo]:g}" for m in examen.materias)
            + ". Es una aproximación: cada materia vale su % de aciertos.")

    def _cambio_puntaje(self) -> None:
        self._puntaje_saber = self.var_puntaje.get()
        self._actualizar_lbl_pesos()
        self._programar_recalculo()

    def editar_pesos(self) -> None:
        """Ventana para cambiar el peso de cada materia en el puntaje (0 = no cuenta)."""
        examen = self.selector.examen
        if not examen:
            return
        ventana = tk.Toplevel(self)
        ventana.title("Pesos del puntaje tipo Saber 11")
        ventana.transient(self.winfo_toplevel())
        ventana.configure(bg=estilos.FONDO, padx=16, pady=14)
        ttk.Label(ventana, wraplength=360, justify="left",
                  text="En el ICFES, Lectura crítica, Matemáticas, Sociales y Ciencias pesan 3 "
                       "e Inglés pesa 1. Con 0, la materia no entra en el puntaje.").pack(
            anchor="w", pady=(0, 10))
        cuadro = ttk.Frame(ventana)
        cuadro.pack(fill="x")
        actuales = pesos_saber(examen, Escala(pesos=self._pesos))
        variables = {}
        for i, m in enumerate(examen.materias):
            ttk.Label(cuadro, text=m.nombre).grid(row=i, column=0, sticky="w", pady=2)
            var = tk.StringVar(value=f"{actuales[m.codigo]:g}")
            ttk.Spinbox(cuadro, from_=0, to=10, increment=1, width=5,
                        textvariable=var).grid(row=i, column=1, padx=8, pady=2)
            variables[m.codigo] = var

        def por_defecto():
            for m in examen.materias:
                variables[m.codigo].set(f"{pesos_saber(examen, Escala())[m.codigo]:g}")

        def aceptar():
            try:
                nuevos = {c: float(v.get().replace(",", ".")) for c, v in variables.items()}
            except ValueError:
                messagebox.showerror("Pesos", "Escriba solo números.", parent=ventana)
                return
            if any(p < 0 for p in nuevos.values()) or not any(nuevos.values()):
                messagebox.showerror("Pesos", "Los pesos deben ser 0 o más, y al menos uno "
                                     "mayor que 0.", parent=ventana)
                return
            self._pesos = nuevos
            ventana.destroy()
            self._actualizar_lbl_pesos()
            self._programar_recalculo()

        botones = ttk.Frame(ventana)
        botones.pack(fill="x", pady=(12, 0))
        ttk.Button(botones, text="Como el ICFES", command=por_defecto).pack(side="left")
        ttk.Button(botones, text="Aceptar", style="Primario.TButton",
                   command=aceptar).pack(side="right")
        ttk.Button(botones, text="Cancelar", command=ventana.destroy).pack(side="right", padx=6)
        ventana.grab_set()

    # ======================================================================
    # Anular preguntas
    # ======================================================================
    def _pregunta_elegida(self):
        """Devuelve (forma, etiqueta, fila de por_pregunta) de la pregunta seleccionada."""
        seleccion = self.tabla_preg.selection()
        if not seleccion or self.resultados is None:
            messagebox.showinfo("Anular pregunta", "Primero elija una pregunta en la tabla.",
                                parent=self)
            return None
        forma, etiqueta = seleccion[0].split("|")
        p = self.resultados.por_pregunta
        fila = p[(p["etiqueta"] == etiqueta) & ((p["forma"] == forma) | (p["forma"] == ""))]
        return forma, etiqueta, fila.iloc[0]

    def anular(self) -> None:
        elegida = self._pregunta_elegida()
        if not elegida:
            return
        forma, etiqueta, fila = elegida
        examen = self.selector.examen
        texto_forma = f" de la forma {forma}" if examen.letras_formas else ""

        ventana = tk.Toplevel(self)
        ventana.title("Anular pregunta")
        ventana.transient(self.winfo_toplevel())
        ventana.configure(bg=estilos.FONDO, padx=16, pady=14)
        ttk.Label(ventana, style="Subtitulo.TLabel", wraplength=400, justify="left",
                  text=f"Pregunta {fila['pregunta']}{texto_forma} · {fila['materia']} · "
                       f"clave {fila['clave']} · la acertó el {fila['acierto']:.0f} %").pack(
            anchor="w")
        ttk.Label(ventana, wraplength=400, justify="left",
                  text="Anule una pregunta cuando estaba mal redactada, tenía dos respuestas "
                       "válidas o no se alcanzó a ver el tema. ¿Qué hacer con ella?").pack(
            anchor="w", pady=(8, 6))
        var_modo = tk.StringVar(value=fila["anulada"] or "bien")
        for modo, texto in MODOS_ANULACION.items():
            ttk.Radiobutton(ventana, text=texto, value=modo, variable=var_modo).pack(
                anchor="w", pady=2)
        ttk.Label(ventana, style="Ayuda.TLabel", wraplength=400, justify="left",
                  text="«Buena a todos» sube la nota de quienes la fallaron. «No cuenta» "
                       "califica sobre las demás preguntas. Se puede deshacer con «Quitar "
                       "anulación».").pack(anchor="w", pady=(6, 0))

        def aceptar():
            anular_pregunta(examen, forma, etiqueta, var_modo.get())
            ventana.destroy()
            self.recalcular()
            if self.tabla_preg.exists(f"{forma}|{etiqueta}"):
                self.tabla_preg.selection_set(f"{forma}|{etiqueta}")
                self.tabla_preg.see(f"{forma}|{etiqueta}")

        botones = ttk.Frame(ventana)
        botones.pack(fill="x", pady=(12, 0))
        ttk.Button(botones, text="Anular", style="Primario.TButton",
                   command=aceptar).pack(side="right")
        ttk.Button(botones, text="Cancelar", command=ventana.destroy).pack(side="right", padx=6)
        ventana.grab_set()

    def quitar_anulacion(self) -> None:
        elegida = self._pregunta_elegida()
        if not elegida:
            return
        forma, etiqueta, fila = elegida
        if not fila["anulada"]:
            messagebox.showinfo("Quitar anulación", "Esa pregunta no está anulada.", parent=self)
            return
        anular_pregunta(self.selector.examen, forma, etiqueta, None)
        self.recalcular()

    def boletines(self) -> None:
        """Un boletín de una página por estudiante, todos en un PDF."""
        if not self.resultados or not self.resultados.hay_datos:
            messagebox.showinfo("Sin resultados", "Todavía no hay resultados para hacer boletines.",
                                parent=self)
            return
        from ..reportes.boletines import crear_boletines
        ruta = self.resultados.examen.carpeta / "boletines.pdf"
        self.winfo_toplevel().configure(cursor="watch")
        self.update_idletasks()
        try:
            crear_boletines(self.resultados, ruta)
        except PermissionError:
            messagebox.showerror("Archivo abierto", "Cierre boletines.pdf y vuelva a intentar.",
                                 parent=self)
            return
        finally:
            self.winfo_toplevel().configure(cursor="")
        n = len(self.resultados.por_estudiante)
        if messagebox.askyesno("Boletines listos",
                               f"Se creó boletines.pdf con {n} boletines (uno por página), en la "
                               "carpeta del examen.\n\n¿Desea abrirlo ahora?", parent=self):
            abrir_con_el_sistema(ruta)

    def exportar(self) -> None:
        if not self.resultados or not self.resultados.hay_datos:
            messagebox.showinfo("Sin resultados", "Todavía no hay resultados para exportar.",
                                parent=self)
            return
        ruta = self.resultados.examen.archivo_excel
        try:
            exportar_excel(self.resultados, ruta)
        except PermissionError:
            messagebox.showerror("Archivo abierto",
                                 "Cierre el archivo resultados.xlsx en Excel y vuelva a intentar.",
                                 parent=self)
            return
        if messagebox.askyesno("Excel listo", f"Se guardó {ruta.name} en la carpeta del examen.\n\n"
                               "¿Desea abrirlo ahora?", parent=self):
            abrir_con_el_sistema(ruta)
