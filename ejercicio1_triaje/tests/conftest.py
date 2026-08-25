"""Fixtures compartidas de los tests del triaje."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

from triaje.config import Config, cargar_config
from triaje.modelos import Correo

RAIZ = Path(__file__).resolve().parents[2]
CSV_CORREOS = RAIZ / "data" / "correos_clientes.csv"


@pytest.fixture(scope="session")
def csv_correos() -> Path:
    """Los 15 correos de muestra entregados con el enunciado."""
    return CSV_CORREOS


@pytest.fixture(scope="session")
def config() -> Config:
    return cargar_config()


@pytest.fixture
def correo():
    """Constructor de correos de prueba con valores por defecto sensatos."""

    def _crear(
        cuerpo: str = "Buenos días, quería consultar algo.",
        asunto: str = "Consulta",
        remitente: str = "cliente@gmail.com",
        fecha: str = "2026-07-20 09:00",
    ) -> Correo:
        return Correo(
            fecha_recepcion=datetime.strptime(fecha, "%Y-%m-%d %H:%M"),
            remitente=remitente,
            asunto=asunto,
            cuerpo=cuerpo,
        )

    return _crear
