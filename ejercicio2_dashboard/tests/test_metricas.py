"""Tests de los indicadores que ve dirección."""

from __future__ import annotations

import pandas as pd
import pytest

from dashboard.etl import ESTADO_DISPONIBLE, ESTADO_VENDIDO
from dashboard.metricas import (
    MAXIMO_HALLAZGOS,
    ORDEN_TONOS,
    avance_acumulado,
    avance_por_altura,
    avance_por_torre,
    cohortes_entrega,
    composicion_pago,
    formato_cop,
    insights,
    resumen,
    ritmo_semanal_reciente,
    tipos_vendidos,
    ventas_por_semana,
)


class TestVentasPorSemana:
    def test_agrupa_por_semana_iso_etiquetando_el_lunes(self, fila, df_de):
        # Miércoles y viernes de la misma semana ISO.
        df = df_de(
            fila(id=1, estado=ESTADO_VENDIDO, fecha_venta=pd.Timestamp("2026-01-07")),
            fila(id=2, piso=6, estado=ESTADO_VENDIDO, fecha_venta=pd.Timestamp("2026-01-09")),
        )
        resultado = ventas_por_semana(df)
        assert len(resultado) == 1
        assert resultado.iloc[0]["semana"] == pd.Timestamp("2026-01-05")  # lunes
        assert resultado.iloc[0]["unidades"] == 2

    def test_rellena_las_semanas_sin_ventas(self, fila, df_de):
        """Un hueco comercial debe verse en el eje, no desaparecer."""
        df = df_de(
            fila(id=1, estado=ESTADO_VENDIDO, fecha_venta=pd.Timestamp("2026-01-05")),
            fila(id=2, piso=6, estado=ESTADO_VENDIDO, fecha_venta=pd.Timestamp("2026-01-26")),
        )
        resultado = ventas_por_semana(df)
        assert len(resultado) == 4
        assert (resultado["unidades"] == [1, 0, 0, 1]).all()

    def test_puede_desactivarse_el_relleno(self, fila, df_de):
        df = df_de(
            fila(id=1, estado=ESTADO_VENDIDO, fecha_venta=pd.Timestamp("2026-01-05")),
            fila(id=2, piso=6, estado=ESTADO_VENDIDO, fecha_venta=pd.Timestamp("2026-01-26")),
        )
        assert len(ventas_por_semana(df, incluir_semanas_vacias=False)) == 2

    def test_ignora_los_disponibles(self, fila, df_de):
        df = df_de(
            fila(id=1, estado=ESTADO_VENDIDO, fecha_venta=pd.Timestamp("2026-01-07")),
            fila(id=2, piso=6, estado=ESTADO_DISPONIBLE),
        )
        assert ventas_por_semana(df)["unidades"].sum() == 1

    def test_sin_ventas_devuelve_tabla_vacia_con_columnas(self, fila, df_de):
        resultado = ventas_por_semana(df_de(fila(estado=ESTADO_DISPONIBLE)))
        assert resultado.empty
        assert list(resultado.columns) == ["semana", "unidades", "valor_cop"]


class TestTiposVendidos:
    def test_los_porcentajes_suman_cien(self, fila, df_de):
        df = df_de(
            fila(id=1, tipo_apartamento="1 Alcoba", estado=ESTADO_VENDIDO, fecha_venta=pd.Timestamp("2026-01-05")),
            fila(id=2, piso=6, tipo_apartamento="1 Alcoba", estado=ESTADO_VENDIDO, fecha_venta=pd.Timestamp("2026-01-05")),
            fila(id=3, piso=7, tipo_apartamento="Penthouse", estado=ESTADO_VENDIDO, fecha_venta=pd.Timestamp("2026-01-05")),
        )
        tabla = tipos_vendidos(df)
        assert tabla["porcentaje"].sum() == pytest.approx(100.0)
        assert tabla.iloc[0]["tipo_apartamento"] == "1 Alcoba"
        assert tabla.iloc[0]["porcentaje"] == pytest.approx(66.67, abs=0.01)

    def test_el_porcentaje_es_sobre_ventas_no_sobre_inventario(self, fila, df_de):
        """Dos vendidos y ocho disponibles: cada vendido es el 50 % de las ventas."""
        vendidos = [
            fila(id=i, piso=i, tipo_apartamento=t, estado=ESTADO_VENDIDO, fecha_venta=pd.Timestamp("2026-01-05"))
            for i, t in enumerate(["1 Alcoba", "Penthouse"], start=1)
        ]
        disponibles = [fila(id=100 + i, piso=100 + i) for i in range(8)]
        tabla = tipos_vendidos(df_de(*vendidos, *disponibles))
        assert set(tabla["porcentaje"]) == {50.0}

    def test_sin_ventas_devuelve_tabla_vacia(self, fila, df_de):
        assert tipos_vendidos(df_de(fila(estado=ESTADO_DISPONIBLE))).empty


class TestResumen:
    def test_cuenta_vendidos_disponibles_y_variedad(self, fila, df_de):
        df = df_de(
            fila(id=1, tipo_apartamento="1 Alcoba", estado=ESTADO_VENDIDO, fecha_venta=pd.Timestamp("2026-01-05")),
            fila(id=2, piso=6, tipo_apartamento="Penthouse", estado=ESTADO_DISPONIBLE),
            fila(id=3, piso=7, tipo_apartamento="Penthouse", estado=ESTADO_DISPONIBLE),
        )
        r = resumen(df)
        assert (r.vendidos, r.disponibles, r.total_unidades) == (1, 2, 3)
        assert r.variedad_tipos == 2
        assert r.porcentaje_avance == pytest.approx(33.33, abs=0.01)

    def test_sin_ventas_no_divide_por_cero(self, fila, df_de):
        r = resumen(df_de(fila(estado=ESTADO_DISPONIBLE)))
        assert r.ritmo_semanal_reciente == 0.0
        assert r.meses_inventario is None
        assert r.primera_venta is None


class TestFormatoCop:
    @pytest.mark.parametrize(
        "valor,esperado",
        [
            (137_744_900_000, "$137,7 MM"),
            (682_500_000, "$682 M"),
            (1_500_000, "$2 M"),
            (250_000, "$250.000"),
        ],
    )
    def test_abrevia_segun_magnitud(self, valor, esperado):
        assert formato_cop(valor) == esperado


class TestDatosReales:
    """Golden tests de los cinco apartados exigidos por el enunciado."""

    def test_apartados_del_enunciado(self, datos):
        r = resumen(datos.canonico)
        assert r.vendidos == 209  # 2. apartamentos vendidos
        assert r.disponibles == 91  # 4. apartamentos disponibles
        assert r.variedad_tipos == 5  # 5. variedad de producto

    def test_ventas_por_semana_cubre_el_periodo_completo(self, datos):
        # 1. ventas por semana
        serie = ventas_por_semana(datos.canonico)
        assert serie["unidades"].sum() == 209
        assert len(serie) == 60  # semanas continuas entre la primera y la última venta
        assert (serie["semana"].diff().dropna() == pd.Timedelta(days=7)).all()

    def test_tabla_de_tipos_vendidos(self, datos):
        # 3. tipos de apartamento vendidos, con su porcentaje
        tabla = tipos_vendidos(datos.canonico)
        assert len(tabla) == 5
        assert tabla["unidades_vendidas"].sum() == 209
        assert tabla["porcentaje"].sum() == pytest.approx(100.0)

    def test_el_valor_vendido_coincide_con_la_suma_de_precios(self, datos):
        r = resumen(datos.canonico)
        vendidos = datos.canonico[datos.canonico["estado"] == ESTADO_VENDIDO]
        assert r.valor_vendido_cop == vendidos["precio_cop"].sum()
        assert r.valor_vendido_cop == 137_744_900_000

    def test_el_ritmo_reciente_es_plausible(self, datos):
        ritmo = ritmo_semanal_reciente(datos.canonico)
        assert 0 < ritmo < 20


class TestAvanceAcumulado:
    def test_la_curva_es_monotona_y_acaba_en_el_total(self, datos):
        curva = avance_acumulado(datos.canonico)
        assert (curva["unidades"].diff().dropna() >= 0).all(), (
            "Un acumulado nunca baja."
        )
        assert curva["unidades"].iloc[-1] == 209
        assert curva["porcentaje_proyecto"].iloc[-1] == pytest.approx(209 / 300 * 100)

    def test_sin_ventas_devuelve_tabla_vacia(self, fila, df_de):
        assert avance_acumulado(df_de(fila())).empty


class TestAvancePorTorre:
    def test_los_totales_por_torre_suman_el_proyecto(self, datos):
        torres = avance_por_torre(datos.canonico)
        assert torres["total"].sum() == 300
        assert torres["vendidos"].sum() == 209
        assert (torres["vendidos"] + torres["disponibles"] == torres["total"]).all()

    def test_el_porcentaje_es_sobre_la_propia_torre(self, fila, df_de):
        df = df_de(
            fila(id=1, torre="Torre 1", numero_puerta=1, estado=ESTADO_VENDIDO,
                 fecha_venta=pd.Timestamp("2026-01-05")),
            fila(id=2, torre="Torre 1", numero_puerta=2),
            fila(id=3, torre="Torre 2", numero_puerta=1, estado=ESTADO_VENDIDO,
                 fecha_venta=pd.Timestamp("2026-01-05")),
        )
        torres = avance_por_torre(df).set_index("torre")
        assert torres.loc["Torre 1", "porcentaje"] == pytest.approx(50.0)
        assert torres.loc["Torre 2", "porcentaje"] == pytest.approx(100.0)


class TestAvancePorAltura:
    def test_cada_piso_cae_en_su_franja(self, fila, df_de):
        df = df_de(
            fila(id=1, piso=3, numero_puerta=1),
            fila(id=2, piso=12, numero_puerta=2),
            fila(id=3, piso=20, numero_puerta=3),
        )
        franjas = set(avance_por_altura(df)["franja"])
        assert franjas == {"Bajos · 1-7", "Medios · 8-15", "Altos · 16+"}

    def test_no_pierde_ni_duplica_unidades(self, datos):
        assert avance_por_altura(datos.canonico)["total"].sum() == 300


class TestCohortesEntrega:
    def test_agrupa_por_trimestre_sin_perder_unidades(self, datos):
        cohortes = cohortes_entrega(datos.canonico)
        assert cohortes["total"].sum() == 300
        assert (cohortes["trimestre"].diff().dropna() > pd.Timedelta(0)).all()

    def test_ignora_las_filas_sin_fecha_de_entrega(self, fila, df_de):
        df = df_de(fila(id=1, fecha_entrega=pd.NaT), fila(id=2, numero_puerta=2))
        assert cohortes_entrega(df)["total"].sum() == 1


class TestComposicionPago:
    def test_credito_y_contado_suman_el_valor_vendido(self, datos):
        pagos = composicion_pago(datos.canonico)
        r = resumen(datos.canonico)
        assert pagos["unidades"].sum() == r.vendidos
        assert pagos["valor_cop"].sum() == pytest.approx(r.valor_vendido_cop)

    def test_solo_cuenta_lo_vendido(self, fila, df_de):
        df = df_de(fila(id=1), fila(id=2, numero_puerta=2))  # ambos disponibles
        assert composicion_pago(df).empty


class TestInsights:
    def test_devuelve_hallazgos_estructurados_y_ordenados(self, datos):
        hallazgos = insights(datos.canonico)
        assert hallazgos, "Con los datos reales tiene que salir algún hallazgo."
        assert len(hallazgos) <= MAXIMO_HALLAZGOS
        for h in hallazgos:
            assert h.tono in ORDEN_TONOS
            assert h.titular and h.cifra and h.detalle
        posiciones = [ORDEN_TONOS[h.tono] for h in hallazgos]
        assert posiciones == sorted(posiciones), "Los riesgos van primero."

    def test_no_inventa_hallazgos_sin_datos(self, fila, df_de):
        assert insights(df_de(fila())) == []
        assert insights(df_de(fila()).iloc[0:0]) == []

    def test_calla_cuando_la_diferencia_no_es_significativa(self, fila, df_de):
        """Dos torres al mismo ritmo no son noticia: el umbral evita el ruido."""
        filas = []
        for i in range(20):
            torre = "Torre 1" if i < 10 else "Torre 2"
            vendido = i % 10 < 7  # 70 % en ambas
            filas.append(
                fila(
                    id=i, torre=torre, numero_puerta=i,
                    estado=ESTADO_VENDIDO if vendido else ESTADO_DISPONIBLE,
                    fecha_venta=pd.Timestamp("2026-01-05") if vendido else pd.NaT,
                )
            )
        titulares = " ".join(h.titular for h in insights(df_de(*filas)))
        assert "rezagada" not in titulares
