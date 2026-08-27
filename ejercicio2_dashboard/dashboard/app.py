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
from typing import NamedTuple

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

         Solo por encima de 992 px: en ventanas estrechas Streamlit deja de
         reservar sitio al panel y lo superpone al contenido, y ahí invertir el
         orden lo dejaba encima del gráfico. Por debajo de ese ancho vuelve a
         mandar el comportamiento de Streamlit, que ya resuelve ese caso.

         Si la regla dejara de aplicar en una versión futura, el panel vuelve a
         su sitio de origen y el tablero sigue funcionando igual: el fallo sería
         de colocación, nunca de funcionamiento. */
      @media (min-width: 992px) {{
        [data-testid="stAppViewContainer"] {{ flex-direction: row-reverse; }}
      }}

      /* La barra superior de Streamlit queda vacía al ocultar «Deploy» y el
         menú, pero sigue reservando su altura y empujaba el contenido casi
         medio centímetro hacia abajo. Se recoge, y el margen del contenido baja
         en consecuencia: la marca sube hasta el borde y el gráfico gana sitio.
         El control para reabrir el panel no se pierde — va anclado al viewport,
         no a esta barra. */
      [data-testid="stHeader"] {{ height: 0; min-height: 0; }}
      .block-container {{
        padding-top: 1.6rem;
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
        background: {VERDE};
        border-radius: 8px;
        padding: 0.3rem;
        box-shadow: 0 1px 4px rgba(56, 56, 56, 0.22);
      }}
      [data-testid="stExpandSidebarButton"]:hover {{ background: {GRIS_MARCA}; }}
      [data-testid="stExpandSidebarButton"] span,
      [data-testid="stExpandSidebarButton"] svg {{ color: #ffffff; fill: #ffffff; }}

      /* Ancla y flechas acompañan al panel, y solo mientras el panel esté
         movido: por debajo de 992 px vuelve a la izquierda y estas dos reglas
         lo dejarían señalando al lado equivocado. */
      @media (min-width: 992px) {{
        [data-testid="stExpandSidebarButton"] {{
          position: fixed;
          top: 0.8rem;
          right: 1rem;
          left: auto;
          z-index: 100;
        }}
        [data-testid="stExpandSidebarButton"] [data-testid="stIconMaterial"],
        [data-testid="stSidebarHeader"] [data-testid="stIconMaterial"] {{
          transform: scaleX(-1);
        }}
      }}
      [data-testid="stMetricValue"] {{
        /* Cuerpo fluido en vez de fijo: la cifra más ancha —«$137,7 MM»— tiene
           que caber entera en la tarjeta, y el ancho de esta depende del de la
           ventana. Con un tamaño fijo, Streamlit la recorta con puntos
           suspensivos en cuanto la pantalla se estrecha. */
        font-size: clamp(1.05rem, 1.8vw, 1.55rem);
        font-weight: 600;
        color: {GRIS_MARCA};
      }}
      /* El rótulo más largo —«Apartamentos vendidos»— marca el tamaño: con la
         tipografía por defecto Streamlit lo recorta con puntos suspensivos
         dentro de la tarjeta. */
      [data-testid="stMetricLabel"] p {{
        font-size: 0.7rem;
        text-transform: uppercase;
        letter-spacing: 0.02em;
        color: #7c7c7c;
        /* Por debajo del tamaño objetivo, que el rótulo pase a dos renglones
           antes que perder letras en unos puntos suspensivos. */
        white-space: normal;
        text-overflow: clip;
      }}
      /* Tarjeta de indicador. El relleno por defecto del contenedor con borde
         suma casi 40 px de alto a la cabecera, y esa altura sale del gráfico:
         se ajusta a lo justo para que el marco respire. */
      [data-testid="stMain"] [data-testid="stVerticalBlock"]:has(
        > [data-testid="stElementContainer"] > [data-testid="stMetric"]
      ) {{
        border: 1px solid #ececea;
        border-radius: 10px;
        background: #fcfcfb;
        padding: 0.6rem 0.75rem;
      }}
      /* Rótulo y cifra centrados en su tarjeta. Streamlit los alinea a la
         izquierda y, con el marco alrededor, el contenido quedaba descolgado
         hacia un lado. El rótulo es una rejilla: ahí `justify-content` mueve
         las pistas, no lo que hay dentro de ellas, y por eso hace falta
         `justify-items`. La cifra sí es flex y se centra con `justify-content`. */
      [data-testid="stMain"] [data-testid="stMetric"] {{
        text-align: center;
      }}
      /* El rótulo es una rejilla cuya única pista mide lo que mide el texto:
         ni `justify-content` ni un `width: 100%` en el hijo lo centran, porque
         ambos se resuelven contra esa pista de 57 px y no contra la tarjeta.
         Pasándolo a bloque, el contenedor del texto ocupa el ancho entero y el
         `text-align` heredado ya tiene sitio donde centrar. */
      [data-testid="stMain"] [data-testid="stMetricLabel"] {{
        display: block;
      }}
      [data-testid="stMain"] [data-testid="stMetricValue"] {{
        justify-content: center;
      }}
      /* Por debajo del tamaño objetivo algún rótulo pasa a dos renglones y las
         tarjetas quedan desparejas. Se les reserva ese segundo renglón a todas,
         y solo aquí: en el rango objetivo esos 16 px de alto se los quitaría al
         gráfico sin necesidad. */
      @media (max-width: 1199px) {{
        [data-testid="stMetricLabel"] p {{
          min-height: 3em;
        }}
        [data-testid="stMetricValue"] {{
          font-size: clamp(0.95rem, 1.4vw, 1.3rem);
        }}
      }}
      /* Las tres formas de pago en un solo renglón: el relleno de fábrica las
         hace anchas de más y la última se iba a una segunda fila. */
      [data-testid="stMain"] [data-testid="stButtonGroup"] button {{
        padding-left: 0.7rem;
        padding-right: 0.7rem;
      }}

      /* --- Barra lateral --------------------------------------------------- */
      [data-testid="stSidebar"] {{
        background: #ffffff;
        /* El filete acompaña al panel: ahora separa por la izquierda. */
        border-right: none;
        border-left: 1px solid #ececea;
        /* Al plegarse, el panel se estrecha en lugar de desaparecer de golpe.
           Sin recortar lo que sobra, el contenido se reajusta al nuevo ancho y
           los rótulos se apilan letra a letra mientras dura la animación. */
        overflow-x: hidden;
      }}
      /* Plegado, el panel conserva un píxel de ancho y su filete quedaba
         dibujando una línea vertical suelta sobre el contenido. */
      [data-testid="stSidebar"][aria-expanded="false"] {{ border-left: none; }}
      /* El contenido conserva su ancho aunque el panel se encoja: así se
         recorta limpiamente en lugar de recomponerse. */
      [data-testid="stSidebarUserContent"] {{ min-width: 260px; }}
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
         los datos. El peso visual del tablero está en las cifras.
         El margen negativo lo sube hasta la altura de los indicadores: el
         relleno superior del contenedor está calculado para las etiquetas de
         las cifras, y aquí dejaba la marca descolgada. */
      /* Un filete corto bajo la marca separa identidad de navegación sin
         partir la columna en dos bloques. Sin margen negativo: el contenedor
         recorta lo que sobresale por arriba y el logo aparecía descabezado. */
      .cabecera {{
        padding: 0 0 1.1rem;
        border-bottom: 1px solid #ececea;
        margin-bottom: 1.3rem;
      }}
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

      /* Nombre completo de la vista activa, ahora que el rótulo de navegación
         es de una sola palabra. */
      .titulo-vista {{
        font-size: 1.05rem;
        font-weight: 600;
        color: {GRIS_MARCA};
        margin: 0.15rem 0 0.9rem;
      }}

      /* --- Navegación entre vistas ----------------------------------------- */
      /* Botones alineados a la izquierda, no centrados como los de acción: se
         leen como una lista de secciones y no como cuatro botones sueltos. */
      .rotulo-nav {{
        font-size: 0.68rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.1em;
        color: #a8a8a2;
        margin: 0.35rem 0 0.7rem;
      }}
      /* Selector por descendencia, no por hijo directo: al llevar tooltip, el
         botón queda envuelto en tres capas que Streamlit añade para el aviso
         flotante, y un `>` deja de coincidir sin dar ningún error. */
      [data-testid="stMain"] [data-testid="stButton"] button {{
        justify-content: flex-start;
        gap: 0.6rem;
        padding: 0.62rem 0.9rem;
        border-radius: 9px;
        font-size: 0.92rem;
        font-weight: 500;
        border: 1px solid transparent;
        transition: background 120ms ease, color 120ms ease;
      }}
      /* Los botones de navegación van más juntos entre sí que los elementos
         normales de Streamlit: se leen como una lista, no como acciones
         sueltas repartidas por la columna. */
      [data-testid="stMain"] [data-testid="stVerticalBlock"]:has(> [data-testid="stElementContainer"] [data-testid="stButton"]) {{
        gap: 0.3rem;
      }}
      /* Streamlit envuelve el rótulo en varios contenedores que se encogen al
         ancho del texto: por eso un rótulo corto como «Datos» quedaba centrado
         mientras los largos parecían alineados. Se estiran los envoltorios y se
         reparte el espacio con flex — el icono conserva su tamaño y el texto se
         queda con el resto. Estirar el icono también, como haría un selector
         universal, lo deja separado del texto al otro extremo del botón. */
      [data-testid="stMain"] [data-testid="stButton"] button > div,
      [data-testid="stMain"] [data-testid="stButton"] button > div > span {{
        width: 100%;
      }}
      /* Ancho fijo para el icono: cada símbolo tiene su propio trazo y, sin
         reservarles la misma caja, los rótulos arrancan hasta ocho píxeles
         desplazados entre sí y la columna se ve descuadrada. */
      [data-testid="stMain"] [data-testid="stButton"] button [data-testid="stIconMaterial"] {{
        flex: 0 0 1.15rem;
        width: 1.15rem;
        text-align: center;
      }}
      /* `flex: 1 1 0` y no `auto`: con `auto` el contenedor se queda con el
         ancho de su texto y cada rótulo acaba centrado en el hueco que le
         sobra, así que ninguno arranca donde el de al lado. */
      [data-testid="stMain"] [data-testid="stButton"] button [data-testid="stMarkdownContainer"] {{
        flex: 1 1 0;
        min-width: 0;
      }}
      /* El párrafo ocupa todo el contenedor y alinea a la izquierda. Si algún
         rótulo no cupiera, se recorta con puntos suspensivos: partirlo en dos
         líneas descuadraría la altura de los botones entre sí. */
      [data-testid="stMain"] [data-testid="stButton"] button p {{
        width: 100%;
        text-align: left;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
      }}
      /* La vista activa: fondo de marca y peso, para que se vea de un vistazo
         en cuál estás sin tener que leer los cuatro rótulos. */
      [data-testid="stMain"] [data-testid="stButton"] button[kind="primary"] {{
        background: {VERDE};
        border-color: {VERDE};
        color: #ffffff;
        font-weight: 600;
      }}
      [data-testid="stMain"] [data-testid="stButton"] button[kind="primary"]:hover {{
        background: {GRIS_MARCA};
        border-color: {GRIS_MARCA};
        color: #ffffff;
      }}
      [data-testid="stMain"] [data-testid="stButton"] button[kind="tertiary"] {{
        color: #6b6b66;
      }}
      [data-testid="stMain"] [data-testid="stButton"] button[kind="tertiary"]:hover {{
        background: #f2f4ee;
        color: {GRIS_MARCA};
      }}
      /* --- Control que recoge la columna de vistas -------------------------- */
      /* Gemelo del que pliega el panel de filtros: mismo icono y mismo tamaño,
         cada uno arriba en su borde. Se saca del flujo para que no ocupe una
         fila propia bajo los botones, donde se leía como una quinta vista. */
      .st-key-nav_plegar {{
        position: absolute;
        top: 0.15rem;
        right: 1.2rem;
        width: auto !important;
        z-index: 5;
      }}
      [data-testid="stMain"] .st-key-nav_plegar button {{
        width: 28px;
        height: 28px;
        min-height: 0;
        padding: 0;
        justify-content: center;
        border-radius: 7px;
      }}
      [data-testid="stMain"] .st-key-nav_plegar button [data-testid="stIconMaterial"] {{
        flex: 0 0 auto;
        font-size: 1.15rem;
      }}
      /* El rótulo solo existe para lectores de pantalla: sin él, el botón no
         tiene nombre y se anuncia vacío. */
      [data-testid="stMain"] .st-key-nav_plegar button [data-testid="stMarkdownContainer"] {{
        position: absolute;
        width: 1px;
        height: 1px;
        overflow: hidden;
        clip: rect(0 0 0 0);
      }}
      /* Streamlit esconde el control de su panel hasta que el ratón pasa por
         encima. Con uno de los dos siempre a la vista y el otro no, la pantalla
         parecía tener un solo lado plegable —y el que no se ve, no se usa—. */
      [data-testid="stSidebarCollapseButton"],
      [data-testid="stSidebarCollapseButton"] button {{
        visibility: visible !important;
      }}

      /* El mismo filete que separa el panel de filtros del contenido, ahora
         también al otro lado: las tres zonas quedan delimitadas igual y el
         centro se lee como una columna y no como el resto de la página.
         Se ancla en `.cabecera`, que es marca propia, y no en el orden de las
         columnas, que Streamlit puede reorganizar en pantallas estrechas. */
      @media (min-width: 992px) {{
        /* Navegación y contenido, en la misma fila pase lo que pase. Streamlit
           deja que sus columnas envuelvan, y basta con que una vista traiga
           algo ancho —una tabla, por ejemplo— para que el contenido salte
           debajo de la columna de vistas y el centro aparezca vacío. Por debajo
           de este ancho sí queremos que se apilen, y por eso la regla vive
           dentro de la consulta de medios. */
        [data-testid="stMain"] [data-testid="stHorizontalBlock"]:has(
          > [data-testid="stColumn"] .cabecera
        ) {{
          flex-wrap: nowrap;
        }}
        [data-testid="stMain"] [data-testid="stColumn"]:has(.cabecera) {{
          border-right: 1px solid #ececea;
          padding-right: 1.2rem;
          /* Ancla del control que la recoge, que va posicionado sobre ella. */
          position: relative;
          /* La columna se estrecha y se ensancha con la misma suavidad con la
             que Streamlit anima su panel lateral, para que los dos bordes de la
             pantalla se comporten igual. */
          transition: flex-basis 220ms ease, width 220ms ease,
                      min-width 220ms ease, padding-right 220ms ease;
          /* El filete llega abajo, como el del panel de filtros. Sin esto la
             columna mide lo que miden sus cuatro botones y la línea se corta a
             media pantalla, que es peor que no tenerla. `min-height` y no
             `height`: si el contenido central creciera, la columna lo acompaña
             en lugar de dejar la línea corta otra vez. */
          min-height: calc(100vh - 3rem);
        }}
      }}
    </style>
    """,
    unsafe_allow_html=True,
)


# Se inyecta solo cuando la columna está recogida. Vive aparte del bloque
# principal porque depende del estado de la sesión, no del tema.
_CSS_NAV_COMPACTA = """
    <style>
      @media (min-width: 992px) {
        /* Ancho fijo y no proporcional: recogida, la columna tiene que medir lo
           que mide un icono, y un peso de `st.columns` daría un carril más
           ancho en un monitor grande que en un portátil. */
        [data-testid="stMain"] [data-testid="stColumn"]:has(.cabecera) {
          flex: 0 0 76px !important;
          width: 76px !important;
          min-width: 76px !important;
          padding-right: 0.6rem;
        }
        /* El contenido se queda con todo lo que deja libre: sin esto conserva
           el ancho que le tocaba por peso y aparece un hueco entre ambos.
           `flex-basis: 0` y no `auto`: con `auto` la base es el ancho natural
           del contenido, y la vista de calidad —que lleva una tabla de 1069 px
           de mínimo— no cabía junto al carril. La fila envolvía y el contenido
           caía debajo de la columna, que mide una pantalla de alto: se veía el
           centro en blanco y había que bajar a buscarlo. */
        [data-testid="stMain"] [data-testid="stColumn"]:has(.cabecera)
          + [data-testid="stColumn"] {
          flex: 1 1 0 !important;
          width: auto !important;
          min-width: 0 !important;
        }
        /* El rótulo se esconde de la vista pero sigue en el árbol: un botón
           cuyo único contenido es un icono no le dice nada a un lector de
           pantalla. */
        [data-testid="stMain"] [data-testid="stButton"] button [data-testid="stMarkdownContainer"] {
          position: absolute;
          width: 1px;
          height: 1px;
          overflow: hidden;
          clip: rect(0 0 0 0);
          white-space: nowrap;
        }
        [data-testid="stMain"] [data-testid="stButton"] button {
          justify-content: center;
          padding-left: 0;
          padding-right: 0;
        }
        [data-testid="stMain"] [data-testid="stButton"] button [data-testid="stIconMaterial"] {
          flex: 0 0 auto;
        }
        .marca-nombre,
        .rotulo-nav {
          display: none;
        }
        .marca-logo {
          width: 34px;
        }
        .marca-logo-texto {
          font-size: 1.15rem;
        }
        .cabecera {
          padding-bottom: 0.9rem;
          margin-bottom: 1rem;
        }
        /* Recogida, el control invita a abrir: la flecha se voltea y pasa a
           apuntar hacia donde va a salir la columna. Es el mismo gesto que hace
           Streamlit con el suyo al plegar el panel. */
        .st-key-nav_plegar {
          right: 0.55rem;
        }
        .st-key-nav_plegar button [data-testid="stIconMaterial"] {
          transform: scaleX(-1);
        }
      }
    </style>
    """


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


class Vista(NamedTuple):
    """Una entrada de la navegación."""

    icono: str
    nombre: str


# Iconos de Material Symbols, la familia que Streamlit ya trae. Frente a los
# emoji tienen dos ventajas aquí: son monocromáticos —así toman el color del
# botón y acompañan al estado activo en lugar de competir con él— y comparten
# trazo entre sí, que es lo que hace que una lista de iconos se lea como un
# conjunto y no como cuatro pegatinas.
#
# Nombres de una palabra: en una columna de navegación es lo que cabe sin
# recortarse en pantallas estrechas, y el icono más el encabezado de cada vista
# ya dan el contexto que un rótulo largo repetiría.
#
# El orden es el del recorrido natural: primero cómo va la venta, luego qué
# producto es, después de dónde salen las cifras y por último el detalle.
VISTAS = (
    Vista(":material/trending_up:", "Ventas"),
    Vista(":material/apartment:", "Producto"),
    Vista(":material/fact_check:", "Calidad"),
    Vista(":material/table_rows:", "Registros"),
)


def _navegacion() -> str:
    """Dibuja la navegación y devuelve la vista activa.

    Se apoya en `session_state` porque cada botón provoca un redibujado: sin
    guardar la elección, la página volvería siempre a la primera vista. Los
    datos están en caché, así que el redibujado no recalcula nada.
    """
    if "vista" not in st.session_state:
        st.session_state.vista = VISTAS[0].nombre
    if "nav_compacta" not in st.session_state:
        st.session_state.nav_compacta = False

    compacta = st.session_state.nav_compacta
    if compacta:
        st.markdown(_CSS_NAV_COMPACTA, unsafe_allow_html=True)

    # La marca encabeza la navegación: identifica el tablero desde la primera
    # columna que se lee, y deja el panel de la derecha solo para los filtros.
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

    st.markdown('<div class="rotulo-nav">Vistas</div>', unsafe_allow_html=True)
    for vista in VISTAS:
        activa = st.session_state.vista == vista.nombre
        # Sin `help`, tampoco recogida: el tooltip de Streamlit deja por cada
        # botón un segundo elemento de 0x0 en el DOM, y desplegada además
        # descuadra la alineación de los rótulos. El nombre no se pierde —viaja
        # en el rótulo oculto, que sigue siendo el nombre accesible del botón—
        # y la vista activa se lee en el título del centro.
        if st.button(
            vista.nombre,
            icon=vista.icono,
            key=f"nav_{vista.nombre}",
            use_container_width=True,
            type="primary" if activa else "tertiary",
        ):
            st.session_state.vista = vista.nombre
            st.rerun()

    # El control de la columna es gemelo del que pliega el panel de filtros: el
    # mismo icono, el mismo tamaño y cada uno arriba en su borde, apuntando cada
    # cual hacia donde se recoge su barra. Puesto como un botón ancho al final
    # de la lista se leía como una quinta vista, que es justo lo que no es.
    # El rótulo viaja oculto para que el botón conserve su nombre accesible.
    if st.button(
        "Contraer" if not compacta else "Desplegar",
        icon=":material/keyboard_double_arrow_left:",
        key="nav_plegar",
        type="tertiary",
    ):
        st.session_state.nav_compacta = not compacta
        st.rerun()

    return st.session_state.vista


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

        # Sin nota de calidad aquí: entre los filtros se leía como un papel
        # pegado en el margen. El hallazgo tiene su propia vista, con las cifras
        # y el caso de ejemplo, y el selector de arriba ya deja compararlo. La
        # advertencia sigue apareciendo, en rojo y a pantalla completa, en el
        # único sitio donde de verdad hace falta: al elegir el export sin
        # depurar, que es la lectura que engaña.

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

        condiciones = (
            base["precio_cop"].between(
                rango_precio[0] * 1_000_000, rango_precio[1] * 1_000_000
            )
            & base["area_m2"].between(*rango_area)
        )
        if torres_sel:
            condiciones &= base["torre"].isin(torres_sel)
        if tipos_sel:
            condiciones &= base["tipo_apartamento"].isin(tipos_sel)
        filtrado = base[condiciones]
        hay_filtro = len(filtrado) < len(base)

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
        # El avance es del proyecto entero, no de la selección: por eso se
        # calcula sobre el consolidado y no sobre lo que haya filtrado.
        if len(canonico):
            vendidos = int((canonico["estado"] == ESTADO_VENDIDO).sum())
            avance = vendidos / len(canonico) * 100
            ficha.append(f"<strong>{avance:.0f} %</strong> vendido")
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

    return usar_crudo, filtrado, hay_filtro, len(base)


def _kpis(r) -> None:
    """Los cuatro apartados que el enunciado pide como cifra.

    Cuatro columnas y no cinco: con cinco, un importe como «$137,7 MM» no cabe
    en una pantalla de portátil y Streamlit lo corta a media palabra. Lo que
    sobra —el valor pendiente, el avance— baja a la línea de contexto, donde es
    texto y no compite por el ancho ni añade la altura de un chip de delta.
    """
    # Rótulos de una palabra siempre que se pueda: en una tarjeta de 130 px, los
    # largos («Apartamentos vendidos») se recortan con puntos suspensivos en un
    # portátil de 1280. La unidad —apartamentos— ya la dan el título de la vista
    # y el eje del gráfico.
    cifras = (
        ("Vendidos", f"{r.vendidos}"),
        ("Disponibles", f"{r.disponibles}"),
        ("Valor vendido", formato_cop(r.valor_vendido_cop)),
        ("Variedad", f"{r.variedad_tipos} tipos"),
    )
    # Cada cifra en su propia tarjeta: el marco separa los cuatro indicadores
    # entre sí y del gráfico que viene debajo. Se usa el contenedor con borde de
    # Streamlit y no un recuadro dibujado con CSS, para no depender de nombres
    # internos del framework en un elemento tan visible.
    for columna, (etiqueta, valor) in zip(st.columns(4), cifras, strict=True):
        with columna.container(border=True):
            st.metric(etiqueta, valor)


def _pestana_ventas(df: pd.DataFrame, r) -> None:
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
    # El reparto no es arbitrario: las tres formas de pago suman unos 250 px de
    # botón, y con menos ancho la última se iba a un segundo renglón estirada de
    # lado a lado. Se le reserva sitio para que la fila quepa entera.
    c1, c2, c3 = st.columns([3.8, 3.8, 2.4])
    with c1:
        periodo = st.slider(
            "Periodo de ventas", min_value=minima, max_value=maxima,
            value=(minima, maxima), format="MMM YYYY",
        )
    with c2:
        formas = ["Todas"] + sorted(vendidos["forma_pago"].dropna().unique())
        forma = st.segmented_control("Forma de pago", formas, default="Todas") or "Todas"
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

    # El ritmo y los meses de inventario son la lectura del gráfico, no una
    # cifra de cabecera: puestos aquí se leen junto a las barras que los
    # explican, y no compiten por el alto de la pantalla.
    if r.meses_inventario is not None:
        st.caption(
            f"Ritmo del último trimestre: {r.ritmo_semanal_reciente:.1f} "
            f"apartamentos/semana · inventario para {r.meses_inventario:.0f} meses."
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
                # Sin anchos declarados, la barra de progreso se queda con el
                # sitio y la última columna —el importe— se corta y obliga a
                # desplazar la tabla a mano para leerla.
                column_config={
                    "Tipo": st.column_config.TextColumn("Tipo", width="small"),
                    "Vendidos": st.column_config.NumberColumn(
                        "Vendidos", width="small"
                    ),
                    "% sobre ventas": st.column_config.ProgressColumn(
                        "% sobre ventas", format="%.1f %%", width="small",
                        min_value=0, max_value=float(tabla["porcentaje"].max()),
                    ),
                    "Valor vendido": st.column_config.TextColumn(
                        "Valor vendido", width="small"
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

    usar_crudo, df, hay_filtro, total_sin_filtrar = _barra_lateral(crudo, canonico, informe)

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

    # Navegación a la izquierda y contenido a la derecha. Se usan columnas de
    # Streamlit —API pública— en lugar de un segundo panel lateral: el framework
    # solo ofrece uno, y fabricar otro con CSS lo haría depender de nombres
    # internos. Como contrapartida, las columnas se apilan solas en pantallas
    # estrechas, que es justo el comportamiento que se quiere.
    # 1,15 y no 1: con la columna más estrecha, «Producto e inventario» no
    # cabía y se recortaba a media palabra.
    navegacion, contenido = st.columns([1.15, 4.2], gap="medium")

    with navegacion:
        vista = _navegacion()

    with contenido:
        _kpis(r)

        # Bajo los indicadores no va nada fijo. Un renglón que encadena avance,
        # ritmo, inventario, valor pendiente y aviso de calidad se lee como una
        # nota al pie y no como un tablero: cada dato de ese resumen tiene ya su
        # sitio —el ritmo y el inventario en «Ventas», el recuento de registros
        # en «Calidad», el estado del proyecto en el panel de la derecha—.
        #
        # La única excepción: que haya filtros puestos. Ese aviso no puede vivir
        # solo en el panel de la derecha, porque el panel se pliega y se lo
        # lleva consigo; entonces las cifras siguen siendo las de una selección
        # y ya nada lo dice. Aparece únicamente cuando hay algo filtrado, así
        # que en la vista de partida la cabecera sigue limpia.
        if hay_filtro:
            st.caption(
                f"⚠️ Filtros activos: estas cifras son de **{len(df)} "
                f"apartamentos** de {total_sin_filtrar}, no del proyecto entero."
            )

        # El rótulo de navegación es de una palabra, así que cada vista se
        # presenta con su nombre completo: es donde se explica qué se está
        # mirando sin ocupar sitio en la columna de la izquierda.
        if vista == VISTAS[0].nombre:
            st.markdown('<div class="titulo-vista">Ventas por semana</div>',
                        unsafe_allow_html=True)
            _pestana_ventas(df, r)
        elif vista == VISTAS[1].nombre:
            st.markdown('<div class="titulo-vista">Producto e inventario</div>',
                        unsafe_allow_html=True)
            _pestana_producto(df)
        elif vista == VISTAS[2].nombre:
            st.markdown('<div class="titulo-vista">Calidad de los datos</div>',
                        unsafe_allow_html=True)
            _pestana_calidad(informe, crudo)
        else:
            st.markdown('<div class="titulo-vista">Registros de la cartera</div>',
                        unsafe_allow_html=True)
            st.caption(f"{len(df)} apartamentos en la selección actual.")
            st.dataframe(
                df, hide_index=True, use_container_width=True, height=380,
                column_config=_columnas_cartera(),
            )


if __name__ == "__main__":
    main()
