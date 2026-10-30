"""
pestana_cuadernillos.py — Pantalla "Cuadernillos" (Módulo 0).

    ┌──────────────────────────────────┬────────────────────────────────┐
    │ Examen: [Simulacro Saber 11 ▼]   │  Ver: [Forma A ▼] ◀ Pág 2/14 ▶ │
    │ 1. Banco de preguntas            │                                │
    │   [Crear plantilla] [Abrir Excel]│      VISTA DEL CUADERNILLO     │
    │   ✔ 105 de 105 preguntas listas  │                                │
    │ 2. Formas                        │                                │
    │   [x] cambiar orden de preguntas │                                │
    │   [x] cambiar orden de opciones  │                                │
    │ 3. Cuadernillo                   │                                │
    │   Tiempo: [4 horas 30 minutos]   │                                │
    │ [ GENERAR CUADERNILLOS ]         │                                │
    └──────────────────────────────────┴────────────────────────────────┘

El docente escribe las preguntas en Excel (una vez); el programa arma un
cuadernillo por forma y deja la clave de cada forma lista en «Resultados».
"""

from __future__ import annotations

import tempfile
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk

from ..cuadernillos.banco import CARPETA_IMAGENES, crear_plantilla, esta_vacia, leer_banco
from ..cuadernillos.formas import cargar_mapa
from ..cuadernillos.generar import generar_cuadernillos, nombre_cuadernillo, ruta_banco
from ..lector.hojas import cargar_hojas
from . import estilos
from .utilidades import MarcoDesplazable, SelectorExamen, VisorImagen, abrir_con_el_sistema


class PestanaCuadernillos(ttk.Frame):
    def __init__(self, padre, raiz_proyecto: Path, var_examen: tk.StringVar):
        super().__init__(padre)
        self.raiz = raiz_proyecto
        self.banco = None
        self._pagina = 0
        self._vista = Path(tempfile.gettempdir()) / "calificatap_vista_cuadernillo.png"
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

        division = ttk.PanedWindow(self, orient="horizontal")
        division.pack(fill="both", expand=True)
        izquierda = ttk.Frame(division, padding=(14, 4, 6, 10))
        derecha = ttk.Frame(division, padding=(6, 4, 14, 10))
        division.add(izquierda, weight=0)
        division.add(derecha, weight=1)

        # El botón principal abajo, siempre visible
        abajo = ttk.Frame(izquierda)
        abajo.pack(side="bottom", fill="x", pady=(8, 0))
        self.btn_generar = ttk.Button(abajo, text="📚 Generar cuadernillos",
                                      style="Primario.TButton", command=self.generar)
        self.btn_generar.pack(fill="x")
        self.lbl_estado = tk.Label(abajo, anchor="w", justify="left", wraplength=380,
                                   bg=estilos.FONDO, fg=estilos.TEXTO_SUAVE,
                                   font=(estilos.FAMILIA, 9))
        self.lbl_estado.pack(fill="x", pady=(6, 0))

        desplazable = MarcoDesplazable(izquierda, width=430)
        desplazable.pack(fill="both", expand=True)
        formulario = desplazable.interior

        # --- 1. Banco ---
        marco = ttk.LabelFrame(formulario, text="1. Preguntas", style="Seccion.TLabelframe")
        marco.pack(fill="x", pady=(0, 6))
        ttk.Label(marco, style="Ayuda.TLabel", wraplength=355, justify="left",
                  text="Escriba las preguntas en el programa, o tráigalas de un Word. Todo se "
                       "guarda en un Excel (banco_preguntas.xlsx) que también puede editar "
                       "directamente.").pack(anchor="w", pady=(0, 6))
        ttk.Button(marco, text="✏ Escribir las preguntas", style="Primario.TButton",
                   command=self.abrir_editor).pack(fill="x")
        fila = ttk.Frame(marco, style="Panel.TFrame")
        fila.pack(fill="x", pady=(6, 0))
        ttk.Button(fila, text="📄 Traer de un Word…", command=self.importar_word).pack(side="left")
        ttk.Button(fila, text="Word de ejemplo", style="Pequeno.TButton",
                   command=self.word_ejemplo).pack(side="left", padx=6)
        ttk.Button(marco, text="📚 Biblioteca de preguntas del colegio",
                   command=self.ver_biblioteca).pack(fill="x", pady=(6, 0))
        ttk.Label(marco, text="Con Excel:", style="Panel.TLabel").pack(anchor="w", pady=(8, 2))
        fila = ttk.Frame(marco, style="Panel.TFrame")
        fila.pack(fill="x")
        self.btn_plantilla = ttk.Button(fila, text="📥 Crear el Excel", command=self.crear_excel,
                                        style="Pequeno.TButton")
        self.btn_plantilla.pack(side="left")
        ttk.Button(fila, text="📂 Abrir", command=self.abrir_excel,
                   style="Pequeno.TButton").pack(side="left",
                                                                                  padx=6)
        ttk.Button(fila, text="🔄 Revisar", command=self.revisar_banco,
                   style="Pequeno.TButton").pack(side="left")
        ttk.Button(marco, text="Carpeta de imágenes", style="Pequeno.TButton",
                   command=self.abrir_imagenes).pack(anchor="w", pady=(6, 0))
        self.lbl_banco = tk.Label(marco, anchor="w", justify="left", wraplength=355,
                                  bg=estilos.FONDO_PANEL, font=(estilos.FAMILIA, 10, "bold"))
        self.lbl_banco.pack(fill="x", pady=(8, 2))
        self.lista_problemas = tk.Listbox(marco, height=6, activestyle="none", relief="flat",
                                          highlightthickness=1,
                                          highlightbackground=estilos.BORDE,
                                          font=(estilos.FAMILIA, 9))

        # --- 2. Formas ---
        marco = ttk.LabelFrame(formulario, text="2. Formas", style="Seccion.TLabelframe")
        marco.pack(fill="x", pady=6)
        self.lbl_formas = ttk.Label(marco, style="Panel.TLabel", wraplength=355, justify="left")
        self.lbl_formas.pack(anchor="w", pady=(0, 6))
        self.var_preguntas = tk.BooleanVar(value=True)
        self.var_opciones = tk.BooleanVar(value=True)
        self.chk_preguntas = ttk.Checkbutton(
            marco, variable=self.var_preguntas,
            text="Cambiar el orden de las preguntas")
        self.chk_preguntas.pack(anchor="w")
        self.chk_opciones = ttk.Checkbutton(
            marco, variable=self.var_opciones,
            text="Cambiar el orden de las opciones")
        self.chk_opciones.pack(anchor="w")
        ttk.Label(marco, style="Ayuda.TLabel", wraplength=355, justify="left",
                  text="Las preguntas cambian de lugar dentro de su prueba; las de un mismo texto se mueven juntas. Las marcadas como "
                       "«Fija» en el Excel no cambian sus opciones.").pack(anchor="w", pady=(4, 0))

        # --- 3. Cuadernillo ---
        marco = ttk.LabelFrame(formulario, text="3. Cuadernillo", style="Seccion.TLabelframe")
        marco.pack(fill="x", pady=6)
        fila = ttk.Frame(marco, style="Panel.TFrame")
        fila.pack(fill="x")
        ttk.Label(fila, text="Tiempo para responder:", style="Panel.TLabel").pack(side="left")
        self.var_tiempo = tk.StringVar()
        ttk.Entry(fila, textvariable=self.var_tiempo, width=22).pack(side="left", padx=6)
        ttk.Label(marco, style="Ayuda.TLabel", text="Ejemplo: 4 horas 30 minutos (opcional)").pack(
            anchor="w")
        self.var_pagina = tk.BooleanVar(value=True)
        ttk.Checkbutton(marco, variable=self.var_pagina,
                        text="Cada prueba empieza en una página nueva").pack(anchor="w", pady=(6, 0))
        ttk.Label(marco, style="Ayuda.TLabel", wraplength=355, justify="left",
                  text="Desmárquelo para ahorrar papel: la prueba siguiente empieza donde "
                       "termina la anterior.").pack(anchor="w")

        # --- Vista previa (derecha) ---
        barra = ttk.Frame(derecha)
        barra.pack(fill="x")
        ttk.Label(barra, text="Ver:", font=(estilos.FAMILIA, 10, "bold")).pack(side="left")
        self.var_forma = tk.StringVar()
        self.combo_forma = ttk.Combobox(barra, textvariable=self.var_forma, width=10,
                                        state="readonly")
        self.combo_forma.pack(side="left", padx=6)
        self.combo_forma.bind("<<ComboboxSelected>>", lambda e: self._ir_a_pagina(0))
        ttk.Button(barra, text="◀", width=3, command=lambda: self._ir_a_pagina(self._pagina - 1)
                   ).pack(side="left", padx=(10, 0))
        self.lbl_pagina = ttk.Label(barra, width=16, anchor="center")
        self.lbl_pagina.pack(side="left")
        ttk.Button(barra, text="▶", width=3, command=lambda: self._ir_a_pagina(self._pagina + 1)
                   ).pack(side="left")
        ttk.Button(barra, text="Abrir PDF", command=self.abrir_pdf).pack(side="right")
        self.visor = VisorImagen(derecha)
        self.visor.pack(fill="both", expand=True, pady=(6, 0))

    # ======================================================================
    # Examen elegido
    # ======================================================================
    def al_mostrar(self) -> None:
        self.selector.actualizar()
        self.cargar_examen()

    def cargar_examen(self) -> None:
        examen = self.selector.examen
        self.banco = None
        if not examen:
            return
        # Formas del examen (vienen del diseño de la hoja, pestaña 1)
        if examen.letras_formas:
            letras = " y ".join([", ".join(examen.letras_formas[:-1]), examen.letras_formas[-1]])
            self.lbl_formas.configure(
                text=f"Este examen tiene {examen.numero_formas} formas ({letras}). La forma A "
                     "queda en el orden del Excel; en las demás el programa cambia el orden.")
            for chk in (self.chk_preguntas, self.chk_opciones):
                chk.state(["!disabled"])
        else:
            self.lbl_formas.configure(
                text="Este examen no usa formas: se crea un solo cuadernillo, en el orden del "
                     "Excel. (Las formas se activan en «1. Crear hoja», sección Opciones.)")
            for chk in (self.chk_preguntas, self.chk_opciones):
                chk.state(["disabled"])
        # Lo que se eligió la última vez
        mapa = cargar_mapa(examen)
        if mapa:
            self.var_preguntas.set(mapa.get("barajar_preguntas", True))
            self.var_opciones.set(mapa.get("barajar_opciones", True))
            self.var_tiempo.set(mapa.get("tiempo", ""))
            self.var_pagina.set(mapa.get("pagina_por_materia", True))
        existe = ruta_banco(examen).exists()
        self.btn_plantilla.configure(text="📥 Crear el Excel" if not existe else "📥 Crear de nuevo")
        if existe:
            self.revisar_banco(silencioso=True)
        else:
            self._mostrar_banco("Todavía no hay banco de preguntas. Pulse «Crear el Excel».",
                                estilos.TEXTO_SUAVE, [])
        self._actualizar_vista()

    # ======================================================================
    # Banco
    # ======================================================================
    # ======================================================================
    # Editor de preguntas y Word
    # ======================================================================
    def abrir_editor(self) -> None:
        examen = self.selector.examen
        if not examen:
            messagebox.showinfo("Falta el examen", "Primero cree la hoja en la pestaña 1.",
                                parent=self)
            return
        from .editor_preguntas import EditorPreguntas

        def al_cerrar():
            self.btn_plantilla.configure(text="📥 Crear de nuevo")
            self.revisar_banco(silencioso=True)
        EditorPreguntas(self, examen, al_cerrar=al_cerrar,
                        carpeta_biblioteca=self.raiz / "biblioteca")

    def ver_biblioteca(self) -> None:
        """Ver, buscar y borrar las preguntas guardadas (para traerlas, use el editor)."""
        from ..cuadernillos.biblioteca import Biblioteca
        from .ventana_biblioteca import VentanaBiblioteca
        VentanaBiblioteca(self, Biblioteca(self.raiz / "biblioteca"),
                          destino="Para poner preguntas en un examen: abra «Escribir las "
                                  "preguntas» y use «📚 Traer de la biblioteca».")

    def word_ejemplo(self) -> None:
        """Guarda un Word de ejemplo con el formato que entiende el programa y lo abre."""
        examen = self.selector.examen
        if not examen:
            return
        from tkinter import filedialog
        from ..cuadernillos.word import crear_plantilla_word
        ruta = filedialog.asksaveasfilename(
            parent=self, title="Guardar el Word de ejemplo", defaultextension=".docx",
            initialfile="preguntas_ejemplo.docx", filetypes=[("Word", "*.docx")])
        if not ruta:
            return
        try:
            crear_plantilla_word(examen, ruta)
        except (ImportError, RuntimeError) as error:
            messagebox.showerror("Word", str(error), parent=self)
            return
        except PermissionError:
            messagebox.showerror("Word", "Cierre ese archivo en Word y vuelva a intentar.",
                                 parent=self)
            return
        abrir_con_el_sistema(ruta)

    def importar_word(self) -> None:
        examen = self.selector.examen
        if not examen:
            return
        from tkinter import filedialog
        from ..cuadernillos.banco import Banco, banco_vacio, guardar_banco, leer_banco
        from ..cuadernillos.word import combinar, leer_word
        ruta = filedialog.askopenfilename(parent=self, title="Elegir el Word con las preguntas",
                                          filetypes=[("Word", "*.docx")])
        if not ruta:
            return
        self.winfo_toplevel().configure(cursor="watch")
        self.update_idletasks()
        try:
            leido = leer_word(examen, ruta)
        except Exception as error:
            messagebox.showerror("No se pudo leer el Word",
                                 f"{error}\n\n(Si es un archivo .doc antiguo, ábralo en Word y "
                                 "guárdelo como .docx.)", parent=self)
            return
        finally:
            self.winfo_toplevel().configure(cursor="")
        if not leido.preguntas:
            messagebox.showwarning(
                "Word", "No se encontró ninguna pregunta. Revise que cada pregunta empiece "
                "con su número («1.») y cada opción con su letra («A.»). Pulse «Word de "
                "ejemplo» para ver el formato.", parent=self)
            return
        actual = leer_banco(examen, ruta_banco(examen)) if ruta_banco(examen).exists() \
            else banco_vacio(examen)
        completo = {e: actual.preguntas.get(e) for e in examen.todas_las_etiquetas()}
        base = banco_vacio(examen)
        base.preguntas.update({e: p for e, p in completo.items() if p is not None})
        actual = Banco(base.preguntas, actual.contextos, [])
        con_texto = sum(1 for e in leido.preguntas
                        if e in actual.preguntas and not esta_vacia(actual.preguntas[e]))
        texto = (f"Se encontraron {len(leido.preguntas)} preguntas ({leido.resumen(examen)})"
                 + (f" y {len(leido.contextos)} texto(s) compartido(s)" if leido.contextos else "")
                 + ".")
        if leido.avisos:
            texto += "\n\nAvisos:\n• " + "\n• ".join(leido.avisos[:8])
            if len(leido.avisos) > 8:
                texto += f"\n• … y {len(leido.avisos) - 8} más"
        reemplazar = False
        if con_texto:
            respuesta = messagebox.askyesnocancel(
                "Traer de Word", texto + f"\n\n{con_texto} de esas preguntas ya tienen texto en "
                "el banco.\n\n• Sí: reemplazarlas con las del Word.\n• No: llenar solo las "
                "que están vacías.", parent=self)
            if respuesta is None:
                return
            reemplazar = respuesta
        elif not messagebox.askyesno("Traer de Word", texto + "\n\n¿Pasarlas al banco?",
                                     parent=self):
            return
        nuevo, pasadas = combinar(actual, leido, reemplazar)
        try:
            guardar_banco(examen, nuevo, ruta_banco(examen))
        except PermissionError:
            messagebox.showerror("Excel abierto", "Cierre banco_preguntas.xlsx y vuelva a intentar.",
                                 parent=self)
            return
        self.btn_plantilla.configure(text="📥 Crear de nuevo")
        self.revisar_banco(silencioso=True)
        if messagebox.askyesno("Listo", f"Se pasaron {pasadas} preguntas al banco.\n\n¿Abrir "
                               "el editor para revisarlas?", parent=self):
            self.abrir_editor()

    def crear_excel(self) -> None:
        examen = self.selector.examen
        if not examen:
            return
        ruta = ruta_banco(examen)
        if ruta.exists() and not messagebox.askyesno(
                "Crear de nuevo",
                "Ya existe un banco de preguntas para este examen.\n\n"
                "Si lo crea de nuevo, se REEMPLAZA y se pierde lo que haya escrito. "
                "¿Continuar?", icon="warning", parent=self):
            return
        try:
            crear_plantilla(examen, ruta)
        except PermissionError:
            messagebox.showerror("Excel abierto", "Cierre banco_preguntas.xlsx y vuelva a intentar.",
                                 parent=self)
            return
        self.btn_plantilla.configure(text="📥 Crear de nuevo")
        self._mostrar_banco("Excel creado. Llénelo, guárdelo y pulse «Revisar».",
                            estilos.TEXTO_SUAVE, [])
        abrir_con_el_sistema(ruta)

    def abrir_excel(self) -> None:
        examen = self.selector.examen
        if not examen:
            return
        if not ruta_banco(examen).exists():
            messagebox.showinfo("Banco de preguntas", "Primero cree el Excel con «Crear el Excel».",
                                parent=self)
            return
        abrir_con_el_sistema(ruta_banco(examen))

    def abrir_imagenes(self) -> None:
        examen = self.selector.examen
        if examen:
            carpeta = examen.carpeta_cuadernillos / CARPETA_IMAGENES
            carpeta.mkdir(parents=True, exist_ok=True)
            abrir_con_el_sistema(carpeta)

    def revisar_banco(self, silencioso: bool = False) -> None:
        examen = self.selector.examen
        if not examen or not ruta_banco(examen).exists():
            return
        self.winfo_toplevel().configure(cursor="watch")
        self.update_idletasks()
        try:
            self.banco = leer_banco(examen, ruta_banco(examen))
        finally:
            self.winfo_toplevel().configure(cursor="")
        total = examen.total_preguntas
        if self.banco.completo:
            self._mostrar_banco(f"✔ Las {total} preguntas están completas"
                                + (f" · {len(self.banco.contextos)} textos compartidos"
                                   if self.banco.contextos else ""),
                                estilos.VERDE_OSCURO, [])
        else:
            n = len(self.banco.problemas)
            self._mostrar_banco(f"⚠ Hay {n} cosa(s) por completar en el Excel:", estilos.ROJO,
                                self.banco.problemas)

    def _mostrar_banco(self, texto: str, color: str, problemas: list[str]) -> None:
        self.lbl_banco.configure(text=texto, fg=color)
        self.lista_problemas.delete(0, "end")
        if problemas:
            for p in problemas:
                self.lista_problemas.insert("end", f" {p}")
            self.lista_problemas.pack(fill="x", pady=(2, 0))
        else:
            self.lista_problemas.pack_forget()

    # ======================================================================
    # Generar
    # ======================================================================
    def generar(self) -> None:
        examen = self.selector.examen
        if not examen:
            messagebox.showinfo("Falta el examen", "Primero cree la hoja en la pestaña 1.",
                                parent=self)
            return
        if not ruta_banco(examen).exists():
            messagebox.showinfo("Falta el banco", "Primero cree y llene el Excel de preguntas.",
                                parent=self)
            return
        self.revisar_banco()
        if not self.banco.completo:
            messagebox.showwarning("Banco incompleto",
                                   "Complete lo que falta en el Excel (está en la lista) y "
                                   "vuelva a intentar.", parent=self)
            return

        mapa = cargar_mapa(examen)
        nueva = False
        if mapa and examen.letras_formas:
            mismas = (mapa.get("barajar_preguntas") == self.var_preguntas.get()
                      and mapa.get("barajar_opciones") == self.var_opciones.get())
            if not mismas:
                nueva = True
            elif messagebox.askyesno(
                    "Orden de las formas",
                    "Los cuadernillos ya se habían generado.\n\n"
                    "• «Sí»: conservar el MISMO orden (por ejemplo, si solo corrigió un error de "
                    "digitación y ya imprimió).\n"
                    "• «No»: hacer un orden NUEVO al azar.", parent=self) is False:
                nueva = True
            if nueva and cargar_hojas(examen) and not messagebox.askyesno(
                    "Ya hay hojas leídas",
                    "Este examen ya tiene hojas leídas. Con un orden nuevo, las hojas de los "
                    "cuadernillos que ya se usaron se calificarían MAL.\n\n¿Seguro que quiere "
                    "cambiar el orden?", icon="warning", parent=self):
                return

        self.winfo_toplevel().configure(cursor="watch")
        self.lbl_estado.configure(text="Generando los cuadernillos…", fg=estilos.TEXTO_SUAVE)
        self.update_idletasks()
        try:
            resultado = generar_cuadernillos(
                examen, self.banco, self.var_preguntas.get(), self.var_opciones.get(),
                nueva_semilla=nueva, tiempo=self.var_tiempo.get().strip(),
                pagina_por_materia=self.var_pagina.get())
        except PermissionError:
            messagebox.showerror("Archivo abierto", "Cierre los cuadernillos en PDF (o el Excel de "
                                 "la clave) y vuelva a intentar.", parent=self)
            return
        except Exception as error:      # que el docente vea el problema, sin cerrar el programa
            messagebox.showerror("No se pudieron generar", str(error), parent=self)
            return
        finally:
            self.winfo_toplevel().configure(cursor="")

        formas = ", ".join(resultado.archivos)
        texto = (f"✔ Listo: {len(resultado.archivos)} cuadernillo(s) ({formas}) en la carpeta "
                 "«cuadernillos» del examen. La clave de cada forma ya quedó en «Resultados».")
        if resultado.clave_cambio:
            texto += " (Se reemplazó la clave que había.)"
        self.lbl_estado.configure(text=texto, fg=estilos.VERDE_OSCURO)
        self._actualizar_vista()

    # ======================================================================
    # Vista previa
    # ======================================================================
    def _pdf_elegido(self) -> Path | None:
        examen = self.selector.examen
        if not examen:
            return None
        letra = self.var_forma.get().replace("Forma ", "") or "A"
        ruta = examen.carpeta_cuadernillos / nombre_cuadernillo(letra)
        return ruta if ruta.exists() else None

    def _actualizar_vista(self) -> None:
        examen = self.selector.examen
        existentes = []
        if examen:
            existentes = [f"Forma {l}" for l in examen.formas_para_clave
                          if (examen.carpeta_cuadernillos / nombre_cuadernillo(l)).exists()]
        self.combo_forma.configure(values=existentes)
        if existentes and self.var_forma.get() not in existentes:
            self.var_forma.set(existentes[0])
        if not existentes:
            self.var_forma.set("")
        self._ir_a_pagina(0)

    def _ir_a_pagina(self, pagina: int) -> None:
        ruta = self._pdf_elegido()
        if ruta is None:
            self.lbl_pagina.configure(text="")
            self.visor.mostrar(None, "Aquí verá el cuadernillo cuando lo genere.")
            return
        try:
            import pymupdf as fitz
        except ImportError:
            import fitz
        with fitz.open(str(ruta)) as pdf:
            self._pagina = max(0, min(pagina, len(pdf) - 1))
            pdf[self._pagina].get_pixmap(dpi=110).save(str(self._vista))
            self.lbl_pagina.configure(text=f"Página {self._pagina + 1} de {len(pdf)}")
        self.visor.mostrar(self._vista)

    def abrir_pdf(self) -> None:
        ruta = self._pdf_elegido()
        if ruta:
            abrir_con_el_sistema(ruta)
