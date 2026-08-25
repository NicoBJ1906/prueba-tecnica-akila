"""Tests de los indicadores que ve dirección."""

from __future__ import annotations

import pandas as pd
import pytest

from dashboard.etl import ESTADO_DISPONIBLE, ESTADO_VENDIDO
from dashboard.metricas import (
    formato_cop,
    resumen,
    ritmo_semanal_reciente,
    tipos_vendidos,
    ventas_por_semana,
)

from .test_etl import df_de, fila


class TestVentasPorSemana:
    def test_agrupa_por_semana_iso_etiquetando_el_lunes(self):
        # Miércoles y viernes de la misma semana ISO.
        df = df_de(
            fila(id=1, estado=ESTADO_VENDIDO, fecha_venta=pd.Timestamp("2026-01-07")),
            fila(id=2, piso=6, estado=ESTADO_VENDIDO, fecha_venta=pd.Timestamp("2026-01-09")),
        )
        resultado = ventas_por_semana(df)
        assert len(resultado) == 1
        assert resultado.iloc[0]["semana"] == pd.Timestamp("2026-01-05")  # lunes
        assert resultado.iloc[0]["unidades"] == 2

    def test_rellena_las_semanas_sin_ventas(self):
        """Un hueco comercial debe verse en el eje, no desaparecer."""
        df = df_de(
            fila(id=1, estado=ESTADO_VENDIDO, fecha_venta=pd.Timestamp("2026-01-05")),
            fila(id=2, piso=6, estado=ESTADO_VENDIDO, fecha_venta=pd.Timestamp("2026-01-26")),
        )
        resultado = ventas_por_semana(df)
        assert len(resultado) == 4
        assert (resultado["unidades"] == [1, 0, 0, 1]).all()

    def test_puede_desactivarse_el_relleno(self):
        df = df_de(
            fila(id=1, estado=ESTADO_VENDIDO, fecha_venta=pd.Timestamp("2026-01-05")),
            fila(id=2, piso=6, estado=ESTADO_VENDIDO, fecha_venta=pd.Timestamp("2026-01-26")),
        )
        assert len(ventas_por_semana(df, incluir_semanas_vacias=False)) == 2

    def test_ignora_los_disponibles(self):
        df = df_de(
            fila(id=1, estado=ESTADO_VENDIDO, fecha_venta=pd.Timestamp("2026-01-07")),
            fila(id=2, piso=6, estado=ESTADO_DISPONIBLE),
        )
        assert ventas_por_semana(df)["unidades"].sum() == 1

    def test_sin_ventas_devuelve_tabla_vacia_con_columnas(self):
        resultado = ventas_por_semana(df_de(fila(estado=ESTADO_DISPONIBLE)))
        assert resultado.empty
        assert list(resultado.columns) == ["semana", "unidades", "valor_cop"]


class TestTiposVendidos:
    def test_los_porcentajes_suman_cien(self):
        df = df_de(
            fila(id=1, tipo_apartamento="1 Alcoba", estado=ESTADO_VENDIDO, fecha_venta=pd.Timestamp("2026-01-05")),
            fila(id=2, piso=6, tipo_apartamento="1 Alcoba", estado=ESTADO_VENDIDO, fecha_venta=pd.Timestamp("2026-01-05")),
            fila(id=3, piso=7, tipo_apartamento="Penthouse", estado=ESTADO_VENDIDO, fecha_venta=pd.Timestamp("2026-01-05")),
        )
        tabla = tipos_vendidos(df)
        assert tabla["porcentaje"].sum() == pytest.approx(100.0)
        assert tabla.iloc[0]["tipo_apartamento"] == "1 Alcoba"
        assert tabla.iloc[0]["porcentaje"] == pytest.approx(66.67, abs=0.01)

    def test_el_porcentaje_es_sobre_ventas_no_sobre_inventario(self):
        """Dos vendidos y ocho disponibles: cada vendido es el 50 % de las ventas."""
        vendidos = [
            fila(id=i, piso=i, tipo_apartamento=t, estado=ESTADO_VENDIDO, fecha_venta=pd.Timestamp("2026-01-05"))
            for i, t in enumerate(["1 Alcoba", "Penthouse"], start=1)
        ]
        disponibles = [fila(id=100 + i, piso=100 + i) for i in range(8)]
        tabla = tipos_vendidos(df_de(*vendidos, *disponibles))
        assert set(tabla["porcentaje"]) == {50.0}

    def test_sin_ventas_devuelve_tabla_vacia(self):
        assert tipos_vendidos(df_de(fila(estado=ESTADO_DISPONIBLE))).empty


class TestResumen:
    def test_cuenta_vendidos_disponibles_y_variedad(self):
        df = df_de(
            fila(id=1, tipo_apartamento="1 Alcoba", estado=ESTADO_VENDIDO, fecha_venta=pd.Timestamp("2026-01-05")),
            fila(id=2, piso=6, tipo_apartamento="Penthouse", estado=ESTADO_DISPONIBLE),
            fila(id=3, piso=7, tipo_apartamento="Penthouse", estado=ESTADO_DISPONIBLE),
        )
        r = resumen(df)
        assert (r.vendidos, r.disponibles, r.total_unidades) == (1, 2, 3)
        assert r.variedad_tipos == 2
        assert r.porcentaje_avance == pytest.approx(33.33, abs=0.01)

    def test_sin_ventas_no_divide_por_cero(self):
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
