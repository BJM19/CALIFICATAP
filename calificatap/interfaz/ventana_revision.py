"""
ventana_revision.py — Revisión rápida de las hojas "para revisar" (amarillas).

En lugar de abrir cada hoja y buscar el problema, esta ventana muestra UNO
POR UNO los puntos dudosos, con la parte de la imagen AMPLIADA:

    ┌───────────────────────────────────────────────────────────────┐
    │ Revisión 3 de 21  ██████░░░░░░░░░░                            │
    │ Camila Herrera Rojas · 1155921295 · curso_escaneado.pdf (p. 3)│
    │ ┌───────────────────────────────────────────────────────────┐ │
    │ │   16. ○ ○ ○ ○                                             │ │
    │ │   17. ● ○ ● ○   ← la pregunta dudosa, ampliada            │ │
    │ │   18. ○ ● ○ ○                                             │ │
    │ └───────────────────────────────────────────────────────────┘ │
    │ Pregunta 17 · Matemáticas — se leyó A y C (doble marca)       │
    │   [ A ]  [ B ]  [ C ]  [ D ]  [ En blanco ]                   │
    │ [← Anterior] [Saltar →] [Abrir la hoja completa]   [Terminar] │
    └───────────────────────────────────────────────────────────────┘

Teclado: la letra elige la opción, espacio = en blanco, ← → para moverse.

¿CÓMO SABE DÓNDE RECORTAR?
    Las imágenes que guarda el lector ya están "enderezadas" por OMRChecker y
    tienen el mismo tamaño que la página de la plantilla (pageDimensions). Así,
    las coordenadas de template.json sirven directamente para recortar.
"""

from __future__ import annotations

import json
import tkinter as tk
from dataclasses import dataclass
from tkinter import ttk

from PIL import Image, ImageDraw, ImageTk

from ..generador.plantilla_omr import nombre_plantilla
from ..lector.hojas import ERROR, REVISAR, normalizar_documento
from . import estilos

COLOR_MARCO = (230, 120, 0)        # naranja: el recuadro de la pregunta dudosa


# ---------------------------------------------------------------------------
# 1. Dónde está cada burbuja (a partir de template.json)
# ---------------------------------------------------------------------------
def caja_de_campos(template: dict, etiquetas: set[str]) -> tuple[int, int, int, int] | None:
    """
    Rectángulo (x0, y0, x1, y1) que encierra todas las burbujas de las 'etiquetas'
    (por ejemplo {"MAT_17"} o las cifras del documento doc01..doc10).

    En un bloque "horizontal" (una pregunta por fila) la burbuja i del campo k está en
        x = origen_x + i · bubblesGap      y = origen_y + k · labelsGap
    En uno "vertical" (el documento: una cifra por columna) es al revés.
    """
    ancho_b, alto_b = template["bubbleDimensions"]
    xs, ys = [], []
    for bloque in template["fieldBlocks"].values():
        campos = bloque["fieldLabels"]
        n_valores = len(bloque["bubbleValues"])
        ox, oy = bloque["origin"]
        for k, etiqueta in enumerate(campos):
            if etiqueta not in etiquetas:
                continue
            for i in (0, n_valores - 1):              # primera y última burbuja bastan
                if bloque.get("direction", "horizontal") == "horizontal":
                    x, y = ox + i * bloque["bubblesGap"], oy + k * bloque["labelsGap"]
                else:
                    x, y = ox + k * bloque["labelsGap"], oy + i * bloque["bubblesGap"]
                xs += [x, x + ancho_b]
                ys += [y, y + alto_b]
    if not xs:
        return None
    return int(min(xs)), int(min(ys)), int(max(xs)), int(max(ys))


# ---------------------------------------------------------------------------
# 2. La lista de cosas por revisar
# ---------------------------------------------------------------------------
@dataclass
class Punto:
    """Una cosa por revisar en una hoja."""
    hoja: object              # HojaLeida
    tipo: str                 # "pregunta" | "documento" | "forma"
    etiqueta: str = ""        # MAT_17 (si es una pregunta)


def puntos_por_revisar(hojas: list, nombres: dict[str, str]) -> list[Punto]:
    """
    Recorre las hojas en orden y arma la lista de puntos dudosos:
        - hojas amarillas: forma sin marcar, documento incompleto, preguntas con doble marca;
        - cualquier hoja leída cuyo documento no esté en la lista del curso.
    """
    puntos = []
    for h in hojas:
        if h.estado == ERROR:
            continue                       # las rojas se corrigen con la hoja completa
        documento = normalizar_documento(h.documento)
        if h.estado == REVISAR and h.letras_forma and h.forma not in h.letras_forma:
            puntos.append(Punto(h, "forma"))
        if h.documento_incompleto() or (nombres and documento not in nombres):
            puntos.append(Punto(h, "documento"))
        if h.estado == REVISAR:
            puntos += [Punto(h, "pregunta", e) for e in h.doble_marca()]
    return puntos


# ---------------------------------------------------------------------------
# 3. La ventana
# ---------------------------------------------------------------------------
class VentanaRevision(tk.Toplevel):
    ZOOM = 2.6                 # cuánto se amplía el recorte de una pregunta

    def __init__(self, padre, examen, hojas: list, nombres: dict[str, str], al_cambiar):
        super().__init__(padre)
        self.title("Revisión rápida")
        self.geometry("920x680")
        self.minsize(760, 560)
        self.configure(bg=estilos.FONDO)
        self.transient(padre.winfo_toplevel())
        self.examen, self.nombres = examen, nombres
        self.al_cambiar = al_cambiar        # guarda y refresca la tabla de «Leer hojas»
        self.puntos = puntos_por_revisar(hojas, nombres)
        self.indice = 0
        self.resueltos: set[int] = set()
        self.numeros = examen.numeros_impresos()
        self.materia_de = {e: m for m in examen.materias for e in m.etiquetas()}
        self._plantillas: dict[int, dict] = {}
        self._imagenes: dict[str, Image.Image] = {}
        self._foto = None
        self._construir()
        self._mostrar()
        self.grab_set()
        self.focus_set()

    # --- Construcción ------------------------------------------------------
    def _construir(self) -> None:
        caja = ttk.Frame(self, padding=14)
        caja.pack(fill="both", expand=True)

        arriba = ttk.Frame(caja)
        arriba.pack(fill="x")
        self.lbl_progreso = ttk.Label(arriba, style="Titulo.TLabel")
        self.lbl_progreso.pack(side="left")
        self.barra = ttk.Progressbar(arriba, length=260, maximum=max(1, len(self.puntos)))
        self.barra.pack(side="right")
        self.lbl_hoja = ttk.Label(caja, style="Subtitulo.TLabel")
        self.lbl_hoja.pack(anchor="w", pady=(2, 8))

        # Abajo primero (para que la imagen no los tape al encoger la ventana)
        navegacion = ttk.Frame(caja)
        navegacion.pack(side="bottom", fill="x", pady=(10, 0))
        ttk.Button(navegacion, text="← Anterior", command=self.anterior).pack(side="left")
        ttk.Button(navegacion, text="Saltar →", command=self.siguiente).pack(side="left", padx=6)
        ttk.Button(navegacion, text="Abrir la hoja completa…",
                   command=self._abrir_completa).pack(side="left", padx=(12, 0))
        ttk.Button(navegacion, text="Terminar", style="Primario.TButton",
                   command=self.destroy).pack(side="right")
        ttk.Label(caja, style="Subtitulo.TLabel",
                  text="Teclado: la letra elige la opción · espacio = en blanco · "
                       "← → para moverse · Esc para salir").pack(side="bottom", anchor="w")

        self.zona_respuesta = ttk.Frame(caja)
        self.zona_respuesta.pack(side="bottom", fill="x", pady=(8, 0))
        self.lbl_pregunta = tk.Label(caja, bg=estilos.FONDO, fg=estilos.TEXTO, anchor="w",
                                     justify="left", font=(estilos.FAMILIA, 12, "bold"))
        self.lbl_pregunta.pack(side="bottom", fill="x", pady=(8, 0))

        self.lienzo = tk.Label(caja, bg=estilos.FONDO_VISTA_PREVIA, relief="flat")
        self.lienzo.pack(fill="both", expand=True)

        self.bind("<Key>", self._tecla)
        self.bind("<Left>", lambda e: self.anterior())
        self.bind("<Right>", lambda e: self.siguiente())
        self.bind("<Escape>", lambda e: self.destroy())

    # --- Recortes ------------------------------------------------------------
    def _plantilla(self, hoja: int) -> dict:
        if hoja not in self._plantillas:
            ruta = self.examen.carpeta / nombre_plantilla(hoja)
            self._plantillas[hoja] = json.loads(ruta.read_text(encoding="utf-8"))
        return self._plantillas[hoja]

    def _imagen(self, h) -> Image.Image | None:
        if h.imagen not in self._imagenes:
            try:
                self._imagenes[h.imagen] = Image.open(self.examen.carpeta / h.imagen).convert("RGB")
            except OSError:
                return None
        return self._imagenes[h.imagen]

    def _recorte(self, punto: Punto) -> Image.Image | None:
        """La parte de la imagen donde está el punto dudoso, ampliada y con un marco."""
        h = punto.hoja
        imagen = self._imagen(h)
        if imagen is None:
            return None
        template = self._plantilla(h.hoja)
        if punto.tipo == "pregunta":
            etiquetas = {punto.etiqueta}
        elif punto.tipo == "forma":
            etiquetas = {"forma"}
        else:
            etiquetas = {e for b in template["fieldBlocks"].values()
                         for e in b["fieldLabels"] if e.startswith(("doc", "lis"))}
        caja = caja_de_campos(template, etiquetas)
        if caja is None:
            return None
        x0, y0, x1, y1 = caja
        alto_b = template["bubbleDimensions"][1]
        # Margen: a la izquierda cabe el número impreso; arriba y abajo, las preguntas vecinas
        if punto.tipo == "pregunta":
            margen = (60, int(alto_b * 2.2), 20, int(alto_b * 2.2))
            zoom = self.ZOOM
        else:
            margen = (40, 40, 20, 20)
            zoom = min(self.ZOOM, 380 / max(1, (y1 - y0 + 60)), 820 / max(1, (x1 - x0 + 60)))
        recorte = imagen.crop((max(0, x0 - margen[0]), max(0, y0 - margen[1]),
                               min(imagen.width, x1 + margen[2]),
                               min(imagen.height, y1 + margen[3])))
        dibujo = ImageDraw.Draw(recorte)
        dx, dy = max(0, x0 - margen[0]), max(0, y0 - margen[1])
        dibujo.rectangle((x0 - dx - 6, y0 - dy - 4, x1 - dx + 6, y1 - dy + 4),
                         outline=COLOR_MARCO, width=2)
        return recorte.resize((int(recorte.width * zoom), int(recorte.height * zoom)),
                              Image.LANCZOS)

    # --- Mostrar un punto ----------------------------------------------------
    def _mostrar(self) -> None:
        for hijo in self.zona_respuesta.winfo_children():
            hijo.destroy()
        total = len(self.puntos)
        if not total:
            self.lbl_progreso.configure(text="No hay nada por revisar")
            self.lbl_hoja.configure(text="Todas las hojas están listas.")
            self.lbl_pregunta.configure(text="")
            self.lienzo.configure(image="", text="✔", font=(estilos.FAMILIA, 48))
            return
        if self.indice >= total:
            self._mostrar_final()
            return
        punto = self.puntos[self.indice]
        h = punto.hoja
        self.lbl_progreso.configure(text=f"Revisión {self.indice + 1} de {total}")
        self.barra.configure(value=len(self.resueltos))
        nombre = self.nombres.get(normalizar_documento(h.documento), "")
        ident = (f"N.º {h.documento}" if h.por_lista and h.documento else h.documento)
        self.lbl_hoja.configure(text=" · ".join(x for x in (nombre, ident, h.origen) if x))

        recorte = self._recorte(punto)
        if recorte is not None:
            self._foto = ImageTk.PhotoImage(recorte)
            self.lienzo.configure(image=self._foto, text="")
        else:
            self.lienzo.configure(image="", text="(no se encontró la imagen de la hoja)",
                                  font=(estilos.FAMILIA, 11))

        if punto.tipo == "pregunta":
            self._mostrar_pregunta(punto)
        elif punto.tipo == "forma":
            self._mostrar_forma(punto)
        else:
            self._mostrar_documento(punto)

    def _boton_opcion(self, texto: str, accion) -> None:
        tk.Button(self.zona_respuesta, text=texto, command=accion, width=4 if len(texto) == 1 else 10,
                  font=(estilos.FAMILIA, 14, "bold"), bg=estilos.FONDO_PANEL, fg=estilos.TEXTO,
                  activebackground=estilos.VERDE_CLARO, relief="solid", bd=1,
                  cursor="hand2").pack(side="left", padx=4)

    def _mostrar_pregunta(self, punto: Punto) -> None:
        h, e = punto.hoja, punto.etiqueta
        materia = self.materia_de[e]
        leida = h.respuestas.get(e, "")
        if len(leida) > 1:
            detalle = f"se leyó {' y '.join(leida)} (doble marca)"
        else:
            detalle = f"ya quedó: {leida or 'en blanco'}"
        self.lbl_pregunta.configure(
            text=f"Pregunta {self.numeros[e]} · {materia.nombre} — {detalle}. ¿Qué marcó?")
        for letra in "ABCDEFGH"[:materia.opciones_de(e)]:
            self._boton_opcion(letra, lambda l=letra: self._responder(l))
        self._boton_opcion("En blanco", lambda: self._responder(""))
        ttk.Label(self.zona_respuesta, style="Subtitulo.TLabel", wraplength=250, justify="left",
                  text="Si de verdad marcó dos, elija «En blanco» (no se califica).").pack(
            side="left", padx=10)

    def _mostrar_forma(self, punto: Punto) -> None:
        h = punto.hoja
        self.lbl_pregunta.configure(
            text=f"Forma — se leyó «{h.forma or 'nada'}». ¿Qué forma tiene la hoja?")
        for letra in h.letras_forma:
            self._boton_opcion(letra, lambda l=letra: self._responder(l))

    def _mostrar_documento(self, punto: Punto) -> None:
        h = punto.hoja
        documento = normalizar_documento(h.documento)
        que = "N.º de lista" if h.por_lista else "Documento"
        motivo = ("está incompleto" if h.documento_incompleto() else "no está en la lista del curso")
        self.lbl_pregunta.configure(text=f"{que} «{h.documento or '—'}»: {motivo}. "
                                         "Escríbalo bien y pulse Enter.")
        var = tk.StringVar(value=h.documento)
        entrada = ttk.Entry(self.zona_respuesta, textvariable=var, width=18,
                            font=(estilos.FAMILIA, 14))
        entrada.pack(side="left", padx=4)
        lbl_nombre = ttk.Label(self.zona_respuesta, style="Subtitulo.TLabel")
        lbl_nombre.pack(side="left", padx=8)

        def buscar(*_):
            nombre = self.nombres.get(normalizar_documento(var.get()), "")
            lbl_nombre.configure(text=f"→ {nombre}" if nombre else
                                 ("→ no está en la lista" if self.nombres else ""))
        var.trace_add("write", buscar)
        buscar()
        ttk.Button(self.zona_respuesta, text="Aceptar", style="Primario.TButton",
                   command=lambda: self._responder(var.get().strip())).pack(side="left", padx=8)
        entrada.bind("<Return>", lambda e: self._responder(var.get().strip()))
        entrada.focus_set()
        entrada.icursor("end")

    def _mostrar_final(self) -> None:
        hojas = len({id(p.hoja) for p in self.puntos})
        self.lbl_progreso.configure(text="¡Revisión terminada!")
        self.barra.configure(value=len(self.resueltos))
        self.lbl_hoja.configure(text=f"Se revisaron {len(self.resueltos)} de {len(self.puntos)} "
                                     f"puntos en {hojas} hoja(s).")
        self.lbl_pregunta.configure(text="Los cambios ya quedaron guardados. "
                                         "Use «← Anterior» si quiere volver a alguno.")
        self.lienzo.configure(image="", text="✔", font=(estilos.FAMILIA, 48),
                              fg=estilos.VERDE)

    # --- Respuestas y navegación ---------------------------------------------
    def _responder(self, valor: str) -> None:
        punto = self.puntos[self.indice]
        h = punto.hoja
        if punto.tipo == "pregunta":
            h.respuestas[punto.etiqueta] = valor.upper()
        elif punto.tipo == "forma":
            h.forma = valor.upper()
        else:
            h.documento = valor
        self.resueltos.add(self.indice)
        # Si ya se revisaron TODOS los puntos de esta hoja, queda como corregida (verde)
        de_esta_hoja = [i for i, p in enumerate(self.puntos) if p.hoja is h]
        if all(i in self.resueltos for i in de_esta_hoja):
            h.corregida = True
        h.actualizar_estado()
        self.al_cambiar()           # se guarda enseguida (si se cierra la ventana, no se pierde)
        self.siguiente()

    def siguiente(self) -> None:
        if self.indice < len(self.puntos):
            self.indice += 1
            self._mostrar()

    def anterior(self) -> None:
        if self.indice > 0:
            self.indice -= 1
            self._mostrar()

    def _tecla(self, evento) -> None:
        if isinstance(self.focus_get(), (ttk.Entry, tk.Entry)):
            return                  # escribiendo el documento: las letras no son atajos
        if self.indice >= len(self.puntos):
            return
        punto = self.puntos[self.indice]
        letra = (evento.char or "").upper()
        if punto.tipo == "pregunta":
            opciones = "ABCDEFGH"[:self.materia_de[punto.etiqueta].opciones_de(punto.etiqueta)]
            if letra and letra in opciones:
                self._responder(letra)
            elif evento.keysym in ("space", "0", "Delete", "BackSpace"):
                self._responder("")
        elif punto.tipo == "forma" and letra and letra in punto.hoja.letras_forma:
            self._responder(letra)

    def _abrir_completa(self) -> None:
        """Abre la ventana de corrección de siempre, con la hoja entera."""
        if self.indice >= len(self.puntos):
            return
        from .pestana_lector import VentanaCorreccion     # aquí, para no importar en círculo

        def guardada():
            self.al_cambiar()
            self._mostrar()
            self.grab_set()
        self.grab_release()
        VentanaCorreccion(self, self.examen, self.puntos[self.indice].hoja, al_guardar=guardada)
