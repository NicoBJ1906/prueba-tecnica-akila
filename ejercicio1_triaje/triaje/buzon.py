"""Lectura de correos desde un buzón IMAP.

Sustituye a `leer_correos()` y devuelve lo mismo, una lista de `Correo`. Opcional:
sin credenciales el triaje sigue funcionando sobre el CSV.

Solo lee. No marca como leído, no archiva y no responde.

Sirve cualquier servidor IMAP, no solo Gmail:

    export TRIAJE_IMAP_USUARIO="buzon@dominio.com"
    export TRIAJE_IMAP_CLAVE="xxxx xxxx xxxx xxxx"   # contraseña de aplicación
    export TRIAJE_IMAP_SERVIDOR="imap.zoho.com"      # opcional
"""

from __future__ import annotations

import email
import imaplib
import os
import re
from datetime import datetime, timedelta
from email.header import decode_header, make_header
from email.message import Message
from email.utils import parsedate_to_datetime

from .modelos import Correo

SERVIDOR_POR_DEFECTO = "imap.gmail.com"

# Servidores IMAP de los proveedores más habituales. Todos usan el puerto 993.
SERVIDORES_CONOCIDOS = {
    "gmail": "imap.gmail.com",
    "outlook": "outlook.office365.com",
    "office365": "outlook.office365.com",
    "hotmail": "outlook.office365.com",
    "zoho": "imap.zoho.com",
    "yahoo": "imap.mail.yahoo.com",
    "icloud": "imap.mail.me.com",
    "gmx": "imap.gmx.com",
}
PUERTO_SSL = 993
CARPETA_POR_DEFECTO = "INBOX"

# Tope por si se apunta a un buzón con años de historia.
MAXIMO_MENSAJES = 200


class ErrorDeBuzon(RuntimeError):
    """No se pudo leer el buzón."""


def _comprobar_carpeta(carpeta: str, permitir_inbox: bool) -> None:
    """Exige una carpeta dedicada: apuntar a INBOX por descuido vacía la bandeja."""
    if carpeta.strip().upper() == "INBOX" and not permitir_inbox:
        raise ErrorDeBuzon(
            "Leer INBOX descargaría la bandeja de entrada completa.\n"
            "Usa una carpeta o etiqueta dedicada:\n"
            "    python -m triaje --buzon --carpeta Akila\n"
            "Si de verdad quieres la bandeja entera, añade --permitir-inbox."
        )


def _texto_de_cabecera(valor: str | None) -> str:
    """Decodifica «=?UTF-8?Q?Consulta?=» a texto legible."""
    if not valor:
        return ""
    try:
        return str(make_header(decode_header(valor))).strip()
    except (UnicodeDecodeError, LookupError, ValueError):
        return valor.strip()


def _cuerpo_de_mensaje(mensaje: Message) -> str:
    """Texto plano del correo, sin adjuntos ni el hilo citado."""
    partes: list[str] = []

    for parte in mensaje.walk() if mensaje.is_multipart() else [mensaje]:
        if parte.get_content_maintype() == "multipart":
            continue
        if parte.get_content_disposition() == "attachment":
            continue
        if parte.get_content_type() != "text/plain":
            continue

        carga = parte.get_payload(decode=True)
        if carga is None:
            continue
        juego = parte.get_content_charset() or "utf-8"
        try:
            partes.append(carga.decode(juego, errors="replace"))
        except LookupError:
            partes.append(carga.decode("utf-8", errors="replace"))

    if not partes:
        return ""

    texto = "\n".join(partes)

    # Sin cortar la cita, un «gracias» hereda el tema del correo que responde.
    # La tilde de «escribió» depende del idioma del cliente del remitente.
    corte = re.search(
        r"\n\s*(?:El .{0,80}escribi[oó]\s*:|On .{0,80}wrote\s*:|-{2,}\s*Mensaje original)",
        texto,
        re.IGNORECASE,
    )
    if corte:
        texto = texto[: corte.start()]

    limpio = [linea for linea in texto.splitlines() if not linea.lstrip().startswith(">")]
    return "\n".join(limpio).strip()


def _a_correo(bruto: bytes) -> Correo | None:
    mensaje = email.message_from_bytes(bruto)

    # «Nombre <correo@dominio>» → «correo@dominio», como venía en el CSV.
    remitente = _texto_de_cabecera(mensaje.get("From"))
    encontrado = re.search(r"<([^>]+)>", remitente)
    if encontrado:
        remitente = encontrado.group(1)
    remitente = remitente.strip()

    if not remitente:
        return None

    cabecera_fecha = mensaje.get("Date")
    try:
        fecha = parsedate_to_datetime(cabecera_fecha) if cabecera_fecha else datetime.now()
    except (TypeError, ValueError):
        fecha = datetime.now()

    # A hora local antes de quitar la zona, para no desplazar el correo de día.
    if fecha.tzinfo is not None:
        fecha = fecha.astimezone().replace(tzinfo=None)

    return Correo(
        fecha_recepcion=fecha,
        remitente=remitente,
        asunto=_texto_de_cabecera(mensaje.get("Subject")),
        cuerpo=_cuerpo_de_mensaje(mensaje),
    )


def servidor_para(usuario: str) -> str | None:
    """Deduce el servidor a partir del dominio del correo."""
    dominio = usuario.partition("@")[2].lower()
    if not dominio:
        return None
    for clave, host in SERVIDORES_CONOCIDOS.items():
        if dominio.startswith(clave) or f".{clave}." in f".{dominio}":
            return host
    return None


def servidor_configurado(por_defecto: str = SERVIDOR_POR_DEFECTO) -> str:
    """Servidor IMAP: nombre corto («outlook»), host completo, o deducido del correo."""
    valor = os.environ.get("TRIAJE_IMAP_SERVIDOR", "").strip()
    if valor:
        return SERVIDORES_CONOCIDOS.get(valor.lower(), valor)

    usuario = os.environ.get("TRIAJE_IMAP_USUARIO", "").strip()
    return servidor_para(usuario) or por_defecto


def credenciales() -> tuple[str, str]:
    usuario = os.environ.get("TRIAJE_IMAP_USUARIO", "").strip()
    clave = os.environ.get("TRIAJE_IMAP_CLAVE", "").strip()

    if not usuario or not clave:
        raise ErrorDeBuzon(
            "Faltan las credenciales del buzón. Defínelas en el entorno:\n"
            '    export TRIAJE_IMAP_USUARIO="tu.cuenta@gmail.com"\n'
            '    export TRIAJE_IMAP_CLAVE="contraseña de aplicación de 16 letras"\n'
            "En Gmail se generan en https://myaccount.google.com/apppasswords y\n"
            "requieren tener activada la verificación en dos pasos.\n"
            "O ejecuta sin --buzon para procesar el CSV de la muestra."
        )

    # Google la muestra en grupos de cuatro; con espacios el login falla.
    return usuario, clave.replace(" ", "")


def leer_buzon(
    dias: int = 1,
    carpeta: str = CARPETA_POR_DEFECTO,
    servidor: str | None = None,
    conexion: object | None = None,
    permitir_inbox: bool = False,
) -> list[Correo]:
    """Correos recientes del buzón. `conexion` permite inyectar un doble en las pruebas."""
    _comprobar_carpeta(carpeta, permitir_inbox)
    propia = conexion is None

    if propia:
        usuario, clave = credenciales()
        servidor = servidor or servidor_configurado()
        try:
            conexion = imaplib.IMAP4_SSL(servidor, PUERTO_SSL)
            conexion.login(usuario, clave)
        except imaplib.IMAP4.error as exc:
            raise ErrorDeBuzon(
                f"No se pudo entrar en el buzón ({exc}). Comprueba el usuario y "
                "que la contraseña sea una CONTRASEÑA DE APLICACIÓN, no la del correo."
            ) from exc
        except OSError as exc:
            raise ErrorDeBuzon(f"No se pudo conectar con {servidor}: {exc}") from exc

    try:
        estado, _ = conexion.select(carpeta, readonly=True)
        if estado != "OK":
            raise ErrorDeBuzon(f"No existe la carpeta «{carpeta}» en el buzón.")

        desde = (datetime.now() - timedelta(days=max(dias, 1))).strftime("%d-%b-%Y")
        estado, respuesta = conexion.search(None, "SINCE", desde)
        if estado != "OK":
            raise ErrorDeBuzon("El buzón rechazó la búsqueda de correos recientes.")

        identificadores = (respuesta[0] or b"").split()[-MAXIMO_MENSAJES:]

        correos: list[Correo] = []
        for identificador in identificadores:
            # PEEK descarga sin añadir la marca \Seen; con BODY[] o RFC822 el
            # servidor daría por leído el correo del cliente.
            estado, datos = conexion.fetch(identificador, "(BODY.PEEK[])")
            if estado != "OK" or not datos or not isinstance(datos[0], tuple):
                continue

            correo = _a_correo(datos[0][1])
            if correo is not None:
                correos.append(correo)

        correos.sort(key=lambda c: c.fecha_recepcion)
        return correos
    finally:
        if propia:
            try:
                conexion.close()
                conexion.logout()
            except (imaplib.IMAP4.error, OSError):
                pass
