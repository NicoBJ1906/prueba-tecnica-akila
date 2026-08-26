"""Dashboard de dirección del proyecto de vivienda.

Capa de presentación: todo el cálculo vive en `etl.py` y `metricas.py`, que se
testean sin levantar la interfaz. Este fichero solo compone y dibuja.

El contenido se reparte en pestañas para que cada vista quepa en una pantalla.
El enunciado pide entender el proyecto «de un vistazo», y un tablero que exige
recorrer tres pantallas de scroll no cumple eso; además, los gráficos de Vega
capturan la rueda del ratón, así que obligar a scrollear sobre ellos deja al
lector atascado a mitad de página.

Ejecutar desde la raíz del repositorio:
    streamlit run ejercicio2_dashboard/dashboard/app.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

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
# Ajustado para que la vista completa —cabecera, indicadores, controles y
# gráfico— quepa sin scroll en una pantalla de portátil de 1280 × 800.
ALTO_GRAFICO = 250
# El de inventario va junto a una tabla y sin controles encima, así que dispone
# de más sitio; lo necesita para que quepan las cinco categorías con su nombre.
ALTO_INVENTARIO = 300

st.set_page_config(
    page_title="Akila · Dashboard de ventas",
    page_icon="🏗️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Ajustes de espacio sobre el tema por defecto de Streamlit:
#
# - Reserva unos 6 rem sobre el contenido y 80 px a cada lado. En una pantalla
#   de portátil eso es la diferencia entre ver el gráfico entero y no verlo, y
#   deja dos franjas vacías a los lados que estrechan los gráficos sin motivo.
# - El puente de la rueda se monta en un iframe de altura cero; como los
#   iframes son `inline`, arrastra el espacio de una línea de texto. Se colapsa
#   para que no empuje el contenido hacia abajo.
st.markdown(
    """
    <style>
      .block-container {
        padding-top: 2.5rem;
        padding-bottom: 1rem;
        padding-left: 2.5rem;
        padding-right: 2.5rem;
      }
      [data-testid="stSidebarContent"] { padding-top: 1.5rem; }
      [data-testid="stMetricValue"] { font-size: 2rem; }
      /* Colapsado, pero nunca `display: none`: un iframe oculto así puede no
         llegar a ejecutar su script, y con él se perdería el scroll. */
      .stIFrame { display: block; height: 0; border: 0; }
      [data-testid="stElementContainer"]:has(> .stIFrame) {
        height: 0; min-height: 0; margin: 0; overflow: hidden;
      }
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_data(show_spinner="Cargando cartera…")
def _cargar(ruta: str):
    resultado = cargar(ruta)
    return resultado.crudo, resultado.canonico, resultado.informe


def _devolver_la_rueda_a_la_pagina() -> None:
    """Hace que la rueda del ratón siga desplazando la página sobre un gráfico.

    Vega registra su propio manejador de `wheel` sobre el lienzo del gráfico y
    cancela el evento. En una ventana donde el contenido no cabe entero, eso
    deja al lector atascado en cuanto el cursor pasa por encima de un gráfico:
    la página simplemente deja de bajar, sin ninguna señal de por qué.

    El puente escucha en fase de captura —antes que Vega— y traslada el
    desplazamiento al contenedor que scrollea de verdad. Se instala una sola vez
    por elemento y un observador lo aplica a los gráficos que Streamlit dibuja
    después, al cambiar de pestaña o de filtro.
    """
    components.html(
        """
        <script>
        (function () {
          const doc = window.parent.document;
          const marca = 'ruedaEnlazada';

          function enlazar() {
            doc.querySelectorAll('.stVegaLiteChart').forEach(function (grafico) {
              if (grafico.dataset[marca]) return;
              grafico.dataset[marca] = '1';
              grafico.addEventListener('wheel', function (evento) {
                const contenedor = doc.querySelector('[data-testid="stMain"]');
                if (!contenedor) return;
                evento.preventDefault();
                contenedor.scrollTop += evento.deltaY;
              }, { capture: true, passive: false });
            });
          }

          enlazar();
          new MutationObserver(enlazar).observe(doc.body, {
            childList: true, subtree: true,
          });
        })();
        </script>
        """,
        height=0,
    )


def _columnas_cartera() -> dict:
    """Formato legible para las tablas que muestran filas del CSV.

    Sin esto, las fechas arrastran un «00:00:00» que no significa nada y los
    precios salen como 351400000, que nadie lee de un vistazo.
    """
    # `localized` respeta la separación de miles del idioma de quien mira, en
    # lugar de imponer la inglesa (682,500,000 donde aquí se escribe
    # 682.500.000). La moneda va en el nombre de la columna.
    return {
        "precio_cop": st.column_config.NumberColumn("Precio (COP)", format="localized"),
        "monto_credito_cop": st.column_config.NumberColumn("Crédito (COP)", format="localized"),
        "monto_contado_cop": st.column_config.NumberColumn("Contado (COP)", format="localized"),
        "fecha_venta": st.column_config.DateColumn("Venta", format="DD/MM/YYYY"),
        "fecha_entrega": st.column_config.DateColumn("Entrega", format="DD/MM/YYYY"),
        "area_m2": st.column_config.NumberColumn("Área", format="%d m²"),
        "tipo_apartamento": st.column_config.TextColumn("Tipo"),
        "numero_puerta": st.column_config.NumberColumn("Puerta"),
        "porcentaje_credito": st.column_config.NumberColumn("% crédito", format="%d %%"),
    }


def _eje_x():
    return alt.X(
        "semana:T",
        title=None,
        axis=alt.Axis(format="%b %Y", labelColor=TINTA_TENUE, titleColor=TINTA_TENUE),
    )


def _grafico_ventas_semana(serie: pd.DataFrame, medir_valor: bool, media_movil: bool):
    """Barras por semana; la tendencia va en el mismo eje, nunca en un segundo."""
    campo = "valor_cop" if medir_valor else "unidades"
    titulo_y = "Valor vendido (COP)" if medir_valor else "Apartamentos vendidos"
    formato = "$,.0f" if medir_valor else "d"

    datos = serie.copy()
    datos["media_movil"] = datos[campo].rolling(MEDIA_MOVIL_SEMANAS, min_periods=1).mean()

    base = alt.Chart(datos).encode(x=_eje_x())

    barras = base.mark_bar(
        color=AZUL, cornerRadiusTopLeft=4, cornerRadiusTopRight=4, size=9
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
        return barras.properties(height=ALTO_GRAFICO)

    linea = base.mark_line(color=NARANJA, strokeWidth=2).encode(
        y=alt.Y("media_movil:Q", title=titulo_y),
        tooltip=[
            alt.Tooltip("semana:T", title="Semana del", format="%d/%m/%Y"),
            alt.Tooltip(
                "media_movil:Q", title=f"Media {MEDIA_MOVIL_SEMANAS} semanas", format=",.1f"
            ),
        ],
    )
    return (barras + linea).properties(height=ALTO_GRAFICO)


def _grafico_inventario(df: pd.DataFrame):
    """Vendido frente a disponible por tipo: dónde queda producto por colocar."""
    datos = inventario_por_tipo(df)
    return (
        alt.Chart(datos)
        .mark_bar(stroke=SUPERFICIE, strokeWidth=2, cornerRadius=3)
        .encode(
            y=alt.Y(
                "tipo_apartamento:N", title=None, sort="-x",
                # Sin esto, Altair esconde etiquetas cuando el alto va justo y
                # el gráfico acaba con cinco barras y tres nombres.
                axis=alt.Axis(labelColor=TINTA_TENUE, labelOverlap=False, labelLimit=140),
            ),
            x=alt.X(
                "unidades:Q", title="Apartamentos",
                axis=alt.Axis(labelColor=TINTA_TENUE, titleColor=TINTA_TENUE),
            ),
            color=alt.Color(
                "estado:N", title=None,
                scale=alt.Scale(
                    domain=[ESTADO_VENDIDO, ESTADO_DISPONIBLE], range=[AZUL, NARANJA]
                ),
                legend=alt.Legend(orient="top", labelColor=TINTA_TENUE),
            ),
            tooltip=["tipo_apartamento", "estado", "unidades"],
        )
        .properties(height=ALTO_INVENTARIO)
    )


def _barra_lateral(crudo: pd.DataFrame, canonico: pd.DataFrame, informe):
    """Filtros estructurales: los que describen QUÉ apartamentos se miran.

    Aquí solo entran los atributos que tiene toda unidad —torre, tipo, precio—.
    Filtrar por forma de pago o por fecha de venta dejaría el inventario
    disponible en cero, porque un apartamento libre no tiene ninguna de las dos:
    esos filtros viven en la pestaña de ventas, donde su alcance se entiende.
    """
    with st.sidebar:
        st.subheader("Origen de los datos")
        usar_crudo = st.radio(
            "Vista",
            ["Consolidado", "Export crudo"],
            label_visibility="collapsed",
            help=(
                "El export crudo cuenta cada registro como un apartamento, "
                "incluidos los duplicados. Sirve para comparar, no para decidir."
            ),
        ) == "Export crudo"

        base = crudo if usar_crudo else canonico

        st.divider()
        st.subheader("Filtros")

        # Dejar la selección vacía significa «todas». Evita que la barra se
        # llene de etiquetas repitiendo el estado por defecto y la mantiene
        # corta en pantallas de portátil.
        torres_sel = st.multiselect(
            "Torre", sorted(base["torre"].unique()), placeholder="Todas las torres"
        )
        tipos_sel = st.multiselect(
            "Tipo de apartamento", sorted(base["tipo_apartamento"].unique()),
            placeholder="Todos los tipos",
        )

        # Los umbrales se manejan en millones: un deslizador que muestra
        # «217800000» no lo lee nadie.
        precio_min = int(base["precio_cop"].min() // 1_000_000)
        precio_max = int(-(-base["precio_cop"].max() // 1_000_000))
        rango_precio = st.slider(
            "Precio (millones COP)",
            min_value=precio_min, max_value=precio_max,
            value=(precio_min, precio_max), step=10, format="$%d M",
            help="Para aislar el producto de gama alta del resto.",
        )

        area_min, area_max = int(base["area_m2"].min()), int(base["area_m2"].max())
        rango_area = st.slider(
            "Área", min_value=area_min, max_value=area_max,
            value=(area_min, area_max), format="%d m²",
        )

        st.divider()
        st.caption(
            f"`{RUTA_CSV_POR_DEFECTO.name}` · {informe.filas_totales} registros "
            f"· {informe.unidades_unicas} apartamentos reales"
        )

    condiciones = (
        base["precio_cop"].between(rango_precio[0] * 1_000_000, rango_precio[1] * 1_000_000)
        & base["area_m2"].between(*rango_area)
    )
    if torres_sel:
        condiciones &= base["torre"].isin(torres_sel)
    if tipos_sel:
        condiciones &= base["tipo_apartamento"].isin(tipos_sel)

    filtrado = base[condiciones]
    return usar_crudo, base, filtrado, len(filtrado) < len(base)


def _cabecera_calidad(informe) -> None:
    """Aviso de una sola línea; el detalle vive en su propia pestaña."""
    if not informe.hay_conflictos:
        return

    st.warning(
        f"**{informe.filas_totales} registros, pero solo {informe.unidades_unicas} "
        f"apartamentos reales** · {informe.unidades_con_conflicto} unidades se "
        "contradicen entre sí · ver pestaña «Calidad de los datos»",
        icon="⚠️",
    )


def _kpis(r) -> None:
    """Los cuatro apartados que el enunciado pide como cifra.

    Cuatro columnas y no cinco: con cinco, un importe como «$137,7 MM» no cabe
    en una pantalla de portátil y Streamlit lo corta a media palabra. Lo que
    sobra (el valor pendiente) va a la línea de contexto, donde es texto y no
    compite por el ancho.

    Los `delta` son contexto, no variación: se muestran en gris (`off`) para no
    sugerir una subida que nadie ha medido.
    """
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Apartamentos vendidos", f"{r.vendidos}",
              f"{r.porcentaje_avance:.0f} % del proyecto", delta_color="off")
    c2.metric("Disponibles", f"{r.disponibles}",
              f"de {r.total_unidades} unidades", delta_color="off")
    c3.metric("Valor vendido", formato_cop(r.valor_vendido_cop))
    c4.metric("Variedad de producto", f"{r.variedad_tipos} tipos")


def _pestana_ventas(df: pd.DataFrame) -> None:
    """Filtros propios del periodo comercial, donde su alcance es evidente."""
    vendidos = df[df["estado"] == ESTADO_VENDIDO]
    if vendidos.empty:
        st.info("No hay ventas registradas para la selección actual.")
        return

    fechas = pd.to_datetime(vendidos["fecha_venta"])
    minima, maxima = fechas.min().date(), fechas.max().date()

    # Controles en línea y de la misma familia visual: un desplegable ancho
    # junto a dos interruptores pequeños deja un bloque gris descolgado a la
    # derecha, y el ojo lo lee como un hueco en la maqueta.
    c1, c2, c3 = st.columns([5, 3, 2])
    with c1:
        periodo = st.slider(
            "Periodo de ventas", min_value=minima, max_value=maxima,
            value=(minima, maxima), format="MMM YYYY",
        )
    with c2:
        formas = ["Todas"] + sorted(vendidos["forma_pago"].dropna().unique())
        forma = st.segmented_control(
            "Forma de pago", formas, default="Todas", width="stretch"
        ) or "Todas"
    with c3:
        medir_valor = st.toggle("Medir en COP", value=False)
        media_movil = st.toggle("Tendencia", value=True)

    en_periodo = vendidos[fechas.dt.date.between(*periodo)]
    if forma != "Todas":
        en_periodo = en_periodo[en_periodo["forma_pago"] == forma]

    if en_periodo.empty:
        st.info("Ninguna venta cumple estos criterios. Prueba a ampliar el periodo.")
        return

    serie = ventas_por_semana(en_periodo)
    st.altair_chart(
        _grafico_ventas_semana(serie, medir_valor, media_movil),
        use_container_width=True,
    )

    semanas_activas = int((serie["unidades"] > 0).sum())
    st.caption(
        f"**{int(serie['unidades'].sum())} apartamentos** por "
        f"**{formato_cop(float(serie['valor_cop'].sum()))}** en el periodo · "
        f"{semanas_activas} de {len(serie)} semanas con al menos una venta."
    )


def _pestana_producto(df: pd.DataFrame) -> None:
    izquierda, derecha = st.columns([1, 1])

    with izquierda:
        st.caption("**Tipos de apartamento vendidos** · % sobre el total de ventas")
        tabla = tipos_vendidos(df)
        if tabla.empty:
            st.info("Sin ventas en la selección actual.")
        else:
            vista = tabla.assign(valor_cop=tabla["valor_cop"].map(formato_cop))
            st.dataframe(
                vista.rename(
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
                        "% sobre ventas", format="%.1f %%",
                        min_value=0, max_value=float(tabla["porcentaje"].max()),
                    ),
                },
            )
            st.caption(
                f"Porcentaje sobre los {int(tabla['unidades_vendidas'].sum())} "
                "apartamentos vendidos de la selección."
            )

    with derecha:
        st.caption("**Inventario por tipo** · dónde queda producto sin colocar")
        st.altair_chart(_grafico_inventario(df), use_container_width=True)


def _pestana_calidad(informe, crudo: pd.DataFrame) -> None:
    if not informe.hay_conflictos:
        st.success("El export no presenta registros duplicados.")
        return

    c1, c2, c3 = st.columns(3)
    c1.metric("Registros en el fichero", informe.filas_totales)
    c2.metric("Apartamentos reales", informe.unidades_unicas)
    c3.metric("Unidades en conflicto", informe.unidades_con_conflicto)

    st.markdown(
        f"""
Un apartamento se identifica por **torre + piso + puerta**. Cuando una misma
unidad aparece en varias filas con tipo, área, precio o estado distintos, se
aplica esta regla:

1. Si la unidad tiene alguna venta registrada, **está vendida**, y manda el
   registro de la **venta más reciente**. Una venta es un hecho fechado y con
   contraparte: es la evidencia más fuerte disponible.
2. Si no hay ninguna venta, manda **el último registro** del inventario.

En este export, **{informe.unidades_con_ventas_multiples} unidades** figuran
vendidas más de una vez en fechas distintas y
**{informe.unidades_con_estado_contradictorio}** aparecen a la vez como vendidas
y disponibles. Campos en conflicto:
{", ".join(f"`{k}` en {v} unidades" for k, v in informe.campos_en_conflicto.items())}.
        """
    )

    st.caption("**Un caso real del fichero.** La misma unidad, dos versiones incompatibles:")
    conflictivas = crudo[crudo.duplicated(subset=["torre", "piso", "numero_puerta"], keep=False)]
    if not conflictivas.empty:
        primera = conflictivas.iloc[0]
        ejemplo = conflictivas[
            (conflictivas["torre"] == primera["torre"])
            & (conflictivas["piso"] == primera["piso"])
            & (conflictivas["numero_puerta"] == primera["numero_puerta"])
        ]
        st.dataframe(
            ejemplo[["id", "apartamento", "tipo_apartamento", "area_m2",
                     "precio_cop", "estado", "fecha_venta"]],
            hide_index=True, use_container_width=True,
            column_config=_columnas_cartera(),
        )


def main() -> None:
    _devolver_la_rueda_a_la_pagina()

    try:
        crudo, canonico, informe = _cargar(str(RUTA_CSV_POR_DEFECTO))
    except (FileNotFoundError, ErrorDeEsquema) as exc:
        st.error(f"No se pudieron cargar los datos.\n\n{exc}")
        st.stop()

    usar_crudo, base, df, hay_filtro = _barra_lateral(crudo, canonico, informe)

    st.subheader("Cartera de apartamentos · estado del proyecto")
    _cabecera_calidad(informe)

    if usar_crudo:
        st.error(
            "Estás viendo el **export crudo**: los duplicados están contados como "
            "apartamentos distintos, así que las cifras están infladas.",
            icon="🚫",
        )

    if df.empty:
        st.info("Ningún apartamento cumple los filtros actuales. Amplía la selección.")
        st.stop()

    r = resumen(df)
    _kpis(r)

    partes = [f"Pendiente por vender: **{formato_cop(r.valor_disponible_cop)}**"]
    if r.meses_inventario is not None:
        partes.append(
            f"ritmo reciente **{r.ritmo_semanal_reciente:.1f} apartamentos/semana** "
            f"(últimas {SEMANAS_RITMO_RECIENTE} semanas), inventario para "
            f"**{r.meses_inventario:.0f} meses**"
        )
    if hay_filtro:
        partes.append(f"filtros activos: **{len(df)} de {len(base)}** apartamentos")
    st.caption(" · ".join(partes) + ".")

    ventas, producto, calidad, datos = st.tabs(
        ["Ventas por semana", "Producto e inventario", "Calidad de los datos", "Datos"]
    )
    with ventas:
        _pestana_ventas(df)
    with producto:
        _pestana_producto(df)
    with calidad:
        _pestana_calidad(informe, crudo)
    with datos:
        st.caption(f"{len(df)} apartamentos en la selección actual.")
        st.dataframe(
            df, hide_index=True, use_container_width=True, height=380,
            column_config=_columnas_cartera(),
        )


if __name__ == "__main__":
    main()
