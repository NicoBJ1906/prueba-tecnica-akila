"""Carga, validación y consolidación de la cartera de apartamentos.

Este módulo no depende de Streamlit: es pandas puro y se puede testear y
reutilizar desde cualquier otro proceso (un notebook, un job programado, otra
aplicación). La interfaz de usuario vive en `app.py`.

El export de origen declara "cada fila es un apartamento", pero contiene varias
filas contradictorias por unidad física. `consolidar()` aplica la regla canónica
documentada en el README para obtener una fila por unidad.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import IO

import pandas as pd

# Columnas que el export debe traer para que el dashboard funcione.
COLUMNAS_REQUERIDAS = (
    "id",
    "torre",
    "piso",
    "numero_puerta",
    "apartamento",
    "tipo_apartamento",
    "area_m2",
    "precio_cop",
    "estado",
    "fecha_venta",
    "fecha_entrega",
    "forma_pago",
    "porcentaje_credito",
    "monto_credito_cop",
    "monto_contado_cop",
)

# Identifica la unidad física. Dos filas con la misma clave son la misma
# vivienda, por mucho que difieran en tipo, área o precio.
CLAVE_UNIDAD = ("torre", "piso", "numero_puerta")

ESTADO_VENDIDO = "Vendido"
ESTADO_DISPONIBLE = "Disponible"
ESTADOS_VALIDOS = {ESTADO_VENDIDO, ESTADO_DISPONIBLE}

# Campos donde una discrepancia entre filas de la misma unidad es informativa
# para el informe de calidad (el estado y la fecha de venta se analizan aparte).
CAMPOS_COMPARABLES = (
    "tipo_apartamento",
    "area_m2",
    "precio_cop",
    "fecha_entrega",
)

RUTA_CSV_POR_DEFECTO = Path(__file__).resolve().parents[2] / "data" / "apartamentos_akila.csv"


class ErrorDeEsquema(ValueError):
    """El CSV de entrada no tiene la forma que el dashboard espera."""


@dataclass(frozen=True)
class InformeCalidad:
    """Radiografía de la calidad del export, previa a cualquier cálculo."""

    filas_totales: int
    unidades_unicas: int
    unidades_con_conflicto: int
    filas_descartadas: int
    unidades_con_ventas_multiples: int
    unidades_con_estado_contradictorio: int
    campos_en_conflicto: dict[str, int] = field(default_factory=dict)

    @property
    def hay_conflictos(self) -> bool:
        return self.unidades_con_conflicto > 0

    @property
    def porcentaje_filas_descartadas(self) -> float:
        if not self.filas_totales:
            return 0.0
        return self.filas_descartadas / self.filas_totales * 100


@dataclass(frozen=True)
class ResultadoETL:
    """Las dos lecturas del mismo export, más el diagnóstico que las separa."""

    crudo: pd.DataFrame
    canonico: pd.DataFrame
    informe: InformeCalidad


def validar_esquema(df: pd.DataFrame) -> None:
    """Falla con un mensaje accionable si el export cambió de forma.

    Se ejecuta antes de cualquier cálculo: es preferible un error explícito a un
    dashboard que muestra cifras silenciosamente equivocadas.
    """
    faltantes = [c for c in COLUMNAS_REQUERIDAS if c not in df.columns]
    if faltantes:
        raise ErrorDeEsquema(
            "El CSV no tiene las columnas requeridas: "
            + ", ".join(faltantes)
            + f". Columnas encontradas: {', '.join(df.columns)}"
        )

    if df.empty:
        raise ErrorDeEsquema("El CSV no contiene ninguna fila de datos.")

    estados = set(df["estado"].dropna().unique()) - ESTADOS_VALIDOS
    if estados:
        raise ErrorDeEsquema(
            f"Valores de 'estado' no reconocidos: {sorted(estados)}. "
            f"Esperados: {sorted(ESTADOS_VALIDOS)}."
        )

    for columna in ("precio_cop", "area_m2", "piso"):
        if df[columna].isna().any():
            filas = df.index[df[columna].isna()].tolist()[:5]
            raise ErrorDeEsquema(
                f"La columna '{columna}' tiene valores vacíos (filas {filas}). "
                "Es obligatoria para calcular los indicadores."
            )

    vendidos_sin_fecha = df[(df["estado"] == ESTADO_VENDIDO) & df["fecha_venta"].isna()]
    if not vendidos_sin_fecha.empty:
        ids = vendidos_sin_fecha["id"].head(5).tolist()
        raise ErrorDeEsquema(
            f"Hay {len(vendidos_sin_fecha)} apartamentos marcados como vendidos sin "
            f"fecha_venta (ids {ids}). Sin fecha no se pueden calcular ventas por semana."
        )


def cargar_crudo(origen: str | Path | IO = RUTA_CSV_POR_DEFECTO) -> pd.DataFrame:
    """Lee el CSV tal cual viene, con tipos ya normalizados y validado.

    Acepta una ruta o cualquier objeto de fichero abierto. Lo segundo es lo que
    permite cargar un export distinto desde el navegador sin escribirlo antes en
    disco: el ETL no tiene por qué saber de dónde salen los bytes.
    """
    if isinstance(origen, (str, Path)):
        ruta = Path(origen)
        if not ruta.exists():
            raise FileNotFoundError(
                f"No se encontró el fichero de datos en {ruta}. "
                "Comprueba que ejecutas el comando desde la raíz del repositorio."
            )
        origen = ruta

    try:
        df = pd.read_csv(origen, parse_dates=["fecha_venta", "fecha_entrega"])
    except ValueError as exc:  # fechas no parseables
        raise ErrorDeEsquema(
            f"No se pudieron interpretar las fechas del CSV: {exc}"
        ) from exc

    validar_esquema(df)
    return df


def analizar_calidad(df: pd.DataFrame) -> InformeCalidad:
    """Cuantifica los duplicados contradictorios antes de resolverlos.

    La cifra que importa a dirección no es cuántas filas trae el fichero, sino
    cuántas unidades físicas existen y en cuántas hay versiones que se
    contradicen entre sí.
    """
    total_filas = len(df)
    grupos = df.groupby(list(CLAVE_UNIDAD), sort=False)
    unidades_unicas = grupos.ngroups

    unidades_con_conflicto = 0
    ventas_multiples = 0
    estado_contradictorio = 0
    campos_en_conflicto: dict[str, int] = {campo: 0 for campo in CAMPOS_COMPARABLES}

    for _, grupo in grupos:
        if len(grupo) == 1:
            continue

        conflictivo = False
        for campo in CAMPOS_COMPARABLES:
            if grupo[campo].nunique(dropna=False) > 1:
                campos_en_conflicto[campo] += 1
                conflictivo = True

        estados = set(grupo["estado"])
        if len(estados) > 1:
            estado_contradictorio += 1
            conflictivo = True

        if grupo.loc[grupo["estado"] == ESTADO_VENDIDO, "fecha_venta"].nunique() > 1:
            ventas_multiples += 1
            conflictivo = True

        if conflictivo:
            unidades_con_conflicto += 1

    return InformeCalidad(
        filas_totales=total_filas,
        unidades_unicas=unidades_unicas,
        unidades_con_conflicto=unidades_con_conflicto,
        filas_descartadas=total_filas - unidades_unicas,
        unidades_con_ventas_multiples=ventas_multiples,
        unidades_con_estado_contradictorio=estado_contradictorio,
        campos_en_conflicto={k: v for k, v in campos_en_conflicto.items() if v},
    )


def consolidar(df: pd.DataFrame) -> pd.DataFrame:
    """Devuelve una fila por unidad física aplicando la regla canónica.

    Regla, en este orden:

    1. Si la unidad tiene alguna fila `Vendido`, la unidad está vendida y gana
       el registro de la venta **más reciente**. Una venta es un hecho fechado y
       con contraparte: es la evidencia más fuerte disponible, y el registro que
       la acompaña (tipo, área, precio) es el que se firmó.
    2. Si no hay ninguna venta, gana la fila de `id` más alto, por ser la última
       versión registrada del inventario.

    Los empates de fecha se resuelven por `id` descendente. La regla es
    determinista y no depende del orden de lectura del fichero.
    """
    if df.empty:
        return df.copy()

    orden_estado = (df["estado"] == ESTADO_VENDIDO).astype(int)
    fecha_orden = df["fecha_venta"].fillna(pd.Timestamp.min)

    ordenado = df.assign(_es_vendido=orden_estado, _fecha_orden=fecha_orden).sort_values(
        ["_es_vendido", "_fecha_orden", "id"],
        ascending=[False, False, False],
        kind="stable",
    )

    canonico = ordenado.drop_duplicates(subset=list(CLAVE_UNIDAD), keep="first")
    return (
        canonico.drop(columns=["_es_vendido", "_fecha_orden"])
        .sort_values("id", kind="stable")
        .reset_index(drop=True)
    )


def cargar(origen: str | Path | IO = RUTA_CSV_POR_DEFECTO) -> ResultadoETL:
    """Punto de entrada único: crudo, canónico e informe de calidad."""
    crudo = cargar_crudo(origen)
    return ResultadoETL(
        crudo=crudo,
        canonico=consolidar(crudo),
        informe=analizar_calidad(crudo),
    )
