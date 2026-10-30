"""
formulas.py — Convierte una fórmula escrita "a lo LaTeX" en una imagen.

    "x^{2} + \\frac{3}{4}"   →   x² + ¾ (dibujada como en un libro)

Usa el "mathtext" de matplotlib, que viene incluido y funciona SIN internet
(no hace falta instalar LaTeX). La imagen se pone en la pregunta del cuadernillo.
"""

from __future__ import annotations

import io

# Botones de ayuda del editor: (texto del botón, lo que se escribe)
ATAJOS = [
    ("a/b", r"\dfrac{a}{b}"), ("x²", r"x^{2}"), ("xₙ", r"x_{n}"), ("√", r"\sqrt{x}"),
    ("π", r"\pi"), ("≤", r"\leq"), ("≥", r"\geq"), ("≠", r"\neq"), ("×", r"\times"),
    ("÷", r"\div"), ("±", r"\pm"), ("°", r"^{\circ}"), ("α", r"\alpha"), ("Δ", r"\Delta"),
]


class FormulaInvalida(Exception):
    """La fórmula tiene un error de escritura (llaves sin cerrar, comando desconocido...)."""


def formula_a_png(formula: str, tamano: int = 13) -> bytes:
    """Dibuja la fórmula y devuelve la imagen PNG (fondo blanco, recortada)."""
    from matplotlib.figure import Figure      # (sin pyplot: no interfiere con las ventanas)

    formula = formula.strip().strip("$")
    if not formula:
        raise FormulaInvalida("Escriba una fórmula.")
    # fracciones grandes (como en un libro), no las pequeñitas de texto
    formula = formula.replace("\\dfrac", "\\frac").replace("\\frac", "\\dfrac")
    figura = Figure(figsize=(0.01, 0.01), dpi=200)
    figura.text(0, 0, f"${formula}$", fontsize=tamano)
    memoria = io.BytesIO()
    try:
        figura.savefig(memoria, format="png", bbox_inches="tight", pad_inches=0.06,
                       facecolor="white")
    except ValueError as error:
        raise FormulaInvalida("La fórmula tiene un error. Revise las llaves { } y los "
                              "comandos (por ejemplo \\frac{a}{b}).") from error
    return memoria.getvalue()
