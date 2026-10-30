"""
calificar.py — Cruza las respuestas leídas con la clave y la lista de estudiantes.

Produce tablas (DataFrames de pandas) listas para mostrar o exportar:
    por_estudiante  → una fila por estudiante: % por materia, aciertos, nota
    por_materia     → promedio, mejor y peor resultado de cada materia
    por_pregunta    → % de acierto de cada pregunta y qué opciones se marcaron
    alertas         → cosas que el docente debe revisar

Reglas de calificación:
    - Una pregunta vale 1 si la respuesta es igual a la clave.
    - En blanco o con doble marca vale 0.
    - Nota = mínima + (máxima − mínima) × porcentaje de aciertos
      (con la escala colombiana 1,0 a 5,0: el 60 % de aciertos da 3,4).
    - Preguntas ANULADAS: "bien" = cuenta como acierto para todos;
      "excluir" = no cuenta (se califica sobre las demás).

Puntaje tipo Saber 11 (opcional, 0 a 500):
    Como en el ICFES, cada materia da un puntaje de 0 a 100 y el global es un
    promedio ponderado multiplicado por 5:
        global = 5 × (3·LC + 3·MAT + 3·SOC + 3·CN + 1·ING) / 13
    Aquí el puntaje de cada materia es su % de aciertos. El ICFES, en cambio,
    usa un modelo estadístico (Rasch) que tiene en cuenta la dificultad de cada
    pregunta, así que este puntaje es una APROXIMACIÓN para los simulacros.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field

import pandas as pd

from ..examenes import Examen
from ..lector.hojas import ERROR, HojaLeida, normalizar_documento
from .clave import cargar_anuladas


@dataclass
class Escala:
    minima: float = 1.0
    maxima: float = 5.0
    aprobacion: float = 3.0
    # Puntaje tipo Saber 11: None = automático (sí, si las materias son las del ICFES)
    puntaje_saber: bool | None = None
    pesos: dict = field(default_factory=dict)      # {código_materia: peso}

    def nota(self, proporcion: float) -> float:
        return round(self.minima + (self.maxima - self.minima) * proporcion, 1)


# Palabras que identifican las cinco pruebas del ICFES en el nombre de una materia
AREAS_SABER = {
    "lectura": ("lectura", "lenguaje", "español", "espanol", "castellano"),
    "matematicas": ("matem",),
    "sociales": ("social", "ciudadan"),
    "naturales": ("natural", "ciencias nat", "biolog", "química", "quimica", "física", "fisica"),
    "ingles": ("inglés", "ingles", "english"),
}


def area_saber(nombre_materia: str) -> str:
    """'Ciencias Naturales' → 'naturales'; una materia que no es del ICFES → ''."""
    nombre = nombre_materia.lower()
    for area, palabras in AREAS_SABER.items():
        if any(p in nombre for p in palabras):
            return area
    return ""


def es_tipo_saber(examen: Examen) -> bool:
    """¿El examen parece un simulacro Saber 11? (al menos 4 de las 5 pruebas)"""
    return len({area_saber(m.nombre) for m in examen.materias} - {""}) >= 4


def pesos_saber(examen: Examen, escala: Escala) -> dict[str, float]:
    """Peso de cada materia: el que eligió el docente o, por defecto, 1 para inglés y 3 para las demás."""
    return {m.codigo: float(escala.pesos.get(m.codigo, 1 if area_saber(m.nombre) == "ingles" else 3))
            for m in examen.materias}


def usa_puntaje_saber(examen: Examen, escala: Escala) -> bool:
    return es_tipo_saber(examen) if escala.puntaje_saber is None else escala.puntaje_saber


def puntaje_global(porcentajes: dict[str, float], pesos: dict[str, float]) -> float:
    """
    porcentajes = {código_materia: 0..100}. Devuelve el puntaje de 0 a 500.
    Las materias sin dato (sin clave) no entran en el promedio.
    """
    validos = {c: p for c, p in porcentajes.items() if not pd.isna(p) and pesos.get(c, 0) > 0}
    suma_pesos = sum(pesos[c] for c in validos)
    if not suma_pesos:
        return float("nan")
    return round(5 * sum(pesos[c] * p for c, p in validos.items()) / suma_pesos)


@dataclass
class Resultados:
    examen: Examen
    escala: Escala
    por_estudiante: pd.DataFrame
    por_materia: pd.DataFrame
    por_pregunta: pd.DataFrame
    respuestas: pd.DataFrame            # respuestas marcadas, una fila por estudiante
    aciertos: pd.DataFrame              # True/False por pregunta, misma forma que 'respuestas'
    alertas: list[tuple[str, str]] = field(default_factory=list)   # (tipo, detalle)
    formas: pd.Series = field(default_factory=pd.Series)           # forma de cada estudiante
    claves: dict = field(default_factory=dict)                     # {forma: {etiqueta: letra}}
    anuladas: dict = field(default_factory=dict)                   # {forma: {etiqueta: modo}}

    @property
    def con_puntaje(self) -> bool:
        """¿Se calculó el puntaje tipo Saber 11 (0–500)?"""
        return "puntaje" in self.por_estudiante

    @property
    def hay_datos(self) -> bool:
        return not self.por_estudiante.empty


def guardar_escala(examen: Examen, escala: Escala) -> None:
    """La escala de notas se recuerda por examen (la usa también el seguimiento)."""
    examen.archivo_escala.write_text(json.dumps(asdict(escala)), encoding="utf-8")


def cargar_escala(examen: Examen) -> Escala:
    try:
        return Escala(**json.loads(examen.archivo_escala.read_text(encoding="utf-8")))
    except (OSError, ValueError, TypeError):
        return Escala()


MIN_PARA_GRUPOS = 10     # con menos estudiantes, los grupos alto/bajo no son confiables


def calidad(discriminacion: float) -> str:
    """
    Qué tan bien separa una pregunta a los que saben de los que no.
        ≥ 0,30  Buena       (la aciertan mucho más los mejores que los más flojos)
        ≥ 0,20  Aceptable
        < 0,20  Revisar     (quizás está mal redactada, es ambigua o tiene la clave mal)
    """
    if pd.isna(discriminacion):
        return ""
    if discriminacion >= 0.30:
        return "Buena"
    if discriminacion >= 0.20:
        return "Aceptable"
    return "Revisar"


def grupos_alto_bajo(puntajes: pd.Series) -> tuple[pd.Index, pd.Index]:
    """
    El 27 % de estudiantes con mejor puntaje y el 27 % con peor puntaje.
    (El 27 % es la proporción clásica de Kelley para el análisis de ítems.)
    """
    ordenados = puntajes.sort_values(ascending=False)
    k = max(1, round(len(ordenados) * 0.27))
    return ordenados.index[:k], ordenados.index[-k:]


def sospecha_de_clave(marcadas: pd.Series, clave: str, grupo: pd.Index,
                      porcentaje_acierto: float) -> str:
    """
    ¿La clave de esta pregunta podría estar equivocada?
    Si casi nadie acertó (menos del 35 %) y la mayoría de los MEJORES estudiantes
    eligió una misma opción distinta de la clave (y casi ninguno eligió la clave),
    lo más probable es que el error esté en la clave y no en ellos.
    Devuelve la letra sospechosa o "".
    """
    elegidas = marcadas.loc[grupo]
    if len(elegidas) < 3 or porcentaje_acierto >= 35:
        return ""
    sencillas = elegidas[elegidas.str.len() == 1]
    if sencillas.empty:
        return ""
    conteo = sencillas.value_counts()
    favorita, veces = conteo.index[0], conteo.iloc[0]
    if (favorita != clave and veces / len(elegidas) >= 0.5
            and (elegidas == clave).mean() < 0.3):
        return favorita
    return ""


def dificultad(porcentaje: float) -> str:
    """Clasifica una pregunta según cuántos la acertaron."""
    if porcentaje >= 70:
        return "Fácil"
    if porcentaje >= 40:
        return "Media"
    return "Difícil"


def calificar(examen: Examen, hojas: list[HojaLeida], claves: dict[str, dict[str, str]],
              estudiantes: pd.DataFrame, escala: Escala,
              anuladas: dict[str, dict[str, str]] | None = None) -> Resultados:
    """
    claves = {"A": {"MAT_01": "D", ...}, "B": {...}}
    Si el examen no tiene formas, solo existe la clave "A".
    Cada hoja se califica con la clave de SU forma.
    anuladas = {"A": {"MAT_05": "bien"}, ...}; si no se pasa, se lee de clave.json.
    """
    if anuladas is None:
        anuladas = cargar_anuladas(examen)
    alertas: list[tuple[str, str]] = []
    materias = examen.materias
    todas = examen.todas_las_etiquetas()
    numeros = examen.numeros_impresos()
    hay_formas = bool(examen.letras_formas)
    claves = {f: c for f, c in claves.items() if c}

    for forma in examen.formas_para_clave:
        faltan = examen.total_preguntas - len(claves.get(forma, {}))
        if faltan and forma in claves:
            texto = f"forma {forma}: " if hay_formas else ""
            alertas.append(("Clave incompleta",
                            f"{texto}{faltan} preguntas no tienen clave y no se califican."))

    # --- 1. Una fila por estudiante ---
    # Primero se agrupan las hojas de cada estudiante (si el examen tiene varias
    # hojas, cada estudiante entrega varias: se juntan por el documento).
    nombres = dict(zip(estudiantes["documento"], estudiantes["nombre"]))
    cursos = dict(zip(estudiantes["documento"], estudiantes["curso"]))
    n_hojas = examen.numero_hojas
    grupos: dict[str, dict[int, HojaLeida]] = {}
    for h in hojas:
        if h.estado == ERROR:
            alertas.append(("Hoja sin leer", f"{h.origen}: {h.problemas()[0]}."))
            continue
        doc = normalizar_documento(h.documento)
        if not doc:
            alertas.append(("Sin documento", f"{h.origen}: la hoja no tiene documento."))
            doc = f"(sin documento) {h.archivo}"
        grupo = grupos.setdefault(doc, {})
        if h.hoja in grupo:
            hoja_txt = f" (hoja {h.hoja})" if n_hojas > 1 else ""
            alertas.append(("Documento repetido",
                            f"{doc}{hoja_txt} aparece en {grupo[h.hoja].origen} y en {h.origen}. "
                            "Se usa la última."))
        grupo[h.hoja] = h

    filas, vistos = [], {}
    for doc, paginas in grupos.items():
        origen = " + ".join(p.origen for _, p in sorted(paginas.items()))
        vistos[doc] = origen
        # La forma: la que tenga marcada cualquiera de sus hojas
        formas_marcadas = {p.forma for p in paginas.values() if p.forma}
        forma = (sorted(formas_marcadas)[0] if formas_marcadas else "") if hay_formas else "A"
        if hay_formas and (len(formas_marcadas) > 1 or forma not in examen.letras_formas):
            alertas.append(("Sin forma", f"{origen} ({doc}): no se sabe qué forma es. "
                            "Corríjala en «Leer hojas»."))
            continue
        if forma not in claves:
            alertas.append(("Falta clave", f"{origen}: es forma {forma} y esa forma no tiene clave."))
            continue
        faltan = [k for k in range(1, n_hojas + 1) if k not in paginas]
        if faltan and not doc.startswith("(sin documento)"):
            alertas.append(("Falta una hoja",
                            f"{nombres.get(doc, doc)}: falta la hoja {', '.join(map(str, faltan))}; "
                            "esas preguntas cuentan como no respondidas."))
        if not doc.startswith("(sin documento)") and not estudiantes.empty and doc not in nombres:
            alertas.append(("No está en la lista",
                            f"{doc} ({origen}) no aparece en la lista de estudiantes."))
        # Juntar las respuestas: cada hoja aporta SOLO las preguntas que tiene impresas
        respuestas_est = {e: "" for e in todas}
        for k, p in paginas.items():
            for e in (examen.etiquetas_de_hoja(k) if n_hojas > 1 else todas):
                respuestas_est[e] = p.respuestas.get(e, "")
        filas.append({"documento": doc, "archivo": origen, "forma": forma, **respuestas_est})

    # Estudiantes de la lista que no entregaron hoja
    if not estudiantes.empty:
        for doc, nombre in nombres.items():
            if doc not in vistos:
                alertas.append(("Sin hoja", f"{nombre} ({doc}) no tiene hoja leída."))

    if not filas:
        vacio = pd.DataFrame()
        return Resultados(examen, escala, vacio, vacio, vacio, vacio, vacio, alertas)

    respuestas = (pd.DataFrame(filas).drop_duplicates("documento", keep="last")
                  .set_index("documento"))
    archivos = respuestas.pop("archivo")
    formas = respuestas.pop("forma")

    # Tabla de aciertos: 1 = bien, 0 = mal, vacío (NaN) = esa pregunta no tiene clave.
    # Se llena forma por forma, comparando con la clave que corresponde.
    aciertos = pd.DataFrame(float("nan"), index=respuestas.index, columns=todas)
    for forma, clave in claves.items():
        filas_forma = formas[formas == forma].index
        cols = [e for e in todas if e in clave]
        if len(filas_forma) and cols:
            comparacion = respuestas.loc[filas_forma, cols].eq(pd.Series(clave)[cols])
            aciertos.loc[filas_forma, cols] = comparacion.astype(float)
    # Lo que de verdad acertaron, ANTES de aplicar las anuladas (para analizar las preguntas)
    reales = aciertos.copy()
    # Preguntas anuladas: "bien" = acierto para todos; "excluir" = no cuenta
    for forma, de_la_forma in anuladas.items():
        filas_forma = formas[formas == forma].index
        for e, modo in de_la_forma.items():
            if e in aciertos and e in claves.get(forma, {}) and len(filas_forma):
                aciertos.loc[filas_forma, e] = 1.0 if modo == "bien" else float("nan")

    # --- 2. Por estudiante ---
    por_est = pd.DataFrame(index=respuestas.index)
    por_est["nombre"] = [nombres.get(d, "") for d in por_est.index]
    por_est["curso"] = [cursos.get(d, "") for d in por_est.index]
    if hay_formas:
        por_est["forma"] = formas
    for m in materias:
        cols = m.etiquetas()
        if aciertos[cols].notna().any().any():
            por_est[m.nombre] = (aciertos[cols].mean(axis=1) * 100).round(0)
    por_est["aciertos"] = aciertos.sum(axis=1).astype(int)
    por_est["porcentaje"] = (aciertos.mean(axis=1) * 100).round(1)
    por_est["nota"] = [escala.nota(p / 100) for p in por_est["porcentaje"]]
    por_est["aprobado"] = por_est["nota"] >= escala.aprobacion
    orden = "porcentaje"
    if usa_puntaje_saber(examen, escala):
        # Puntaje tipo Saber 11 (0–500): promedio ponderado de las materias × 5
        pesos = pesos_saber(examen, escala)
        con_dato = [m for m in materias if m.nombre in por_est]
        por_est["puntaje"] = [
            puntaje_global({m.codigo: fila[m.nombre] for m in con_dato}, pesos)
            for _, fila in por_est.iterrows()]
        orden = "puntaje"          # con pesos, el puesto lo da el puntaje
    por_est["archivo"] = archivos
    por_est = por_est.sort_values([orden, "porcentaje", "nombre"], ascending=[False, False, True])
    por_est = por_est.reset_index()
    por_est.insert(0, "puesto", range(1, len(por_est) + 1))

    # --- 3. Por materia ---
    filas_materia = []
    for m in materias:
        if m.nombre not in por_est:
            continue
        columna = por_est[m.nombre].dropna()
        filas_materia.append({
            "materia": m.nombre, "preguntas": m.preguntas,
            "promedio": round(columna.mean(), 1),
            "maximo": columna.max(), "minimo": columna.min(),
            "nota_promedio": escala.nota(columna.mean() / 100),
            "aprueban": int((columna.map(lambda p: escala.nota(p / 100)) >= escala.aprobacion).sum()),
        })
    por_materia = pd.DataFrame(filas_materia)

    # --- 4. Por pregunta (y por forma: la pregunta 5 de la forma B puede ser otra) ---
    nombre_materia = {e: m.nombre for m in materias for e in m.etiquetas()}
    opciones_de = {e: m.opciones for m in materias for e in m.etiquetas()}
    filas_pregunta = []
    for forma, clave in claves.items():
        filas_forma = formas[formas == forma].index
        if not len(filas_forma):
            continue
        # Grupos alto y bajo (solo si hay suficientes estudiantes en esta forma)
        hay_grupos = len(filas_forma) >= MIN_PARA_GRUPOS
        puntajes = reales.loc[filas_forma].mean(axis=1)
        alto, bajo = grupos_alto_bajo(puntajes)
        # Para sospechar de la clave se mira el mejor tercio (mínimo 5 estudiantes)
        mejores = puntajes.sort_values(ascending=False).index[
            :max(5, round(len(puntajes) / 3))]
        for e in [x for x in todas if x in clave]:
            marcadas = respuestas.loc[filas_forma, e]
            pct = round(reales.loc[filas_forma, e].mean() * 100, 1)
            anulada = anuladas.get(forma, {}).get(e, "")
            # La opción incorrecta más elegida (el "distractor" más fuerte)
            erradas = marcadas[(marcadas != clave[e]) & (marcadas.str.len() == 1)]
            distractor = erradas.value_counts().idxmax() if not erradas.empty else ""
            # Discriminación: % de acierto del grupo alto − % del grupo bajo (de −1 a 1)
            disc = (reales.loc[alto, e].mean() - reales.loc[bajo, e].mean()
                    if hay_grupos else float("nan"))
            # Con pocos estudiantes (menos de 10 en esta forma) no se sospecha: sería azar
            sospecha = (sospecha_de_clave(marcadas, clave[e], mejores, pct)
                        if hay_grupos and not anulada else "")   # si ya se anuló, no se avisa
            fila = {"forma": forma if hay_formas else "", "pregunta": numeros[e], "etiqueta": e,
                    "materia": nombre_materia[e], "clave": clave[e], "acierto": pct,
                    "dificultad": dificultad(pct),
                    "discriminacion": round(disc, 2) if not pd.isna(disc) else float("nan"),
                    "calidad": calidad(disc), "sospecha_clave": sospecha,
                    "respondieron": len(filas_forma),
                    "en_blanco": int((marcadas == "").sum()),
                    "doble_marca": int((marcadas.str.len() > 1).sum()),
                    "distractor": distractor, "anulada": anulada}
            if sospecha:
                texto_forma = f" de la forma {forma}" if hay_formas else ""
                alertas.insert(0, ("⚠ Revise la clave",
                                   f"Pregunta {numeros[e]}{texto_forma} ({nombre_materia[e]}): "
                                   f"la clave dice {clave[e]}, pero la mayoría de los mejores "
                                   f"estudiantes marcó {sospecha}. ¿Está bien la clave?"))
            # Cuántos estudiantes marcaron cada opción (A, B, C...)
            for letra in "ABCDEFGH"[:opciones_de[e]]:
                fila[letra] = int((marcadas == letra).sum())
            filas_pregunta.append(fila)
    # Las materias con menos opciones quedan con "" en las letras que no tienen
    por_pregunta = pd.DataFrame(filas_pregunta)
    for letra in "ABCDEFGH":
        if letra in por_pregunta:
            por_pregunta[letra] = por_pregunta[letra].map(lambda v: "" if pd.isna(v) else int(v))

    return Resultados(examen, escala, por_est, por_materia, por_pregunta,
                      respuestas, aciertos, alertas, formas, claves, anuladas)
