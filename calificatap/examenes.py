"""
examenes.py — Encuentra los exámenes ya generados y sus archivos.

Cada examen generado por el Módulo 1 vive en su propia carpeta dentro de
"salidas/". Los módulos 2 y 3 guardan ahí mismo lo que producen:

    salidas/simulacro_saber_11_grado_11/
    ├── hoja_respuestas.pdf, template.json, ...   ← Módulo 1
    ├── examen.json                               ← configuración usada
    ├── lecturas/
    │   ├── respuestas.csv                        ← Módulo 2: lo leído de cada hoja
    │   └── imagenes/                             ← hojas con las marcas detectadas
    ├── clave.json                                ← Módulo 3: respuestas correctas
    ├── estudiantes.csv                           ← Módulo 3: lista del curso
    └── resultados.xlsx                           ← Módulo 3: el reporte
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass
class MateriaExamen:
    codigo: str
    nombre: str
    preguntas: int
    opciones: int
    partes: tuple = ()        # ((desde, hasta, opciones), ...) si cambia según la pregunta

    def opciones_de(self, etiqueta: str) -> int:
        """Cuántas opciones tiene una pregunta ('ING_03' → 8 si la parte 1 es A-H)."""
        numero = int(etiqueta.rsplit("_", 1)[1])
        for desde, hasta, opciones in self.partes:
            if desde <= numero <= hasta:
                return opciones
        return self.opciones

    @property
    def opciones_max(self) -> int:
        return max([self.opciones] + [o for _, _, o in self.partes])

    def etiquetas(self) -> list[str]:
        """['MAT_01', 'MAT_02', ...] — los nombres de columna de cada pregunta."""
        return [f"{self.codigo}_{n:02d}" for n in range(1, self.preguntas + 1)]


@dataclass
class Examen:
    carpeta: Path
    datos: dict                      # contenido de examen.json

    # --- Datos básicos ----------------------------------------------------
    @property
    def nombre(self) -> str:
        return self.datos["examen"]["nombre"]

    @property
    def grado(self) -> str:
        return str(self.datos["examen"]["grado"])

    @property
    def nombre_visible(self) -> str:
        """Texto para las listas desplegables: 'Simulacro Saber 11 · Grado 11'."""
        return f"{self.nombre} · Grado {self.grado}"

    @property
    def materias(self) -> list[MateriaExamen]:
        return [MateriaExamen(m["codigo"].upper(), m["nombre"], m["preguntas"], m["opciones"],
                              tuple((p["desde"], p["hasta"], p["opciones"])
                                    for p in m.get("partes") or []))
                for m in self.datos["materias"]]

    def todas_las_etiquetas(self) -> list[str]:
        return [e for m in self.materias for e in m.etiquetas()]

    @property
    def hojas(self) -> list[list[str]]:
        """Qué preguntas van en cada hoja: [[MAT_01, ...], [FIS_05, ...]] (casi siempre una)."""
        return self.datos.get("hojas") or [self.todas_las_etiquetas()]

    @property
    def numero_hojas(self) -> int:
        return len(self.hojas)

    def etiquetas_de_hoja(self, hoja: int) -> list[str]:
        return self.hojas[hoja - 1] if 1 <= hoja <= self.numero_hojas else []

    @property
    def numero_formas(self) -> int:
        return int(self.datos.get("opciones", {}).get("formas", 1) or 1)

    @property
    def letras_formas(self) -> str:
        """'AB' si hay dos formas; '' si el examen no usa formas."""
        n = self.numero_formas
        return "ABCDEFGH"[:n] if n > 1 else ""

    @property
    def formas_para_clave(self) -> str:
        """Formas que necesitan clave: 'AB'..., o 'A' si no hay formas."""
        return self.letras_formas or "A"

    @property
    def por_lista(self) -> bool:
        """True si la hoja pide el N.º de lista en vez del número de documento."""
        return (self.datos.get("documento") or {}).get("tipo") == "lista"

    @property
    def codigo(self) -> int | None:
        """Código impreso en las hojas (None en exámenes creados antes de esta función)."""
        return self.datos.get("codigo_examen")

    def numeros_impresos(self) -> dict[str, int]:
        """{etiqueta: número que aparece impreso en la hoja} (según la numeración elegida)."""
        continua = self.datos.get("opciones", {}).get("numeracion", "continua") == "continua"
        numeros, siguiente = {}, 1
        for m in self.materias:
            for n, e in enumerate(m.etiquetas(), start=1):
                numeros[e] = siguiente if continua else n
                siguiente += 1
        return numeros

    @property
    def total_preguntas(self) -> int:
        return sum(m.preguntas for m in self.materias)

    # --- Archivos ---------------------------------------------------------
    @property
    def carpeta_lecturas(self) -> Path:
        return self.carpeta / "lecturas"

    @property
    def archivo_respuestas(self) -> Path:
        return self.carpeta_lecturas / "respuestas.csv"

    @property
    def archivo_clave(self) -> Path:
        return self.carpeta / "clave.json"

    @property
    def archivo_estudiantes(self) -> Path:
        return self.carpeta / "estudiantes.csv"

    @property
    def archivo_escala(self) -> Path:
        return self.carpeta / "escala.json"

    @property
    def creado(self) -> str:
        """Fecha en que se creó el examen (para ordenarlos en el seguimiento)."""
        if self.datos.get("creado"):
            return self.datos["creado"]
        from datetime import datetime
        return datetime.fromtimestamp((self.carpeta / "template.json").stat().st_mtime).isoformat()

    @property
    def carpeta_cuadernillos(self) -> Path:
        """Banco de preguntas, cuadernillos en PDF y formas.json (Módulo 0)."""
        return self.carpeta / "cuadernillos"

    @property
    def archivo_excel(self) -> Path:
        return self.carpeta / "resultados.xlsx"


def listar_examenes(carpeta_salidas: str | Path) -> list[Examen]:
    """Todos los exámenes generados, del más reciente al más antiguo."""
    carpeta_salidas = Path(carpeta_salidas)
    examenes = []
    if not carpeta_salidas.exists():
        return examenes
    for carpeta in carpeta_salidas.iterdir():
        archivo = carpeta / "examen.json"
        if (carpeta / "template.json").exists() and archivo.exists():
            try:
                examenes.append(Examen(carpeta, json.loads(archivo.read_text(encoding="utf-8"))))
            except (ValueError, KeyError):
                continue   # carpeta dañada: la ignoramos
    examenes.sort(key=lambda e: (e.carpeta / "template.json").stat().st_mtime, reverse=True)
    return examenes
