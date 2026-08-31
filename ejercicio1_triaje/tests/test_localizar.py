"""Pruebas del localizador del Excel de seguimiento."""

from __future__ import annotations

from triaje.localizar import NOMBRE_POR_DEFECTO, buscar, carpetas_candidatas, resolver


def test_encuentra_el_excel_en_la_carpeta_configurada(tmp_path, monkeypatch):
    esperado = tmp_path / NOMBRE_POR_DEFECTO
    esperado.touch()
    monkeypatch.setenv("TRIAJE_CARPETA_SEGUIMIENTO", str(tmp_path))

    assert buscar() == esperado


def test_lo_encuentra_dentro_de_una_subcarpeta(tmp_path, monkeypatch):
    hondo = tmp_path / "Akila" / "seguimiento"
    hondo.mkdir(parents=True)
    esperado = hondo / NOMBRE_POR_DEFECTO
    esperado.touch()
    monkeypatch.setenv("TRIAJE_CARPETA_SEGUIMIENTO", str(tmp_path))

    assert buscar() == esperado


def test_busca_por_el_nombre_que_se_le_pida(tmp_path, monkeypatch):
    otro = tmp_path / "control_correos.xlsx"
    otro.touch()
    monkeypatch.setenv("TRIAJE_CARPETA_SEGUIMIENTO", str(tmp_path))

    assert buscar("control_correos.xlsx") == otro
    assert buscar(NOMBRE_POR_DEFECTO) is None


def test_si_no_existe_devuelve_donde_crearlo(tmp_path, monkeypatch):
    monkeypatch.setenv("TRIAJE_CARPETA_SEGUIMIENTO", str(tmp_path))

    destino = resolver()
    assert destino == tmp_path / NOMBRE_POR_DEFECTO
    assert not destino.exists()


def test_la_carpeta_configurada_manda_sobre_las_demas(tmp_path, monkeypatch):
    monkeypatch.setenv("TRIAJE_CARPETA_SEGUIMIENTO", str(tmp_path))
    assert carpetas_candidatas()[0] == tmp_path


def test_una_carpeta_inexistente_no_rompe_la_busqueda(monkeypatch):
    monkeypatch.setenv("TRIAJE_CARPETA_SEGUIMIENTO", "/no/existe/esta/ruta")
    assert resolver() is not None


def test_nunca_se_queda_sin_destino(monkeypatch):
    """Aunque no haya ninguna carpeta candidata, resolver() devuelve una ruta."""
    monkeypatch.delenv("TRIAJE_CARPETA_SEGUIMIENTO", raising=False)
    monkeypatch.setattr("triaje.localizar.carpetas_candidatas", list)
    assert resolver().name == NOMBRE_POR_DEFECTO
