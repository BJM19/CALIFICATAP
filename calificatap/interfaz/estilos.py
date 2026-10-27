"""
estilos.py — Colores, letras y estilos de la interfaz.

Si quieren cambiar el aspecto de la aplicación (por ejemplo, los colores
del colegio), este es el archivo que deben tocar.
"""

import sys
import tkinter as tk
from tkinter import font as tkfont
from tkinter import ttk

# --- Paleta de colores ------------------------------------------------------
VERDE = "#1F7A4D"          # color principal (botón Generar, encabezado)
VERDE_OSCURO = "#165C3A"
VERDE_CLARO = "#E3F1E9"
ROJO = "#B3261E"
ROJO_CLARO = "#FBE9E7"
FONDO = "#F4F6F5"
FONDO_PANEL = "#FFFFFF"
TEXTO = "#1D2522"
TEXTO_SUAVE = "#5C6B64"
BORDE = "#D5DDD9"
FONDO_VISTA_PREVIA = "#E4E8E6"

# Fuente según el sistema operativo
FAMILIA = "Segoe UI" if sys.platform == "win32" else "DejaVu Sans"


def aplicar_estilos(raiz: tk.Tk) -> None:
    """Configura el tema y los estilos con nombre (Titulo.TLabel, Primario.TButton...)."""
    # Letra por defecto de todos los controles
    for nombre in ("TkDefaultFont", "TkTextFont", "TkMenuFont", "TkHeadingFont"):
        tkfont.nametofont(nombre).configure(family=FAMILIA, size=10)

    raiz.configure(bg=FONDO)
    estilo = ttk.Style(raiz)
    estilo.theme_use("clam")   # "clam" se ve igual en Windows, Linux y Mac

    estilo.configure(".", background=FONDO, foreground=TEXTO, font=(FAMILIA, 10))
    estilo.configure("TFrame", background=FONDO)
    estilo.configure("Panel.TFrame", background=FONDO_PANEL)
    estilo.configure("TLabel", background=FONDO)
    estilo.configure("Panel.TLabel", background=FONDO_PANEL)
    estilo.configure("Titulo.TLabel", font=(FAMILIA, 16, "bold"), background=FONDO)
    estilo.configure("Subtitulo.TLabel", foreground=TEXTO_SUAVE, background=FONDO)
    estilo.configure("Ayuda.TLabel", foreground=TEXTO_SUAVE, background=FONDO_PANEL,
                     font=(FAMILIA, 9))
    estilo.configure("Encabezado.TFrame", background=VERDE)
    estilo.configure("Encabezado.TLabel", background=VERDE, foreground="white",
                     font=(FAMILIA, 15, "bold"))
    estilo.configure("EncabezadoSub.TLabel", background=VERDE, foreground="#D7EDE1")

    # Secciones del formulario
    estilo.configure("Seccion.TLabelframe", background=FONDO_PANEL, bordercolor=BORDE,
                     relief="solid", borderwidth=1, padding=10)
    estilo.configure("Seccion.TLabelframe.Label", background=FONDO_PANEL,
                     foreground=VERDE_OSCURO, font=(FAMILIA, 11, "bold"))
    estilo.configure("TRadiobutton", background=FONDO_PANEL)

    # Botones
    estilo.configure("TButton", padding=(10, 5))
    estilo.configure("Primario.TButton", background=VERDE, foreground="white",
                     font=(FAMILIA, 11, "bold"), padding=(16, 9), borderwidth=0)
    estilo.map("Primario.TButton",
               background=[("disabled", "#9DB8A9"), ("active", VERDE_OSCURO)])
    estilo.configure("Pequeno.TButton", padding=(6, 3))

    # Tabla de materias
    estilo.configure("Treeview", rowheight=26, background=FONDO_PANEL,
                     fieldbackground=FONDO_PANEL)
    estilo.configure("Treeview.Heading", font=(FAMILIA, 9, "bold"))
    estilo.map("Treeview", background=[("selected", VERDE_CLARO)],
               foreground=[("selected", TEXTO)])

    # Pestañas
    estilo.configure("TNotebook", background=FONDO, borderwidth=0)
    estilo.configure("TNotebook.Tab", padding=(16, 7), font=(FAMILIA, 10, "bold"))
    estilo.map("TNotebook.Tab", background=[("selected", FONDO_PANEL)])
