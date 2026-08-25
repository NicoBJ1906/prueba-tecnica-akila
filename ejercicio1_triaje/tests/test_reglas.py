"""Tests de la capa determinista: extracción, filtros y clasificación por reglas."""

from __future__ import annotations

import pytest

from triaje.reglas import (
    categoria_remitente,
    clasificar_por_reglas,
    detectar_tema,
    detectar_temas,
    elevar_urgencia,
    es_ambiguo,
    es_cortesia,
    es_remitente_automatico,
    evaluar_urgencia,
    extraer_apartamento,
    extraer_cliente,
    requiere_revision_obligatoria,
    tiene_segunda_peticion,
)


class TestExtraccionApartamento:
    @pytest.mark.parametrize(
        "cuerpo,esperado",
        [
            ("compré el apartamento 1105 de la Torre 2", "Torre 2 Apto 1105"),
            ("soy Ana Gómez, apartamento 803", "Apto 803"),
            ("el color del piso de mi apartamento (el 906)", "Apto 906"),
            ("los acabados del apartamento 402", "Apto 402"),
            ("el apto 1502 y las fechas de notaría", "Apto 1502"),
            ("Torre 3 apto. 704 tiene una fuga", "Torre 3 Apto 704"),
        ],
    )
    def test_reconoce_las_formas_habituales(self, correo, cuerpo, esperado):
        assert extraer_apartamento(correo(cuerpo=cuerpo)) == esperado

    def test_devuelve_vacio_si_no_hay_apartamento(self, correo):
        assert extraer_apartamento(correo(cuerpo="Buenas, una pregunta rápida")) == ""

    def test_no_confunde_cualquier_numero_con_un_apartamento(self, correo):
        """Un teléfono o un importe no son un número de apartamento."""
        assert extraer_apartamento(correo(cuerpo="Mi teléfono es 3105554433")) == ""
        assert extraer_apartamento(correo(cuerpo="Pagué 350000000 pesos")) == ""


class TestExtraccionCliente:
    def test_prefiere_la_firma_del_cuerpo(self, correo):
        nombre = extraer_cliente(
            correo(cuerpo="Hola, soy Ana Gómez, apartamento 803", remitente="ana.gomez83@gmail.com")
        )
        assert nombre == "Ana Gómez"

    def test_usa_el_remitente_si_no_hay_firma(self, correo):
        assert extraer_cliente(correo(remitente="diana.castro@gmail.com")) == "Diana Castro"

    def test_ignora_los_numeros_del_correo(self, correo):
        assert extraer_cliente(correo(remitente="ana.gomez83@gmail.com")) == "Ana Gomez"

    def test_los_buzones_de_empresa_usan_la_organizacion(self, correo):
        assert extraer_cliente(correo(remitente="gerencia@inmobiliariasur.co")) == "Inmobiliariasur"


class TestRemitentesAutomaticos:
    def test_detecta_una_notificacion_bancaria(self, correo, config):
        detectado = es_remitente_automatico(
            correo(remitente="notificaciones@bancolombia.com.co"), config
        )
        assert detectado == "notificaciones@"

    def test_detecta_por_el_cuerpo_aunque_el_remitente_parezca_humano(self, correo, config):
        detectado = es_remitente_automatico(
            correo(cuerpo="Este es un mensaje automático, por favor no responda.", remitente="info@banco.com"),
            config,
        )
        assert detectado is not None

    def test_un_cliente_normal_no_se_filtra(self, correo, config):
        assert es_remitente_automatico(correo(remitente="maria.lopez@gmail.com"), config) is None

    def test_una_inmobiliaria_no_es_un_remitente_automatico(self, correo, config):
        """Un tercero que ofrece servicios es una persona: va al seguimiento."""
        assert es_remitente_automatico(correo(remitente="gerencia@inmobiliariasur.co"), config) is None


class TestCortesia:
    def test_detecta_un_agradecimiento_breve(self, correo, config):
        assert es_cortesia(correo(cuerpo="Ok, muchas gracias."), config)

    def test_un_gracias_con_pregunta_no_es_cortesia(self, correo, config):
        """El correo de Claudia Rojas: agradece y además pregunta algo."""
        cuerpo = "Muchas gracias por la atención del sábado. ¿El 1203 incluye parqueadero?"
        assert not es_cortesia(correo(cuerpo=cuerpo), config)

    def test_un_gracias_dentro_de_un_correo_largo_no_es_cortesia(self, correo, config):
        cuerpo = (
            "Buenos días, necesito la lista de documentos para la escrituración "
            "del apartamento 1502 y las fechas disponibles en notaría para poder "
            "coordinar con el banco antes del desembolso. Muchas gracias."
        )
        assert not es_cortesia(correo(cuerpo=cuerpo), config)


class TestRevisionObligatoria:
    @pytest.mark.parametrize("texto", ["quiero desistir de la compra", "solicito la devolución",
                                       "hablaré con mi abogado", "pondré una tutela"])
    def test_los_asuntos_legales_siempre_pasan_por_una_persona(self, correo, config, texto):
        assert requiere_revision_obligatoria(correo(cuerpo=texto), config) is not None

    def test_una_consulta_normal_no_requiere_revision(self, correo, config):
        assert requiere_revision_obligatoria(correo(cuerpo="¿cuándo entregan?"), config) is None

    def test_funciona_sin_tildes(self, correo, config):
        assert requiere_revision_obligatoria(correo(cuerpo="quiero la devolucion"), config) is not None


class TestUrgencia:
    def test_alta_cuando_hay_dinero_en_movimiento(self, correo, config):
        cuerpo = "El banco ya aprobó el crédito, el desembolso es esta semana"
        assert evaluar_urgencia(correo(cuerpo=cuerpo), config) == "Alta"

    def test_alta_cuando_el_cliente_lleva_tiempo_sin_respuesta(self, correo, config):
        cuerpo = "Llevo tres semanas esperando y nadie me contesta"
        assert evaluar_urgencia(correo(cuerpo=cuerpo), config) == "Alta"

    def test_media_ante_una_peticion_concreta(self, correo, config):
        assert evaluar_urgencia(correo(cuerpo="Necesito la lista de documentos"), config) == "Media"

    def test_baja_por_defecto(self, correo, config):
        assert evaluar_urgencia(correo(cuerpo="Les escribo para saludar"), config) == "Baja"

    def test_elevar_nunca_baja_la_urgencia(self):
        assert elevar_urgencia("Alta", "Media") == "Alta"
        assert elevar_urgencia("Baja", "Media") == "Media"
        assert elevar_urgencia("Media", "Media") == "Media"


class TestTemas:
    @pytest.mark.parametrize(
        "cuerpo,tema",
        [
            ("quería confirmar la fecha de entrega", "entrega"),
            ("el banco ya aprobó el crédito hipotecario", "credito"),
            ("cambiar el color del piso", "acabados"),
            ("documentos para la escrituración", "escrituracion"),
            ("quiero desistir de la compra", "desistimiento"),
            ("el parqueadero estaba inundado", "zonas_comunes"),
            ("queremos comercializar las unidades restantes", "alianza"),
        ],
    )
    def test_detecta_el_tema_por_palabras_clave(self, correo, config, cuerpo, tema):
        assert detectar_tema(correo(cuerpo=cuerpo, asunto=""), config) == tema

    def test_el_tema_del_asunto_manda_sobre_el_del_cuerpo(self, correo, config):
        """El asunto es lo que el cliente considera el motivo del correo."""
        temas = detectar_temas(
            correo(asunto="Cotización locales comerciales",
                   cuerpo="El parqueadero que nos mostraron estaba inundado"),
            config,
        )
        assert temas[0] == "comercial"
        assert "zonas_comunes" in temas

    def test_sin_coincidencias_devuelve_otro(self, correo, config):
        assert detectar_tema(correo(cuerpo="Hola", asunto=""), config) == "otro"


class TestSegundaPeticion:
    def test_detecta_el_cambio_de_asunto(self, correo):
        assert tiene_segunda_peticion(correo(cuerpo="Envíenme precios. Por otro lado, hay una fuga."))

    def test_un_correo_de_un_solo_tema_no_la_tiene(self, correo):
        assert not tiene_segunda_peticion(correo(cuerpo="Envíenme precios y áreas disponibles."))


class TestAmbiguedad:
    def test_un_correo_sin_contexto_es_ambiguo(self, correo, config):
        sospechoso = correo(
            asunto="Sin asunto",
            cuerpo="Buenas, una pregunta rápida... lo que hablamos la vez pasada sigue en pie?",
        )
        assert es_ambiguo(sospechoso, config)

    def test_un_correo_con_apartamento_no_es_ambiguo(self, correo, config):
        assert not es_ambiguo(correo(asunto="", cuerpo="sobre el apartamento 803"), config)


class TestCategoriaRemitente:
    def test_quien_menciona_su_apartamento_es_cliente(self, correo, config):
        assert categoria_remitente(correo(cuerpo="mi apartamento 803"), config) == "cliente"

    def test_quien_pide_informacion_es_prospecto(self, correo, config):
        cuerpo = "vi el proyecto y me gustaría recibir información: precios y formas de pago"
        assert categoria_remitente(correo(cuerpo=cuerpo), config) == "prospecto"

    def test_quien_ofrece_servicios_es_un_tercero(self, correo, config):
        cuerpo = "Somos una inmobiliaria y queremos comercializar las unidades"
        assert categoria_remitente(correo(cuerpo=cuerpo), config) == "tercero"


class TestClasificadorPorReglas:
    def test_devuelve_al_menos_un_asunto_valido(self, correo, config):
        clasificacion = clasificar_por_reglas(correo(), config)
        assert clasificacion.asuntos
        assert clasificacion.fuente == "reglas"

    def test_una_queja_reiterada_es_reclamacion(self, correo, config):
        cuerpo = "Llevo tres semanas esperando respuesta y nadie me contesta"
        clasificacion = clasificar_por_reglas(correo(cuerpo=cuerpo), config)
        assert clasificacion.asuntos[0].tipo == "Reclamación"

    def test_un_desperfecto_reportado_es_incidencia(self, correo, config):
        cuerpo = "El parqueadero que nos mostraron el sábado estaba inundado"
        clasificacion = clasificar_por_reglas(correo(cuerpo=cuerpo, asunto=""), config)
        assert clasificacion.asuntos[0].tipo == "Incidencia"

    def test_una_pregunta_sobre_zonas_comunes_es_consulta(self, correo, config):
        """Preguntar por el parqueadero no es reportar una avería."""
        cuerpo = "¿El apartamento 1203 incluye parqueadero o se compra aparte?"
        clasificacion = clasificar_por_reglas(correo(cuerpo=cuerpo, asunto=""), config)
        assert clasificacion.asuntos[0].tipo == "Consulta"

    def test_dos_peticiones_generan_dos_asuntos(self, correo, config):
        doble = correo(
            asunto="Cotización locales comerciales",
            cuerpo=(
                "Estamos interesados en los locales comerciales. ¿Precios y áreas? "
                "Por otro lado, el parqueadero estaba inundado, deberían revisarlo."
            ),
        )
        clasificacion = clasificar_por_reglas(doble, config)
        assert len(clasificacion.asuntos) == 2
        assert clasificacion.asuntos[0].tipo == "Pedido"
        assert clasificacion.asuntos[1].tipo == "Incidencia"

    def test_dos_temas_sin_conector_no_parten_el_correo(self, correo, config):
        """Mencionar el crédito y la entrega en la misma frase es una sola petición."""
        junto = correo(cuerpo="Ya pagué el crédito, ¿cuándo entregan?", asunto="")
        assert len(clasificar_por_reglas(junto, config).asuntos) == 1

    def test_la_confianza_baja_cuando_el_tema_es_desconocido(self, correo, config):
        clasificacion = clasificar_por_reglas(correo(cuerpo="Hola", asunto=""), config)
        assert clasificacion.asuntos[0].confianza < config.umbral_confianza
