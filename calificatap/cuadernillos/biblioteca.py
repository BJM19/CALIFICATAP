"""
biblioteca.py — El banco de preguntas DEL COLEGIO.

Cada examen tiene su propio banco (banco_preguntas.xlsx). La biblioteca, en
cambio, junta las preguntas de TODOS los exámenes para reutilizarlas: se guardan
con su materia, su grado y su tema, y en un examen nuevo se traen con un clic.

Se guarda en la carpeta del programa:

    biblioteca/
    ├── biblioteca.json        ← las preguntas y los textos compartidos
    └── imagenes/              ← las imágenes (una vez cada una, por su "huella")

Una pregunta repetida (mismo enunciado, opciones e imagen) no se guarda dos veces.
"""

from __future__ import annotations

import hashlib
import json
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from .banco import Contexto, Pregunta

ARCHIVO = "biblioteca.json"


def _huella(*partes) -> str:
    """Un código corto que identifica un contenido (iguales → mismo código)."""
    h = hashlib.sha1()
    for p in partes:
        h.update(p if isinstance(p, bytes) else str(p).encode("utf-8"))
        h.update(b"|")
    return h.hexdigest()[:12]


def normalizar(texto: str) -> str:
    """'Ciencias  Naturales' → 'ciencias naturales' (sin tildes, para buscar)."""
    texto = unicodedata.normalize("NFD", (texto or "").lower())
    return " ".join("".join(c for c in texto if unicodedata.category(c) != "Mn").split())


@dataclass
class Entrada:
    """Una pregunta guardada en la biblioteca."""
    id: str
    materia: str
    grado: str = ""
    tema: str = ""
    enunciado: str = ""
    opciones: list[str] = field(default_factory=list)
    opciones_imagen: list = field(default_factory=list)   # huellas de imagen (o None)
    correcta: str = ""
    fija: bool = False
    imagen: str | None = None                              # huella de la imagen
    contexto: str | None = None                            # id del texto compartido
    origen: str = ""                                       # examen de donde salió
    agregada: str = ""
    usada_en: list[str] = field(default_factory=list)


class Biblioteca:
    def __init__(self, carpeta: str | Path):
        self.carpeta = Path(carpeta)
        self.entradas: dict[str, Entrada] = {}
        self.contextos: dict[str, dict] = {}          # {id: {"texto": ..., "imagen": huella}}
        self.cargar()

    # --- Archivo -----------------------------------------------------------
    @property
    def carpeta_imagenes(self) -> Path:
        return self.carpeta / "imagenes"

    def cargar(self) -> None:
        try:
            datos = json.loads((self.carpeta / ARCHIVO).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return
        campos = Entrada.__dataclass_fields__
        self.entradas = {e["id"]: Entrada(**{k: v for k, v in e.items() if k in campos})
                         for e in datos.get("preguntas", [])}
        self.contextos = datos.get("contextos", {})

    def guardar(self) -> None:
        self.carpeta.mkdir(parents=True, exist_ok=True)
        datos = {"preguntas": [vars(e) for e in self.entradas.values()],
                 "contextos": self.contextos}
        temporal = self.carpeta / (ARCHIVO + ".tmp")
        temporal.write_text(json.dumps(datos, ensure_ascii=False, indent=1), encoding="utf-8")
        temporal.replace(self.carpeta / ARCHIVO)

    def _guardar_imagen(self, datos: bytes | None) -> str | None:
        if not datos:
            return None
        huella = _huella(datos)
        self.carpeta_imagenes.mkdir(parents=True, exist_ok=True)
        ruta = self.carpeta_imagenes / f"{huella}.img"
        if not ruta.exists():
            ruta.write_bytes(datos)
        return huella

    def imagen(self, huella: str | None) -> bytes | None:
        if not huella:
            return None
        try:
            return (self.carpeta_imagenes / f"{huella}.img").read_bytes()
        except OSError:
            return None

    # --- Agregar -----------------------------------------------------------
    def agregar(self, p: Pregunta, materia: str, grado: str, tema: str, origen: str,
                contexto: Contexto | None = None) -> tuple[str, bool]:
        """Guarda una pregunta. Devuelve (id, es_nueva)."""
        imagen = self._guardar_imagen(p.imagen)
        imagenes_op = [self._guardar_imagen(p.imagen_de_opcion(i)) for i in range(len(p.opciones))]
        id_ctx = None
        if contexto and (contexto.texto or contexto.imagen):
            imagen_ctx = self._guardar_imagen(contexto.imagen)
            id_ctx = "c_" + _huella(contexto.texto, imagen_ctx or "")
            self.contextos.setdefault(id_ctx, {"texto": contexto.texto, "imagen": imagen_ctx})
        ident = "p_" + _huella(normalizar(materia), p.enunciado, p.opciones, imagen or "",
                               imagenes_op, id_ctx or "")
        if ident in self.entradas:
            e = self.entradas[ident]
            e.correcta, e.fija = p.correcta, p.fija               # por si se corrigió
            if tema:
                e.tema = tema
            return ident, False
        self.entradas[ident] = Entrada(
            ident, materia, grado, tema, p.enunciado, list(p.opciones),
            imagenes_op if any(imagenes_op) else [], p.correcta, p.fija, imagen, id_ctx, origen,
            datetime.now().isoformat(timespec="seconds"))
        return ident, True

    # --- Buscar ------------------------------------------------------------
    def materias(self) -> list[str]:
        return sorted({e.materia for e in self.entradas.values()}, key=normalizar)

    def temas(self, materia: str | None = None) -> list[str]:
        return sorted({e.tema for e in self.entradas.values() if e.tema
                       and (not materia or normalizar(e.materia) == normalizar(materia))},
                      key=normalizar)

    def grados(self) -> list[str]:
        return sorted({e.grado for e in self.entradas.values() if e.grado},
                      key=lambda g: (len(g), g))

    def buscar(self, materia: str = "", grado: str = "", tema: str = "",
               texto: str = "") -> list[Entrada]:
        texto_n = normalizar(texto)
        resultado = []
        for e in self.entradas.values():
            if materia and normalizar(e.materia) != normalizar(materia):
                continue
            if grado and e.grado != grado:
                continue
            if tema and normalizar(e.tema) != normalizar(tema):
                continue
            if texto_n:
                todo = normalizar(" ".join([e.enunciado, e.tema, *e.opciones,
                                             self.contextos.get(e.contexto or "", {}).get("texto", "")]))
                if texto_n not in todo:
                    continue
            resultado.append(e)
        return resultado

    def del_mismo_texto(self, entrada: Entrada) -> list[Entrada]:
        """Todas las preguntas que comparten el texto de 'entrada', en su orden."""
        if not entrada.contexto:
            return [entrada]
        return [e for e in self.entradas.values() if e.contexto == entrada.contexto]

    # --- Llevar a un examen ------------------------------------------------
    def a_pregunta(self, entrada: Entrada, etiqueta: str) -> tuple[Pregunta, Contexto | None]:
        """Convierte una entrada en una Pregunta del banco del examen (y su texto compartido)."""
        p = Pregunta(etiqueta, etiqueta.split("_")[0], entrada.enunciado, list(entrada.opciones),
                     entrada.correcta, "", self.imagen(entrada.imagen), entrada.fija,
                     opciones_imagen=[self.imagen(h) for h in entrada.opciones_imagen])
        contexto = None
        if entrada.contexto and entrada.contexto in self.contextos:
            datos = self.contextos[entrada.contexto]
            contexto = Contexto(entrada.contexto, datos.get("texto", ""),
                                self.imagen(datos.get("imagen")))
        return p, contexto

    def marcar_uso(self, ids: list[str], examen: str) -> None:
        for i in ids:
            if i in self.entradas and examen not in self.entradas[i].usada_en:
                self.entradas[i].usada_en.append(examen)

    def eliminar(self, ids: list[str]) -> None:
        for i in ids:
            self.entradas.pop(i, None)
        usados = {e.contexto for e in self.entradas.values()}
        self.contextos = {k: v for k, v in self.contextos.items() if k in usados}
