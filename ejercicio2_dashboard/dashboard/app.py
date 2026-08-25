"""Dashboard de dirección del proyecto de vivienda.

Capa de presentación: todo el cálculo vive en `etl.py` y `metricas.py`, que se
testean sin levantar la interfaz. Este fichero solo compone y dibuja.

Ejecutar desde la raíz del repositorio:
    streamlit run ejercicio2_dashboard/dashboard/app.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

# Permite ejecutar el fichero directamente con `streamlit run ruta/app.py`,
# que no añade el paquete padre al path.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dashboard.etl import (  # noqa: E402
    ESTADO_DISPONIBLE,
    ESTADO_VENDIDO,
    RUTA_CSV_POR_DEFECTO,
    ErrorDeEsquema,
    cargar,
)
from dashboard.metricas import (  # noqa: E402
    SEMANAS_RITMO_RECIENTE,
    formato_cop,
    inventario_por_tipo,
    resumen,
    tipos_vendidos,
    ventas_por_semana,
)

# Paleta validada para superficie clara (contraste y separación para daltonismo
# comprobados con el validador de la guía de visualización).
AZUL = "#2a78d6"  # vendido / serie principal
NARANJA = "#eb6834"  # disponible / tendencia
TINTA_TENUE = "#898781"
SUPERFICIE = "#ffffff"
MEDIA_MOVIL_SEMANAS = 4

st.set_page_config(
    page_title="Akila · Dashboard de ventas",
    page_icon="🏗️",
    layout="wide",
)


@st.cache_data(show_spinner="Cargando cartera…")
def _cargar(ruta: str):
    resultado = cargar(ruta)
    return resultado.crudo, resultado.canonico, resultado.informe


def _grafico_ventas_semana(serie: pd.DataFrame, medir_valor: bool, media_movil: bool):
    """Barras por semana; la tendencia va en el mismo eje, nunca en un segundo."""
    campo = "valor_cop" if medir_valor else "unidades"
    titulo_y = "Valor vendido (COP)" if medir_valor else "Apartamentos vendidos"
    formato = "$,.0f" if medir_valor else "d"

    datos = serie.copy()
    datos["media_movil"] = (
        datos[campo].rolling(MEDIA_MOVIL_SEMANAS, min_periods=1).mean()
    )

    base = alt.Chart(datos).encode(
        x=alt.X(
            "semana:T",
            title="Semana (lunes)",
            axis=alt.Axis(format="%b %Y", labelColor=TINTA_TENUE, titleColor=TINTA_TENUE),
        )
    )

    barras = base.mark_bar(
        color=AZUL,
        cornerRadiusTopLeft=4,
        cornerRadiusTopRight=4,
        size=9,
    ).encode(
        y=alt.Y(
            f"{campo}:Q",
            title=titulo_y,
            axis=alt.Axis(format=formato, labelColor=TINTA_TENUE, titleColor=TINTA_TENUE),
        ),
        tooltip=[
            alt.Tooltip("semana:T", title="Semana del", format="%d/%m/%Y"),
            alt.Tooltip("unidades:Q", title="Apartamentos"),
            alt.Tooltip("valor_cop:Q", title="Valor (COP)", format=",.0f"),
        ],
    )

    if not media_movil:
        return barras.properties(height=320)

    linea = base.mark_line(color=NARANJA, strokeWidth=2).encode(
        y=alt.Y("media_movil:Q", title=titulo_y),
        tooltip=[
            alt.Tooltip("semana:T", title="Semana del", format="%d/%m/%Y"),
            alt.Tooltip("media_movil:Q", title=f"Media {MEDIA_MOVIL_SEMANAS} semanas", format=",.1f"),
        ],
    )
    return (barras + linea).properties(height=320)


def _grafico_inventario(df: pd.DataFrame):
    """Vendido frente a disponible por tipo: dónde queda producto por colocar."""
    datos = inventario_por_tipo(df)
    return (
        alt.Chart(datos)
        .mark_bar(stroke=SUPERFICIE, strokeWidth=2, cornerRadius=3)
        .encode(
            y=alt.Y("tipo_apartamento:N", title=None, sort="-x",
                    axis=alt.Axis(labelColor=TINTA_TENUE)),
            x=alt.X("unidades:Q", title="Apartamentos",
                    axis=alt.Axis(labelColor=TINTA_TENUE, titleColor=TINTA_TENUE)),
            color=alt.Color(
                "estado:N",
                title=None,
                scale=alt.Scale(
                    domain=[ESTADO_VENDIDO, ESTADO_DISPONIBLE],
                    range=[AZUL, NARANJA],
                ),
                legend=alt.Legend(orient="top", labelColor=TINTA_TENUE),
            ),
            tooltip=["tipo_apartamento", "estado", "unidades"],
        )
        .properties(height=260)
    )


def main() -> None:
    st.title("Cartera de apartamentos · estado del proyecto")

    try:
        crudo, canonico, informe = _cargar(str(RUTA_CSV_POR_DEFECTO))
    except (FileNotFoundError, ErrorDeEsquema) as exc:
        st.error(f"No se pudieron cargar los datos.\n\n{exc}")
        st.stop()

    # --- Calidad de datos: lo primero que debe ver dirección ---------------
    if informe.hay_conflictos:
        st.warning(
            f"**El export contiene {informe.filas_totales} registros, pero solo "
            f"{informe.unidades_unicas} apartamentos reales.** "
            f"{informe.unidades_con_conflicto} unidades aparecen varias veces con datos "
            f"que se contradicen entre sí ({informe.porcentaje_filas_descartadas:.0f} % "
            "de los registros son versiones duplicadas).",
            icon="⚠️",
        )
        with st.expander("Cómo se resuelven los registros duplicados"):
            st.markdown(
                f"""
Un apartamento se identifica por **torre + piso + puerta**. Cuando una misma
unidad aparece en varias filas con tipo, área, precio o estado distintos, se
aplica esta regla:

1. Si la unidad tiene alguna venta registrada, **está vendida**, y manda el
   registro de la **venta más reciente**. Una venta es un hecho fechado y con
   contraparte: es la evidencia más fuerte disponible.
2. Si no hay ninguna venta, manda **el último registro** del inventario.

En este export: **{informe.unidades_con_ventas_multiples} unidades** figuran
vendidas más de una vez en fechas distintas y **{informe.unidades_con_estado_contradictorio}**
aparecen a la vez como vendidas y disponibles. El desglose de campos en
conflicto: {", ".join(f"`{k}` en {v} unidades" for k, v in informe.campos_en_conflicto.items())}.

Puedes contrastar ambas lecturas con el selector de la barra lateral.
                """
            )

    # --- Controles ---------------------------------------------------------
    with st.sidebar:
        st.header("Vista")
        vista = st.radio(
            "Origen de los datos",
            ["Consolidado (recomendado)", "Export crudo"],
            help=(
                "El export crudo cuenta cada registro como un apartamento, "
                "incluidos los duplicados. Sirve para comparar, no para decidir."
            ),
        )
        usar_crudo = vista.startswith("Export")

        st.divider()
        st.header("Filtros")
        df_base = crudo if usar_crudo else canonico
        torres = sorted(df_base["torre"].unique())
        torres_sel = st.multiselect("Torre", torres, default=torres)
        st.divider()
        st.caption(
            f"Fuente: `{RUTA_CSV_POR_DEFECTO.name}` · "
            f"{informe.filas_totales} registros · {informe.unidades_unicas} unidades"
        )

    df = df_base[df_base["torre"].isin(torres_sel)] if torres_sel else df_base.iloc[0:0]

    if df.empty:
        st.info("Selecciona al menos una torre para ver los indicadores.")
        st.stop()

    if usar_crudo:
        st.error(
            "Estás viendo el **export crudo**: los duplicados están contados como "
            "apartamentos distintos, así que las cifras están infladas.",
            icon="🚫",
        )

    r = resumen(df)

    # --- Indicadores de cabecera ------------------------------------------
    # Los `delta` aquí son contexto, no variación: se muestran en gris (`off`)
    # para no sugerir una subida que nadie ha medido.
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Apartamentos vendidos", f"{r.vendidos}",
              f"{r.porcentaje_avance:.0f} % del proyecto", delta_color="off")
    c2.metric("Disponibles", f"{r.disponibles}",
              f"de {r.total_unidades} unidades", delta_color="off")
    c3.metric("Valor vendido", formato_cop(r.valor_vendido_cop))
    c4.metric("Pendiente por vender", formato_cop(r.valor_disponible_cop))
    c5.metric("Variedad de producto", f"{r.variedad_tipos} tipos")

    if r.meses_inventario is not None:
        st.caption(
            f"Ritmo reciente: **{r.ritmo_semanal_reciente:.1f} apartamentos/semana** "
            f"(media de las últimas {SEMANAS_RITMO_RECIENTE} semanas). A ese ritmo, el inventario "
            f"disponible se agota en **{r.meses_inventario:.0f} meses**. "
            f"Primera venta: {r.primera_venta:%d/%m/%Y} · última: {r.ultima_venta:%d/%m/%Y}."
        )

    st.divider()

    # --- Ventas por semana -------------------------------------------------
    izq, der = st.columns([3, 1])
    izq.subheader("Ventas por semana")
    medir_valor = der.toggle("Medir en valor (COP)", value=False)
    media_movil = der.toggle("Mostrar tendencia", value=True)

    serie = ventas_por_semana(df)
    if serie.empty:
        st.info("No hay ventas registradas para la selección actual.")
    else:
        st.altair_chart(
            _grafico_ventas_semana(serie, medir_valor, media_movil),
            use_container_width=True,
        )

    st.divider()

    # --- Tipos vendidos e inventario --------------------------------------
    col_tabla, col_grafico = st.columns(2)

    with col_tabla:
        st.subheader("Tipos de apartamento vendidos")
        tabla = tipos_vendidos(df)
        if tabla.empty:
            st.info("Sin ventas en la selección actual.")
        else:
            vista_tabla = tabla.assign(valor_cop=tabla["valor_cop"].map(formato_cop))
            st.dataframe(
                vista_tabla.rename(
                    columns={
                        "tipo_apartamento": "Tipo",
                        "unidades_vendidas": "Vendidos",
                        "porcentaje": "% sobre ventas",
                        "valor_cop": "Valor vendido",
                    }
                ),
                hide_index=True,
                use_container_width=True,
                column_config={
                    "% sobre ventas": st.column_config.ProgressColumn(
                        "% sobre ventas",
                        format="%.1f %%",
                        min_value=0,
                        max_value=float(tabla["porcentaje"].max()),
                    ),
                },
            )
            st.caption(
                f"Porcentaje calculado sobre el total de {int(tabla['unidades_vendidas'].sum())} "
                "apartamentos vendidos."
            )

    with col_grafico:
        st.subheader("Inventario por tipo")
        st.altair_chart(_grafico_inventario(df), use_container_width=True)

    with st.expander("Ver los datos de la selección"):
        st.dataframe(df, hide_index=True, use_container_width=True)


if __name__ == "__main__":
    main()
