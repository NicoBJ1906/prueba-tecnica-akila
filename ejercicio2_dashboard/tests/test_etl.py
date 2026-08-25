"""Tests del ETL: validación de esquema y regla de consolidación."""

from __future__ import annotations

import pandas as pd
import pytest

from dashboard.etl import (
    CLAVE_UNIDAD,
    ESTADO_DISPONIBLE,
    ESTADO_VENDIDO,
    ErrorDeEsquema,
    analizar_calidad,
    cargar_crudo,
    consolidar,
    validar_esquema,
)


class TestValidacionEsquema:
    def test_falta_una_columna_obligatoria(self, fila, df_de):
        df = df_de(fila()).drop(columns=["precio_cop"])
        with pytest.raises(ErrorDeEsquema, match="precio_cop"):
            validar_esquema(df)

    def test_csv_sin_filas(self, fila, df_de):
        df = df_de(fila()).iloc[0:0]
        with pytest.raises(ErrorDeEsquema, match="ninguna fila"):
            validar_esquema(df)

    def test_estado_desconocido(self, fila, df_de):
        df = df_de(fila(estado="Reservado"))
        with pytest.raises(ErrorDeEsquema, match="Reservado"):
            validar_esquema(df)

    def test_precio_vacio(self, fila, df_de):
        df = df_de(fila(precio_cop=None))
        with pytest.raises(ErrorDeEsquema, match="precio_cop"):
            validar_esquema(df)

    def test_vendido_sin_fecha_de_venta(self, fila, df_de):
        df = df_de(fila(estado=ESTADO_VENDIDO, fecha_venta=pd.NaT))
        with pytest.raises(ErrorDeEsquema, match="sin\nfecha_venta|sin fecha_venta"):
            validar_esquema(df)

    def test_fichero_inexistente(self, tmp_path, fila, df_de):
        with pytest.raises(FileNotFoundError):
            cargar_crudo(tmp_path / "no_existe.csv")


class TestConsolidacion:
    def test_unidad_sin_duplicados_se_conserva(self, fila, df_de):
        df = df_de(fila(id=1))
        assert len(consolidar(df)) == 1

    def test_gana_la_fila_vendida_sobre_la_disponible(self, fila, df_de):
        df = df_de(
            fila(id=1, estado=ESTADO_DISPONIBLE),
            fila(id=2, estado=ESTADO_VENDIDO, fecha_venta=pd.Timestamp("2026-01-10")),
        )
        resultado = consolidar(df)
        assert len(resultado) == 1
        assert resultado.iloc[0]["estado"] == ESTADO_VENDIDO
        assert resultado.iloc[0]["id"] == 2

    def test_el_id_alto_no_gana_a_una_venta(self, fila, df_de):
        """Una fila 'Disponible' posterior no borra una venta ya registrada."""
        df = df_de(
            fila(id=1, estado=ESTADO_VENDIDO, fecha_venta=pd.Timestamp("2026-01-10")),
            fila(id=99, estado=ESTADO_DISPONIBLE),
        )
        resultado = consolidar(df)
        assert resultado.iloc[0]["estado"] == ESTADO_VENDIDO
        assert resultado.iloc[0]["id"] == 1

    def test_entre_dos_ventas_gana_la_mas_reciente(self, fila, df_de):
        df = df_de(
            fila(id=1, estado=ESTADO_VENDIDO, fecha_venta=pd.Timestamp("2025-03-01"), precio_cop=400_000_000),
            fila(id=2, estado=ESTADO_VENDIDO, fecha_venta=pd.Timestamp("2026-05-20"), precio_cop=600_000_000),
        )
        resultado = consolidar(df)
        assert len(resultado) == 1
        assert resultado.iloc[0]["precio_cop"] == 600_000_000

    def test_sin_ventas_gana_el_registro_mas_reciente(self, fila, df_de):
        df = df_de(
            fila(id=1, area_m2=60),
            fila(id=7, area_m2=72),
        )
        resultado = consolidar(df)
        assert len(resultado) == 1
        assert resultado.iloc[0]["area_m2"] == 72

    def test_empate_de_fecha_se_rompe_por_id(self, fila, df_de):
        misma_fecha = pd.Timestamp("2026-02-02")
        df = df_de(
            fila(id=3, estado=ESTADO_VENDIDO, fecha_venta=misma_fecha),
            fila(id=8, estado=ESTADO_VENDIDO, fecha_venta=misma_fecha),
        )
        assert consolidar(df).iloc[0]["id"] == 8

    def test_unidades_distintas_no_se_mezclan(self, fila, df_de):
        df = df_de(
            fila(id=1, torre="Torre 1", piso=5, numero_puerta=1),
            fila(id=2, torre="Torre 2", piso=5, numero_puerta=1),
            fila(id=3, torre="Torre 1", piso=6, numero_puerta=1),
            fila(id=4, torre="Torre 1", piso=5, numero_puerta=2),
        )
        assert len(consolidar(df)) == 4

    def test_es_determinista_ante_el_orden_de_lectura(self, fila, df_de):
        filas = [
            fila(id=1, estado=ESTADO_DISPONIBLE),
            fila(id=2, estado=ESTADO_VENDIDO, fecha_venta=pd.Timestamp("2026-01-10")),
            fila(id=3, estado=ESTADO_VENDIDO, fecha_venta=pd.Timestamp("2025-01-10")),
        ]
        directo = consolidar(df_de(*filas))
        invertido = consolidar(df_de(*reversed(filas)))
        assert directo.iloc[0]["id"] == invertido.iloc[0]["id"] == 2

    def test_dataframe_vacio(self, fila, df_de):
        df = df_de(fila()).iloc[0:0]
        assert consolidar(df).empty


class TestInformeCalidad:
    def test_sin_duplicados_no_hay_conflictos(self, fila, df_de):
        df = df_de(fila(id=1), fila(id=2, piso=6, numero_puerta=3))
        informe = analizar_calidad(df)
        assert informe.unidades_con_conflicto == 0
        assert informe.filas_descartadas == 0
        assert not informe.hay_conflictos

    def test_detecta_campos_en_conflicto(self, fila, df_de):
        df = df_de(
            fila(id=1, area_m2=60, precio_cop=400_000_000),
            fila(id=2, area_m2=75, precio_cop=500_000_000),
        )
        informe = analizar_calidad(df)
        assert informe.unidades_con_conflicto == 1
        assert informe.campos_en_conflicto["area_m2"] == 1
        assert informe.campos_en_conflicto["precio_cop"] == 1

    def test_detecta_ventas_multiples_y_estado_contradictorio(self, fila, df_de):
        df = df_de(
            fila(id=1, estado=ESTADO_VENDIDO, fecha_venta=pd.Timestamp("2025-05-05")),
            fila(id=2, estado=ESTADO_VENDIDO, fecha_venta=pd.Timestamp("2026-05-05")),
            fila(id=3, estado=ESTADO_DISPONIBLE),
        )
        informe = analizar_calidad(df)
        assert informe.unidades_con_ventas_multiples == 1
        assert informe.unidades_con_estado_contradictorio == 1


class TestDatosReales:
    """Golden tests: cifras verificadas a mano sobre el CSV entregado."""

    def test_el_export_trae_457_filas_para_300_unidades(self, datos):
        assert datos.informe.filas_totales == 457
        assert datos.informe.unidades_unicas == 300
        assert datos.informe.unidades_con_conflicto == 109
        assert datos.informe.unidades_con_ventas_multiples == 47

    def test_el_canonico_tiene_una_fila_por_unidad(self, datos):
        assert len(datos.canonico) == 300
        assert not datos.canonico.duplicated(subset=list(CLAVE_UNIDAD)).any()

    def test_el_canonico_es_subconjunto_del_crudo(self, datos):
        """Consolidar selecciona filas existentes; nunca inventa ni promedia."""
        assert set(datos.canonico["id"]).issubset(set(datos.crudo["id"]))

    def test_los_totales_cuadran(self, datos):
        vendidos = (datos.canonico["estado"] == ESTADO_VENDIDO).sum()
        disponibles = (datos.canonico["estado"] == ESTADO_DISPONIBLE).sum()
        assert vendidos == 209
        assert disponibles == 91
        assert vendidos + disponibles == len(datos.canonico)

    def test_la_lectura_cruda_infla_las_cifras(self, datos):
        """Deja constancia de por qué la consolidación importa."""
        vendidos_crudo = (datos.crudo["estado"] == ESTADO_VENDIDO).sum()
        vendidos_canonico = (datos.canonico["estado"] == ESTADO_VENDIDO).sum()
        assert vendidos_crudo == 271
        assert vendidos_crudo > vendidos_canonico

    def test_toda_venta_canonica_tiene_fecha(self, datos):
        vendidos = datos.canonico[datos.canonico["estado"] == ESTADO_VENDIDO]
        assert vendidos["fecha_venta"].notna().all()
