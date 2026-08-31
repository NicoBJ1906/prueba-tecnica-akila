"""Pruebas del conector IMAP.

No usan red ni credenciales: se inyecta un doble que responde como un servidor.
"""

from __future__ import annotations

import pytest

from triaje.buzon import (
    MAXIMO_MENSAJES,
    SERVIDOR_POR_DEFECTO,
    ErrorDeBuzon,
    _a_correo,
    credenciales,
    leer_buzon,
    servidor_configurado,
    servidor_para,
)


def mensaje(
    remitente: str = "Maria Lopez <maria.lopez@gmail.com>",
    asunto: str = "Consulta apartamento",
    cuerpo: str = "Buenos dias, compre el apartamento 1105.",
    fecha: str = "Mon, 30 Aug 2026 08:14:00 +0200",
    tipo: str = "text/plain",
) -> bytes:
    return (
        f"From: {remitente}\r\n"
        f"Subject: {asunto}\r\n"
        f"Date: {fecha}\r\n"
        f"Content-Type: {tipo}; charset=utf-8\r\n"
        f"\r\n"
        f"{cuerpo}\r\n"
    ).encode()


class ConexionFalsa:
    """Doble de IMAP4_SSL que registra las órdenes recibidas."""

    def __init__(self, mensajes: list[bytes], estado_select: str = "OK") -> None:
        self.mensajes = mensajes
        self.estado_select = estado_select
        self.ordenes: list[str] = []
        self.select_readonly: bool | None = None
        self.carpeta: str | None = None

    def select(self, carpeta, readonly=False):
        self.carpeta = carpeta
        self.select_readonly = readonly
        return self.estado_select, [b""]

    def search(self, _juego, *criterios):
        self.ordenes.append("search " + " ".join(criterios))
        ids = b" ".join(str(i).encode() for i in range(1, len(self.mensajes) + 1))
        return "OK", [ids]

    def fetch(self, identificador, partes):
        self.ordenes.append(f"fetch {partes}")
        indice = int(identificador) - 1
        return "OK", [(b"1 (RFC822 {n}", self.mensajes[indice])]

    def close(self):
        self.ordenes.append("close")

    def logout(self):
        self.ordenes.append("logout")


# ---------------------------------------------------------------------------
# La promesa que no se puede romper: leer sin modificar el buzón
# ---------------------------------------------------------------------------

def test_descarga_sin_marcar_como_leido():
    """La descarga usa BODY.PEEK[]; con BODY[] o RFC822 el correo quedaría leído."""
    conexion = ConexionFalsa([mensaje()])
    leer_buzon(carpeta="Akila", conexion=conexion)

    ordenes_fetch = [o for o in conexion.ordenes if o.startswith("fetch")]
    assert ordenes_fetch, "no se descargó ningún mensaje"
    for orden in ordenes_fetch:
        assert "BODY.PEEK[]" in orden
        assert "RFC822" not in orden, "RFC822 marca el correo como leído"


def test_la_sesion_se_abre_en_solo_lectura():
    """Con readonly=True el servidor rechaza cualquier escritura."""
    conexion = ConexionFalsa([mensaje()])
    leer_buzon(carpeta="Akila", conexion=conexion)
    assert conexion.select_readonly is True


# ---------------------------------------------------------------------------
# Conversión a los objetos que entiende el pipeline
# ---------------------------------------------------------------------------

def test_devuelve_objetos_correo_del_pipeline():
    correos = leer_buzon(carpeta="Akila", conexion=ConexionFalsa([mensaje()]))
    assert len(correos) == 1
    assert correos[0].remitente == "maria.lopez@gmail.com"
    assert correos[0].asunto == "Consulta apartamento"


def test_decodifica_asunto_mime():
    """Un asunto MIME se convierte a texto legible."""
    crudo = mensaje(asunto="=?UTF-8?Q?Escrituraci=C3=B3n_apartamento?=")
    assert _a_correo(crudo).asunto == "Escrituración apartamento"


def test_extrae_la_direccion_del_remitente():
    crudo = mensaje(remitente="Ana Gómez <ana.gomez83@gmail.com>")
    assert _a_correo(crudo).remitente == "ana.gomez83@gmail.com"


def test_remitente_sin_nombre_tambien_vale():
    assert _a_correo(mensaje(remitente="pedro@yahoo.es")).remitente == "pedro@yahoo.es"


def test_la_fecha_queda_sin_zona_horaria():
    """Las fechas se normalizan sin zona, como las del CSV."""
    correo = _a_correo(mensaje(fecha="Mon, 30 Aug 2026 08:14:00 +0200"))
    assert correo.fecha_recepcion.tzinfo is None


def test_fecha_ilegible_no_tumba_el_correo():
    correo = _a_correo(mensaje(fecha="ayer por la tarde"))
    assert correo.fecha_recepcion is not None


@pytest.mark.parametrize(
    "marca",
    [
        "El 29 ago 2026 a las 10:00, Akila escribio:",
        "El 29 ago 2026 a las 10:00, Akila escribió:",
        "On Fri, Aug 29, 2026 at 10:00 AM Akila wrote:",
        "---- Mensaje original ----",
    ],
)
def test_corta_el_hilo_citado(marca):
    """El cuerpo se queda solo con lo que escribió el remitente."""
    cuerpo = f"Muchas gracias.\n\n{marca}\n> texto anterior del hilo"
    assert _a_correo(mensaje(cuerpo=cuerpo)).cuerpo == "Muchas gracias."


def test_ignora_las_lineas_citadas_con_mayor_que():
    cuerpo = "Mi pregunta es esta.\n> lo que dijo el otro\n> y su firma"
    assert _a_correo(mensaje(cuerpo=cuerpo)).cuerpo == "Mi pregunta es esta."


def test_un_correo_solo_html_no_rompe_nada():
    """Sin parte text/plain el cuerpo queda vacío, pero el correo se procesa."""
    crudo = mensaje(cuerpo="<p>Hola</p>", tipo="text/html")
    correo = _a_correo(crudo)
    assert correo is not None
    assert correo.cuerpo == ""


def test_correo_sin_remitente_se_descarta():
    assert _a_correo(mensaje(remitente="")) is None


# ---------------------------------------------------------------------------
# Comportamiento del conector
# ---------------------------------------------------------------------------

def test_los_correos_salen_ordenados_por_fecha():
    conexion = ConexionFalsa(
        [
            mensaje(fecha="Mon, 30 Aug 2026 14:50:00 +0200", asunto="tarde"),
            mensaje(fecha="Mon, 30 Aug 2026 08:14:00 +0200", asunto="manana"),
        ]
    )
    correos = leer_buzon(carpeta="Akila", conexion=conexion)
    assert [c.asunto for c in correos] == ["manana", "tarde"]


def test_acota_la_busqueda_a_los_dias_pedidos():
    conexion = ConexionFalsa([mensaje()])
    leer_buzon(dias=3, carpeta="Akila", conexion=conexion)
    assert any(o.startswith("search SINCE") for o in conexion.ordenes)


def test_no_descarga_un_buzon_entero():
    """La descarga se corta en MAXIMO_MENSAJES."""
    conexion = ConexionFalsa([mensaje() for _ in range(MAXIMO_MENSAJES + 25)])
    assert len(leer_buzon(carpeta="Akila", conexion=conexion)) == MAXIMO_MENSAJES


def test_carpeta_inexistente_da_un_error_claro():
    conexion = ConexionFalsa([mensaje()], estado_select="NO")
    with pytest.raises(ErrorDeBuzon, match="carpeta"):
        leer_buzon(carpeta="NoExiste", conexion=conexion)


def test_sin_credenciales_el_error_explica_que_hacer(monkeypatch):
    monkeypatch.delenv("TRIAJE_IMAP_USUARIO", raising=False)
    monkeypatch.delenv("TRIAJE_IMAP_CLAVE", raising=False)
    with pytest.raises(ErrorDeBuzon) as exc:
        credenciales()
    assert "TRIAJE_IMAP_USUARIO" in str(exc.value)
    assert "apppasswords" in str(exc.value)


def test_la_clave_admite_los_espacios_que_muestra_google(monkeypatch):
    """Los espacios de la contraseña de aplicación se ignoran."""
    monkeypatch.setenv("TRIAJE_IMAP_USUARIO", "triaje@gmail.com")
    monkeypatch.setenv("TRIAJE_IMAP_CLAVE", "abcd efgh ijkl mnop")
    assert credenciales() == ("triaje@gmail.com", "abcdefghijklmnop")


def test_el_servidor_no_esta_atado_a_gmail(monkeypatch):
    """El servidor se toma de TRIAJE_IMAP_SERVIDOR."""
    monkeypatch.setenv("TRIAJE_IMAP_SERVIDOR", "imap.zoho.com")
    assert servidor_configurado() == "imap.zoho.com"


def test_sin_variable_de_servidor_se_usa_gmail(monkeypatch):
    monkeypatch.delenv("TRIAJE_IMAP_SERVIDOR", raising=False)
    assert servidor_configurado() == SERVIDOR_POR_DEFECTO


def test_no_lee_la_bandeja_entera_por_descuido():
    """Leer INBOX sin permiso explícito falla."""
    with pytest.raises(ErrorDeBuzon, match="INBOX"):
        leer_buzon(conexion=ConexionFalsa([mensaje()]))


def test_inbox_solo_si_se_pide_a_proposito():
    correos = leer_buzon(conexion=ConexionFalsa([mensaje()]), permitir_inbox=True)
    assert len(correos) == 1


def test_una_carpeta_dedicada_no_necesita_permiso():
    conexion = ConexionFalsa([mensaje()])
    leer_buzon(carpeta="Akila", conexion=conexion)
    assert conexion.carpeta == "Akila"


def test_deduce_el_servidor_por_el_dominio_del_correo():
    assert servidor_para("ana@gmail.com") == "imap.gmail.com"
    assert servidor_para("jefe@outlook.com") == "outlook.office365.com"
    assert servidor_para("x@hotmail.es") == "outlook.office365.com"


def test_un_dominio_propio_no_se_deduce():
    """Con un correo corporativo hay que indicar el servidor a mano."""
    assert servidor_para("contacto@akila.com.co") is None


def test_el_servidor_explicito_manda_sobre_el_deducido(monkeypatch):
    monkeypatch.setenv("TRIAJE_IMAP_USUARIO", "ana@gmail.com")
    monkeypatch.setenv("TRIAJE_IMAP_SERVIDOR", "outlook")
    assert servidor_configurado() == "outlook.office365.com"
