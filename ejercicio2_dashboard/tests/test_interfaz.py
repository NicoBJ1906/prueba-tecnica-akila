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
        """Con cinco indicadores, «$137,7 MM» se cortaba a media palabra."""
        p = pagina(ancho, alto)
        cortados = p.evaluate(
            """() => [...document.querySelectorAll('[data-testid="stMetricValue"]')]
                 .filter(e => e.scrollWidth > e.clientWidth + 1)
                 .map(e => e.innerText)"""
        )
        assert cortados == [], f"Indicadores cortados: {cortados}"

    def test_no_hay_errores_de_python_en_pantalla(self, pagina):
        p = pagina()
        assert p.locator('[data-testid="stException"]').count() == 0


class TestNavegacion:
    ETIQUETAS = ["Ventas por semana", "Producto e inventario",
                 "Calidad de los datos", "Datos"]

    def test_las_cuatro_pestanas_abren_y_pintan_contenido(self, pagina):
        # Se seleccionan por posición y no por nombre: «Datos» también aparece
        # dentro de «Calidad de los datos» y la búsqueda por texto es ambigua.
        p = pagina()
        pestanas = p.locator('[role="tab"]')
        assert pestanas.count() == len(self.ETIQUETAS)

        for indice, etiqueta in enumerate(self.ETIQUETAS):
            pestana = pestanas.nth(indice)
            assert etiqueta in pestana.inner_text()
            pestana.click()
            p.wait_for_timeout(1200)
            assert p.locator('[data-testid="stException"]').count() == 0
            visible = p.evaluate(
                """() => {
                  const panel = document.querySelector('[role="tabpanel"]:not([hidden])');
                  return panel ? panel.innerText.trim().length : 0;
                }"""
            )
            assert visible > 20, f"La pestaña «{etiqueta}» aparece vacía."

    def test_la_tabla_de_tipos_esta_en_su_pestana(self, pagina):
        """El contenido que se buscaba haciendo scroll tiene que estar aquí."""
        p = pagina()
        p.get_by_role("tab", name="Producto e inventario").click()
        p.wait_for_timeout(1500)
        texto = p.locator('[role="tabpanel"]:not([hidden])').inner_text()
        assert "Tipos de apartamento vendidos" in texto
        assert "Inventario por tipo" in texto


class TestCifras:
    def test_el_tablero_muestra_las_cifras_consolidadas(self, pagina):
        p = pagina()
        texto = p.locator('[data-testid="stMain"]').inner_text()
        assert "209" in texto  # vendidos
        assert "91" in texto   # disponibles
        assert "5 tipos" in texto  # variedad de producto

    def test_el_export_crudo_infla_las_cifras_y_avisa(self, pagina):
        """El contraste que sostiene la entrega: 209 consolidados frente a 271."""
        p = pagina()
        p.get_by_text("Export crudo", exact=True).click()
        p.wait_for_timeout(2500)
        texto = p.locator('[data-testid="stMain"]').inner_text()
        assert "271" in texto
        assert "186" in texto
        assert "crudo" in texto.lower()
