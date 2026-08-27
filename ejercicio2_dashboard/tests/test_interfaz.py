"""Pruebas de la interfaz real, con un navegador.

Existen por un motivo concreto: los fallos de maquetación no los detecta ningún
test de datos. El tablero puede calcular bien los 209 vendidos y aun así
mostrarlos con el gráfico cortado por abajo, que es justo lo que pasó durante el
desarrollo. Estas pruebas abren el dashboard en un navegador de verdad y miden
la página, para que la maqueta esté verificada también en la máquina de quien lo
despliegue y no solo en la de quien lo escribió.

Son OPCIONALES: si Playwright no está instalado, se saltan y el resto de la
batería sigue pasando. Para ejecutarlas:

    pip install -r requirements-dev.txt
    playwright install chromium
    pytest ejercicio2_dashboard/tests/test_interfaz.py
"""

from __future__ import annotations

import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

import pytest

sync_playwright = pytest.importorskip(
    "playwright.sync_api",
    reason="Playwright no está instalado; ver requirements-dev.txt",
).sync_playwright

RAIZ = Path(__file__).resolve().parents[2]
APP = RAIZ / "ejercicio2_dashboard" / "dashboard" / "app.py"

# Tamaños que debe soportar sin que el gráfico quede cortado. El más exigente es
# 1280x720, que es lo que queda visible en un portátil de 13" con Chrome
# maximizado una vez descontada la barra del navegador.
TAMANOS = [(1280, 720), (1440, 900)]

ESPERA_ARRANQUE = 60  # segundos
ESPERA_RENDER = 3500  # ms que tarda Streamlit en pintar los gráficos


def _puerto_libre() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _esperar(url: str, limite: int = ESPERA_ARRANQUE) -> bool:
    fin = time.time() + limite
    while time.time() < fin:
        try:
            with urllib.request.urlopen(url, timeout=2) as respuesta:
                if respuesta.status == 200:
                    return True
        except (urllib.error.URLError, OSError):
            time.sleep(0.5)
    return False


@pytest.fixture(scope="session")
def servidor() -> str:
    """Levanta el dashboard en un puerto libre y lo apaga al terminar."""
    puerto = _puerto_libre()
    proceso = subprocess.Popen(
        [
            sys.executable, "-m", "streamlit", "run", str(APP),
            "--server.port", str(puerto),
            "--server.headless", "true",
            "--browser.gatherUsageStats", "false",
        ],
        cwd=RAIZ,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    url = f"http://localhost:{puerto}"
    try:
        if not _esperar(f"{url}/_stcore/health"):
            proceso.terminate()
            pytest.skip("El servidor de Streamlit no respondió a tiempo.")
        yield url
    finally:
        proceso.terminate()
        try:
            proceso.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proceso.kill()


@pytest.fixture(scope="session")
def navegador():
    with sync_playwright() as p:
        try:
            chromium = p.chromium.launch()
        except Exception as exc:  # falta el binario del navegador
            pytest.skip(f"No se pudo abrir Chromium: {exc}")
        yield chromium
        chromium.close()


@pytest.fixture
def pagina(navegador, servidor):
    """Una pestaña ya cargada, del tamaño que pida cada test."""

    def _abrir(ancho: int = 1440, alto: int = 900):
        contexto = navegador.new_context(viewport={"width": ancho, "height": alto})
        pagina = contexto.new_page()
        pagina.goto(servidor, wait_until="networkidle")
        pagina.wait_for_selector(".stVegaLiteChart", timeout=30_000)
        # Hasta que las tipografías no están listas, un icono ocupa el ancho de
        # su nombre en texto y desplaza lo que tiene al lado: medir antes da
        # posiciones que no son las que verá nadie.
        pagina.wait_for_function("() => document.fonts.status === 'loaded'", timeout=20_000)
        pagina.wait_for_timeout(ESPERA_RENDER)
        return pagina

    return _abrir


class TestMaquetacion:
    @pytest.mark.parametrize("ancho,alto", TAMANOS)
    def test_el_grafico_se_ve_entero_sin_scroll(self, pagina, ancho, alto):
        """La regresión que motivó estas pruebas.

        El encabezado creció hasta empujar el gráfico fuera de la pantalla: se
        veían las barras pero no el eje de meses, y había que buscarlo con el
        scroll. Comprobamos que el borde inferior del gráfico cae dentro del
        alto visible.
        """
        p = pagina(ancho, alto)
        borde_inferior = p.evaluate(
            "() => document.querySelector('.stVegaLiteChart').getBoundingClientRect().bottom"
        )
        assert borde_inferior <= alto, (
            f"El gráfico termina en {borde_inferior:.0f} px con una ventana de "
            f"{alto} px: queda cortado y hay que hacer scroll para ver el eje."
        )

    @pytest.mark.parametrize("ancho,alto", TAMANOS)
    def test_la_pagina_no_desborda_a_lo_ancho(self, pagina, ancho, alto):
        p = pagina(ancho, alto)
        assert not p.evaluate(
            "() => document.documentElement.scrollWidth > window.innerWidth"
        )

    @pytest.mark.parametrize("ancho,alto", TAMANOS)
    def test_ningun_indicador_queda_cortado(self, pagina, ancho, alto):
        """Con cinco indicadores, «$137,7 MM» se cortaba a media palabra.

        Se mide el ancho real del texto con un `Range` y no con `scrollWidth`:
        cuando el recorte lo hace un `text-overflow: ellipsis`, el navegador
        deja `scrollWidth` igual a `clientWidth` y el fallo pasa inadvertido.
        Se comprueban también los rótulos, no solo las cifras.
        """
        p = pagina(ancho, alto)
        cortados = p.evaluate(
            """() => {
                 const recortado = el => {
                   const r = document.createRange();
                   r.selectNodeContents(el);
                   return Math.ceil(r.getBoundingClientRect().width) > el.clientWidth + 1;
                 };
                 return [...document.querySelectorAll(
                     '[data-testid="stMetricValue"] > div, [data-testid="stMetricLabel"] p'
                 )].filter(recortado).map(e => e.innerText);
               }"""
        )
        assert cortados == [], f"Indicadores cortados: {cortados}"

    @pytest.mark.parametrize("ancho,alto", TAMANOS)
    def test_los_indicadores_van_en_tarjetas(self, pagina, ancho, alto):
        """Cada cifra dentro de su recuadro, para separarla de las de al lado."""
        p = pagina(ancho, alto)
        con_borde = p.evaluate(
            """() => [...document.querySelectorAll(
                     '[data-testid="stMain"] [data-testid="stVerticalBlock"]'
                 )]
                 .filter(e => e.querySelector(
                     ':scope > [data-testid="stElementContainer"] > [data-testid="stMetric"]'
                 ))
                 .filter(e => parseFloat(getComputedStyle(e).borderTopWidth) > 0)
                 .length"""
        )
        assert con_borde == 4, f"Indicadores en tarjeta: {con_borde} de 4"

    @pytest.mark.parametrize("ancho,alto", TAMANOS)
    def test_las_formas_de_pago_caben_en_un_renglon(self, pagina, ancho, alto):
        """«Crédito» se iba a una segunda fila y aparecía estirada y descolgada.

        La columna que las aloja tiene que ser lo bastante ancha para las tres.
        """
        p = pagina(ancho, alto)
        renglones = p.evaluate(
            """() => {
                 const grupo = document.querySelector(
                     '[data-testid="stMain"] [data-testid="stButtonGroup"]'
                 );
                 if (!grupo) return null;
                 return new Set([...grupo.querySelectorAll('button')]
                   .map(b => Math.round(b.getBoundingClientRect().y))).size;
               }"""
        )
        assert renglones == 1, (
            f"Las formas de pago ocupan {renglones} renglones en lugar de uno."
        )

    def test_el_panel_de_filtros_esta_a_la_derecha(self, pagina):
        """Streamlit coloca su único panel lateral a la izquierda.

        El tablero lo lleva a la derecha invirtiendo el orden del contenedor,
        para separar la navegación —arriba— de los filtros. La regla se apoya en
        un nombre interno de Streamlit, así que esta prueba avisa si una versión
        futura deja de aplicarla: el tablero seguiría funcionando, pero con la
        maqueta cambiada.
        """
        p = pagina()
        posiciones = p.evaluate(
            """() => {
              const panel = document.querySelector('[data-testid="stSidebar"]');
              const contenido = document.querySelector('[data-testid="stMain"]');
              return {panel: panel.getBoundingClientRect().left,
                      contenido: contenido.getBoundingClientRect().left};
            }"""
        )
        assert posiciones["panel"] > posiciones["contenido"], (
            "El panel de filtros volvió a la izquierda: revisa la regla que "
            "invierte el contenedor."
        )

    def test_no_hay_errores_de_python_en_pantalla(self, pagina):
        p = pagina()
        assert p.locator('[data-testid="stException"]').count() == 0

    def test_los_iconos_no_muestran_su_nombre_en_crudo(self, pagina):
        """Un icono con la tipografía equivocada escribe su nombre en pantalla.

        Los iconos de Streamlit son ligaduras: el elemento contiene el texto
        «keyboard_double_arrow_left» y es su fuente la que lo dibuja como
        símbolo. Al fijar una tipografía propia para toda la aplicación es fácil
        pisarlos sin darse cuenta, y entonces el nombre aparece escrito junto al
        logo. Pasó, y por eso existe esta prueba.
        """
        p = pagina()
        rotos = p.evaluate(
            """() => [...document.querySelectorAll('[data-testid="stIconMaterial"]')]
                 .filter(e => !/material|symbols|icons/i.test(getComputedStyle(e).fontFamily))
                 .map(e => `${e.textContent.trim()} → ${getComputedStyle(e).fontFamily}`)"""
        )
        assert rotos == [], f"Iconos sin su tipografía: {rotos}"


class TestNavegacion:
    ETIQUETAS = ["Ventas", "Producto", "Calidad", "Registros"]

    @staticmethod
    def _botones(p):
        """Solo los de vista.

        La columna lleva además el control que la recoge, que no navega a
        ninguna parte: se descarta por su clave para que contar botones siga
        contando vistas.
        """
        return p.locator(
            '[data-testid="stMain"] [data-testid="stElementContainer"]'
            ':not(.st-key-nav_plegar) [data-testid="stButton"] button'
        )

    def test_las_cuatro_vistas_abren_y_pintan_contenido(self, pagina):
        # Se seleccionan por posición y no por nombre: «Datos» también aparece
        # dentro de «Calidad de los datos» y la búsqueda por texto es ambigua.
        p = pagina()
        botones = self._botones(p)
        assert botones.count() == len(self.ETIQUETAS)

        for indice, etiqueta in enumerate(self.ETIQUETAS):
            boton = botones.nth(indice)
            assert etiqueta in boton.inner_text()
            boton.click()
            p.wait_for_timeout(1500)
            assert p.locator('[data-testid="stException"]').count() == 0

            activo = p.evaluate(
                """() => {
                  const b = [...document.querySelectorAll(
                    '[data-testid="stMain"] [data-testid="stButton"] button')]
                    .find(x => x.getAttribute('kind') === 'primary');
                  return b ? b.innerText.trim() : null;
                }"""
            )
            assert etiqueta in activo, (
                f"Se pulsó «{etiqueta}» pero la vista marcada como activa es «{activo}»."
            )

    def test_los_rotulos_de_navegacion_quedan_alineados(self, pagina):
        """Los contenedores internos del botón se encogen al ancho del texto.

        Sin estirarlos, un rótulo corto como «Datos» aparece centrado mientras
        los largos parecen alineados, y la columna se ve descuadrada.

        Se admiten unos pocos píxeles de diferencia: cada icono tiene su propio
        ancho de trazo y desplaza el texto de forma imperceptible.
        """
        p = pagina()
        posiciones = p.evaluate(
            """() => [...document.querySelectorAll(
                 '[data-testid="stMain"] [data-testid="stButton"] button')]
                 .filter(b => b.getBoundingClientRect().width > 0)
                 .map(b => Math.round(b.querySelector('p').getBoundingClientRect().left))"""
        )
        assert max(posiciones) - min(posiciones) <= 4, (
            f"Los rótulos empiezan en posiciones muy distintas: {posiciones}"
        )

    def test_la_navegacion_se_recoge_a_iconos_y_vuelve(self, pagina):
        """Recogida deja el carril de iconos; desplegada vuelve a los rótulos.

        Es un ciclo completo a propósito: recoger una barra sin poder volver a
        abrirla ya pasó una vez con el panel de filtros, y desde fuera parece
        que el tablero se ha roto.
        """
        p = pagina(1440, 900)
        medir = """() => {
            const nav = [...document.querySelectorAll(
                '[data-testid="stMain"] [data-testid="stColumn"]')]
                .find(c => c.querySelector('.cabecera'));
            const bot = [...document.querySelectorAll(
                '[data-testid="stMain"] [data-testid="stButton"] button')];
            const visible = el => el && el.getBoundingClientRect().width > 2;
            return {
              ancho: Math.round(nav.getBoundingClientRect().width),
              rotulos: bot.filter(
                b => visible(b.querySelector('[data-testid="stMarkdownContainer"]'))).length,
              iconos: bot.filter(
                b => visible(b.querySelector('[data-testid="stIconMaterial"]'))).length,
            };
        }"""

        desplegada = p.evaluate(medir)
        assert desplegada["rotulos"] == desplegada["iconos"] > 0

        p.get_by_role("button", name="Contraer").click()
        p.wait_for_timeout(ESPERA_RENDER)
        recogida = p.evaluate(medir)
        assert recogida["ancho"] < desplegada["ancho"], (
            "La columna no se estrechó al recogerla."
        )
        assert recogida["rotulos"] == 0, "Recogida no debería mostrar ningún rótulo."
        assert recogida["iconos"] == desplegada["iconos"], (
            "Recogida tienen que seguir viéndose todos los iconos: son la "
            "única forma de navegar en ese estado."
        )

        p.get_by_role("button", name="Desplegar").click()
        p.wait_for_timeout(ESPERA_RENDER)
        vuelta = p.evaluate(medir)
        assert vuelta == desplegada, f"No volvió al estado inicial: {vuelta}"

    @pytest.mark.parametrize("ancho,alto", TAMANOS)
    def test_las_tres_zonas_estan_separadas_por_un_filete(self, pagina, ancho, alto):
        """El centro va delimitado a los dos lados, no solo por la derecha."""
        p = pagina(ancho, alto)
        bordes = p.evaluate(
            """() => {
                 const nav = [...document.querySelectorAll(
                     '[data-testid="stMain"] [data-testid="stColumn"]')]
                     .find(c => c.querySelector('.cabecera'));
                 const panel = document.querySelector('[data-testid="stSidebar"]');
                 return {
                   navDerecha: parseFloat(getComputedStyle(nav).borderRightWidth),
                   panelIzquierda: parseFloat(getComputedStyle(panel).borderLeftWidth),
                   navAlto: nav.getBoundingClientRect().height,
                 };
               }"""
        )
        assert bordes["navDerecha"] > 0, "Falta el filete de la columna de vistas."
        assert bordes["panelIzquierda"] > 0, "Falta el filete del panel de filtros."
        # Un filete que se corta a media pantalla se lee peor que ninguno.
        assert bordes["navAlto"] >= alto * 0.9, (
            f"El filete de la izquierda solo llega a {bordes['navAlto']:.0f} px "
            f"de los {alto} de la ventana."
        )

    def test_los_iconos_de_navegacion_son_simbolos_y_no_texto(self, pagina):
        """Cada vista lleva un icono de Material Symbols, no un emoji."""
        p = pagina()
        iconos = p.evaluate(
            """() => [...document.querySelectorAll(
                 '[data-testid="stMain"] [data-testid="stElementContainer"]'
                 + ':not(.st-key-nav_plegar) [data-testid="stButton"]'
                 + ' [data-testid="stIconMaterial"]')]
                 .map(e => ({nombre: e.textContent.trim(),
                             fuente: getComputedStyle(e).fontFamily}))"""
        )
        assert len(iconos) == len(self.ETIQUETAS)
        rotos = [i["nombre"] for i in iconos if "ymbols" not in i["fuente"]]
        assert rotos == [], f"Iconos sin su tipografía: {rotos}"

    def test_la_barra_lateral_se_pliega_y_se_puede_volver_a_abrir(self, pagina):
        """Plegar la barra no puede ser un viaje sin retorno.

        El control para reabrirla vive dentro de la barra de herramientas de
        Streamlit. Al ocultar esa barra entera para quitar el botón «Deploy», el
        de reabrir se fue con ella: la barra lateral se plegaba y ya no había
        forma de recuperarla sin recargar la página.
        """
        p = pagina()
        ancho = lambda: p.evaluate(  # noqa: E731
            "() => document.querySelector('[data-testid=\"stSidebar\"]')"
            "?.getBoundingClientRect().width ?? 0"
        )
        assert ancho() > 100, "La barra lateral debería empezar abierta."

        p.hover('[data-testid="stSidebar"]')
        p.wait_for_timeout(400)
        p.click('[data-testid="stSidebarHeader"] button')
        p.wait_for_timeout(1500)
        assert ancho() < 50, "La barra lateral no llegó a plegarse."

        reabrir = p.locator('[data-testid="stExpandSidebarButton"]')
        caja = reabrir.bounding_box()
        assert caja and caja["width"] > 10 and caja["height"] > 10, (
            "Con la barra plegada no queda ningún control visible para reabrirla."
        )

        reabrir.click()
        p.wait_for_timeout(1500)
        assert ancho() > 100, "El control de reabrir no devolvió la barra lateral."

    def test_la_tabla_de_tipos_esta_en_su_vista(self, pagina):
        """El contenido que se buscaba haciendo scroll tiene que estar aquí."""
        p = pagina()
        self._botones(p).nth(1).click()   # Producto e inventario
        p.wait_for_timeout(1600)
        texto = p.locator('[data-testid="stMain"]').inner_text()
        assert "Tipos de apartamento vendidos" in texto
        assert "Inventario por tipo" in texto


class TestCifras:
    def test_el_tablero_muestra_las_cifras_consolidadas(self, pagina):
        p = pagina()
        texto = p.locator('[data-testid="stMain"]').inner_text()
        assert "209" in texto  # vendidos
        assert "91" in texto   # disponibles
        assert "5 tipos" in texto  # variedad de producto

    def test_el_export_sin_depurar_infla_las_cifras_y_avisa(self, pagina):
        """El contraste que sostiene la entrega: 209 consolidados frente a 271."""
        p = pagina()
        p.get_by_text("Export sin depurar", exact=True).click()
        p.wait_for_timeout(2500)
        texto = p.locator('[data-testid="stMain"]').inner_text()
        assert "271" in texto
        assert "186" in texto
        assert "inflada" in texto.lower()
