"""
editor_preguntas.py — Ventana para escribir las preguntas del cuadernillo
sin abrir Excel.

    ┌──────────────────┬───────────────────────────────────┬─────────────────────┐
    │ ▾ Matemáticas 3/24│ Pregunta 4 · Matemáticas  ◀  ▶    │ Así se verá:        │
    │   ✔ 1. Una cam…   │ Texto compartido: [ninguno ▼]     │                     │
    │   ✔ 2. Si 3x+5…   │ Enunciado: [                    ] │  4. En el triángulo │
    │   ✏ 4. En el t…   │ ² ³ ½ π √ ≤ ≥ °   ∑ Fórmula       │     ...             │
    │   ○ 5.            │ Imagen: [miniatura] Pegar Archivo │  A. 10 cm           │
    │ ▸ Lectura    0/25 │ (•) A [10 cm ]  ( ) B [14 cm ]    │  B. 14 cm           │
    │                  │ [ ] Fija                          │                     │
    └──────────────────┴───────────────────────────────────┴─────────────────────┘

Todo se guarda solo en el mismo Excel del banco (banco_preguntas.xlsx): quien
prefiera Excel puede seguir usándolo. Las imágenes quedan pegadas en el Excel.
"""

from __future__ import annotations

import io
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from PIL import Image, ImageTk

from ..cuadernillos.banco import (LETRAS, Banco, Contexto, Pregunta, banco_vacio, esta_vacia,
                                  guardar_banco, leer_banco, problemas_de_contextos,
                                  problemas_de_pregunta)
from ..cuadernillos.formulas import ATAJOS, FormulaInvalida, formula_a_png
from ..cuadernillos.generar import ruta_banco
from ..cuadernillos.pdf import vista_previa_pregunta
from . import estilos

SIMBOLOS = ["²", "³", "½", "¼", "¾", "π", "√", "≤", "≥", "≠", "°", "±", "×", "÷", "→", "∞"]
ICONO = {"lista": "✔", "media": "✏", "vacia": "○"}
COLOR = {"lista": estilos.VERDE_OSCURO, "media": "#B07800", "vacia": estilos.TEXTO_SUAVE}


def leer_imagen_portapapeles() -> bytes | None:
    """La imagen copiada (captura de pantalla, imagen copiada de Word...) como PNG."""
    try:
        from PIL import ImageGrab
        contenido = ImageGrab.grabclipboard()
    except Exception:
        return None
    if isinstance(contenido, list):              # se copiaron ARCHIVOS: se usa el primero
        for ruta in contenido:
            try:
                contenido = Image.open(ruta)
                break
            except Exception:
                continue
        else:
            return None
    if not isinstance(contenido, Image.Image):
        return None
    memoria = io.BytesIO()
    contenido.convert("RGB").save(memoria, format="PNG")
    return memoria.getvalue()


def _miniatura(datos: bytes | None, alto: int = 80) -> ImageTk.PhotoImage | None:
    if not datos:
        return None
    try:
        imagen = Image.open(io.BytesIO(datos))
        imagen.thumbnail((alto * 3, alto))
        return ImageTk.PhotoImage(imagen)
    except Exception:
        return None


class EditorPreguntas(tk.Toplevel):
    def __init__(self, padre, examen, al_cerrar=None):
        super().__init__(padre)
        self.title(f"Preguntas del cuadernillo — {examen.nombre_visible}")
        self.geometry("1320x820")
        self.minsize(1100, 680)
        self.configure(bg=estilos.FONDO)
        self.transient(padre.winfo_toplevel())
        self.examen, self.al_cerrar = examen, al_cerrar
        self.ruta = ruta_banco(examen)
        self.materias = {m.codigo: m for m in examen.materias}
        self.numeros = examen.numeros_impresos()
        self.orden = examen.todas_las_etiquetas()
        self.actual: str | None = None
        self._cargando = False
        self._sucio = False
        self._id_guardar = self._id_vista = None
        self._fotos = {}
        self._ultimo_campo = None

        self.banco = self._cargar_banco()
        self._construir()
        self._llenar_arbol()
        primera = next((e for e in self.orden if self._estado(e) != "lista"), self.orden[0])
        self.ir_a(primera)
        self.protocol("WM_DELETE_WINDOW", self.cerrar)
        self.bind("<Control-v>", self._pegar_atajo, add="+")
        self.bind("<Control-V>", self._pegar_atajo, add="+")
        self.bind("<Prior>", lambda e: self.mover(-1))
        self.bind("<Next>", lambda e: self.mover(1))

    # ======================================================================
    # Datos
    # ======================================================================
    def _cargar_banco(self) -> Banco:
        if self.ruta.exists():
            banco = leer_banco(self.examen, self.ruta)
        else:
            banco = banco_vacio(self.examen)
        # que estén todas las preguntas del examen, en orden
        preguntas = {e: banco.preguntas.get(e) or Pregunta(e, e.split("_")[0]) for e in self.orden}
        return Banco(preguntas, dict(banco.contextos), [])

    def _estado(self, etiqueta: str) -> str:
        p = self.banco.preguntas[etiqueta]
        if esta_vacia(p):
            return "vacia"
        problemas = problemas_de_pregunta(p, self.materias[p.materia], self.banco.contextos)
        return "media" if problemas else "lista"

    def _guardar_ya(self) -> None:
        """Escribe el Excel (si hubo cambios)."""
        self._id_guardar = None
        if not self._sucio:
            return
        try:
            guardar_banco(self.examen, self.banco, self.ruta)
        except PermissionError:
            self._estado_barra("⚠ No se pudo guardar: cierre banco_preguntas.xlsx en Excel. "
                               "Se reintentará solo.", estilos.ROJO)
            self._id_guardar = self.after(4000, self._guardar_ya)
            return
        except Exception as error:
            self._estado_barra(f"⚠ No se pudo guardar: {error}", estilos.ROJO)
            return
        self._sucio = False
        listas = sum(1 for e in self.orden if self._estado(e) == "lista")
        aviso = problemas_de_contextos(self.examen, self.banco.preguntas)
        texto = (f"✔ Guardado {datetime.now():%H:%M} · {listas} de {len(self.orden)} preguntas "
                 "listas")
        self._estado_barra(texto + (f" · ⚠ {aviso[0]}" if aviso else ""),
                           estilos.ROJO if aviso else estilos.VERDE_OSCURO)

    def _cambio(self, *_):
        """Algo cambió en el formulario: pasar a la pregunta, programar guardado y vista previa."""
        if self._cargando or self.actual is None:
            return
        self._formulario_a_pregunta()
        self._sucio = True
        self._estado_barra("Cambios sin guardar…", estilos.TEXTO_SUAVE)
        if self._id_guardar:
            self.after_cancel(self._id_guardar)
        self._id_guardar = self.after(1500, self._guardar_ya)
        self._programar_vista()
        self._refrescar_item(self.actual)
        self._mostrar_problemas()

    # ======================================================================
    # Construcción
    # ======================================================================
    def _construir(self) -> None:
        barra = tk.Frame(self, bg=estilos.FONDO, padx=12, pady=6)
        barra.pack(side="bottom", fill="x")
        self.lbl_estado = tk.Label(barra, bg=estilos.FONDO, anchor="w",
                                   font=(estilos.FAMILIA, 9), fg=estilos.TEXTO_SUAVE)
        self.lbl_estado.pack(side="left", fill="x", expand=True)
        ttk.Button(barra, text="Cerrar", style="Primario.TButton",
                   command=self.cerrar).pack(side="right")

        division = ttk.PanedWindow(self, orient="horizontal")
        division.pack(fill="both", expand=True, padx=10, pady=(10, 0))

        # --- Izquierda: lista de preguntas ---
        izquierda = ttk.Frame(division)
        division.add(izquierda, weight=0)
        ttk.Label(izquierda, text="Preguntas", style="Titulo.TLabel").pack(anchor="w")
        ttk.Label(izquierda, style="Subtitulo.TLabel",
                  text="✔ lista · ✏ le falta algo · ○ vacía").pack(anchor="w")
        marco = ttk.Frame(izquierda)
        marco.pack(fill="both", expand=True, pady=(6, 0))
        self.arbol = ttk.Treeview(marco, show="tree", selectmode="browse")
        self.arbol.column("#0", width=270)
        barra_arbol = ttk.Scrollbar(marco, orient="vertical", command=self.arbol.yview)
        self.arbol.configure(yscrollcommand=barra_arbol.set)
        self.arbol.pack(side="left", fill="both", expand=True)
        barra_arbol.pack(side="left", fill="y")
        for estado, color in COLOR.items():
            self.arbol.tag_configure(estado, foreground=color)
        self.arbol.tag_configure("materia", font=(estilos.FAMILIA, 10, "bold"))
        self.arbol.bind("<<TreeviewSelect>>", self._elegida_en_arbol)
        ttk.Button(izquierda, text="Ir a la siguiente sin terminar →",
                   command=self.siguiente_pendiente).pack(fill="x", pady=(6, 0))

        # --- Centro: formulario ---
        centro = ttk.Frame(division, padding=(14, 0, 14, 0))
        division.add(centro, weight=1)
        fila = ttk.Frame(centro)
        fila.pack(fill="x")
        self.lbl_titulo = ttk.Label(fila, style="Titulo.TLabel")
        self.lbl_titulo.pack(side="left")
        ttk.Button(fila, text="▶", width=3, command=lambda: self.mover(1)).pack(side="right")
        ttk.Button(fila, text="◀", width=3, command=lambda: self.mover(-1)).pack(side="right")

        fila = ttk.Frame(centro)
        fila.pack(fill="x", pady=(8, 0))
        ttk.Label(fila, text="Texto compartido:").pack(side="left")
        self.var_contexto = tk.StringVar()
        self.combo_contexto = ttk.Combobox(fila, textvariable=self.var_contexto, state="readonly",
                                           width=42)
        self.combo_contexto.pack(side="left", padx=6)
        self.combo_contexto.bind("<<ComboboxSelected>>", self._cambio)
        ttk.Button(fila, text="Textos compartidos…", style="Pequeno.TButton",
                   command=self.editar_contextos).pack(side="left")

        ttk.Label(centro, text="Enunciado", font=(estilos.FAMILIA, 10, "bold")).pack(
            anchor="w", pady=(10, 2))
        self.txt_enunciado = tk.Text(centro, height=5, wrap="word", font=(estilos.FAMILIA, 11),
                                     relief="solid", bd=1, undo=True)
        self.txt_enunciado.pack(fill="x")
        self.txt_enunciado.bind("<<Modified>>", self._texto_modificado)
        self.txt_enunciado.bind("<FocusIn>", lambda e: setattr(self, "_ultimo_campo",
                                                                self.txt_enunciado))
        simbolos = ttk.Frame(centro)
        simbolos.pack(fill="x", pady=(4, 0))
        for s in SIMBOLOS:
            tk.Button(simbolos, text=s, width=2, relief="flat", bg=estilos.FONDO_PANEL,
                      font=(estilos.FAMILIA, 10), cursor="hand2",
                      command=lambda s=s: self._insertar(s)).pack(side="left", padx=1)
        ttk.Button(simbolos, text="∑ Fórmula…", style="Pequeno.TButton",
                   command=self.formula).pack(side="left", padx=(8, 0))

        fila = ttk.Frame(centro)
        fila.pack(fill="x", pady=(10, 0))
        ttk.Label(fila, text="Imagen", font=(estilos.FAMILIA, 10, "bold")).pack(side="left")
        ttk.Button(fila, text="📋 Pegar (Ctrl+V)", style="Pequeno.TButton",
                   command=self.pegar_imagen).pack(side="left", padx=(10, 4))
        ttk.Button(fila, text="📁 Archivo…", style="Pequeno.TButton",
                   command=self.imagen_archivo).pack(side="left", padx=4)
        ttk.Button(fila, text="Quitar", style="Pequeno.TButton",
                   command=self.quitar_imagen).pack(side="left", padx=4)
        self.lbl_imagen = tk.Label(centro, bg=estilos.FONDO, anchor="w", fg=estilos.TEXTO_SUAVE,
                                   font=(estilos.FAMILIA, 9))
        self.lbl_imagen.pack(fill="x", pady=(4, 0))

        ttk.Label(centro, text="Opciones (marque la correcta)",
                  font=(estilos.FAMILIA, 10, "bold")).pack(anchor="w", pady=(10, 2))
        self.marco_opciones = ttk.Frame(centro)
        self.marco_opciones.pack(fill="x")
        self.var_correcta = tk.StringVar()
        self.var_correcta.trace_add("write", self._cambio)
        self.vars_opciones: list[tk.StringVar] = []
        self.entradas_opciones: list[ttk.Entry] = []
        for i, letra in enumerate(LETRAS[:max(m.opciones for m in self.materias.values())]):
            fila = ttk.Frame(self.marco_opciones)
            ttk.Radiobutton(fila, text=f"{letra}.", value=letra,
                            variable=self.var_correcta).pack(side="left")
            var = tk.StringVar()
            var.trace_add("write", self._cambio)
            entrada = ttk.Entry(fila, textvariable=var, font=(estilos.FAMILIA, 11))
            entrada.pack(side="left", fill="x", expand=True, padx=(4, 0))
            entrada.bind("<FocusIn>", lambda e, w=entrada: setattr(self, "_ultimo_campo", w))
            self.vars_opciones.append(var)
            self.entradas_opciones.append(entrada)
            fila._letra = letra
        self.var_fija = tk.BooleanVar()
        ttk.Checkbutton(centro, variable=self.var_fija, command=self._cambio,
                        text="Fija: no cambiar el orden de estas opciones en las otras formas"
                        ).pack(anchor="w", pady=(8, 0))
        self.lbl_problemas = tk.Label(centro, bg=estilos.FONDO, anchor="w", justify="left",
                                      wraplength=520, font=(estilos.FAMILIA, 10))
        self.lbl_problemas.pack(fill="x", pady=(10, 0))

        # --- Derecha: vista previa ---
        derecha = ttk.Frame(division, padding=(4, 0, 0, 0))
        division.add(derecha, weight=0)
        ttk.Label(derecha, text="Así se verá en el cuadernillo", style="Subtitulo.TLabel").pack(
            anchor="w")
        lienzo = tk.Frame(derecha, bg="white", highlightthickness=1,
                          highlightbackground=estilos.BORDE, width=440)
        lienzo.pack(fill="both", expand=True, pady=(4, 0))
        lienzo.pack_propagate(False)
        self.lbl_vista = tk.Label(lienzo, bg="white", anchor="n")
        self.lbl_vista.pack(fill="both", expand=True, padx=6, pady=6)

    # ======================================================================
    # Lista de preguntas
    # ======================================================================
    def _texto_item(self, etiqueta: str) -> str:
        p = self.banco.preguntas[etiqueta]
        resumen = " ".join(p.enunciado.split())[:34] or ("(imagen)" if p.imagen else "")
        return f"{ICONO[self._estado(etiqueta)]} {self.numeros[etiqueta]}. {resumen}"

    def _llenar_arbol(self) -> None:
        self.arbol.delete(*self.arbol.get_children())
        for m in self.examen.materias:
            self.arbol.insert("", "end", iid=m.codigo, open=True, tags=("materia",))
            for e in m.etiquetas():
                self.arbol.insert(m.codigo, "end", iid=e, text=self._texto_item(e),
                                  tags=(self._estado(e),))
            self._refrescar_materia(m.codigo)

    def _refrescar_materia(self, codigo: str) -> None:
        m = self.materias[codigo]
        listas = sum(1 for e in m.etiquetas() if self._estado(e) == "lista")
        self.arbol.item(codigo, text=f"{m.nombre}   {listas}/{m.preguntas}")

    def _refrescar_item(self, etiqueta: str) -> None:
        self.arbol.item(etiqueta, text=self._texto_item(etiqueta), tags=(self._estado(etiqueta),))
        self._refrescar_materia(etiqueta.split("_")[0])

    def _elegida_en_arbol(self, _=None) -> None:
        seleccion = self.arbol.selection()
        if not seleccion or seleccion[0] == self.actual:
            return
        if seleccion[0] in self.materias:            # clic en la materia: su primera pregunta
            self.ir_a(self.materias[seleccion[0]].etiquetas()[0])
        else:
            self.ir_a(seleccion[0])

    def mover(self, paso: int) -> None:
        i = self.orden.index(self.actual) + paso
        if 0 <= i < len(self.orden):
            self.ir_a(self.orden[i])

    def siguiente_pendiente(self) -> None:
        i = self.orden.index(self.actual)
        for e in self.orden[i + 1:] + self.orden[:i]:
            if self._estado(e) != "lista":
                self.ir_a(e)
                return
        messagebox.showinfo("¡Listo!", "Todas las preguntas están completas.", parent=self)

    # ======================================================================
    # Formulario ⇄ pregunta
    # ======================================================================
    def ir_a(self, etiqueta: str) -> None:
        self.actual = etiqueta
        p = self.banco.preguntas[etiqueta]
        m = self.materias[p.materia]
        self._cargando = True
        self.lbl_titulo.configure(text=f"Pregunta {self.numeros[etiqueta]} · {m.nombre}")
        self._llenar_combo_contextos()
        self.var_contexto.set(self._texto_contexto(p.contexto) if p.contexto else "(ninguno)")
        self.txt_enunciado.delete("1.0", "end")
        self.txt_enunciado.insert("1.0", p.enunciado)
        self.txt_enunciado.edit_modified(False)
        # tantas opciones como tiene la hoja de respuestas en esta materia
        for i, fila in enumerate(self.marco_opciones.winfo_children()):
            if i < m.opciones:
                fila.pack(fill="x", pady=2)
            else:
                fila.pack_forget()
            self.vars_opciones[i].set(p.opciones[i] if i < len(p.opciones) else "")
        self.var_correcta.set(p.correcta)
        self.var_fija.set(p.fija)
        self._mostrar_imagen()
        self._cargando = False
        if self.arbol.selection() != (etiqueta,):
            self.arbol.selection_set(etiqueta)
            self.arbol.see(etiqueta)
        self._mostrar_problemas()
        self._programar_vista(inmediata=True)

    def _formulario_a_pregunta(self) -> None:
        p = self.banco.preguntas[self.actual]
        m = self.materias[p.materia]
        p.enunciado = self.txt_enunciado.get("1.0", "end").strip()
        opciones = [v.get().strip() for v in self.vars_opciones[:m.opciones]]
        while opciones and not opciones[-1]:
            opciones.pop()
        p.opciones = opciones
        p.correcta = self.var_correcta.get()
        p.fija = self.var_fija.get()
        texto = self.var_contexto.get()
        p.contexto = "" if texto == "(ninguno)" else texto.split(" · ")[0]

    def _texto_modificado(self, _=None) -> None:
        if self.txt_enunciado.edit_modified():
            self.txt_enunciado.edit_modified(False)
            self._cambio()

    def _mostrar_problemas(self) -> None:
        p = self.banco.preguntas[self.actual]
        if esta_vacia(p):
            self.lbl_problemas.configure(text="Pregunta vacía.", fg=estilos.TEXTO_SUAVE)
            return
        problemas = problemas_de_pregunta(p, self.materias[p.materia], self.banco.contextos)
        if problemas:
            self.lbl_problemas.configure(text="Falta: " + " · ".join(x.rstrip(".") for x in problemas),
                                         fg="#B07800")
        else:
            self.lbl_problemas.configure(text="✔ Pregunta lista.", fg=estilos.VERDE_OSCURO)

    def _insertar(self, simbolo: str) -> None:
        """Escribe un símbolo (², π, ≤...) donde estaba el cursor."""
        campo = self._ultimo_campo or self.txt_enunciado
        campo.insert("insert", simbolo)
        campo.focus_set()
        if campo is self.txt_enunciado:
            self._cambio()

    # ======================================================================
    # Imagen
    # ======================================================================
    def _mostrar_imagen(self) -> None:
        p = self.banco.preguntas[self.actual]
        foto = _miniatura(p.imagen)
        self._fotos["imagen"] = foto
        if foto:
            self.lbl_imagen.configure(image=foto, text="", compound="left")
        else:
            self.lbl_imagen.configure(image="", text="(sin imagen) — copie una imagen o una "
                                                     "captura y pulse Ctrl+V")

    def _poner_imagen(self, datos: bytes | None) -> None:
        self.banco.preguntas[self.actual].imagen = datos
        self._mostrar_imagen()
        self._cambio()

    def pegar_imagen(self) -> None:
        datos = leer_imagen_portapapeles()
        if datos:
            self._poner_imagen(datos)
        else:
            messagebox.showinfo("Pegar imagen", "No hay una imagen copiada.\n\nCopie una imagen "
                                "(clic derecho → Copiar imagen) o tome una captura con "
                                "Windows + Shift + S, y vuelva a intentar.", parent=self)

    def _pegar_atajo(self, _=None):
        datos = leer_imagen_portapapeles()
        if datos:
            self._poner_imagen(datos)
            return "break"
        return None                      # no era una imagen: pegado normal de texto

    def imagen_archivo(self) -> None:
        ruta = filedialog.askopenfilename(parent=self, title="Elegir imagen",
                                          filetypes=[("Imágenes", "*.png *.jpg *.jpeg *.gif *.bmp")])
        if ruta:
            self._poner_imagen(Path(ruta).read_bytes())

    def quitar_imagen(self) -> None:
        if self.banco.preguntas[self.actual].imagen:
            self._poner_imagen(None)

    def formula(self) -> None:
        VentanaFormula(self, al_aceptar=self._formula_lista)

    def _formula_lista(self, datos: bytes) -> None:
        if self.banco.preguntas[self.actual].imagen and not messagebox.askyesno(
                "Fórmula", "La pregunta ya tiene una imagen. ¿Reemplazarla por la fórmula?",
                parent=self):
            return
        self._poner_imagen(datos)

    # ======================================================================
    # Textos compartidos
    # ======================================================================
    def _texto_contexto(self, ident: str) -> str:
        ctx = self.banco.contextos.get(ident)
        if not ctx:
            return ident
        resumen = " ".join(ctx.texto.split())[:40] or "(imagen)"
        return f"{ident} · {resumen}"

    def _llenar_combo_contextos(self) -> None:
        self.combo_contexto.configure(
            values=["(ninguno)"] + [self._texto_contexto(i) for i in self.banco.contextos])

    def editar_contextos(self) -> None:
        def listo():
            self._cargando = True
            self._llenar_combo_contextos()
            p = self.banco.preguntas[self.actual]
            if p.contexto and p.contexto not in self.banco.contextos:
                p.contexto = ""
            self.var_contexto.set(self._texto_contexto(p.contexto) if p.contexto else "(ninguno)")
            self._cargando = False
            self._sucio = True
            self._cambio()
            for e in self.orden:
                self._refrescar_item(e)
        VentanaContextos(self, self.banco, al_cerrar=listo)

    # ======================================================================
    # Vista previa
    # ======================================================================
    def _programar_vista(self, inmediata: bool = False) -> None:
        if self._id_vista:
            self.after_cancel(self._id_vista)
        self._id_vista = self.after(50 if inmediata else 700, self._dibujar_vista)

    def _dibujar_vista(self) -> None:
        self._id_vista = None
        imagen = vista_previa_pregunta(self.examen, self.banco, self.actual)
        if imagen is None:
            self.lbl_vista.configure(image="", text="(no se pudo dibujar la vista previa)")
            return
        ancho = max(200, self.lbl_vista.winfo_width() - 4)
        if imagen.width > ancho:
            imagen = imagen.resize((ancho, int(imagen.height * ancho / imagen.width)), Image.LANCZOS)
        self._fotos["vista"] = ImageTk.PhotoImage(imagen)
        self.lbl_vista.configure(image=self._fotos["vista"], text="")

    def _estado_barra(self, texto: str, color: str) -> None:
        self.lbl_estado.configure(text=texto, fg=color)

    def cerrar(self) -> None:
        if self.actual and not self._cargando:
            self._formulario_a_pregunta()
        if self._id_guardar:
            self.after_cancel(self._id_guardar)
        self._guardar_ya()
        if self._sucio and not messagebox.askyesno(
                "Sin guardar", "No se pudieron guardar los últimos cambios (¿el Excel está "
                "abierto?). ¿Cerrar de todos modos?", parent=self):
            return
        self.destroy()
        if self.al_cerrar:
            self.al_cerrar()


# ---------------------------------------------------------------------------
# Ventana de textos compartidos
# ---------------------------------------------------------------------------
class VentanaContextos(tk.Toplevel):
    """Lista de textos compartidos: crear, escribir, poner imagen, eliminar."""

    def __init__(self, padre, banco: Banco, al_cerrar):
        super().__init__(padre)
        self.title("Textos compartidos")
        self.geometry("900x560")
        self.configure(bg=estilos.FONDO, padx=12, pady=12)
        self.transient(padre)
        self.banco, self.al_cerrar = banco, al_cerrar
        self.actual: str | None = None
        self._foto = None

        ttk.Label(self, wraplength=860, justify="left", style="Subtitulo.TLabel",
                  text="Un texto compartido es una lectura, tabla o gráfica que usan varias "
                       "preguntas seguidas. En el cuadernillo sale antes de ellas con «RESPONDA "
                       "LAS PREGUNTAS ... DE ACUERDO CON LA SIGUIENTE INFORMACIÓN». Después, en "
                       "cada pregunta elija el texto en «Texto compartido».").pack(anchor="w")
        cuerpo = ttk.Frame(self)
        cuerpo.pack(fill="both", expand=True, pady=(8, 0))
        izquierda = ttk.Frame(cuerpo)
        izquierda.pack(side="left", fill="y")
        self.lista = tk.Listbox(izquierda, width=34, activestyle="none", exportselection=False,
                                font=(estilos.FAMILIA, 10))
        self.lista.pack(fill="y", expand=True)
        self.lista.bind("<<ListboxSelect>>", self._elegido)
        fila = ttk.Frame(izquierda)
        fila.pack(fill="x", pady=(6, 0))
        ttk.Button(fila, text="+ Nuevo", command=self.nuevo).pack(side="left")
        ttk.Button(fila, text="Eliminar", command=self.eliminar).pack(side="left", padx=6)

        derecha = ttk.Frame(cuerpo, padding=(12, 0, 0, 0))
        derecha.pack(side="left", fill="both", expand=True)
        self.lbl_id = ttk.Label(derecha, font=(estilos.FAMILIA, 11, "bold"))
        self.lbl_id.pack(anchor="w")
        self.txt = tk.Text(derecha, wrap="word", height=12, font=(estilos.FAMILIA, 11),
                           relief="solid", bd=1, undo=True)
        self.txt.pack(fill="both", expand=True, pady=(4, 0))
        ttk.Label(derecha, style="Ayuda.TLabel",
                  text="Deje una línea en blanco entre párrafos.").pack(anchor="w")
        fila = ttk.Frame(derecha)
        fila.pack(fill="x", pady=(6, 0))
        ttk.Button(fila, text="📋 Pegar imagen", style="Pequeno.TButton",
                   command=self.pegar).pack(side="left")
        ttk.Button(fila, text="📁 Archivo…", style="Pequeno.TButton",
                   command=self.archivo).pack(side="left", padx=4)
        ttk.Button(fila, text="Quitar imagen", style="Pequeno.TButton",
                   command=lambda: self._imagen(None)).pack(side="left")
        self.lbl_imagen = tk.Label(derecha, bg=estilos.FONDO, anchor="w")
        self.lbl_imagen.pack(fill="x", pady=(4, 0))
        ttk.Button(self, text="Listo", style="Primario.TButton", command=self.cerrar).pack(
            anchor="e", pady=(10, 0))
        self.protocol("WM_DELETE_WINDOW", self.cerrar)
        self._llenar()
        if self.banco.contextos:
            self.lista.selection_set(0)
            self._elegido()
        self.grab_set()

    def _llenar(self) -> None:
        self.lista.delete(0, "end")
        for ident, ctx in self.banco.contextos.items():
            usos = sum(1 for p in self.banco.preguntas.values() if p.contexto == ident)
            resumen = " ".join(ctx.texto.split())[:22] or "(imagen)"
            self.lista.insert("end", f"{ident} · {resumen} ({usos} preg.)")

    def _guardar_actual(self) -> None:
        if self.actual and self.actual in self.banco.contextos:
            self.banco.contextos[self.actual].texto = self.txt.get("1.0", "end").strip()

    def _elegido(self, _=None) -> None:
        seleccion = self.lista.curselection()
        if not seleccion:
            return
        self._guardar_actual()
        self.actual = list(self.banco.contextos)[seleccion[0]]
        ctx = self.banco.contextos[self.actual]
        self.lbl_id.configure(text=f"Texto {self.actual}")
        self.txt.delete("1.0", "end")
        self.txt.insert("1.0", ctx.texto)
        self._mostrar_imagen()

    def _mostrar_imagen(self) -> None:
        ctx = self.banco.contextos.get(self.actual)
        self._foto = _miniatura(ctx.imagen if ctx else None, 110)
        self.lbl_imagen.configure(image=self._foto or "", text="" if self._foto else "(sin imagen)")

    def _imagen(self, datos: bytes | None) -> None:
        if self.actual:
            self.banco.contextos[self.actual].imagen = datos
            self._mostrar_imagen()

    def pegar(self) -> None:
        datos = leer_imagen_portapapeles()
        if datos:
            self._imagen(datos)
        else:
            messagebox.showinfo("Pegar imagen", "No hay una imagen copiada.", parent=self)

    def archivo(self) -> None:
        ruta = filedialog.askopenfilename(parent=self, filetypes=[("Imágenes",
                                                                   "*.png *.jpg *.jpeg *.gif *.bmp")])
        if ruta:
            self._imagen(Path(ruta).read_bytes())

    def nuevo(self) -> None:
        self._guardar_actual()
        k = 1
        while f"T{k}" in self.banco.contextos:
            k += 1
        ident = f"T{k}"
        self.banco.contextos[ident] = Contexto(ident, "")
        self._llenar()
        self.lista.selection_clear(0, "end")
        self.lista.selection_set("end")
        self._elegido()
        self.txt.focus_set()

    def eliminar(self) -> None:
        if not self.actual:
            return
        usos = sum(1 for p in self.banco.preguntas.values() if p.contexto == self.actual)
        if usos and not messagebox.askyesno(
                "Eliminar", f"{usos} pregunta(s) usan este texto. Se les quitará. ¿Continuar?",
                parent=self):
            return
        for p in self.banco.preguntas.values():
            if p.contexto == self.actual:
                p.contexto = ""
        del self.banco.contextos[self.actual]
        self.actual = None
        self.txt.delete("1.0", "end")
        self.lbl_id.configure(text="")
        self._llenar()
        self._mostrar_imagen()

    def cerrar(self) -> None:
        self._guardar_actual()
        # los textos vacíos (sin texto ni imagen) que nadie usa se borran
        for ident in [i for i, c in self.banco.contextos.items() if not c.texto and not c.imagen]:
            if not any(p.contexto == ident for p in self.banco.preguntas.values()):
                del self.banco.contextos[ident]
        self.destroy()
        self.al_cerrar()


# ---------------------------------------------------------------------------
# Ventana de fórmula
# ---------------------------------------------------------------------------
class VentanaFormula(tk.Toplevel):
    def __init__(self, padre, al_aceptar):
        super().__init__(padre)
        self.title("Insertar fórmula")
        self.configure(bg=estilos.FONDO, padx=14, pady=12)
        self.transient(padre)
        self.al_aceptar = al_aceptar
        self._datos = None
        self._foto = None
        self._id = None
        ttk.Label(self, wraplength=520, justify="left",
                  text="Escriba la fórmula con los botones o a mano. Ejemplos: x^{2} (potencia), "
                       "x_{1} (subíndice), \\frac{3}{4} (fracción), \\sqrt{x} (raíz).").pack(anchor="w")
        botones = ttk.Frame(self)
        botones.pack(fill="x", pady=(8, 4))
        for texto, codigo in ATAJOS:
            tk.Button(botones, text=texto, width=3, relief="flat", bg=estilos.FONDO_PANEL,
                      cursor="hand2", command=lambda c=codigo: self._insertar(c)).pack(side="left",
                                                                                     padx=1)
        self.var = tk.StringVar()
        self.var.trace_add("write", lambda *_: self._programar())
        entrada = ttk.Entry(self, textvariable=self.var, font=("Consolas", 12), width=50)
        entrada.pack(fill="x")
        entrada.focus_set()
        self.entrada = entrada
        self.lbl = tk.Label(self, bg="white", height=6, relief="solid", bd=1)
        self.lbl.pack(fill="x", pady=8)
        self.lbl_error = tk.Label(self, bg=estilos.FONDO, fg=estilos.ROJO, anchor="w")
        self.lbl_error.pack(fill="x")
        fila = ttk.Frame(self)
        fila.pack(fill="x")
        ttk.Button(fila, text="Usar como imagen de la pregunta", style="Primario.TButton",
                   command=self.aceptar).pack(side="right")
        ttk.Button(fila, text="Cancelar", command=self.destroy).pack(side="right", padx=6)
        self.grab_set()

    def _insertar(self, codigo: str) -> None:
        self.entrada.insert("insert", codigo)
        self.entrada.focus_set()

    def _programar(self) -> None:
        if self._id:
            self.after_cancel(self._id)
        self._id = self.after(400, self._dibujar)

    def _dibujar(self) -> None:
        self._id = None
        try:
            self._datos = formula_a_png(self.var.get())
        except FormulaInvalida as error:
            self._datos = None
            self.lbl.configure(image="")
            self.lbl_error.configure(text=str(error) if self.var.get().strip() else "")
            return
        self._foto = _miniatura(self._datos, 90)
        self.lbl.configure(image=self._foto, height=0)
        self.lbl_error.configure(text="")

    def aceptar(self) -> None:
        self._dibujar()
        if self._datos:
            self.destroy()
            self.al_aceptar(self._datos)
