"""Indicadores del proyecto a partir de un DataFrame ya consolidado.

Funciones puras: reciben un DataFrame y devuelven datos. No conocen Streamlit,
de modo que los mismos números que ve dirección se pueden verificar en un test
sin levantar la interfaz.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from .etl import ESTADO_DISPONIBLE, ESTADO_VENDIDO

# Ventana usada para estimar el ritmo comercial reciente. Doce semanas es un
# trimestre: suficiente para absorber el ruido semanal sin arrastrar un ritmo
# de hace un año que ya no refleja la realidad del proyecto.
SEMANAS_RITMO_RECIENTE = 12


@dataclass(frozen=True)
class ResumenProyecto:
    """Los cinco apartados exigidos, más el contexto que dirección necesita."""

    total_unidades: int
    vendidos: int
    disponibles: int
    variedad_tipos: int
    valor_vendido_cop: float
    valor_disponible_cop: float
    porcentaje_avance: float
    ritmo_semanal_reciente: float
    meses_inventario: float | None
    primera_venta: pd.Timestamp | None
    ultima_venta: pd.Timestamp | None


def _vendidos(df: pd.DataFrame) -> pd.DataFrame:
    return df[df["estado"] == ESTADO_VENDIDO]


def _disponibles(df: pd.DataFrame) -> pd.DataFrame:
    return df[df["estado"] == ESTADO_DISPONIBLE]


def ventas_por_semana(df: pd.DataFrame, incluir_semanas_vacias: bool = True) -> pd.DataFrame:
    """Unidades y valor vendidos por semana, etiquetados por el lunes de cada una.

    Las semanas sin ventas se incluyen con valor cero: un hueco en el eje
    temporal es información comercial (hubo una parada), no un dato ausente.
    """
    vendidos = _vendidos(df).dropna(subset=["fecha_venta"])
    columnas = ["semana", "unidades", "valor_cop"]

    if vendidos.empty:
        return pd.DataFrame(columns=columnas).astype(
            {"unidades": "int64", "valor_cop": "float64"}
        )

    fechas = pd.to_datetime(vendidos["fecha_venta"])
    lunes = fechas - pd.to_timedelta(fechas.dt.weekday, unit="D")

    agrupado = (
        vendidos.assign(semana=lunes.dt.normalize())
        .groupby("semana", as_index=False)
        .agg(unidades=("id", "count"), valor_cop=("precio_cop", "sum"))
        .sort_values("semana")
    )

    if incluir_semanas_vacias and len(agrupado) > 1:
        rango = pd.date_range(
            agrupado["semana"].min(), agrupado["semana"].max(), freq="W-MON"
        )
        agrupado = (
            agrupado.set_index("semana")
            .reindex(rango, fill_value=0)
            .rename_axis("semana")
            .reset_index()
        )

    agrupado["unidades"] = agrupado["unidades"].astype("int64")
    agrupado["valor_cop"] = agrupado["valor_cop"].astype("float64")
    return agrupado[columnas]


def tipos_vendidos(df: pd.DataFrame) -> pd.DataFrame:
    """Tabla por tipo de apartamento: unidades vendidas y % sobre el total vendido.

    El porcentaje se calcula sobre el total de ventas, tal y como pide el
    enunciado, no sobre el inventario completo.
    """
    vendidos = _vendidos(df)
    columnas = ["tipo_apartamento", "unidades_vendidas", "porcentaje", "valor_cop"]

    if vendidos.empty:
        return pd.DataFrame(columns=columnas)

    tabla = (
        vendidos.groupby("tipo_apartamento", as_index=False)
        .agg(unidades_vendidas=("id", "count"), valor_cop=("precio_cop", "sum"))
        .sort_values("unidades_vendidas", ascending=False, ignore_index=True)
    )
    tabla["porcentaje"] = tabla["unidades_vendidas"] / len(vendidos) * 100
    return tabla[columnas]


def inventario_por_tipo(df: pd.DataFrame) -> pd.DataFrame:
    """Vendidos frente a disponibles por tipo: dónde queda producto sin colocar."""
    if df.empty:
        return pd.DataFrame(columns=["tipo_apartamento", "estado", "unidades"])

    return (
        df.groupby(["tipo_apartamento", "estado"], as_index=False)
        .agg(unidades=("id", "count"))
        .sort_values(["tipo_apartamento", "estado"], ignore_index=True)
    )


def ritmo_semanal_reciente(df: pd.DataFrame, semanas: int = SEMANAS_RITMO_RECIENTE) -> float:
    """Media de unidades vendidas por semana en la ventana reciente."""
    serie = ventas_por_semana(df)
    if serie.empty:
        return 0.0
    return float(serie.tail(semanas)["unidades"].mean())


def resumen(df: pd.DataFrame) -> ResumenProyecto:
    """Calcula de una vez todos los indicadores de cabecera."""
    vendidos = _vendidos(df)
    disponibles = _disponibles(df)
    total = len(df)

    ritmo = ritmo_semanal_reciente(df)
    ritmo_mensual = ritmo * 52 / 12
    meses_inventario = len(disponibles) / ritmo_mensual if ritmo_mensual > 0 else None

    fechas_venta = vendidos["fecha_venta"].dropna()

    return ResumenProyecto(
        total_unidades=total,
        vendidos=len(vendidos),
        disponibles=len(disponibles),
        variedad_tipos=int(df["tipo_apartamento"].nunique()),
        valor_vendido_cop=float(vendidos["precio_cop"].sum()),
        valor_disponible_cop=float(disponibles["precio_cop"].sum()),
        porcentaje_avance=len(vendidos) / total * 100 if total else 0.0,
        ritmo_semanal_reciente=ritmo,
        meses_inventario=meses_inventario,
        primera_venta=fechas_venta.min() if not fechas_venta.empty else None,
        ultima_venta=fechas_venta.max() if not fechas_venta.empty else None,
    )


def avance_acumulado(df: pd.DataFrame) -> pd.DataFrame:
    """Unidades y valor vendidos acumulados semana a semana.

    Las barras semanales responden «cuánto se vendió esa semana»; esta curva
    responde «por dónde vamos», que es la pregunta que hace dirección. Un
    escalón plano en la curva es un mes perdido, y se ve de lejos.
    """
    serie = ventas_por_semana(df)
    columnas = ["semana", "unidades", "valor_cop", "porcentaje_proyecto"]
    if serie.empty:
        return pd.DataFrame(columns=columnas)

    total = len(df)
    acumulado = serie.assign(
        unidades=serie["unidades"].cumsum(),
        valor_cop=serie["valor_cop"].cumsum(),
    )
    acumulado["porcentaje_proyecto"] = (
        acumulado["unidades"] / total * 100 if total else 0.0
    )
    return acumulado[columnas]


def avance_por_torre(df: pd.DataFrame) -> pd.DataFrame:
    """Cuánto lleva vendido cada torre. Sirve para comparar, no para sumar."""
    columnas = ["torre", "total", "vendidos", "disponibles", "porcentaje", "valor_cop"]
    if df.empty:
        return pd.DataFrame(columns=columnas)

    tabla = df.groupby("torre", as_index=False).agg(
        total=("id", "count"),
        vendidos=("estado", lambda s: int((s == ESTADO_VENDIDO).sum())),
        valor_cop=("precio_cop", "sum"),
    )
    tabla["disponibles"] = tabla["total"] - tabla["vendidos"]
    tabla["porcentaje"] = tabla["vendidos"] / tabla["total"] * 100
    return tabla[columnas].sort_values("torre", ignore_index=True)


# Tres franjas de altura y no los 22 pisos uno a uno: una rejilla de 88 celdas
# hay que estudiarla, y una de 12 se lee de un vistazo. Los cortes siguen cómo
# se vende un edificio —planta baja, zona media y alturas—, no un reparto
# aritmético.
FRANJAS_ALTURA = [(1, 7, "Bajos · 1-7"), (8, 15, "Medios · 8-15"), (16, 99, "Altos · 16+")]


def _franja(piso: int) -> str:
    for desde, hasta, nombre in FRANJAS_ALTURA:
        if desde <= piso <= hasta:
            return nombre
    return FRANJAS_ALTURA[-1][2]


def avance_por_altura(df: pd.DataFrame) -> pd.DataFrame:
    """Una celda por torre y franja de altura: doce cifras que se leen de un vistazo.

    Responde a la pregunta que el reparto por tipo no contesta: si lo que no
    rota está en una torre concreta, en una altura concreta, o en el cruce de
    las dos.
    """
    columnas = ["torre", "franja", "total", "vendidos", "disponibles", "porcentaje"]
    if df.empty:
        return pd.DataFrame(columns=columnas)

    tabla = (
        df.assign(franja=df["piso"].map(_franja))
        .groupby(["torre", "franja"], as_index=False)
        .agg(
            total=("id", "count"),
            vendidos=("estado", lambda s: int((s == ESTADO_VENDIDO).sum())),
        )
    )
    tabla["disponibles"] = tabla["total"] - tabla["vendidos"]
    tabla["porcentaje"] = tabla["vendidos"] / tabla["total"] * 100
    return tabla[columnas]


def cohortes_entrega(df: pd.DataFrame) -> pd.DataFrame:
    """Unidades agrupadas por trimestre de entrega, vendidas y libres.

    Lo que sigue libre y se entrega pronto es urgencia comercial; lo que sigue
    libre y se entrega tarde todavía tiene margen. Sin esta lectura, «91
    disponibles» es un número sin plazo.
    """
    columnas = ["trimestre", "total", "vendidos", "disponibles", "porcentaje"]
    entregas = df.dropna(subset=["fecha_entrega"])
    if entregas.empty:
        return pd.DataFrame(columns=columnas)

    periodo = pd.to_datetime(entregas["fecha_entrega"]).dt.to_period("Q")
    tabla = (
        entregas.assign(trimestre=periodo.dt.to_timestamp())
        .groupby("trimestre", as_index=False)
        .agg(
            total=("id", "count"),
            vendidos=("estado", lambda s: int((s == ESTADO_VENDIDO).sum())),
        )
    )
    tabla["disponibles"] = tabla["total"] - tabla["vendidos"]
    tabla["porcentaje"] = tabla["vendidos"] / tabla["total"] * 100
    return tabla[columnas].sort_values("trimestre", ignore_index=True)


def composicion_pago(df: pd.DataFrame) -> pd.DataFrame:
    """Reparto de lo vendido entre contado y crédito, con el importe financiado.

    Dos ventas del mismo precio no valen lo mismo para caja si una llega
    financiada al 70 %. El dato existe en el fichero y no se estaba usando.
    """
    columnas = ["forma_pago", "unidades", "valor_cop", "credito_cop", "contado_cop"]
    vendidos = _vendidos(df).dropna(subset=["forma_pago"])
    if vendidos.empty:
        return pd.DataFrame(columns=columnas)

    return (
        vendidos.groupby("forma_pago", as_index=False)
        .agg(
            unidades=("id", "count"),
            valor_cop=("precio_cop", "sum"),
            credito_cop=("monto_credito_cop", "sum"),
            contado_cop=("monto_contado_cop", "sum"),
        )
        .sort_values("forma_pago", ignore_index=True)[columnas]
    )


def precio_por_m2(df: pd.DataFrame) -> pd.DataFrame:
    """Cada unidad con su precio por metro, para comparar entre tipos.

    Es la medida que permite decir si un producto está caro: comparar precios
    absolutos entre un apartaestudio y un penthouse no dice nada.
    """
    if df.empty:
        return df.assign(precio_m2=pd.Series(dtype="float64"))
    return df.assign(precio_m2=df["precio_cop"] / df["area_m2"])


# Umbral a partir del cual una diferencia entre grupos se considera digna de
# mención. Por debajo de diez puntos, con lotes de 60-80 unidades, la diferencia
# entra dentro de lo que puede mover el azar y señalarla sería ruido.
PUNTOS_DIFERENCIA_RELEVANTE = 10

# Por debajo de este tamaño, un grupo no da para sacar conclusiones: con ocho
# apartamentos, dos ventas mueven el porcentaje veinticinco puntos.
MINIMO_UNIDADES_CELDA = 15


def _unidades(n: int) -> str:
    """«1 unidad», no «1 unidades»: el tablero lo lee una persona."""
    return "unidad" if n == 1 else "unidades"


@dataclass(frozen=True)
class Hallazgo:
    """Un hallazgo, partido en las tres piezas con las que se lee.

    La forma no es decorativa. Cinco frases largas seguidas se leen como un
    párrafo: hay que recorrerlas enteras para saber si alguna importa. Partidas
    en categoría, titular y evidencia se escanean —se mira la columna de
    titulares, y solo se baja al detalle del que interesa—, que es como está
    resuelto en las herramientas de BI que generan narrativa (Tableau Pulse,
    Power BI) y en cualquier informe de auditoría.

    - `tono` clasifica: riesgo, atención o dato. Da color y orden.
    - `titular` es la conclusión en cinco o seis palabras.
    - `cifra` es el número que la sostiene, para leerlo sin buscarlo.
    - `detalle` es la evidencia comprobable en el gráfico de al lado.
    """

    tono: str
    titular: str
    cifra: str
    detalle: str


TONO_RIESGO = "riesgo"
TONO_ATENCION = "atencion"
TONO_DATO = "dato"

# Los riesgos primero: si alguien solo lee la primera tarjeta, que sea la que
# más le cuesta ignorar.
ORDEN_TONOS = {TONO_RIESGO: 0, TONO_ATENCION: 1, TONO_DATO: 2}

# Cuántos se muestran. Cuatro caben en una fila de tarjetas sin robarle altura
# al gráfico que viene debajo.
MAXIMO_HALLAZGOS = 4


def insights(df: pd.DataFrame) -> list[Hallazgo]:
    """Hallazgos en texto, calculados con reglas, no redactados por un modelo.

    Un tablero enseña cifras; quien lo mira tiene que sacar la conclusión. Estas
    frases hacen ese trabajo cuando la conclusión es aritmética y verificable:
    qué torre va rezagada, qué producto no rota, qué inventario entrega pronto.
    Se escriben con reglas a propósito —el mismo criterio que el Ejercicio 1—:
    son afirmaciones sobre cifras que dirección puede comprobar en la tabla de
    al lado, y no admiten una redacción distinta cada vez que se recarga.
    """
    if df.empty or len(df) < 2:
        return []

    hallazgos: list[Hallazgo] = []

    # Mismo mínimo muestral que en el cruce por altura: sin él, una torre con
    # una sola unidad sin vender salía como «va rezagada, 75 puntos por
    # detrás». Un porcentaje sobre un lote diminuto no es una tendencia.
    torres = avance_por_torre(df)
    torres = torres[torres["total"] >= MINIMO_UNIDADES_CELDA]
    if len(torres) > 1:
        mejor = torres.loc[torres["porcentaje"].idxmax()]
        peor = torres.loc[torres["porcentaje"].idxmin()]
        brecha = mejor["porcentaje"] - peor["porcentaje"]
        if brecha >= PUNTOS_DIFERENCIA_RELEVANTE:
            hallazgos.append(
                Hallazgo(
                    tono=TONO_RIESGO,
                    titular=f"{peor['torre']} va rezagada",
                    cifra=f"{brecha:.0f} pts",
                    detalle=(
                        f"{peor['porcentaje']:.0f} % vendido frente al "
                        f"{mejor['porcentaje']:.0f} % de {mejor['torre']}. "
                        f"Quedan {int(peor['disponibles'])} "
                        f"{_unidades(int(peor['disponibles']))} por colocar."
                    ),
                )
            )

    # El cruce de torre y altura afina lo anterior: una torre puede ir bien de
    # media y tener una franja parada dentro. Se exige un mínimo de unidades
    # para no señalar una celda de cuatro apartamentos como si fuera una
    # tendencia.
    alturas = avance_por_altura(df)
    if not alturas.empty:
        grandes = alturas[alturas["total"] >= MINIMO_UNIDADES_CELDA]
        if not grandes.empty:
            fria = grandes.loc[grandes["porcentaje"].idxmin()]
            media = df.pipe(lambda x: len(_vendidos(x)) / len(x) * 100)
            if media - fria["porcentaje"] >= PUNTOS_DIFERENCIA_RELEVANTE:
                altura = fria["franja"].split(" ·")[0].lower()
                hallazgos.append(
                    Hallazgo(
                        tono=TONO_RIESGO,
                        titular=f"{fria['torre']}, pisos {altura}",
                        cifra=f"{int(fria['disponibles'])} libres",
                        detalle=(
                            f"El punto más frío del proyecto: "
                            f"{fria['porcentaje']:.0f} % colocado frente al "
                            f"{media:.0f} % de media, sobre "
                            f"{int(fria['total'])} unidades."
                        ),
                    )
                )

    disponibles = _disponibles(df)
    if not disponibles.empty:
        por_tipo = disponibles["tipo_apartamento"].value_counts()
        tipo, cuantos = por_tipo.index[0], int(por_tipo.iloc[0])
        cuota = cuantos / len(disponibles) * 100
        hallazgos.append(
            Hallazgo(
                tono=TONO_ATENCION,
                titular=f"Se acumula producto de {tipo}",
                cifra=f"{cuota:.0f} %",
                detalle=(
                    f"{cuantos} de las {len(disponibles)} unidades libres son de "
                    f"este tipo: es donde está concentrado el inventario."
                ),
            )
        )

    # Lo que entrega dentro del año y sigue libre es lo que aprieta: una unidad
    # sin vender que se entrega en 2028 todavía tiene recorrido comercial.
    cohortes = cohortes_entrega(disponibles)
    if not cohortes.empty:
        # La ventana se ancla a HOY, no a la primera entrega del fichero. Anclada
        # al dato, un proyecto que entrega entero en 2032 seguía saliendo como
        # «entrega cercana»: siempre había un trimestre a menos de doce meses
        # del primero. La urgencia es respecto al calendario, no respecto al
        # propio dato.
        limite = pd.Timestamp.today().normalize() + pd.DateOffset(months=12)
        proximas = cohortes[cohortes["trimestre"] < limite]
        pendientes = int(proximas["total"].sum())
        if pendientes:
            hasta = proximas["trimestre"].max()
            hallazgos.append(
                Hallazgo(
                    tono=TONO_ATENCION,
                    titular="Inventario con entrega cercana",
                    cifra=f"{pendientes} {_unidades(pendientes)}",
                    detalle=(
                        f"Sin vender y con entrega antes de {hasta:%m/%Y}: dejan "
                        "de venderse sobre plano y pasan a competir como "
                        "producto terminado."
                    ),
                )
            )

    pagos = composicion_pago(df)
    if not pagos.empty and "Crédito" in set(pagos["forma_pago"]):
        credito = pagos.loc[pagos["forma_pago"] == "Crédito"].iloc[0]
        financiado = float(credito["credito_cop"])
        total_vendido = float(pagos["valor_cop"].sum())
        if total_vendido > 0:
            hallazgos.append(
                Hallazgo(
                    tono=TONO_DATO,
                    titular="Parte de lo vendido no es caja",
                    cifra=formato_cop(financiado),
                    detalle=(
                        f"El {financiado / total_vendido * 100:.0f} % del valor "
                        "colocado está financiado a crédito y entra según el "
                        "calendario del banco, no en la firma."
                    ),
                )
            )

    # Como mucho cuatro. Ordenados por gravedad, los que sobran son siempre los
    # menos urgentes, y una segunda fila de tarjetas le quita al gráfico la
    # altura que necesita para verse sin scroll. Un tablero con doce avisos no
    # tiene ninguno.
    ordenados = sorted(hallazgos, key=lambda h: ORDEN_TONOS.get(h.tono, 9))
    return ordenados[:MAXIMO_HALLAZGOS]


def formato_cop(valor: float) -> str:
    """Formatea pesos colombianos de forma legible para dirección.

    Por encima de mil millones se abrevia: en un tablero, `$137.744 M` se lee de
    un vistazo y `$137.744.900.000` no.
    """
    if valor >= 1_000_000_000:
        return f"${valor / 1_000_000_000:,.1f} MM".replace(",", "@").replace(".", ",").replace("@", ".")
    if valor >= 1_000_000:
        return f"${valor / 1_000_000:,.0f} M".replace(",", ".")
    return f"${valor:,.0f}".replace(",", ".")
