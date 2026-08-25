"""Fixtures compartidas de los tests del dashboard."""

from __future__ import annotations

import pandas as pd
import pytest

from dashboard.etl import ESTADO_DISPONIBLE, ResultadoETL, cargar


@pytest.fixture(scope="session")
def datos() -> ResultadoETL:
    """El CSV real entregado por Akila, cargado una sola vez por sesión."""
    return cargar()


@pytest.fixture
def fila():
    """Fila válida mínima; cada test sobrescribe solo lo que le interesa."""

    def _crear(**cambios) -> dict:
        base = {
            "id": 1,
            "torre": "Torre 1",
            "piso": 5,
            "numero_puerta": 1,
            "apartamento": "Torre 1 Apto 501",
            "tipo_apartamento": "2 Alcobas",
            "area_m2": 70,
            "precio_cop": 500_000_000,
            "estado": ESTADO_DISPONIBLE,
            "fecha_venta": pd.NaT,
            "fecha_entrega": pd.Timestamp("2027-01-01"),
            "forma_pago": None,
            "porcentaje_credito": None,
            "monto_credito_cop": None,
            "monto_contado_cop": None,
        }
        return {**base, **cambios}

    return _crear


@pytest.fixture
def df_de():
    """Construye un DataFrame a partir de las filas que se le pasen."""

    def _crear(*filas) -> pd.DataFrame:
        return pd.DataFrame(list(filas))

    return _crear
