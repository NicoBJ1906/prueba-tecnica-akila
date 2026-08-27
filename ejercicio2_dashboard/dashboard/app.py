"""Dashboard de dirección del proyecto de vivienda.

Capa de presentación: todo el cálculo vive en `etl.py` y `metricas.py`, que se
testean sin levantar la interfaz. Este fichero solo compone y dibuja.

El contenido se reparte en pestañas para que cada vista quepa en una pantalla:
el enunciado pide entender el proyecto «de un vistazo», y un tablero que exige
recorrer varias pantallas de scroll no cumple eso. El objetivo concreto de
maquetación es que el gráfico completo, con su eje de meses, entre sin scroll
desde 1280 × 720 en adelante.

Los colores y la tipografía son los de Akila, tomados de akila.com.co.

Ejecutar desde la raíz del repositorio:
    streamlit run ejercicio2_dashboard/dashboard/app.py
"""

from __future__ import annotations

import base64
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
    formato_cop,
    inventario_por_tipo,
    resumen,
    tipos_vendidos,
    ventas_por_semana,
)

# Identidad de Akila, tomada de su propia web (akila.com.co): el tema declara
# `--green: #95b747` y `--dark-gray: #383838`, y compone en Poppins.
GRIS_MARCA = "#383838"

# El verde corporativo se usa oscurecido: el original (#95b747) se queda en
# 2,3:1 de contraste sobre blanco y no llega al mínimo legible de 3:1.
VERDE = "#7a9a35"
TINTA_TENUE = "#898781"
SUPERFICIE = "#ffffff"

# Un color por tipo de apartamento, empezando por el verde de marca. Los demás
# tonos salen del mundo de Akila: la terracota de las fachadas de sus torres y
# el turquesa que da nombre a uno de sus proyectos.
#
# El orden no es decorativo, es lo que mantiene legible el gráfico apilado. La
# pareja natural de su web —verde y naranja— es indistinguible para el
# daltonismo rojo-verde (ΔE 3,3), así que la secuencia se eligió con el
# validador de la guía de visualización: el peor par contiguo queda en ΔE 10,4
# (deuteranopía) y los cinco superan 3:1 de contraste sobre blanco.
PALETA_TIPOS = [VERDE, "#1f5fae", "#b5623a", "#0a8f80", "#a67c00"]

# De menor a mayor, para que el color siga al producto y no al ranking de ventas:
# «1 Alcoba» conserva su color aunque un filtro cambie qué tipo va primero.
ORDEN_TIPOS = ["Apartaestudio", "1 Alcoba", "2 Alcobas", "3 Alcobas", "Penthouse"]

# Versión del logo en gris de marca sobre fondo transparente, derivada del
# original (blanco sobre gris). Sobre la barra clara, una banda oscura a sangre
# pesaba demasiado para lo que es: una firma, no un encabezado.
RUTA_LOGO = Path(__file__).resolve().parent / "recursos" / "akila-logo-oscuro.png"
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

# El tema por defecto de Streamlit reserva unos 6 rem sobre el contenido y 80 px
# a cada lado. En una pantalla de portátil, ese margen es la diferencia entre ver
# el gráfico entero —con su eje de meses— y tener que buscarlo con el scroll.
#
# Las pestañas también se estilan aquí: de serie son texto subrayado y pasan
# desapercibidas, hasta el punto de que se busca abajo el contenido que en
# realidad está detrás de ellas.
st.markdown(
    f"""
    <style>
      /* Poppins es la tipografía de akila.com.co. Si no hay red, la pila de
         reserva deja el tablero idéntico en estructura. */
      @import url('https://fonts.googleapis.com/css2?family=Poppins:wght@400;500;600&display=swap');

      /* Los iconos de Streamlit son ligaduras tipográficas: el elemento
         contiene el nombre del icono («keyboard_double_arrow_left») y es su
         fuente la que lo dibuja como símbolo. Si se les impone otra familia,
         la ligadura no resuelve y el nombre aparece escrito en pantalla, así
         que quedan excluidos de la regla. */
      html, body,
      [class*="st-"]:not([data-testid="stIconMaterial"]),
      [data-testid="stMarkdownContainer"] {{
        font-family: 'Poppins', system-ui, -apple-system, 'Segoe UI', sans-serif;
      }}

      /* El panel de filtros, a la derecha.
         Streamlit solo tiene un panel lateral y lo coloca a la izquierda, así
         que se invierte el orden de las dos columnas del contenedor. Separa lo
         que se mira —la navegación, arriba— de con qué se acota, que es donde
         la mano vuelve una y otra vez.
         Si esta regla dejara de aplicar en una versión futura, el panel vuelve
         a su sitio de origen y el tablero sigue funcionando igual: el fallo
         sería de colocación, nunca de funcionamiento. */
      [data-testid="stAppViewContainer"] {{ flex-direction: row-reverse; }}

      /* 3 rem, no menos: Streamlit fija una barra superior propia y con menos
         margen las etiquetas de los indicadores quedan por debajo de ella. */
      .block-container {{
        padding-top: 3rem;
        padding-bottom: 1rem;
        padding-left: 2.5rem;
        padding-right: 2.5rem;
      }}
      /* El botón «Deploy» y el menú de Streamlit no pintan nada en un tablero
         de dirección. Se ocultan uno a uno, y no la barra entera: dentro vive
         el control para volver a abrir la barra lateral, y sin él plegarla no
         tendría vuelta atrás. */
      [data-testid="stToolbar"] [data-testid="stBaseButton-header"],
      [data-testid="stMainMenuButton"] {{ display: none; }}

      /* Ese control aparece solo con el panel plegado, y de serie es un icono
         suelto que se pierde contra el fondo. Aquí se presenta como un botón
         con la marca, para que se vea que hay algo que abrir.
         Va anclado a la derecha: Streamlit lo deja a la izquierda, que es
         donde vivía el panel antes de moverlo, y un botón que abre algo desde
         el lado contrario despista más que ayuda. */
      [data-testid="stExpandSidebarButton"] {{
        position: fixed;
        top: 0.8rem;
        right: 1rem;
        left: auto;
        z-index: 100;
        background: {VERDE};
        border-radius: 8px;
        padding: 0.3rem;
        box-shadow: 0 1px 4px rgba(56, 56, 56, 0.22);
      }}
      [data-testid="stExpandSidebarButton"]:hover {{ background: {GRIS_MARCA}; }}
      [data-testid="stExpandSidebarButton"] span,
      [data-testid="stExpandSidebarButton"] svg {{ color: #ffffff; fill: #ffffff; }}

      /* Las flechas de plegar y desplegar apuntan al lado donde Streamlit
         espera tener el panel. Con el panel a la derecha, señalarían al revés. */
      [data-testid="stExpandSidebarButton"] [data-testid="stIconMaterial"],
      [data-testid="stSidebarHeader"] [data-testid="stIconMaterial"] {{
        transform: scaleX(-1);
      }}
      [data-testid="stMetricValue"] {{
        font-size: 1.75rem;
        font-weight: 600;
        color: {GRIS_MARCA};
      }}
      [data-testid="stMetricLabel"] p {{
        font-size: 0.78rem;
        text-transform: uppercase;
        letter-spacing: 0.04em;
        color: #7c7c7c;
      }}

      /* --- Barra lateral --------------------------------------------------- */
      [data-testid="stSidebar"] {{
        background: #ffffff;
        /* El filete acompaña al panel: ahora separa por la izquierda. */
        border-right: none;
        border-left: 1px solid #ececea;
      }}
      /* Streamlit reserva 60 px arriba para el botón de plegar la barra, y eso
         dejaba una franja clara sobre el logo. El botón se superpone a la banda
         de marca —sigue siendo accesible— y la cabecera empieza en el borde. */
      [data-testid="stSidebarContent"] {{ padding-top: 0; }}
      [data-testid="stSidebarHeader"] {{
        position: absolute;
        top: 0;
        right: 0;
        z-index: 5;
        height: 46px;
        padding: 0 0.35rem;
      }}
      [data-testid="stSidebarHeader"] button {{ color: #ffffff; }}
      [data-testid="stSidebarUserContent"] {{ padding-top: 0; }}

      /* El logo, como una firma: sin banda, sin recuadro y sin competir con
         los datos. El peso visual del tablero está en las cifras. */
      /* El relleno superior deja sitio al botón de plegar, que va superpuesto. */
      .cabecera {{ padding: 1.15rem 0 1.7rem; }}
      .marca-logo {{
        width: 92px;
        display: block;
        opacity: 0.9;
        margin-bottom: 0.85rem;
      }}
      .marca-logo-texto {{
        color: {GRIS_MARCA};
        font-size: 1.6rem;
        font-weight: 500;
        letter-spacing: -0.02em;
        margin-bottom: 0.85rem;
      }}
      .marca-nombre {{
        font-size: 0.9rem;
        font-weight: 500;
        color: #6b6b66;
      }}
      /* Rótulos de sección: separan sin dibujar. */
      .rotulo {{
        font-size: 0.68rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.1em;
        color: #a8a8a2;
        margin: 1.9rem 0 0.5rem;
      }}
      .ficha {{
        font-size: 0.78rem;
        color: #8a8a85;
        line-height: 1.75;
      }}
      .ficha strong {{ color: {GRIS_MARCA}; font-weight: 500; }}

      /* --- Navegación entre vistas ----------------------------------------- */
      /* Con los filtros a la derecha, esta fila es lo único que dice dónde
         estás, así que se trata como una barra de navegación y no como unas
         pestañas discretas: más alto, más aire y un borde que la asienta. */
      [data-testid="stTabs"] [data-baseweb="tab-list"],
      [data-testid="stTabs"] [role="tablist"] {{
        gap: 0.3rem;
        background: #f6f8f2;
        padding: 0.35rem;
        border: 1px solid #e8ebe1;
        border-radius: 12px;
        margin-bottom: 0.4rem;
      }}
      [data-testid="stTabs"] [role="tab"] {{
        padding: 0.62rem 1.25rem;
        border-radius: 9px;
        font-size: 0.95rem;
        font-weight: 500;
        color: #6b6b66;
        transition: background 120ms ease, color 120ms ease;
      }}
      [data-testid="stTabs"] [role="tab"]:hover {{
        background: rgba(255, 255, 255, 0.65);
        color: {GRIS_MARCA};
      }}
      /* El espacio entre el icono y el texto está en el propio rótulo; basta
         con impedir que el navegador lo colapse para que no queden pegados. */
      [data-testid="stTabs"] [role="tab"] [data-testid="stMarkdownContainer"] p {{
        white-space: pre;
      }}
      [data-testid="stTabs"] [role="tab"][aria-selected="true"] {{
        background: #ffffff;
        color: {VERDE};
        font-weight: 600;
        box-shadow: 0 1px 3px rgba(56, 56, 56, 0.14);
      }}
      /* El subrayado deslizante sobra cuando la pestaña activa ya tiene fondo. */
      [data-testid="stTabs"] [data-baseweb="tab-highlight"],
      [data-testid="stTabs"] [data-baseweb="tab-border"],
      [data-testid="stTabs"] .react-aria-SelectionIndicator {{ display: none; }}
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_data(show_spinner="Cargando cartera…")
def _cargar(ruta: str):
    resultado = cargar(ruta)
    return resultado.crudo, resultado.canonico, resultado.informe


@st.cache_data
def _logo_incrustado(ruta: str) -> str:
    """El logo como data URI, para poder maquetarlo dentro de la cabecera.

    Con `st.image` la imagen llega envuelta en el contenedor de Streamlit y no
    se puede ajustar su tamaño ni su alineación con precisión.

    La ruta entra como argumento, y no leyendo la constante, para que la caché
    dependa de ella: si no, cambiar de fichero de logo no refresca nada.
    """
    fichero = Path(ruta)
    if not fichero.exists():
        return ""
    return base64.b64encode(fichero.read_bytes()).decode("ascii")


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


def _grafico_ventas_por_tipo(vendidos: pd.DataFrame, medir_valor: bool):
    """Las mismas semanas, desglosadas por tipo de apartamento.

    Responde a una pregunta que el total no contesta: no solo cuánto se vendió
    cada semana, sino qué producto salió. Es donde se ve si el inventario que
    queda es el que no se mueve.
    """
    campo = "valor_cop" if medir_valor else "unidades"
    fechas = pd.to_datetime(vendidos["fecha_venta"])
    datos = vendidos.assign(
        semana=(fechas - pd.to_timedelta(fechas.dt.weekday, unit="D")).dt.normalize()
    )
    agrupado = (
        datos.groupby(["semana", "tipo_apartamento"], as_index=False)
        .agg(unidades=("id", "count"), valor_cop=("precio_cop", "sum"))
    )
    tipos = [t for t in ORDEN_TIPOS if t in set(agrupado["tipo_apartamento"])]

    return (
        alt.Chart(agrupado)
        .mark_bar(size=9, stroke=SUPERFICIE, strokeWidth=0.5)
        .encode(
            x=_eje_x(),
            y=alt.Y(
                f"{campo}:Q",
                title="Valor vendido (COP)" if medir_valor else "Apartamentos vendidos",
                axis=alt.Axis(
                    format="$,.0f" if medir_valor else "d",
                    labelColor=TINTA_TENUE, titleColor=TINTA_TENUE,
                ),
            ),
            color=alt.Color(
                "tipo_apartamento:N", title=None,
                scale=alt.Scale(domain=tipos, range=PALETA_TIPOS[: len(tipos)]),
                legend=alt.Legend(orient="top", labelColor=TINTA_TENUE, columns=5),
            ),
            tooltip=[
                alt.Tooltip("semana:T", title="Semana del", format="%d/%m/%Y"),
                alt.Tooltip("tipo_apartamento:N", title="Tipo"),
                alt.Tooltip("unidades:Q", title="Apartamentos"),
                alt.Tooltip("valor_cop:Q", title="Valor (COP)", format=",.0f"),
            ],
        )
        .properties(height=ALTO_GRAFICO)
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
        color=VERDE, cornerRadiusTopLeft=4, cornerRadiusTopRight=4, size=9
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

    linea = base.mark_line(color=GRIS_MARCA, strokeWidth=2).encode(
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
    """Vendido frente a disponible por tipo: dónde queda producto por colocar.

    Dos canales a la vez: el color identifica el tipo de apartamento —el mismo
    que se usa en el resto del tablero— y la opacidad separa lo vendido de lo
    que sigue libre. Así una sola barra cuenta qué producto es y cómo va.
    """
    datos = inventario_por_tipo(df)
    tipos = [t for t in ORDEN_TIPOS if t in set(datos["tipo_apartamento"])]
    # Lo vendido arranca en cero y lo disponible se apila detrás: así la barra
    # se lee como avance, no como si el inventario libre fuera lo primero.
    datos = datos.assign(_orden=(datos["estado"] != ESTADO_VENDIDO).astype(int))

    return (
        alt.Chart(datos)
        .mark_bar(stroke=SUPERFICIE, strokeWidth=2, cornerRadius=3)
        .encode(
            order=alt.Order("_orden:Q", sort="ascending"),
            y=alt.Y(
                "tipo_apartamento:N", title=None, sort=tipos,
                # Sin esto, Altair esconde etiquetas cuando el alto va justo y
                # el gráfico acaba con cinco barras y tres nombres.
                axis=alt.Axis(labelColor=TINTA_TENUE, labelOverlap=False, labelLimit=140),
            ),
            x=alt.X(
                "unidades:Q", title="Apartamentos",
                axis=alt.Axis(labelColor=TINTA_TENUE, titleColor=TINTA_TENUE),
            ),
            color=alt.Color(
                "tipo_apartamento:N", title=None,
                scale=alt.Scale(domain=tipos, range=PALETA_TIPOS[: len(tipos)]),
                legend=None,  # el eje ya nombra cada barra
            ),
            opacity=alt.Opacity(
                "estado:N",
                scale=alt.Scale(
                    domain=[ESTADO_VENDIDO, ESTADO_DISPONIBLE], range=[1.0, 0.32]
                ),
                # Sin `symbolFillColor` los cuadrados de la leyenda salen negros
                # y no se parecen a nada de lo que hay en el gráfico.
                legend=alt.Legend(
                    orient="top", title=None, labelColor=TINTA_TENUE,
                    symbolFillColor=GRIS_MARCA, symbolStrokeWidth=0, symbolSize=110,
                ),
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
        # El título vive aquí y no sobre el contenido: en la pantalla principal
        # cada línea de cabecera empuja el gráfico hacia abajo y le come el eje.
        logo = _logo_incrustado(str(RUTA_LOGO))
        imagen = (
            f'<img class="marca-logo" src="data:image/png;base64,{logo}" alt="Akila">'
            if logo
            else '<div class="marca-logo-texto">akila</div>'
        )
        st.markdown(
            f'<div class="cabecera">{imagen}'
            '<div class="marca-nombre">Cartera de apartamentos</div>'
            "</div>",
            unsafe_allow_html=True,
        )

        st.markdown('<div class="rotulo">Vista de datos</div>', unsafe_allow_html=True)
        usar_crudo = st.radio(
            "Vista de datos",
            ["Consolidado", "Export sin depurar"],
            label_visibility="collapsed",
            help=(
                "El export sin depurar cuenta cada registro como un apartamento, "
                "incluidos los duplicados. Sirve para comparar, no para decidir."
            ),
        ) == "Export sin depurar"

        base = crudo if usar_crudo else canonico

        st.markdown('<div class="rotulo">Filtros</div>', unsafe_allow_html=True)

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

        # Pie: la ficha del proyecto, no la del fichero. A dirección le dice
        # algo «300 apartamentos en 4 torres»; «apartamentos_akila.csv», no.
        ventas = canonico[canonico["estado"] == ESTADO_VENDIDO]["fecha_venta"].dropna()
        entregas = canonico["fecha_entrega"].dropna()
        st.markdown('<div class="rotulo">El proyecto</div>', unsafe_allow_html=True)
        # Dentro de un bloque HTML el markdown no se interpreta: los énfasis van
        # con <strong> o aparecerían los asteriscos en pantalla.
        ficha = [
            f"<strong>{informe.unidades_unicas}</strong> apartamentos · "
            f"<strong>{canonico['torre'].nunique()}</strong> torres · "
            f"<strong>{canonico['tipo_apartamento'].nunique()}</strong> tipos",
        ]
        if not ventas.empty:
            ficha.append(
                f"Última venta: <strong>{ventas.max():%d/%m/%Y}</strong>"
            )
        if not entregas.empty:
            ficha.append(
                f"Entregas: <strong>{entregas.min():%m/%Y}</strong> – "
                f"<strong>{entregas.max():%m/%Y}</strong>"
            )
        st.markdown(
            f'<div class="ficha">{"<br>".join(ficha)}</div>', unsafe_allow_html=True
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


def _kpis(r) -> None:
    """Los cuatro apartados que el enunciado pide como cifra.

    Cuatro columnas y no cinco: con cinco, un importe como «$137,7 MM» no cabe
    en una pantalla de portátil y Streamlit lo corta a media palabra. Lo que
    sobra —el valor pendiente, el avance— baja a la línea de contexto, donde es
    texto y no compite por el ancho ni añade la altura de un chip de delta.
    """
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Apartamentos vendidos", f"{r.vendidos}")
    c2.metric("Disponibles", f"{r.disponibles}")
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
        por_tipo = st.toggle("Desglosar por tipo", value=False)

    en_periodo = vendidos[fechas.dt.date.between(*periodo)]
    if forma != "Todas":
        en_periodo = en_periodo[en_periodo["forma_pago"] == forma]

    if en_periodo.empty:
        st.info("Ninguna venta cumple estos criterios. Prueba a ampliar el periodo.")
        return

    if por_tipo:
        grafico = _grafico_ventas_por_tipo(en_periodo, medir_valor)
    else:
        # La tendencia solo tiene sentido sobre el total: una media móvil por
        # cada tipo dejaría el gráfico ilegible.
        grafico = _grafico_ventas_semana(
            ventas_por_semana(en_periodo), medir_valor, media_movil=True
        )
    st.altair_chart(grafico, use_container_width=True)


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
    try:
        crudo, canonico, informe = _cargar(str(RUTA_CSV_POR_DEFECTO))
    except (FileNotFoundError, ErrorDeEsquema) as exc:
        st.error(f"No se pudieron cargar los datos.\n\n{exc}")
        st.stop()

    usar_crudo, base, df, hay_filtro = _barra_lateral(crudo, canonico, informe)

    if usar_crudo:
        st.error(
            "Estás viendo el **export sin depurar**: los duplicados están contados como "
            "apartamentos distintos, así que las cifras están infladas.",
            icon="🚫",
        )

    if df.empty:
        st.info("Ningún apartamento cumple los filtros actuales. Amplía la selección.")
        st.stop()

    r = resumen(df)
    _kpis(r)

    # Una sola línea de contexto bajo los indicadores. Cada línea que se añade
    # aquí baja el gráfico y le recorta el eje de meses, así que todo lo que no
    # es una cifra de cabecera se resume en este renglón.
    partes = [f"**{r.porcentaje_avance:.0f} %** del proyecto vendido"]
    if r.meses_inventario is not None:
        partes.append(
            f"ritmo **{r.ritmo_semanal_reciente:.1f}/semana**, inventario para "
            f"**{r.meses_inventario:.0f} meses**"
        )
    partes.append(f"pendiente **{formato_cop(r.valor_disponible_cop)}**")
    if hay_filtro:
        partes.append(f"filtrando **{len(df)} de {len(base)}**")
    if informe.hay_conflictos and not usar_crudo:
        partes.append(
            f"⚠️ {informe.filas_totales} registros → {informe.unidades_unicas} "
            "apartamentos reales (ver «Calidad de los datos»)"
        )
    st.caption(" · ".join(partes))

    # Espacio fino (U+2002) entre icono y texto: el espacio normal se pierde
    # al renderizar el emoji y los rótulos quedan como «📈Ventas por semana».
    ventas, producto, calidad, datos = st.tabs(
        ["📈 Ventas por semana", "🏢 Producto e inventario",
         "⚠️ Calidad de los datos", "📋 Datos"]
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
