"""
pestana_generador.py — Pantalla "Crear hoja de respuestas" (Módulo 1).

    ┌─────────────────────────────┬──────────────────────────────┐
    │ 1. Colegio                  │                              │
    │ 2. Examen                   │       VISTA PREVIA           │
    │ 3. Materias  (tabla)        │   (se actualiza sola)        │
    │ 4. Opciones                 │                              │
    │ [estado: ✔ cabe / ✘ error]  │                              │
    │ [Abrir] [Guardar] [GENERAR] │                              │
    └─────────────────────────────┴──────────────────────────────┘

Idea central: el formulario NO guarda los datos en sus propias variables
sueltas; cada vez que algo cambia arma un diccionario con el MISMO formato
del JSON de configuración (función datos_actuales) y se lo pasa al generador.
Así la interfaz y la consola usan exactamente el mismo código.
"""

from __future__ import annotations

import json
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

import pandas as pd
from PIL import ImageTk

from ..generador.configuracion import ErrorDeConfiguracion
from ..generador.generar import estructura, generar_desde_datos, nombre_de_carpeta
from ..generador.maquetador import ErrorDeMaquetacion
from . import estilos
from .utilidades import MarcoDesplazable, abrir_con_el_sistema, sugerir_codigo
from .ventana_importar import importar_lista
from .vista_previa import imagen_vista_previa

# Materias que se cargan con el botón "Plantilla Saber 11"
PLANTILLA_SABER_11 = [
    {"nombre": "Matemáticas", "preguntas": 25, "opciones": 4},
    {"nombre": "Lectura Crítica", "preguntas": 25, "opciones": 4},
    {"nombre": "Ciencias Naturales", "preguntas": 20, "opciones": 4},
    {"nombre": "Sociales y Ciudadanas", "preguntas": 20, "opciones": 4},
    {"nombre": "Inglés", "preguntas": 15, "opciones": 3},
]

# Texto que se muestra en la lista de "opciones por pregunta"
LETRAS = "ABCDEFGH"
TEXTOS_OPCIONES = [f"{n} opciones (A a {LETRAS[n - 1]})" for n in range(2, 9)]

TEXTOS_FORMAS = ["Una sola (sin formas)", "2 formas (A y B)", "3 formas (A, B y C)",
                 "4 formas (A, B, C y D)"]

ESPERA_VISTA_PREVIA_MS = 400  # espera tras la última tecla antes de redibujar


class PestanaGenerador(ttk.Frame):
    def __init__(self, padre, raiz_proyecto: Path, al_generar=None):
        super().__init__(padre)
        self.al_generar = al_generar    # función a llamar cuando se genera una hoja
        self.raiz = raiz_proyecto
        self.carpeta_config = raiz_proyecto / "configuracion"
        self.carpeta_salidas = raiz_proyecto / "salidas"
        self.archivo_sesion = self.carpeta_config / "ultima_sesion.json"

        # Lista de materias: cada una es un diccionario como en el JSON.
        # "_codigo_auto" (con guion bajo) es interno: indica si el código
        # se calcula solo a partir del nombre o si el docente lo escribió.
        self.materias: list[dict] = []
        # Lista de estudiantes para las hojas con nombre (opcional)
        self.lista_estudiantes: list[dict] = []
        self.archivo_lista = self.carpeta_config / "ultima_lista.csv"

        self._cargando = False          # evita que al llenar el formulario se disparen eventos
        self._id_refresco = None        # temporizador pendiente de la vista previa
        self._imagen_tk = None          # referencia a la imagen (si no, Python la borra)
        self._datos_validos = False

        self._crear_variables()
        self._construir_interfaz()
        self._cargar_sesion_inicial()

    # ======================================================================
    # 1. Variables de tkinter (enlazadas a los campos del formulario)
    # ======================================================================
    def _crear_variables(self) -> None:
        self.var_colegio = tk.StringVar()
        self.var_municipio = tk.StringVar()
        self.var_logo = tk.StringVar()
        self.var_examen = tk.StringVar()
        self.var_grado = tk.StringVar()
        self.var_fecha = tk.StringVar()
        self.var_digitos = tk.StringVar(value="10")
        self.var_numeracion = tk.StringVar(value="continua")
        self.var_formas = tk.StringVar(value=TEXTOS_FORMAS[0])
        self.var_repartir = tk.BooleanVar(value=True)
        # Editor de la materia seleccionada
        self.var_m_nombre = tk.StringVar()
        self.var_m_preguntas = tk.StringVar()
        self.var_m_opciones = tk.StringVar()
        self.var_m_codigo = tk.StringVar()

        # Cualquier cambio en estas variables → actualizar la vista previa
        for var in (self.var_colegio, self.var_municipio, self.var_logo, self.var_examen,
                    self.var_grado, self.var_fecha, self.var_digitos, self.var_numeracion,
                    self.var_formas):
            var.trace_add("write", lambda *_: self._programar_vista_previa())
        # Cambios en el editor de materia → copiar a la materia seleccionada
        for var in (self.var_m_nombre, self.var_m_preguntas, self.var_m_opciones):
            var.trace_add("write", lambda *_: self._editor_cambio())
        self.var_m_codigo.trace_add("write", lambda *_: self._editor_cambio(codigo_manual=True))

    # ======================================================================
    # 2. Construcción de la interfaz
    # ======================================================================
    def _construir_interfaz(self) -> None:
        division = ttk.PanedWindow(self, orient="horizontal")
        division.pack(fill="both", expand=True)

        izquierda = ttk.Frame(division, padding=(14, 10, 6, 10))
        derecha = ttk.Frame(division, padding=(6, 10, 14, 10))
        division.add(izquierda, weight=0)
        division.add(derecha, weight=1)

        # --- Formulario (con desplazamiento) ---
        desplazable = MarcoDesplazable(izquierda, width=470)
        desplazable.pack(fill="both", expand=True)
        formulario = desplazable.interior

        ttk.Label(formulario, text="Crear hoja de respuestas", style="Titulo.TLabel").pack(anchor="w")
        ttk.Label(formulario, style="Subtitulo.TLabel", wraplength=430, justify="left",
                  text="Llene los datos. La vista previa de la derecha se actualiza sola."
                  ).pack(anchor="w", pady=(0, 8))

        self._seccion_colegio(formulario)
        self._seccion_examen(formulario)
        self._seccion_materias(formulario)
        self._seccion_opciones(formulario)
        self._seccion_lista(formulario)

        # --- Estado + botones (fijos abajo, fuera del desplazamiento) ---
        self.lbl_estado = tk.Label(izquierda, anchor="w", justify="left", wraplength=440,
                                   padx=10, pady=8, font=(estilos.FAMILIA, 10))
        self.lbl_estado.pack(fill="x", pady=(8, 6))

        botones = ttk.Frame(izquierda)
        botones.pack(fill="x")
        ttk.Button(botones, text="📂 Abrir…", command=self.abrir).pack(side="left")
        ttk.Button(botones, text="💾 Guardar…", command=self.guardar).pack(side="left", padx=6)
        self.btn_generar = ttk.Button(botones, text="Generar hoja de respuestas",
                                      style="Primario.TButton", command=self.generar)
        self.btn_generar.pack(side="right")

        # --- Vista previa ---
        fila_vista = ttk.Frame(derecha)
        fila_vista.pack(fill="x")
        self.lbl_vista = ttk.Label(fila_vista, text="Vista previa — así se va a imprimir",
                                   style="Subtitulo.TLabel")
        self.lbl_vista.pack(side="left")
        # Si el examen ocupa varias hojas: botones para pasar de una a otra
        self.nav_hojas = ttk.Frame(fila_vista)
        ttk.Button(self.nav_hojas, text="◀", width=3, style="Pequeno.TButton",
                   command=lambda: self._cambiar_hoja(-1)).pack(side="left")
        self.lbl_hoja = ttk.Label(self.nav_hojas, font=(estilos.FAMILIA, 10, "bold"))
        self.lbl_hoja.pack(side="left", padx=6)
        ttk.Button(self.nav_hojas, text="▶", width=3, style="Pequeno.TButton",
                   command=lambda: self._cambiar_hoja(1)).pack(side="left")
        self._hoja_vista, self._total_hojas = 1, 1
        self.lienzo = tk.Canvas(derecha, bg=estilos.FONDO_VISTA_PREVIA, highlightthickness=0)
        self.lienzo.pack(fill="both", expand=True, pady=(4, 0))
        self.lienzo.bind("<Configure>", lambda e: self._programar_vista_previa())

    def _seccion(self, padre, titulo: str) -> ttk.LabelFrame:
        marco = ttk.LabelFrame(padre, text=titulo, style="Seccion.TLabelframe")
        marco.pack(fill="x", pady=6)
        marco.columnconfigure(1, weight=1)
        return marco

    def _fila(self, marco, fila: int, etiqueta: str, control, ayuda: str = "") -> None:
        """Pone 'Etiqueta: [control]' en una fila, con un texto de ayuda opcional debajo."""
        ttk.Label(marco, text=etiqueta, style="Panel.TLabel").grid(
            row=fila * 2, column=0, sticky="w", padx=(0, 10), pady=3)
        control.grid(row=fila * 2, column=1, sticky="ew", pady=3)
        if ayuda:
            ttk.Label(marco, text=ayuda, style="Ayuda.TLabel", wraplength=300,
                      justify="left").grid(
                row=fila * 2 + 1, column=1, sticky="w")

    def _seccion_colegio(self, padre) -> None:
        marco = self._seccion(padre, "1. Colegio")
        self._fila(marco, 0, "Nombre:", ttk.Entry(marco, textvariable=self.var_colegio))
        self._fila(marco, 1, "Municipio:", ttk.Entry(marco, textvariable=self.var_municipio))

        caja_logo = ttk.Frame(marco, style="Panel.TFrame")
        self.lbl_logo = ttk.Label(caja_logo, text="(sin logo)", style="Ayuda.TLabel")
        self.lbl_logo.pack(side="left", fill="x", expand=True)
        ttk.Button(caja_logo, text="Quitar", style="Pequeno.TButton",
                   command=lambda: self.var_logo.set("")).pack(side="right")
        ttk.Button(caja_logo, text="Elegir imagen…", style="Pequeno.TButton",
                   command=self._elegir_logo).pack(side="right", padx=4)
        self._fila(marco, 2, "Logo:", caja_logo, "Opcional. Imagen PNG o JPG.")
        self.var_logo.trace_add("write", lambda *_: self.lbl_logo.configure(
            text=Path(self.var_logo.get()).name if self.var_logo.get() else "(sin logo)"))

    def _seccion_examen(self, padre) -> None:
        marco = self._seccion(padre, "2. Examen")
        self._fila(marco, 0, "Nombre:", ttk.Entry(marco, textvariable=self.var_examen),
                   "Ej.: Simulacro Saber 11 – Tercer periodo")
        grados = [str(g) for g in range(1, 12)]
        self._fila(marco, 1, "Grado:", ttk.Combobox(marco, textvariable=self.var_grado,
                                                     values=grados, width=8))
        self._fila(marco, 2, "Fecha:", ttk.Entry(marco, textvariable=self.var_fecha),
                   "Opcional. Ej.: 20 de octubre de 2026")

    def _seccion_materias(self, padre) -> None:
        marco = self._seccion(padre, "3. Materias")

        # Barra de botones
        barra = ttk.Frame(marco, style="Panel.TFrame")
        barra.grid(row=0, column=0, columnspan=2, sticky="ew")
        ttk.Button(barra, text="＋ Agregar", style="Pequeno.TButton",
                   command=self.agregar_materia).pack(side="left")
        ttk.Button(barra, text="Eliminar", style="Pequeno.TButton",
                   command=self.eliminar_materia).pack(side="left", padx=4)
        ttk.Button(barra, text="▲", width=3, style="Pequeno.TButton",
                   command=lambda: self.mover_materia(-1)).pack(side="left")
        ttk.Button(barra, text="▼", width=3, style="Pequeno.TButton",
                   command=lambda: self.mover_materia(1)).pack(side="left", padx=(2, 0))
        ttk.Button(barra, text="Plantilla Saber 11", style="Pequeno.TButton",
                   command=self.cargar_plantilla_saber).pack(side="right")

        # Tabla
        columnas = ("materia", "preguntas", "opciones")
        self.tabla = ttk.Treeview(marco, columns=columnas, show="headings",
                                  height=6, selectmode="browse")
        self.tabla.heading("materia", text="Materia")
        self.tabla.heading("preguntas", text="Preguntas")
        self.tabla.heading("opciones", text="Opciones")
        self.tabla.column("materia", width=210)
        self.tabla.column("preguntas", width=80, anchor="center")
        self.tabla.column("opciones", width=80, anchor="center")
        self.tabla.grid(row=1, column=0, columnspan=2, sticky="ew", pady=6)
        self.tabla.bind("<<TreeviewSelect>>", lambda e: self._seleccion_cambio())

        # Total de preguntas
        self.lbl_total = ttk.Label(marco, style="Ayuda.TLabel")
        self.lbl_total.grid(row=2, column=0, columnspan=2, sticky="w")

        # Editor de la materia seleccionada
        self.editor = ttk.LabelFrame(marco, text="Materia seleccionada", padding=8,
                                     style="Seccion.TLabelframe")
        self.editor.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(6, 0))
        self.editor.columnconfigure(1, weight=1)
        self.ent_m_nombre = ttk.Entry(self.editor, textvariable=self.var_m_nombre)
        self._fila(self.editor, 0, "Nombre:", self.ent_m_nombre)
        self._fila(self.editor, 1, "Preguntas:",
                   ttk.Spinbox(self.editor, from_=1, to=100, width=8,
                               textvariable=self.var_m_preguntas))
        self._fila(self.editor, 2, "Opciones:",
                   ttk.Combobox(self.editor, values=TEXTOS_OPCIONES, state="readonly",
                                textvariable=self.var_m_opciones))
        self._fila(self.editor, 3, "Código:",
                   ttk.Entry(self.editor, textvariable=self.var_m_codigo, width=10),
                   "Se llena solo. Identifica la materia en los reportes.")

    def _seccion_opciones(self, padre) -> None:
        marco = self._seccion(padre, "4. Opciones")
        self._fila(marco, 0, "Dígitos del documento:",
                   ttk.Spinbox(marco, from_=4, to=12, width=8, textvariable=self.var_digitos),
                   "Cuántas cifras tiene el documento más largo de sus estudiantes.")
        caja = ttk.Frame(marco, style="Panel.TFrame")
        ttk.Radiobutton(caja, text="1, 2, 3… seguido en toda la hoja",
                        variable=self.var_numeracion, value="continua").pack(anchor="w")
        ttk.Radiobutton(caja, text="Cada materia empieza en 1",
                        variable=self.var_numeracion, value="por_materia").pack(anchor="w")
        self._fila(marco, 1, "Numeración:", caja)
        self._fila(marco, 2, "Formas:",
                   ttk.Combobox(marco, values=TEXTOS_FORMAS, state="readonly",
                                textvariable=self.var_formas),
                   "Opcional. Con varias formas (A, B...) cada una tiene su propia clave; "
                   "sirve para que los estudiantes no se copien.")

    def _seccion_lista(self, padre) -> None:
        marco = self._seccion(padre, "5. Hojas con nombre (opcional)")
        ttk.Label(marco, style="Ayuda.TLabel", wraplength=420, justify="left",
                  text="Importe la lista del curso y se imprime una hoja por estudiante con su "
                       "nombre y su documento ya marcados: así nadie se equivoca al rellenarlo."
                  ).grid(row=0, column=0, columnspan=2, sticky="w")
        self.lbl_lista = ttk.Label(marco, style="Panel.TLabel", wraplength=420)
        self.lbl_lista.grid(row=1, column=0, columnspan=2, sticky="w", pady=(6, 4))
        fila = ttk.Frame(marco, style="Panel.TFrame")
        fila.grid(row=2, column=0, columnspan=2, sticky="w")
        ttk.Button(fila, text="Importar lista (Excel o CSV)…",
                   command=self.importar_lista).pack(side="left")
        ttk.Button(fila, text="Quitar", style="Pequeno.TButton",
                   command=self.quitar_lista).pack(side="left", padx=6)
        self.chk_repartir = ttk.Checkbutton(
            marco, variable=self.var_repartir,
            text="Repartir las formas en orden (A, B, A, B…)")
        self.chk_repartir.grid(row=3, column=0, columnspan=2, sticky="w", pady=(6, 0))
        # El recuadro de repartir formas solo tiene sentido si hay formas
        self.var_formas.trace_add("write", lambda *_: self._actualizar_lbl_lista())
        self._actualizar_lbl_lista()

    def _actualizar_lbl_lista(self) -> None:
        n = len(self.lista_estudiantes)
        self.lbl_lista.configure(
            text=f"✔ {n} estudiantes: se imprimirán {n} hojas con nombre." if n
            else "Sin lista: se imprime solo la hoja en blanco.")
        if n and self.var_formas.get() != TEXTOS_FORMAS[0]:
            self.chk_repartir.grid()
        else:
            self.chk_repartir.grid_remove()

    def importar_lista(self) -> None:
        def aceptar(lista):
            self.lista_estudiantes = lista.to_dict("records")
            self._guardar_lista()
            self._actualizar_lbl_lista()
            self._programar_vista_previa()
        importar_lista(self, aceptar)

    def quitar_lista(self) -> None:
        self.lista_estudiantes = []
        self._guardar_lista()
        self._actualizar_lbl_lista()
        self._programar_vista_previa()

    def _guardar_lista(self) -> None:
        """La lista se recuerda para la próxima vez que se abra el programa."""
        try:
            if self.lista_estudiantes:
                pd.DataFrame(self.lista_estudiantes).to_csv(self.archivo_lista, index=False,
                                                            encoding="utf-8-sig")
            elif self.archivo_lista.exists():
                self.archivo_lista.unlink()
        except OSError:
            pass

    def _cargar_lista_guardada(self) -> None:
        try:
            tabla = pd.read_csv(self.archivo_lista, dtype=str, encoding="utf-8-sig").fillna("")
            self.lista_estudiantes = tabla.to_dict("records")
        except (OSError, ValueError):
            self.lista_estudiantes = []
        self._actualizar_lbl_lista()

    # ======================================================================
    # 3. Materias: agregar, eliminar, mover, editar
    # ======================================================================
    def _codigos_usados(self, excepto: dict | None = None) -> set[str]:
        return {m["codigo"] for m in self.materias if m is not excepto}

    def _indice_seleccionado(self) -> int | None:
        seleccion = self.tabla.selection()
        return self.tabla.index(seleccion[0]) if seleccion else None

    def _refrescar_tabla(self, seleccionar: int | None = None) -> None:
        """Vuelve a llenar la tabla a partir de self.materias."""
        self.tabla.delete(*self.tabla.get_children())
        for m in self.materias:
            self.tabla.insert("", "end", values=(m["nombre"], m["preguntas"], m["opciones"]))
        if seleccionar is not None and self.materias:
            seleccionar = max(0, min(seleccionar, len(self.materias) - 1))
            fila = self.tabla.get_children()[seleccionar]
            self.tabla.selection_set(fila)
            self.tabla.see(fila)
        self._seleccion_cambio()
        self._programar_vista_previa()

    def agregar_materia(self) -> None:
        nueva = {"nombre": "Nueva materia", "preguntas": 10, "opciones": 4,
                 "codigo": sugerir_codigo("Nueva", self._codigos_usados()),
                 "_codigo_auto": True}
        self.materias.append(nueva)
        self._refrescar_tabla(seleccionar=len(self.materias) - 1)
        # Dejar el nombre listo para escribir encima
        self.ent_m_nombre.focus_set()
        self.ent_m_nombre.select_range(0, "end")

    def eliminar_materia(self) -> None:
        i = self._indice_seleccionado()
        if i is None:
            return
        if messagebox.askyesno("Eliminar materia",
                               f"¿Eliminar «{self.materias[i]['nombre']}»?", parent=self):
            del self.materias[i]
            self._refrescar_tabla(seleccionar=i)

    def mover_materia(self, direccion: int) -> None:
        i = self._indice_seleccionado()
        if i is None:
            return
        j = i + direccion
        if 0 <= j < len(self.materias):
            self.materias[i], self.materias[j] = self.materias[j], self.materias[i]
            self._refrescar_tabla(seleccionar=j)

    def cargar_plantilla_saber(self) -> None:
        if self.materias and not messagebox.askyesno(
                "Plantilla Saber 11", "Esto reemplaza las materias actuales. ¿Continuar?",
                parent=self):
            return
        self.materias = []
        for m in PLANTILLA_SABER_11:
            self.materias.append({**m, "codigo": sugerir_codigo(m["nombre"], self._codigos_usados()),
                                  "_codigo_auto": True})
        self._refrescar_tabla(seleccionar=0)

    def _seleccion_cambio(self) -> None:
        """Al elegir una fila, sus datos pasan al editor de abajo."""
        i = self._indice_seleccionado()
        self._cargando = True
        if i is None:
            for var in (self.var_m_nombre, self.var_m_preguntas,
                        self.var_m_opciones, self.var_m_codigo):
                var.set("")
            self._habilitar_editor(False)
        else:
            m = self.materias[i]
            self.var_m_nombre.set(m["nombre"])
            self.var_m_preguntas.set(str(m["preguntas"]))
            self.var_m_opciones.set(TEXTOS_OPCIONES[m["opciones"] - 2])
            self.var_m_codigo.set(m["codigo"])
            self._habilitar_editor(True)
        self._cargando = False

    def _habilitar_editor(self, activo: bool) -> None:
        for hijo in self.editor.winfo_children():
            if isinstance(hijo, (ttk.Entry, ttk.Spinbox, ttk.Combobox)):
                if isinstance(hijo, ttk.Combobox):
                    hijo.configure(state="readonly" if activo else "disabled")
                else:
                    hijo.configure(state="normal" if activo else "disabled")

    def _editor_cambio(self, codigo_manual: bool = False) -> None:
        """El docente escribió en el editor: copiamos el cambio a la materia."""
        if self._cargando:
            return
        i = self._indice_seleccionado()
        if i is None:
            return
        m = self.materias[i]
        m["nombre"] = self.var_m_nombre.get()

        # Preguntas: si no es un número válido, se guarda el texto tal cual
        # y el mensaje de estado le avisará al docente.
        texto = self.var_m_preguntas.get().strip()
        m["preguntas"] = int(texto) if texto.isdigit() else texto

        if self.var_m_opciones.get() in TEXTOS_OPCIONES:
            m["opciones"] = TEXTOS_OPCIONES.index(self.var_m_opciones.get()) + 2

        if codigo_manual:
            m["codigo"] = self.var_m_codigo.get().strip().upper()
            m["_codigo_auto"] = False
        elif m.get("_codigo_auto", True):
            # El código sigue al nombre mientras el docente no lo cambie a mano
            m["codigo"] = sugerir_codigo(m["nombre"], self._codigos_usados(excepto=m))
            self._cargando = True
            self.var_m_codigo.set(m["codigo"])
            self._cargando = False

        # Actualizar solo la fila de la tabla (sin perder la selección)
        fila = self.tabla.get_children()[i]
        self.tabla.item(fila, values=(m["nombre"], m["preguntas"], m["opciones"]))
        self._programar_vista_previa()

    def _elegir_logo(self) -> None:
        ruta = filedialog.askopenfilename(
            parent=self, title="Elegir logo del colegio",
            filetypes=[("Imágenes", "*.png *.jpg *.jpeg"), ("Todos los archivos", "*.*")])
        if ruta:
            self.var_logo.set(ruta)

    # ======================================================================
    # 4. Del formulario al diccionario (y al revés)
    # ======================================================================
    def datos_actuales(self) -> dict:
        """Arma el diccionario con el MISMO formato del JSON de configuración."""
        digitos = self.var_digitos.get().strip()
        return {
            "colegio": {
                "nombre": self.var_colegio.get().strip(),
                "municipio": self.var_municipio.get().strip(),
                "logo": self.var_logo.get() or None,
            },
            "examen": {
                "nombre": self.var_examen.get().strip(),
                "grado": self.var_grado.get().strip(),
                "fecha": self.var_fecha.get().strip(),
            },
            "documento": {"digitos": int(digitos) if digitos.isdigit() else digitos},
            "opciones": {"numeracion": self.var_numeracion.get(),
                         "formas": TEXTOS_FORMAS.index(self.var_formas.get()) + 1},
            # Las claves que empiezan por "_" son internas: no van al archivo
            "materias": [{k: v for k, v in m.items() if not k.startswith("_")}
                         for m in self.materias],
        }

    def cargar_datos(self, datos: dict) -> None:
        """Llena el formulario a partir de un diccionario (leído de un JSON)."""
        colegio = datos.get("colegio", {})
        examen = datos.get("examen", {})
        self.var_colegio.set(colegio.get("nombre", ""))
        self.var_municipio.set(colegio.get("municipio", ""))
        self.var_logo.set(colegio.get("logo") or "")
        self.var_examen.set(examen.get("nombre", ""))
        self.var_grado.set(str(examen.get("grado", "")))
        self.var_fecha.set(examen.get("fecha", ""))
        self.var_digitos.set(str(datos.get("documento", {}).get("digitos", 10)))
        self.var_numeracion.set(datos.get("opciones", {}).get("numeracion", "continua"))
        formas = int(datos.get("opciones", {}).get("formas", 1) or 1)
        self.var_formas.set(TEXTOS_FORMAS[max(1, min(formas, len(TEXTOS_FORMAS))) - 1])
        self.materias = []
        for m in datos.get("materias", []):
            self.materias.append({
                "nombre": m.get("nombre", ""), "preguntas": m.get("preguntas", 10),
                "opciones": m.get("opciones", 4), "codigo": m.get("codigo", ""),
                "_codigo_auto": False})   # códigos de un archivo: se respetan
        self._refrescar_tabla(seleccionar=0)

    def _cargar_sesion_inicial(self) -> None:
        """Al abrir el programa: recupera lo último que se usó, o el ejemplo."""
        self._cargar_lista_guardada()
        for ruta in (self.archivo_sesion, self.carpeta_config / "examen_ejemplo.json"):
            try:
                self.cargar_datos(json.loads(ruta.read_text(encoding="utf-8")))
                return
            except (OSError, ValueError):
                continue
        self.cargar_plantilla_saber()

    def guardar_sesion(self) -> None:
        """Guarda lo que hay en pantalla para la próxima vez que se abra el programa."""
        try:
            self.carpeta_config.mkdir(exist_ok=True)
            self.archivo_sesion.write_text(json.dumps(self.datos_actuales(), indent=2,
                                                      ensure_ascii=False), encoding="utf-8")
        except OSError:
            pass  # no es grave si no se puede guardar la sesión

    # ======================================================================
    # 5. Validación y vista previa
    # ======================================================================
    def _revision_rapida(self, datos: dict) -> str | None:
        """Revisiones con mensajes pensados para el docente (antes del generador)."""
        if not datos["colegio"]["nombre"]:
            return "Escriba el nombre del colegio."
        if not datos["examen"]["nombre"]:
            return "Escriba el nombre del examen."
        if not datos["examen"]["grado"]:
            return "Escriba el grado."
        if not self.materias:
            return "Agregue al menos una materia con el botón «＋ Agregar»."
        for m in self.materias:
            if not m["nombre"].strip():
                return "Hay una materia sin nombre."
            if not isinstance(m["preguntas"], int) or not 1 <= m["preguntas"] <= 100:
                return f"«{m['nombre']}»: el número de preguntas debe estar entre 1 y 100."
        if not isinstance(datos["documento"]["digitos"], int):
            return "Los dígitos del documento deben ser un número entre 4 y 12."
        largos = [e for e in self.lista_estudiantes
                  if len(str(e["documento"])) > datos["documento"]["digitos"]]
        if largos:
            return (f"{len(largos)} estudiante(s) de la lista tienen un documento de más de "
                    f"{datos['documento']['digitos']} cifras (por ejemplo, {largos[0]['nombre']}). "
                    "Aumente «Dígitos del documento».")
        return None

    def _opacar_vista_previa(self) -> None:
        """Si hay un error, cubre la vista previa para que no parezca válida."""
        self.lienzo.delete("velo")
        ancho, alto = self.lienzo.winfo_width(), self.lienzo.winfo_height()
        self.lienzo.create_rectangle(0, 0, ancho, alto, fill=estilos.FONDO_VISTA_PREVIA,
                                     stipple="gray75", outline="", tags="velo")
        self.lienzo.create_text(ancho // 2, alto // 2, tags="velo", fill=estilos.ROJO,
                                font=(estilos.FAMILIA, 12, "bold"), justify="center",
                                text="Corrija el mensaje en rojo\npara ver la vista previa")

    def _mostrar_estado(self, mensaje: str, ok: bool) -> None:
        self.lbl_estado.configure(
            text=("✔ " if ok else "✘ ") + mensaje,
            fg=estilos.VERDE_OSCURO if ok else estilos.ROJO,
            bg=estilos.VERDE_CLARO if ok else estilos.ROJO_CLARO)
        self.btn_generar.state(["!disabled"] if ok else ["disabled"])
        self._datos_validos = ok

    def _programar_vista_previa(self) -> None:
        """
        Espera unos milisegundos antes de redibujar. Si el docente sigue
        escribiendo, se cancela y se vuelve a esperar. (Esta técnica se llama
        "debounce": evita redibujar con cada letra.)
        """
        if self._cargando:
            return
        if self._id_refresco is not None:
            self.after_cancel(self._id_refresco)
        self._id_refresco = self.after(ESPERA_VISTA_PREVIA_MS, self._actualizar_vista_previa)

    def _actualizar_vista_previa(self) -> None:
        self._id_refresco = None
        total = sum(m["preguntas"] for m in self.materias if isinstance(m["preguntas"], int))
        self.lbl_total.configure(text=f"Total: {total} preguntas en {len(self.materias)} materias")

        datos = self.datos_actuales()
        problema = self._revision_rapida(datos)
        if problema:
            self._mostrar_estado(problema, ok=False)
            self._opacar_vista_previa()
            return

        alto = max(self.lienzo.winfo_height() - 20, 200)
        try:
            estudiante = self.lista_estudiantes[0] if self.lista_estudiantes else None
            imagen, self._total_hojas = imagen_vista_previa(
                datos, self.carpeta_config, alto, estudiante, self._hoja_vista)
            self._hoja_vista = min(self._hoja_vista, self._total_hojas)
            self.lbl_vista.configure(
                text=f"Vista previa — hoja de {estudiante['nombre']} (1 de "
                     f"{len(self.lista_estudiantes)}). Así se va a imprimir."
                if estudiante else "Vista previa — así se va a imprimir")
        except (ErrorDeConfiguracion, ErrorDeMaquetacion) as error:
            self._mostrar_estado(str(error), ok=False)
            self._opacar_vista_previa()
            return

        self._imagen_tk = ImageTk.PhotoImage(imagen)
        self.lienzo.delete("all")
        cx = self.lienzo.winfo_width() // 2
        # Sombra + hoja, para que parezca una hoja de papel
        self.lienzo.create_rectangle(cx - imagen.width // 2 + 4, 14,
                                     cx + imagen.width // 2 + 4, 14 + imagen.height,
                                     fill="#C3C9C6", outline="")
        self.lienzo.create_image(cx, 10, image=self._imagen_tk, anchor="n")
        if self._total_hojas > 1:
            self.lbl_hoja.configure(text=f"Hoja {self._hoja_vista} de {self._total_hojas}")
            self.nav_hojas.pack(side="right")
            self._mostrar_estado(
                f"Listo: {total} preguntas no caben en una hoja, así que cada estudiante "
                f"recibirá {self._total_hojas} hojas (todas se leen y se califican juntas). "
                "Si prefiere una sola hoja, quite preguntas u opciones.", ok=True)
        else:
            self.nav_hojas.pack_forget()
            self._mostrar_estado(f"Todo listo: {total} preguntas caben en una hoja carta.", ok=True)

    def _cambiar_hoja(self, paso: int) -> None:
        self._hoja_vista = max(1, min(self._hoja_vista + paso, self._total_hojas))
        self._programar_vista_previa()

    # ======================================================================
    # 6. Botones: abrir, guardar y generar
    # ======================================================================
    def abrir(self) -> None:
        ruta = filedialog.askopenfilename(
            parent=self, title="Abrir configuración de examen",
            initialdir=self.carpeta_config, filetypes=[("Configuración de examen", "*.json")])
        if not ruta:
            return
        try:
            self.cargar_datos(json.loads(Path(ruta).read_text(encoding="utf-8")))
        except (OSError, ValueError) as error:
            messagebox.showerror("No se pudo abrir", f"El archivo no es válido.\n\n{error}",
                                 parent=self)

    def guardar(self) -> None:
        datos = self.datos_actuales()
        sugerido = nombre_de_carpeta(datos["examen"]["nombre"] or "examen") + ".json"
        ruta = filedialog.asksaveasfilename(
            parent=self, title="Guardar configuración", initialdir=self.carpeta_config,
            initialfile=sugerido, defaultextension=".json",
            filetypes=[("Configuración de examen", "*.json")])
        if ruta:
            Path(ruta).write_text(json.dumps(datos, indent=2, ensure_ascii=False),
                                  encoding="utf-8")
            self._mostrar_estado(f"Configuración guardada en {Path(ruta).name}.", ok=True)

    def generar(self) -> None:
        self._actualizar_vista_previa()          # revisar con los datos más recientes
        if not self._datos_validos:
            return
        datos = self.datos_actuales()
        carpeta = self.carpeta_salidas / nombre_de_carpeta(
            f"{datos['examen']['nombre']}_grado_{datos['examen']['grado']}")
        if (carpeta / "hoja_respuestas.pdf").exists():
            try:
                anterior = json.loads((carpeta / "examen.json").read_text(encoding="utf-8"))
            except (OSError, ValueError):
                anterior = {}
            if estructura(anterior) == estructura(datos):
                texto = ("Ya hay una hoja generada para este examen y grado, con el mismo "
                         "diseño.\n\nSe conserva su código: las hojas que ya imprimió y lo que "
                         "ya se leyó siguen sirviendo.\n\n¿Generarla de nuevo?")
            else:
                texto = ("Ya hay una hoja generada para este examen y grado, pero CAMBIÓ EL "
                         "DISEÑO (materias, preguntas, opciones, dígitos o formas).\n\n"
                         "• Las hojas que ya imprimió dejarán de servir.\n"
                         "• Lo que ya se leyó y la clave se guardarán aparte, en una carpeta "
                         "«anterior_…» dentro del examen (no se borra nada).\n\n"
                         "Si es otro examen, mejor cámbiele el nombre.\n\n¿Continuar?")
            if not messagebox.askyesno("Ya existe", texto, parent=self):
                return

        self.winfo_toplevel().configure(cursor="watch")
        self.update_idletasks()
        try:
            resultado = generar_desde_datos(datos, self.carpeta_config, self.carpeta_salidas,
                                            estudiantes=self.lista_estudiantes or None,
                                            repartir_formas=self.var_repartir.get())
        except Exception as error:  # mostramos cualquier problema en lugar de cerrar el programa
            messagebox.showerror("No se pudo generar", str(error), parent=self)
            return
        finally:
            self.winfo_toplevel().configure(cursor="")

        self.guardar_sesion()
        if self.al_generar:
            self.al_generar(resultado.carpeta)
        VentanaListo(self, resultado)


class VentanaListo(tk.Toplevel):
    """Ventana de "¡Listo!" con accesos directos al PDF y a la carpeta."""

    def __init__(self, padre, resultado):
        super().__init__(padre)
        self.title("Hoja generada")
        self.configure(bg=estilos.FONDO_PANEL, padx=24, pady=20)
        self.resizable(False, False)
        self.transient(padre.winfo_toplevel())

        tk.Label(self, text="✔ ¡Hoja de respuestas lista!", bg=estilos.FONDO_PANEL,
                 fg=estilos.VERDE_OSCURO, font=(estilos.FAMILIA, 14, "bold")).pack(anchor="w")
        texto = (f"Se creó la hoja con {resultado.total_preguntas} preguntas "
                 f"(código del examen N.º {resultado.codigo_examen}).\n")
        if resultado.hojas > 1:
            texto += (f"Cada estudiante recibe {resultado.hojas} hojas (el PDF trae las "
                      f"{resultado.hojas}; imprímalas todas).\n")
        if resultado.hojas_personalizadas:
            texto += (f"También se crearon las hojas con el nombre de cada estudiante "
                      f"({resultado.hojas_personalizadas} estudiantes).\n")
        texto += ("\n"
                 "Al imprimir, elija «Tamaño real» o «100 %» (no «Ajustar a la página»),\n"
                 "para que las marcas de las esquinas queden en su lugar.")
        if resultado.archivado_en:
            texto += (f"\n\nLas hojas leídas y la clave del diseño anterior se guardaron en "
                      f"la carpeta «{resultado.archivado_en.name}».")
        if not resultado.verificacion_ok:
            texto += ("\n\n⚠ La verificación encontró una diferencia. "
                      "Revise el archivo verificacion.png en la carpeta.")
        tk.Label(self, text=texto, bg=estilos.FONDO_PANEL, justify="left",
                 font=(estilos.FAMILIA, 10)).pack(anchor="w", pady=(8, 16))

        botones = ttk.Frame(self, style="Panel.TFrame")
        botones.pack(fill="x")
        if resultado.ruta_personalizadas:
            ttk.Button(botones, text="Abrir hojas con nombre", style="Primario.TButton",
                       command=lambda: abrir_con_el_sistema(resultado.ruta_personalizadas)).pack(
                side="left", padx=(0, 8))
            ttk.Button(botones, text="Hoja en blanco",
                       command=lambda: abrir_con_el_sistema(resultado.ruta_pdf)).pack(side="left")
        else:
            ttk.Button(botones, text="Abrir PDF para imprimir", style="Primario.TButton",
                       command=lambda: abrir_con_el_sistema(resultado.ruta_pdf)).pack(side="left")
        ttk.Button(botones, text="Abrir carpeta",
                   command=lambda: abrir_con_el_sistema(resultado.carpeta)).pack(side="left", padx=8)
        ttk.Button(botones, text="Cerrar", command=self.destroy).pack(side="right")
        tk.Label(self, bg=estilos.FONDO_PANEL, fg=estilos.TEXTO_SUAVE, font=(estilos.FAMILIA, 9),
                 text="Cuando los estudiantes la llenen, siga en la pestaña «2. Leer hojas».").pack(
            anchor="w", pady=(14, 0))
        self.grab_set()
