"""
pestana_lector.py — Pantalla "Leer hojas" (Módulo 2).

    ┌────────────────────────────────────┬──────────────────────────┐
    │ Examen: [Simulacro Saber 11 ▼]     │                          │
    │ 1. Agregue las hojas  [PDF]        │     IMAGEN DE LA HOJA    │
    │ [ LEER HOJAS ]  ████████░░ 18/24   │   con las marcas que     │
    │ 2. Hojas leídas                    │   detectó el programa    │
    │  ✔ 1149573077  Ana Rojas           │                          │
    │  ⚠ 10705839    revisar: documento  │                          │
    │  ✘ curso.pdf (pág. 7) no se leyó   │                          │
    │ [Corregir…] [Eliminar]             │                          │
    └────────────────────────────────────┴──────────────────────────┘

La lectura tarda (unos segundos por hoja), así que se hace en un HILO aparte
(threading). Si se hiciera en el hilo principal, la ventana se congelaría.
El hilo deja mensajes de avance en una cola (queue) y la ventana los revisa
cada 200 ms con after().
"""

from __future__ import annotations

import queue
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from ..lector.hojas import (ERROR, LISTA, REVISAR, cargar_hojas, combinar, guardar_hojas,
                           normalizar_documento)
from ..lector.omr import EXTENSIONES_ADMITIDAS, ErrorDeLectura, leer_hojas
from ..reportes.estudiantes import cargar_estudiantes, nombres_por_lectura

from . import estilos
from .utilidades import MarcoDesplazable, SelectorExamen, VisorImagen
from .ventana_revision import VentanaRevision, puntos_por_revisar

ICONOS = {LISTA: "✔ Lista", REVISAR: "⚠ Revisar", ERROR: "✘ No se leyó"}
AMARILLO_CLARO = "#FFF4D6"
# Color de fondo del recuadro de observaciones, según el estado de la hoja
FONDO_ESTADO = {LISTA: estilos.VERDE_CLARO, REVISAR: AMARILLO_CLARO, ERROR: estilos.ROJO_CLARO}


class PestanaLector(ttk.Frame):
    def __init__(self, padre, raiz_proyecto: Path, var_examen: tk.StringVar):
        super().__init__(padre)
        self.raiz = raiz_proyecto
        self.pendientes: list[Path] = []      # archivos agregados que aún no se leen
        self.hojas = []                       # hojas ya leídas del examen elegido
        self.nombres: dict[str, str] = {}     # documento → nombre (si hay lista)
        self._cola: queue.Queue = queue.Queue()
        self._leyendo = False
        self._construir(var_examen)

    # ======================================================================
    # Construcción
    # ======================================================================
    def _construir(self, var_examen: tk.StringVar) -> None:
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

        # --- 1. Agregar archivos ---
        marco = ttk.LabelFrame(izquierda, text="1. Agregue las hojas diligenciadas",
                               style="Seccion.TLabelframe")
        marco.pack(fill="x")
        barra = ttk.Frame(marco, style="Panel.TFrame")
        barra.pack(fill="x")
        ttk.Button(barra, text="📄 Agregar PDF…",
                   command=self.agregar_archivos).pack(side="left")
        ttk.Button(barra, text="📁 Agregar carpeta…",
                   command=self.agregar_carpeta).pack(side="left", padx=6)
        ttk.Button(barra, text="🧪 Hojas de práctica", style="Pequeno.TButton",
                   command=self.hojas_de_practica).pack(side="left")
        ttk.Button(barra, text="Quitar", style="Pequeno.TButton",
                   command=self.quitar_pendiente).pack(side="right")
        self.lista_pendientes = tk.Listbox(marco, height=4, activestyle="none",
                                           selectbackground=estilos.VERDE_CLARO,
                                           selectforeground=estilos.TEXTO,
                                           relief="flat", highlightthickness=1,
                                           highlightbackground=estilos.BORDE)
        self.lista_pendientes.pack(fill="x", pady=(6, 2))
        ttk.Label(marco, style="Ayuda.TLabel", wraplength=500, justify="left",
                  text="Escanee todas las hojas en un PDF (blanco y negro o grises, 200–300 ppp). "
                       "Puede agregar varios PDF a la vez.").pack(anchor="w")

        # --- Botón leer + barra de avance ---
        fila = ttk.Frame(izquierda)
        fila.pack(fill="x", pady=10)
        self.btn_leer = ttk.Button(fila, text="Leer hojas", style="Primario.TButton",
                                   command=self.leer)
        self.btn_leer.pack(side="left")
        caja = ttk.Frame(fila)
        caja.pack(side="left", fill="x", expand=True, padx=(12, 0))
        self.barra = ttk.Progressbar(caja, mode="determinate")
        self.barra.pack(fill="x")
        self.lbl_avance = ttk.Label(caja, style="Subtitulo.TLabel", text="")
        self.lbl_avance.pack(anchor="w")

        botones = ttk.Frame(izquierda)
        botones.pack(side="bottom", fill="x", pady=(8, 0))   # abajo, siempre visible
        self.btn_revision = ttk.Button(botones, text="⚡ Revisión rápida",
                                       style="Primario.TButton", command=self.revision_rapida)
        self.btn_revision.pack(side="left", padx=(0, 6))
        ttk.Button(botones, text="✏ Corregir…", command=self.corregir).pack(side="left")
        ttk.Button(botones, text="Eliminar", command=self.eliminar).pack(side="left", padx=6)
        ttk.Button(botones, text="Borrar todas", command=self.borrar_todas).pack(side="left")
        ttk.Label(botones, style="Subtitulo.TLabel",
                  text="Doble clic: corregir la hoja").pack(side="right")

        # --- 2. Hojas leídas ---
        marco = ttk.LabelFrame(izquierda, text="2. Hojas leídas", style="Seccion.TLabelframe")
        marco.pack(fill="both", expand=True)
        self.lbl_resumen = ttk.Label(marco, style="Ayuda.TLabel")
        self.lbl_resumen.pack(anchor="w")
        filtro = ttk.Frame(marco, style="Panel.TFrame")
        filtro.pack(fill="x", pady=4)
        ttk.Label(filtro, text="Mostrar:", style="Panel.TLabel").pack(side="left")
        self.var_filtro = tk.StringVar(value="Todas")
        combo = ttk.Combobox(filtro, textvariable=self.var_filtro, state="readonly", width=22,
                             values=["Todas", "Solo para revisar", "Solo listas"])
        combo.pack(side="left", padx=6)
        combo.bind("<<ComboboxSelected>>", lambda e: self._llenar_tabla())

        # --- Recuadro de observaciones (debajo de la tabla) ---
        # La columna "Observaciones" de la tabla es corta; aquí se ve completo
        # lo que encontró el programa en la hoja elegida, con los números de
        # las preguntas.
        self.panel_obs = tk.Frame(marco, bg=estilos.FONDO, highlightthickness=1,
                                  highlightbackground=estilos.BORDE, padx=10, pady=6)
        self.panel_obs.pack(side="bottom", fill="x", pady=(6, 0))
        self.lbl_obs_titulo = tk.Label(self.panel_obs, bg=estilos.FONDO, fg=estilos.TEXTO,
                                       anchor="w", justify="left",
                                       font=(estilos.FAMILIA, 10, "bold"))
        self.lbl_obs_titulo.pack(fill="x")
        self.lbl_obs = tk.Label(self.panel_obs, bg=estilos.FONDO, fg=estilos.TEXTO,
                                anchor="w", justify="left", font=(estilos.FAMILIA, 10))
        self.lbl_obs.pack(fill="x")
        # El texto se acomoda al ancho del recuadro (salta de línea solo)
        self.panel_obs.bind("<Configure>", lambda e: self.lbl_obs.configure(
            wraplength=max(200, e.width - 24)))
        self._mostrar_observaciones(None)

        columnas = ("estado", "documento", "hoja", "forma", "nombre", "origen", "observaciones")
        self.tabla = ttk.Treeview(marco, columns=columnas, show="headings", height=8,
                                  selectmode="extended")
        # Solo "Observaciones" se estira cuando la ventana es más ancha
        for col, titulo, ancho, estira in [
                ("estado", "Estado", 95, False), ("documento", "Documento", 95, False),
                ("hoja", "Hoja", 45, False), ("forma", "Forma", 50, False),
                ("nombre", "Estudiante", 170, False), ("origen", "Archivo", 140, False),
                ("observaciones", "Observaciones", 240, True)]:
            self.tabla.heading(col, text=titulo)
            self.tabla.column(col, width=ancho, minwidth=45, stretch=estira)
        self.tabla.tag_configure(REVISAR, background=AMARILLO_CLARO)
        self.tabla.tag_configure(ERROR, background=estilos.ROJO_CLARO)
        barra_tabla = ttk.Scrollbar(marco, orient="vertical", command=self.tabla.yview)
        self.tabla.configure(yscrollcommand=barra_tabla.set)
        self.tabla.pack(side="left", fill="both", expand=True)
        barra_tabla.pack(side="left", fill="y")
        self.tabla.bind("<<TreeviewSelect>>", lambda e: self._mostrar_seleccionada())
        self.tabla.bind("<Configure>", lambda e: self._ajustar_observaciones())
        self.tabla.bind("<Double-Button-1>", lambda e: self.corregir())

        # --- Visor ---
        self.lbl_visor = ttk.Label(derecha, style="Subtitulo.TLabel",
                                   text="Rueda del ratón: acercar · arrastrar: mover · doble clic: ajustar")
        self.lbl_visor.pack(anchor="w")
        self.visor = VisorImagen(derecha)
        self.visor.pack(fill="both", expand=True, pady=(4, 0))

    # ======================================================================
    # Examen elegido
    # ======================================================================
    def al_mostrar(self) -> None:
        """Se llama cada vez que el docente abre esta pestaña."""
        self.selector.actualizar()
        self.cargar_examen()

    def _ajustar_observaciones(self) -> None:
        """La columna "Observaciones" ocupa todo el ancho que sobra en la tabla."""
        visibles = self.tabla.cget("displaycolumns")
        if visibles in ("#all", ("#all",)):
            visibles = self.tabla.cget("columns")
        otras = sum(self.tabla.column(c, "width") for c in visibles if c != "observaciones")
        self.tabla.column("observaciones", width=max(200, self.tabla.winfo_width() - otras - 4))

    def cargar_examen(self) -> None:
        examen = self.selector.examen
        self.hojas = cargar_hojas(examen) if examen else []
        # La columna "Forma" solo se muestra si el examen tiene formas
        columnas = ["estado", "documento", "nombre", "origen", "observaciones"]
        if examen and examen.letras_formas:
            columnas.insert(2, "forma")
        if examen and examen.numero_hojas > 1:
            columnas.insert(2, "hoja")     # solo si el examen tiene varias hojas
        self.tabla.configure(displaycolumns=columnas)
        self.tabla.heading("documento", text="N.º lista" if examen and examen.por_lista
                           else "Documento")
        self._ajustar_observaciones()
        if examen:
            # {lo que se lee en la hoja → nombre}: documento, o N.º de lista
            self.nombres = nombres_por_lectura(examen, cargar_estudiantes(examen))
        self._llenar_tabla()
        self.visor.mostrar(None, "Las hojas leídas aparecerán aquí"
                           if not self.hojas else "")

    # ======================================================================
    # Archivos pendientes
    # ======================================================================
    def _agregar(self, rutas) -> None:
        for ruta in rutas:
            ruta = Path(ruta)
            if ruta.suffix.lower() in EXTENSIONES_ADMITIDAS and ruta not in self.pendientes:
                self.pendientes.append(ruta)
                self.lista_pendientes.insert("end", f"  {ruta.name}")
        self._mostrar_avance(0, 1, f"{len(self.pendientes)} archivo(s) listos para leer"
                             if self.pendientes else "")

    def agregar_archivos(self) -> None:
        tipos = " ".join(f"*{e}" for e in sorted(EXTENSIONES_ADMITIDAS))
        self._agregar(filedialog.askopenfilenames(
            parent=self, title="Elegir los PDF del escáner",
            filetypes=[("PDF del escáner", tipos)]))

    def agregar_carpeta(self) -> None:
        carpeta = filedialog.askdirectory(parent=self, title="Elegir carpeta con las hojas")
        if carpeta:
            self._agregar(sorted(Path(carpeta).iterdir()))

    def hojas_de_practica(self) -> None:
        """Crea un curso inventado para probar el programa sin imprimir nada."""
        examen = self.selector.examen
        if not examen:
            return
        # Si el examen ya tiene lista de estudiantes, se practica con esos nombres
        lista_real = cargar_estudiantes(examen)
        lista_fija = list(zip(lista_real["documento"], lista_real["nombre"],
                              lista_real["lista"])) or None
        quienes = (f"los {len(lista_fija)} estudiantes de la lista del examen" if lista_fija
                   else "24 estudiantes inventados")
        if not messagebox.askyesno(
                "Hojas de práctica",
                f"Se creará un PDF «escaneado» con hojas llenadas al azar para {quienes}, "
                "para practicar sin imprimir.\n\n¿Crearlas?",
                parent=self):
            return
        from ..lector.practica import crear_curso_de_practica
        from ..reportes.clave import guardar_clave
        from ..reportes.estudiantes import guardar_estudiantes
        import pandas as pd

        self.winfo_toplevel().configure(cursor="watch")
        self.update_idletasks()
        try:
            destino, claves, lista = crear_curso_de_practica(
                examen, self.raiz / "escaneos" / f"practica_{examen.carpeta.name}",
                lista_fija=lista_fija)
        finally:
            self.winfo_toplevel().configure(cursor="")
        self._agregar([destino / "curso_escaneado.pdf"])
        if messagebox.askyesno(
                "Hojas de práctica listas",
                "Ya quedaron en la lista de «Agregue las hojas». Pulse «Leer hojas».\n\n"
                + ("¿Cargar también la clave correcta en «Resultados»? "
                   if lista_fija else
                   "¿Cargar también la clave correcta y la lista de estos estudiantes en "
                   "«Resultados»? ")
                + "(Si prefiere escribirla usted, está en clave_correcta.txt.)\n\n"
                "Ojo: reemplaza la clave que tenga este examen.",
                parent=self):
            guardar_clave(examen, claves)
            if not lista_fija:     # la lista real no se toca
                guardar_estudiantes(examen, pd.DataFrame(
                    [{"documento": d, "nombre": n, "curso": ""} for d, n in lista]))
            self.cargar_examen()

    def quitar_pendiente(self) -> None:
        for i in reversed(self.lista_pendientes.curselection()):
            self.lista_pendientes.delete(i)
            del self.pendientes[i]

    # ======================================================================
    # Leer (en un hilo aparte)
    # ======================================================================
    def leer(self) -> None:
        examen = self.selector.examen
        if self._leyendo:
            return
        if not examen:
            messagebox.showinfo("Falta el examen", "Primero cree una hoja en la pestaña 1.",
                                parent=self)
            return
        if not self.pendientes:
            messagebox.showinfo("Faltan las hojas",
                                "Agregue los PDF del escáner con «Agregar PDF…».",
                                parent=self)
            return
        self._leyendo = True
        self.btn_leer.state(["disabled"])
        archivos = list(self.pendientes)

        def trabajo():
            """Esto corre en el hilo aparte: NO puede tocar la ventana directamente."""
            try:
                hojas = leer_hojas(examen, archivos, self.raiz,
                                   avance=lambda h, t, m: self._cola.put(("avance", h, t, m)))
                self._cola.put(("listo", hojas))
            except ErrorDeLectura as error:
                self._cola.put(("error", str(error)))
            except Exception as error:  # cualquier otro problema
                self._cola.put(("error", f"Problema inesperado: {error}"))

        threading.Thread(target=trabajo, daemon=True).start()
        self.after(200, self._revisar_cola)

    def _revisar_cola(self) -> None:
        """Lee los mensajes que dejó el hilo y actualiza la ventana."""
        try:
            while True:
                mensaje = self._cola.get_nowait()
                if mensaje[0] == "avance":
                    self._mostrar_avance(*mensaje[1:])
                elif mensaje[0] == "listo":
                    self._lectura_terminada(mensaje[1])
                    return
                elif mensaje[0] == "error":
                    self._leyendo = False
                    self.btn_leer.state(["!disabled"])
                    self._mostrar_avance(0, 1, "")
                    messagebox.showerror("No se pudo leer", mensaje[1], parent=self)
                    return
        except queue.Empty:
            pass
        self.after(200, self._revisar_cola)

    def _mostrar_avance(self, hechas: int, total: int, texto: str) -> None:
        self.barra.configure(maximum=max(total, 1), value=hechas)
        detalle = f"  ({hechas} de {total})" if total > 1 else ""
        self.lbl_avance.configure(text=texto + detalle if texto else "")

    def _lectura_terminada(self, nuevas) -> None:
        self._leyendo = False
        self.btn_leer.state(["!disabled"])
        examen = self.selector.examen
        self.hojas, reemplazadas = combinar(self.hojas, nuevas)
        guardar_hojas(examen, self.hojas)
        self._borrar_imagenes(reemplazadas)
        self.pendientes.clear()
        self.lista_pendientes.delete(0, "end")
        self._llenar_tabla()

        ajenas = [h for h in nuevas if h.estado == ERROR and "otro examen" in h.motivo]
        malas = [h for h in nuevas if h.estado == ERROR and h not in ajenas]
        revisar = [h for h in nuevas if h.estado == REVISAR]
        leidas = len(nuevas) - len(malas) - len(ajenas)
        texto = f"Se leyeron {leidas} de {len(nuevas)} hojas."
        if reemplazadas:
            texto += (f"\n\n↻ {len(reemplazadas)} estudiante(s) ya tenían una hoja leída: "
                      "se reemplazó por la nueva (no se duplican).")
        if ajenas:
            texto += (f"\n\n✘ {len(ajenas)} hoja(s) son de OTRO examen (en rojo). "
                      "Sepárelas y léalas en el examen que les corresponde.")
        if revisar:
            texto += f"\n\n⚠ {len(revisar)} hoja(s) tienen algo para revisar (en amarillo)."
        if malas:
            texto += (f"\n\n✘ {len(malas)} hoja(s) no se pudieron leer (en rojo). "
                      "Suele pasar si la hoja entró muy torcida al escáner o se le cortó "
                      "una marca negra de las esquinas: escanéela de nuevo, o corríjala a "
                      "mano con doble clic.")
        self._mostrar_avance(1, 1, "Lectura terminada")
        messagebox.showinfo("Lectura terminada", texto, parent=self)

    # ======================================================================
    # Tabla de hojas leídas
    # ======================================================================
    def _llenar_tabla(self) -> None:
        self.tabla.delete(*self.tabla.get_children())
        self._mostrar_observaciones(None)
        filtro = self.var_filtro.get()
        for i, h in enumerate(self.hojas):
            if filtro == "Solo para revisar" and h.estado == LISTA:
                continue
            if filtro == "Solo listas" and h.estado != LISTA:
                continue
            nombre = self.nombres.get(normalizar_documento(h.documento), "")
            if not nombre and self.nombres and h.estado != ERROR:
                nombre = "⚠ no está en la lista"
            observaciones = "; ".join(h.problemas()) if h.estado != LISTA else (
                "Corregida a mano" if h.corregida else "")
            self.tabla.insert("", "end", iid=str(i), tags=(h.estado,), values=(
                ICONOS[h.estado], h.documento or "—", h.hoja, h.forma or "—", nombre, h.origen,
                observaciones))

        n = len(self.hojas)
        listas = sum(h.estado == LISTA for h in self.hojas)
        revisar = sum(h.estado == REVISAR for h in self.hojas)
        errores = sum(h.estado == ERROR for h in self.hojas)
        # El botón dice cuántas cosas hay por revisar
        pendientes = len(puntos_por_revisar(self.hojas, self.nombres))
        self.btn_revision.configure(text=f"⚡ Revisión rápida ({pendientes})" if pendientes
                                    else "⚡ Revisión rápida")
        self.btn_revision.state(["!disabled"] if pendientes else ["disabled"])
        self.lbl_resumen.configure(
            text=f"{n} hojas · ✔ {listas} listas · ⚠ {revisar} para revisar · ✘ {errores} sin leer"
            if n else "Todavía no hay hojas leídas para este examen.")

    def _hoja_seleccionada(self):
        seleccion = self.tabla.selection()
        return self.hojas[int(seleccion[0])] if seleccion else None

    def _mostrar_seleccionada(self) -> None:
        h = self._hoja_seleccionada()
        n = len(self.tabla.selection())
        self._mostrar_observaciones(h, n)
        if h:
            self.visor.mostrar(self.selector.examen.carpeta / h.imagen)
            self.lbl_visor.configure(text=f"{h.origen}  ·  rueda: acercar · arrastrar: mover · "
                                          "doble clic: ajustar")

    # ======================================================================
    # Observaciones completas de la hoja elegida
    # ======================================================================
    def _detalle_observaciones(self, h) -> list[str]:
        """Lo que encontró el programa en la hoja, en frases completas."""
        examen = self.selector.examen
        if h.estado == ERROR:
            motivo = h.motivo or "No se encontraron las 4 marcas negras de las esquinas"
            if "otro examen" in motivo:
                consejo = ("Sepárela y léala en el examen que le corresponde "
                           "(elíjalo arriba en «Examen»).")
            else:
                consejo = ("Escanéela de nuevo (derecha y con las 4 esquinas completas) o "
                           "corríjala a mano con doble clic.")
            return [motivo.rstrip(".") + ".", consejo]
        # Número de cada pregunta tal como aparece impreso en la hoja
        numeros = examen.numeros_impresos() if examen else {}
        continua = (examen.datos.get("opciones", {}).get("numeracion", "continua")
                    == "continua") if examen else True

        def numero(etiqueta: str) -> str:
            if etiqueta not in numeros:
                return etiqueta
            if continua:
                return str(numeros[etiqueta])
            return f"{etiqueta.split('_')[0]} {numeros[etiqueta]}"   # ej. "MAT 3"

        def lista_de(etiquetas: list[str], maximo: int = 20) -> str:
            texto = ", ".join(numero(e) for e in etiquetas[:maximo])
            return texto + (f" y {len(etiquetas) - maximo} más" if len(etiquetas) > maximo else "")

        lineas = []
        if h.letras_forma and h.forma not in h.letras_forma:
            lineas.append("No marcó la forma." if not h.forma
                          else f"La forma tiene doble marca ({h.forma}).")
        documento = normalizar_documento(h.documento)
        que = "N.º de lista" if h.por_lista else "Documento"
        if h.documento_incompleto():
            lineas.append(f"{que} incompleto: se leyó «{h.documento or 'nada'}». "
                          "Corríjalo con doble clic.")
        elif self.nombres and documento not in self.nombres:
            lineas.append(f"El {'N.º de lista' if h.por_lista else 'documento'} {h.documento} "
                          "no está en la lista del curso.")
        dobles = h.doble_marca()
        if dobles:
            lineas.append(f"Doble marca en {len(dobles)} pregunta(s): {lista_de(dobles)}. "
                          "Si el estudiante borró mal, corríjalas con doble clic; si de verdad "
                          "marcó dos opciones, déjelas vacías.")
        blancas = h.sin_responder()
        total = len(h._propias())
        if blancas:
            aviso = " (más de la mitad)" if len(blancas) > total * 0.5 else ""
            lineas.append(f"Sin responder: {len(blancas)} de {total}{aviso}: {lista_de(blancas)}.")
        if h.corregida:
            lineas.append("Esta hoja ya se corrigió a mano.")
        return lineas

    def _mostrar_observaciones(self, h, seleccionadas: int = 1) -> None:
        """Llena el recuadro de abajo con las observaciones de la hoja elegida."""
        if h is None or seleccionadas > 1:
            fondo = estilos.FONDO
            titulo = (f"{seleccionadas} hojas seleccionadas" if seleccionadas > 1
                      else "Observaciones")
            texto = ("Elija una sola hoja para ver sus observaciones." if seleccionadas > 1
                     else "Haga clic en una hoja para ver aquí todo lo que encontró el programa.")
        else:
            fondo = FONDO_ESTADO[h.estado]
            nombre = self.nombres.get(normalizar_documento(h.documento), "")
            quien = " · ".join(x for x in (h.documento, nombre) if x) or h.origen
            titulo = f"{ICONOS[h.estado]}  —  {quien}"
            lineas = self._detalle_observaciones(h)
            texto = ("\n".join(f"•  {linea}" for linea in lineas) if lineas
                     else "Sin observaciones: la hoja se leyó bien.")
        for w in (self.panel_obs, self.lbl_obs_titulo, self.lbl_obs):
            w.configure(bg=fondo)
        self.lbl_obs_titulo.configure(text=titulo)
        self.lbl_obs.configure(text=texto)

    def eliminar(self) -> None:
        """Quita las hojas seleccionadas (se pueden elegir varias con Ctrl o Shift)."""
        elegidas = [self.hojas[int(i)] for i in self.tabla.selection()]
        if not elegidas:
            return
        texto = (f"¿Quitar la hoja «{elegidas[0].origen}» de este examen?" if len(elegidas) == 1
                 else f"¿Quitar las {len(elegidas)} hojas seleccionadas de este examen?")
        if messagebox.askyesno("Eliminar hojas", texto, parent=self):
            self._quitar(elegidas)

    def borrar_todas(self) -> None:
        """Empieza de cero: quita todas las hojas leídas de este examen."""
        if not self.hojas:
            return
        if messagebox.askyesno(
                "Borrar todas las hojas leídas",
                f"Se quitarán las {len(self.hojas)} hojas leídas de este examen "
                "(los PDF originales NO se borran; se pueden volver a leer).\n\n"
                "¿Continuar?", parent=self):
            self._quitar(list(self.hojas))

    def _quitar(self, hojas) -> None:
        for h in hojas:
            self.hojas.remove(h)
        guardar_hojas(self.selector.examen, self.hojas)
        self._borrar_imagenes(hojas)
        self._llenar_tabla()
        self.visor.mostrar(None)

    def _borrar_imagenes(self, hojas) -> None:
        """Borra las imágenes de hojas que ya no se usan (para no llenar el disco)."""
        en_uso = {h.imagen for h in self.hojas}
        for h in hojas:
            if h.imagen and h.imagen not in en_uso:
                (self.selector.examen.carpeta / h.imagen).unlink(missing_ok=True)

    def revision_rapida(self) -> None:
        """Recorre uno por uno los puntos dudosos (doble marca, documento, forma)."""
        examen = self.selector.examen
        if not examen or not self.hojas:
            return
        VentanaRevision(self, examen, self.hojas, self.nombres, al_cambiar=self._correccion_guardada)

    def corregir(self) -> None:
        h = self._hoja_seleccionada()
        if h:
            VentanaCorreccion(self, self.selector.examen, h, al_guardar=self._correccion_guardada)

    def _correccion_guardada(self) -> None:
        guardar_hojas(self.selector.examen, self.hojas)
        seleccion = self.tabla.selection()
        self._llenar_tabla()
        if seleccion and self.tabla.exists(seleccion[0]):
            self.tabla.selection_set(seleccion[0])


class VentanaCorreccion(tk.Toplevel):
    """
    Ventana para corregir a mano una hoja: a la izquierda la imagen,
    a la derecha el documento y cada respuesta.
    Las preguntas con doble marca se pintan de amarillo y las en blanco de gris.
    """

    def __init__(self, padre, examen, hoja, al_guardar):
        super().__init__(padre)
        self.title(f"Corregir hoja — {hoja.origen}")
        self.geometry("1150x760")
        self.configure(bg=estilos.FONDO)
        self.transient(padre.winfo_toplevel())
        self.hoja, self.examen, self.al_guardar = hoja, examen, al_guardar

        division = ttk.PanedWindow(self, orient="horizontal")
        division.pack(fill="both", expand=True, padx=10, pady=10)
        visor = VisorImagen(division)
        division.add(visor, weight=1)
        visor.after(100, lambda: visor.mostrar(examen.carpeta / hoja.imagen))

        derecha = ttk.Frame(division, padding=(10, 0, 0, 0))
        division.add(derecha, weight=0)
        ttk.Label(derecha, text="Corrija lo que esté mal", style="Titulo.TLabel").pack(anchor="w")
        ttk.Label(derecha, style="Subtitulo.TLabel", wraplength=420, justify="left",
                  text="Amarillo: doble marca · Gris: en blanco. Deje vacío lo que el "
                       "estudiante no respondió.").pack(anchor="w", pady=(0, 6))

        fila = ttk.Frame(derecha)
        fila.pack(fill="x", pady=4)
        ttk.Label(fila, text="N.º de lista:" if examen.por_lista else "Documento:",
                  font=(estilos.FAMILIA, 11, "bold")).pack(side="left")
        self.var_documento = tk.StringVar(value=hoja.documento)
        ttk.Entry(fila, textvariable=self.var_documento, width=18,
                  font=(estilos.FAMILIA, 11)).pack(side="left", padx=8)
        self.var_forma = tk.StringVar(value=hoja.forma)
        if examen.letras_formas:
            ttk.Label(fila, text="Forma:", font=(estilos.FAMILIA, 11, "bold")).pack(side="left",
                                                                                   padx=(10, 0))
            ttk.Combobox(fila, textvariable=self.var_forma, width=4, state="readonly",
                         values=list(examen.letras_formas)).pack(side="left", padx=6)

        desplazable = MarcoDesplazable(derecha, width=440)
        desplazable.pack(fill="both", expand=True, pady=6)
        numeros = examen.numeros_impresos()
        self.variables: dict[str, tk.StringVar] = {}
        # En exámenes de varias hojas, solo las preguntas impresas en ESTA hoja
        propias = set(examen.etiquetas_de_hoja(hoja.hoja)) if examen.numero_hojas > 1 else None
        for m in examen.materias:
            if propias is not None and not propias & set(m.etiquetas()):
                continue
            marco = ttk.LabelFrame(desplazable.interior, text=m.nombre, style="Seccion.TLabelframe")
            marco.pack(fill="x", pady=4, padx=(0, 6))
            for k, etiqueta in enumerate(e for e in m.etiquetas()
                                         if propias is None or e in propias):
                valores = [""] + list("ABCDEFGH"[: m.opciones_de(etiqueta)])
                actual = hoja.respuestas.get(etiqueta, "")
                color = ("#FFE08A" if len(actual) > 1 else
                         "#DADFDC" if actual == "" else estilos.FONDO_PANEL)
                celda = tk.Frame(marco, bg=color, padx=3, pady=2)
                celda.grid(row=k // 3, column=k % 3, padx=2, pady=2, sticky="w")
                tk.Label(celda, text=f"{numeros[etiqueta]}.", bg=color, width=4, anchor="e",
                         font=(estilos.FAMILIA, 9, "bold")).pack(side="left")
                var = tk.StringVar(value=actual)
                ttk.Combobox(celda, textvariable=var, values=valores, width=4).pack(side="left")
                self.variables[etiqueta] = var

        botones = ttk.Frame(derecha)
        botones.pack(fill="x")
        ttk.Button(botones, text="Guardar corrección", style="Primario.TButton",
                   command=self.guardar).pack(side="right")
        ttk.Button(botones, text="Cancelar", command=self.destroy).pack(side="right", padx=6)
        self.grab_set()

    def guardar(self) -> None:
        h = self.hoja
        h.documento = self.var_documento.get().strip()
        h.forma = self.var_forma.get().strip().upper()
        for etiqueta, var in self.variables.items():
            h.respuestas[etiqueta] = var.get().strip().upper()
        h.corregida = True
        if h.estado == ERROR:
            h.estado = LISTA     # el docente la digitó a mano
        h.actualizar_estado()
        self.al_guardar()
        self.destroy()
