"""
compartir.py — Exportar e importar un examen completo en un solo archivo .zip.

Sirve para:
    - pasarle el examen a otro docente (por ejemplo, uno crea la hoja y otro
      califica en otra sede);
    - llevarlo en una USB de un computador a otro;
    - guardar una copia de seguridad.

El .zip contiene la carpeta del examen tal cual está dentro de "salidas/",
más un pequeño archivo de información (calificatap.json).
"""

from __future__ import annotations

import json
import shutil
import zipfile
from datetime import datetime
from pathlib import Path, PurePosixPath

from .examenes import Examen, listar_examenes

INFO = "calificatap.json"

# Archivos del DISEÑO: sin ellos el examen no se puede leer
DISENO = {"examen.json", "config.json", "omr_marker.jpg", "hoja_respuestas.pdf"}
# Clave, lista y escala: lo que necesita otro docente para calificar
CLAVE_Y_LISTA = {"clave.json", "estudiantes.csv", "escala.json", "hojas_con_nombre.pdf"}


class ErrorAlCompartir(Exception):
    """Problema al exportar o importar (con un mensaje para el docente)."""


class ExamenYaExiste(Exception):
    """Al importar: ya hay un examen con esa carpeta."""

    def __init__(self, carpeta: Path):
        super().__init__(carpeta.name)
        self.carpeta = carpeta


def _incluir(relativa: PurePosixPath, clave_y_lista: bool, resultados: bool) -> bool:
    """¿Este archivo del examen va en el .zip?"""
    partes = relativa.parts
    if partes[0].startswith("anterior_") or "_trabajo" in partes:
        return False                    # copias viejas y archivos temporales: no
    nombre = relativa.name
    if len(partes) == 1 and (nombre in DISENO or nombre.startswith("template")
                             or nombre.startswith("verificacion")):
        return True
    if len(partes) == 1 and nombre in CLAVE_Y_LISTA:
        return clave_y_lista
    # Lo leído (lecturas/...) y los reportes (resultados.xlsx, boletines.pdf)
    return resultados


def exportar_examen(examen: Examen, ruta_zip: str | Path, clave_y_lista: bool = True,
                    resultados: bool = True) -> Path:
    """Empaqueta la carpeta del examen en un .zip. Devuelve la ruta del archivo."""
    ruta_zip = Path(ruta_zip)
    base = examen.carpeta
    info = {"programa": "CalificaTAP", "examen": examen.nombre, "grado": examen.grado,
            "carpeta": base.name, "codigo_examen": examen.codigo,
            "exportado": datetime.now().isoformat(timespec="seconds"),
            "incluye_clave_y_lista": clave_y_lista, "incluye_resultados": resultados}
    with zipfile.ZipFile(ruta_zip, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr(f"{base.name}/{INFO}", json.dumps(info, indent=2, ensure_ascii=False))
        for archivo in sorted(base.rglob("*")):
            if archivo.is_file():
                relativa = PurePosixPath(archivo.relative_to(base).as_posix())
                if _incluir(relativa, clave_y_lista, resultados):
                    z.write(archivo, f"{base.name}/{relativa}")
    return ruta_zip


def leer_info(ruta_zip: str | Path) -> dict:
    """Revisa que el .zip sea un examen de CalificaTAP y devuelve su información."""
    try:
        with zipfile.ZipFile(ruta_zip) as z:
            nombres = z.namelist()
            raices = {PurePosixPath(n).parts[0] for n in nombres if n.strip("/")}
            # Seguridad: nada de rutas absolutas ni "../" (que escribirían fuera de salidas)
            if any(n.startswith("/") or ".." in PurePosixPath(n).parts or ":" in n for n in nombres):
                raise ErrorAlCompartir("El archivo tiene rutas no permitidas.")
            if len(raices) != 1:
                raise ErrorAlCompartir("El archivo no tiene el formato de un examen de CalificaTAP.")
            raiz = raices.pop()
            if f"{raiz}/examen.json" not in nombres or f"{raiz}/template.json" not in nombres:
                raise ErrorAlCompartir("Al archivo le falta el diseño del examen "
                                       "(examen.json o template.json).")
            info = {}
            if f"{raiz}/{INFO}" in nombres:
                info = json.loads(z.read(f"{raiz}/{INFO}").decode("utf-8"))
            examen = json.loads(z.read(f"{raiz}/examen.json").decode("utf-8"))
    except zipfile.BadZipFile as error:
        raise ErrorAlCompartir("El archivo no es un .zip válido.") from error
    info.setdefault("examen", examen.get("examen", {}).get("nombre", raiz))
    info.setdefault("grado", examen.get("examen", {}).get("grado", ""))
    info["carpeta"] = raiz
    info["codigo_examen"] = examen.get("codigo_examen")
    return info


def importar_examen(ruta_zip: str | Path, carpeta_salidas: str | Path,
                    modo: str = "nuevo") -> tuple[Path, list[str]]:
    """
    Copia el examen del .zip dentro de "salidas".
        modo="nuevo"      → si ya existe, lanza ExamenYaExiste (para preguntar al docente)
        modo="reemplazar" → el examen actual se guarda en salidas/_respaldos/ y se reemplaza
        modo="copia"      → se importa con otro nombre de carpeta (…_2)
    Devuelve (carpeta_importada, avisos).
    """
    info = leer_info(ruta_zip)
    salidas = Path(carpeta_salidas)
    salidas.mkdir(parents=True, exist_ok=True)
    destino = salidas / info["carpeta"]
    avisos = []

    if destino.exists():
        if modo == "nuevo":
            raise ExamenYaExiste(destino)
        if modo == "reemplazar":
            respaldo = salidas / "_respaldos" / f"{destino.name}_{datetime.now():%Y-%m-%d_%H%M%S}"
            respaldo.parent.mkdir(exist_ok=True)
            shutil.move(str(destino), str(respaldo))
            avisos.append(f"El examen que había se guardó en «_respaldos/{respaldo.name}».")
        else:   # copia
            n = 2
            while (salidas / f"{info['carpeta']}_{n}").exists():
                n += 1
            destino = salidas / f"{info['carpeta']}_{n}"

    with zipfile.ZipFile(ruta_zip) as z:
        for miembro in z.infolist():
            partes = PurePosixPath(miembro.filename).parts
            if miembro.is_dir() or len(partes) < 2 or partes[-1] == INFO:
                continue
            salida = destino.joinpath(*partes[1:])
            salida.parent.mkdir(parents=True, exist_ok=True)
            with z.open(miembro) as origen, open(salida, "wb") as f:
                shutil.copyfileobj(origen, f)

    # ¿Otro examen ya usa el mismo código? (entonces el lector no podría distinguirlos)
    codigo = info.get("codigo_examen")
    for otro in listar_examenes(salidas):
        if otro.carpeta != destino and codigo and otro.codigo == codigo:
            avisos.append(f"Ojo: «{otro.nombre_visible}» tiene el mismo código de examen. "
                          "Si son el mismo examen, puede borrar uno de los dos.")
    return destino, avisos
