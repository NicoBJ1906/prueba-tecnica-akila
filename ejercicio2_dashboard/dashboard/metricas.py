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
