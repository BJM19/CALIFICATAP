"""
CalificaTAP.pyw — Abre la aplicación con doble clic (sin ventana negra de consola).

La extensión .pyw le dice a Windows que use "pythonw", que no muestra consola.
"""

import sys
import traceback
from pathlib import Path

# Para que Python encuentre la carpeta "calificatap" aunque se abra con doble clic
sys.path.insert(0, str(Path(__file__).resolve().parent))


def avisar_error(titulo: str, mensaje: str) -> None:
    """Sin consola, los errores no se verían: los mostramos en una ventanita."""
    import tkinter as tk
    from tkinter import messagebox
    raiz = tk.Tk()
    raiz.withdraw()
    messagebox.showerror(titulo, mensaje)
    raiz.destroy()


try:
    from calificatap.interfaz.app import main
except ImportError as error:
    avisar_error(
        "Falta instalar componentes",
        f"No se encontró el componente «{error.name}».\n\n"
        "Haga doble clic en «Instalar.bat» (con internet) y vuelva a intentarlo.")
    sys.exit(1)

try:
    main()
except Exception:
    avisar_error("Error inesperado", "CalificaTAP tuvo un problema:\n\n" + traceback.format_exc()[-1500:])
    raise
