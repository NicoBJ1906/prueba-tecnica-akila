"""Pruebas de la línea de comandos: los casos que rompen en uso real."""

from __future__ import annotations

import pytest

from triaje.__main__ import FALLOS_SEGUIDOS_TOLERADOS, main


@pytest.fixture
def entrada_csv(tmp_path):
    ruta = tmp_path / "correos.csv"
    ruta.write_text(
        "fecha_recepcion,remitente,asunto,cuerpo\n"
        "2026-07-20 08:14,ana@gmail.com,Consulta entrega,"
        "Compre el apartamento 1105 y quiero saber la fecha de entrega.\n",
        encoding="utf-8",
    )
    return ruta


def test_una_ejecucion_normal_termina_bien(tmp_path, entrada_csv):
    salida = tmp_path / "seguimiento.xlsx"
    codigo = main(["--entrada", str(entrada_csv), "--salida", str(salida), "--sin-estado"])

    assert codigo == 0
    assert salida.exists()


def test_el_excel_abierto_no_revienta_con_un_traceback(tmp_path, entrada_csv, capsys):
    """En Windows, tener el fichero abierto en Excel lo bloquea."""
    salida = tmp_path / "seguimiento.xlsx"
    main(["--entrada", str(entrada_csv), "--salida", str(salida), "--sin-estado"])
    salida.chmod(0o444)

    try:
        codigo = main(["--entrada", str(entrada_csv), "--salida", str(salida),
                       "--sin-estado"])
        error = capsys.readouterr().err
    finally:
        salida.chmod(0o644)

    assert codigo == 2
    assert "Traceback" not in error
    assert "abierto en Excel" in error
    assert "Ningún correo se ha perdido" in error


def test_auto_sin_carpeta_no_arranca(monkeypatch, capsys):
    """Sin carpeta indicada se leería INBOX, que vaciaría un buzón personal."""
    monkeypatch.delenv("TRIAJE_IMAP_CARPETA", raising=False)

    codigo = main(["--auto"])

    assert codigo == 2
    assert "TRIAJE_IMAP_CARPETA" in capsys.readouterr().err


def test_la_vigilancia_aguanta_un_fallo_puntual(monkeypatch, tmp_path, entrada_csv):
    """Un corte de red no debe apagar un proceso que corre todo el día."""
    intentos = {"n": 0}

    def pasada_inestable(*_args):
        intentos["n"] += 1
        if intentos["n"] == 2:
            return 2                     # el fallo transitorio
        if intentos["n"] >= 4:
            raise KeyboardInterrupt      # el usuario para el proceso
        return 0

    monkeypatch.setattr("triaje.__main__._una_pasada", pasada_inestable)
    monkeypatch.setattr("triaje.__main__.time.sleep", lambda _s: None)

    codigo = main(["--entrada", str(entrada_csv), "--sin-estado", "--vigilar", "1"])

    assert codigo == 0
    assert intentos["n"] >= 4, "la vigilancia se detuvo en el primer fallo"


def test_la_vigilancia_se_rinde_si_el_fallo_es_permanente(monkeypatch, entrada_csv):
    """Credenciales mal puestas no se arreglan reintentando para siempre."""
    intentos = {"n": 0}

    def pasada_rota(*_args):
        intentos["n"] += 1
        return 2

    monkeypatch.setattr("triaje.__main__._una_pasada", pasada_rota)
    monkeypatch.setattr("triaje.__main__.time.sleep", lambda _s: None)

    codigo = main(["--entrada", str(entrada_csv), "--sin-estado", "--vigilar", "1"])

    assert codigo == 2
    assert intentos["n"] == FALLOS_SEGUIDOS_TOLERADOS
