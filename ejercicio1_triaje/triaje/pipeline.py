"""Orquestación del triaje.

El orden de las etapas es la decisión de diseño central del ejercicio: cada
filtro determinista que va delante reduce el trabajo —y el coste, y el riesgo—
de la única etapa que puede usar un modelo de lenguaje.

    leer → idempotencia → duplicados → automáticos → cortesía
         → reglas → [modelo, solo si las reglas dudan] → guardrails
         → responsable → fila

Las reglas se ejecutan siempre y resuelven la mayoría. Solo lo que sale por
debajo del umbral de confianza sube al modelo. Sobre los 15 correos de muestra
eso son 2 llamadas en lugar de 12.
"""

from __future__ import annotations

import csv
import logging
import time
from datetime import datetime
from pathlib import Path

from .config import Config
from .estado import RegistroProcesados
from .modelos import (
    ESTADO_AUTOMATICO,
    ESTADO_REVISION,
    ESTADO_SIN_ACCION,
    Clasificacion,
    Correo,
    Descarte,
    FilaSeguimiento,
    ResultadoTriaje,
)
from .proveedores import ErrorDeProveedor, Proveedor, ProveedorReglas
from .reglas import (
    categoria_remitente,
    clasificar_por_reglas,
    elevar_urgencia,
    es_ambiguo,
    es_cortesia,
    es_remitente_automatico,
    extraer_apartamento,
    extraer_cliente,
    requiere_revision_obligatoria,
)

registro = logging.getLogger("triaje")

FORMATOS_FECHA = ("%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d")


def _parsear_fecha(valor: str) -> datetime:
    for formato in FORMATOS_FECHA:
        try:
            return datetime.strptime(valor.strip(), formato)
        except ValueError:
            continue
    raise ValueError(f"Fecha de recepción no reconocida: {valor!r}")


def leer_correos(ruta: str | Path) -> list[Correo]:
    """Lee el CSV de correos.

    En producción esta función se sustituye por el conector del buzón (IMAP,
    Microsoft Graph, n8n). Es el único punto del sistema que cambia: todo lo
    demás trabaja con objetos `Correo`, no con ficheros.
    """
    ruta = Path(ruta)
    if not ruta.exists():
        raise FileNotFoundError(f"No se encontró el fichero de correos en {ruta}.")

    # `utf-8-sig` descarta la marca BOM que Excel añade al exportar en Windows.
    # Sin esto, la primera columna se llamaría "﻿fecha_recepcion" y el
    # fichero parecería no tener la columna de fecha.
    with ruta.open(encoding="utf-8-sig", newline="") as fichero:
        lector = csv.DictReader(fichero)
        columnas = {"fecha_recepcion", "remitente", "asunto", "cuerpo"}
        faltantes = columnas - set(lector.fieldnames or [])
        if faltantes:
            raise ValueError(
                f"Al CSV de correos le faltan columnas: {', '.join(sorted(faltantes))}"
            )

        correos = []
        for numero, registro_csv in enumerate(lector, start=2):
            try:
                correos.append(
                    Correo(
                        fecha_recepcion=_parsear_fecha(registro_csv["fecha_recepcion"] or ""),
                        remitente=(registro_csv["remitente"] or "").strip(),
                        asunto=(registro_csv["asunto"] or "").strip(),
                        cuerpo=(registro_csv["cuerpo"] or "").strip(),
                    )
                )
            except ValueError as exc:
                # Una fila ilegible no debe tumbar el proceso del día entero.
                registro.warning("Fila %s del CSV descartada: %s", numero, exc)

    return correos


def _clasificar(correo: Correo, config: Config, proveedor: Proveedor) -> tuple[Clasificacion, str]:
    """Reglas primero; el modelo solo para lo que las reglas no resuelven.

    Esta es la forma del híbrido, y no «el modelo clasifica y las reglas son el
    respaldo». Las reglas se ejecutan siempre: son gratis e instantáneas. Si
    salen con confianza suficiente, el correo ya está clasificado y no se llama
    a nadie. Solo lo dudoso —un asunto vago, un cuerpo sin contexto— sube al
    modelo, que es donde comprender el texto vale lo que cuesta.

    El efecto se mide: sobre los 15 correos de la muestra, llamar al modelo
    siempre son 12 llamadas; escalando solo lo dudoso, 2. Mismo resultado en los
    otros 10, a coste cero y sin que salga nada del equipo.

    Devuelve también el motivo del respaldo, si lo hubo: que el sistema haya
    tenido que degradarse es información que la persona debe ver en el Excel,
    no algo que se traga un log.
    """
    por_reglas = clasificar_por_reglas(correo, config)

    if isinstance(proveedor, ProveedorReglas):
        return por_reglas, ""

    # El umbral es el mismo que decide si una fila va a revisión humana: lo que
    # no convence a las reglas es exactamente lo que merece una segunda opinión.
    # La mínima y no la media: un correo con dos peticiones, una clara y otra
    # dudosa, necesita la segunda opinión igual. Promediar la escondería.
    if por_reglas.confianza_minima >= config.umbral_confianza:
        return por_reglas, ""

    try:
        return proveedor.clasificar(correo, config), ""
    except ErrorDeProveedor as exc:
        registro.warning("Respaldo a reglas en el correo %s: %s", correo.id, exc)
        return (
            por_reglas,
            f"El clasificador automático falló ({exc}); se aplicaron reglas.",
        )


def _construir_filas(
    correo: Correo,
    clasificacion: Clasificacion,
    config: Config,
    motivo_forzado: str = "",
    estado_forzado: str = "",
    urgencia_minima: str = "Baja",
) -> list[FilaSeguimiento]:
    """Convierte una clasificación en filas del Excel, aplicando los guardrails."""
    cliente = extraer_cliente(correo)
    apartamento = extraer_apartamento(correo)
    categoria = categoria_remitente(correo, config)
    ambiguo = es_ambiguo(correo, config)

    filas = []
    for asunto in clasificacion.asuntos:
        motivos = []
        estado = estado_forzado or ESTADO_AUTOMATICO

        if motivo_forzado:
            motivos.append(motivo_forzado)
        if not estado_forzado:
            if asunto.confianza < config.umbral_confianza:
                estado = ESTADO_REVISION
                motivos.append(
                    f"Confianza {asunto.confianza:.2f} por debajo del umbral "
                    f"{config.umbral_confianza:.2f}."
                )
            if ambiguo:
                estado = ESTADO_REVISION
                motivos.append(
                    "El correo no aporta contexto suficiente (sin asunto claro, "
                    "sin apartamento y sin tema identificable)."
                )
        if clasificacion.notas:
            motivos.append(clasificacion.notas)

        # La acción combina la plantilla del negocio con el detalle del correo:
        # la plantilla garantiza que la fila siempre es accionable aunque el
        # modelo se quede corto.
        accion = asunto.accion or config.accion_de(asunto.tema)
        if apartamento and apartamento.lower() not in accion.lower():
            accion = f"{accion} ({apartamento})"

        filas.append(
            FilaSeguimiento(
                fecha=correo.fecha_recepcion,
                cliente=cliente,
                tipo=asunto.tipo,
                urgencia=elevar_urgencia(asunto.urgencia, urgencia_minima),
                accion=accion,
                responsable=config.responsable_de(asunto.tema, asunto.tipo),
                estado=estado,
                categoria=categoria,
                confianza=asunto.confianza,
                fuente=clasificacion.fuente,
                id_correo=correo.id,
                remitente=correo.remitente,
                apartamento=apartamento,
                motivo=" ".join(motivos),
            )
        )
    return filas


def _fila_de_cortesia(correo: Correo, config: Config) -> FilaSeguimiento:
    """Deja constancia de un agradecimiento, sin generar tarea ni responsable."""
    return FilaSeguimiento(
        fecha=correo.fecha_recepcion,
        cliente=extraer_cliente(correo),
        tipo="Consulta",
        urgencia="Baja",
        accion="Ninguna: mensaje de cortesía, no requiere gestión",
        responsable="—",
        estado=ESTADO_SIN_ACCION,
        categoria=categoria_remitente(correo, config),
        confianza=1.0,
        fuente="reglas",
        id_correo=correo.id,
        remitente=correo.remitente,
        apartamento=extraer_apartamento(correo),
        motivo="Agradecimiento o confirmación sin petición asociada.",
    )


def ejecutar(
    correos: list[Correo],
    config: Config,
    proveedor: Proveedor | None = None,
    registro_procesados: RegistroProcesados | None = None,
) -> ResultadoTriaje:
    """Recorre los correos y devuelve el resultado completo del triaje."""
    proveedor = proveedor or ProveedorReglas()
    inicio = time.perf_counter()

    resultado = ResultadoTriaje(
        correos_leidos=len(correos), proveedor=getattr(proveedor, "nombre", "reglas")
    )
    vistos_en_este_lote: set[str] = set()

    for correo in correos:
        # 1. Ya procesado en una ejecución anterior.
        if registro_procesados is not None and registro_procesados.ya_procesado(correo):
            resultado.ya_procesados.append(correo)
            continue

        # 2. Mismo mensaje repetido en la misma jornada.
        if correo.huella_del_dia in vistos_en_este_lote:
            resultado.descartes.append(
                Descarte(
                    correo=correo,
                    motivo="El mismo mensaje ya entró hoy desde este remitente.",
                    regla="deduplicación",
                )
            )
            if registro_procesados is not None:
                registro_procesados.marcar(correo)
            continue
        vistos_en_este_lote.add(correo.huella_del_dia)

        # 3. Remitente automático: no es un cliente escribiendo.
        patron = es_remitente_automatico(correo, config)
        if patron:
            resultado.descartes.append(
                Descarte(
                    correo=correo,
                    motivo=f"Remitente o contenido automático (coincide con «{patron}»).",
                    regla="remitentes automáticos",
                )
            )
            if registro_procesados is not None:
                registro_procesados.marcar(correo)
            continue

        # 4. Cortesía sin nada que hacer: se registra, no genera trabajo.
        #    Queda en el seguimiento como constancia de que el correo se leyó,
        #    pero sin tarea ni responsable: asignarle trabajo a nadie sería
        #    justo el ruido que este proceso pretende eliminar.
        if es_cortesia(correo, config):
            resultado.filas.append(_fila_de_cortesia(correo, config))
            if registro_procesados is not None:
                registro_procesados.marcar(correo)
            continue

        # 5. Asunto legal o financiero: lo decide una persona, clasifique lo que
        #    clasifique el modelo. Este guardrail va ANTES de la IA a propósito.
        palabra = requiere_revision_obligatoria(correo, config)

        # 6. Clasificación (la única etapa que puede usar IA).
        clasificacion, motivo_respaldo = _clasificar(correo, config, proveedor)

        motivo = motivo_respaldo
        estado = ""
        # Un asunto legal o financiero nunca es de baja prioridad: hay dinero o
        # un plazo de por medio aunque el cliente lo redacte con calma.
        urgencia_minima = "Baja"
        if palabra:
            estado = ESTADO_REVISION
            urgencia_minima = "Media"
            motivo = f"{config.motivo_revision} (detectado: «{palabra}»). {motivo}".strip()
        elif motivo_respaldo:
            estado = ESTADO_REVISION

        resultado.filas.extend(
            _construir_filas(correo, clasificacion, config, motivo, estado, urgencia_minima)
        )
        if registro_procesados is not None:
            registro_procesados.marcar(correo)

    resultado.llamadas_ia = getattr(proveedor, "llamadas", 0)
    resultado.tokens_entrada = getattr(proveedor, "tokens_entrada", 0)
    resultado.tokens_salida = getattr(proveedor, "tokens_salida", 0)
    resultado.segundos = time.perf_counter() - inicio
    return resultado
