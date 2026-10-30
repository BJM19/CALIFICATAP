"""
hojas.py — Qué se leyó de cada hoja y cómo se guarda.

Cada hoja leída se representa con un objeto HojaLeida. Todas las hojas de un
examen se guardan juntas en lecturas/respuestas.csv (se puede abrir en Excel).
"""

from __future__ import annotations

import csv
import re
from dataclasses import dataclass, field

from ..examenes import Examen

# Estados posibles de una hoja
LISTA = "lista"          # se leyó bien
REVISAR = "revisar"      # se leyó, pero algo merece una mirada (doble marca, documento raro...)
ERROR = "error"          # no se pudo leer (no se encontraron las 4 marcas)


def normalizar_documento(texto: str) -> str:
    """Deja solo los dígitos y quita los ceros a la izquierda: ' 0012345' → '12345'."""
    return re.sub(r"\D", "", str(texto)).lstrip("0")


@dataclass
class HojaLeida:
    archivo: str                     # nombre de la imagen procesada (único)
    origen: str                      # PDF que subió el docente (y página)
    documento: str = ""
    respuestas: dict[str, str] = field(default_factory=dict)   # {"MAT_01": "B", ...}
    imagen: str = ""                 # ruta de la imagen con las marcas detectadas
    estado: str = LISTA
    corregida: bool = False          # True si el docente la corrigió a mano
    forma: str = ""                  # "A", "B"... si el examen tiene formas
    motivo: str = ""                 # por qué no se pudo leer (si estado == ERROR)
    hoja: int = 1                    # qué hoja del examen es (si tiene varias)
    letras_forma: str = ""           # formas válidas del examen ("AB"); no se guarda
    etiquetas_hoja: list[str] = field(default_factory=list)   # preguntas de esta hoja; no se guarda
    por_lista: bool = False          # la hoja trae N.º de lista (1-99) y no documento; no se guarda

    # --- Revisiones automáticas -----------------------------------------
    def documento_incompleto(self) -> bool:
        """Un documento tiene al menos 5 cifras; un N.º de lista, 1 o 2 (basta con una)."""
        cifras = normalizar_documento(self.documento)
        return not cifras if self.por_lista else len(cifras) < 5

    def _propias(self) -> dict[str, str]:
        """Las respuestas de ESTA hoja (en exámenes de varias hojas, cada una tiene las suyas)."""
        if not self.etiquetas_hoja:
            return self.respuestas
        return {e: self.respuestas.get(e, "") for e in self.etiquetas_hoja}

    def sin_responder(self) -> list[str]:
        return [e for e, v in self._propias().items() if v == ""]

    def doble_marca(self) -> list[str]:
        """Preguntas con más de una burbuja rellena (OMRChecker las une: 'AB')."""
        return [e for e, v in self._propias().items() if len(v) > 1]

    def problemas(self) -> list[str]:
        """Lista de motivos para revisar la hoja, en palabras del docente."""
        if self.estado == ERROR:
            return [self.motivo or "No se encontraron las 4 marcas de las esquinas"]
        motivos = []
        if self.letras_forma and self.forma not in self.letras_forma:
            motivos.append("No marcó la forma" if not self.forma else "Forma con doble marca")
        if self.documento_incompleto():
            motivos.append("Falta el N.º de lista" if self.por_lista else "Documento incompleto")
        if self.doble_marca():
            motivos.append(f"{len(self.doble_marca())} con doble marca")
        if len(self.sin_responder()) > len(self._propias()) * 0.5:
            motivos.append("Más de la mitad sin responder")
        return motivos

    def actualizar_estado(self) -> None:
        if self.estado != ERROR:
            self.estado = REVISAR if self.problemas() and not self.corregida else LISTA


# ---------------------------------------------------------------------------
# Guardar y cargar
# ---------------------------------------------------------------------------
COLUMNAS_FIJAS = ["archivo", "origen", "documento", "hoja", "forma", "estado", "corregida",
                  "motivo", "imagen"]


def guardar_hojas(examen: Examen, hojas: list[HojaLeida]) -> None:
    examen.carpeta_lecturas.mkdir(parents=True, exist_ok=True)
    etiquetas = examen.todas_las_etiquetas()
    with open(examen.archivo_respuestas, "w", newline="", encoding="utf-8-sig") as f:
        # utf-8-sig: así Excel muestra bien las tildes al abrir el CSV
        escritor = csv.writer(f)
        escritor.writerow(COLUMNAS_FIJAS + etiquetas)
        for h in hojas:
            escritor.writerow([h.archivo, h.origen, h.documento, h.hoja, h.forma, h.estado,
                               "sí" if h.corregida else "", h.motivo, h.imagen]
                              + [h.respuestas.get(e, "") for e in etiquetas])


def cargar_hojas(examen: Examen) -> list[HojaLeida]:
    if not examen.archivo_respuestas.exists():
        return []
    etiquetas = examen.todas_las_etiquetas()
    hojas = []
    with open(examen.archivo_respuestas, newline="", encoding="utf-8-sig") as f:
        for fila in csv.DictReader(f):
            hojas.append(HojaLeida(
                archivo=fila["archivo"], origen=fila["origen"], documento=fila["documento"],
                respuestas={e: fila.get(e, "") or "" for e in etiquetas},
                imagen=fila.get("imagen", ""), estado=fila.get("estado", LISTA),
                corregida=fila.get("corregida", "") == "sí", forma=fila.get("forma", "") or "",
                motivo=fila.get("motivo", "") or "", letras_forma=examen.letras_formas,
                hoja=int(fila.get("hoja") or 1), por_lista=examen.por_lista,
                etiquetas_hoja=examen.etiquetas_de_hoja(int(fila.get("hoja") or 1))))
    return hojas


def _clave_de_hoja(h: HojaLeida) -> str:
    """
    Qué identifica a una hoja: el documento del estudiante y el número de hoja
    (un estudiante tiene una sola hoja 1, una sola hoja 2...).
    Las hojas sin documento o sin leer se identifican por su archivo.
    """
    doc = normalizar_documento(h.documento)
    return f"doc:{doc}:hoja{h.hoja}" if doc and h.estado != ERROR else f"archivo:{h.archivo}"


def combinar(existentes: list[HojaLeida],
             nuevas: list[HojaLeida]) -> tuple[list[HojaLeida], list[HojaLeida]]:
    """
    Agrega las hojas nuevas a las que ya había.
    Si un estudiante ya tenía una hoja leída (mismo documento), la nueva REEMPLAZA a
    la anterior: así, leer dos veces el mismo PDF no duplica a nadie.
    Devuelve (hojas_resultantes, hojas_reemplazadas).
    """
    por_clave = {_clave_de_hoja(h): h for h in existentes}
    reemplazadas = []
    for h in nuevas:
        clave = _clave_de_hoja(h)
        if clave in por_clave:
            reemplazadas.append(por_clave[clave])
        por_clave[clave] = h
    return list(por_clave.values()), reemplazadas
