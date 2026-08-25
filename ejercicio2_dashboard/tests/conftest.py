"""Fixtures compartidas de los tests del dashboard."""

from __future__ import annotations

import pytest

from dashboard.etl import ResultadoETL, cargar


@pytest.fixture(scope="session")
def datos() -> ResultadoETL:
    """El CSV real entregado por Akila, cargado una sola vez por sesión."""
    return cargar()
