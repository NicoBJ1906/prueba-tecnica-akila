"""Línea de comandos del triaje.

    python -m triaje                          # usa las rutas por defecto
    python -m triaje --proveedor anthropic    # fuerza el clasificador con IA
    python -m triaje --reiniciar-estado       # vuelve a procesar todo

Se ejecuta desde `ejercicio1_triaje/`.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from .config import RUTA_CONFIG_POR_DEFECTO, ErrorDeConfiguracion, cargar_config
from .estado import RegistroProcesados
from .excel import coste_estimado, escribir
from .informe import escribir_informe
from .modelos import ResultadoTriaje
from .pipeline import ejecutar, leer_correos
from .proveedores import ErrorDeProveedor, crear_proveedor

RAIZ = Path(__file__).resolve().parents[2]
CORREOS_POR_DEFECTO = RAIZ / "data" / "correos_clientes.csv"
SALIDA_POR_DEFECTO = RAIZ / "ejercicio1_triaje" / "salida" / "seguimiento.xlsx"
ESTADO_POR_DEFECTO = RAIZ / "ejercicio1_triaje" / "salida" / "estado.json"


def construir_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m triaje",
        description="Triaje de correos de clientes y volcado al Excel de seguimiento.",
    )
    parser.add_argument("--entrada", type=Path, default=CORREOS_POR_DEFECTO,
                        help="CSV de correos a procesar.")
    parser.add_argument("--salida", type=Path, default=SALIDA_POR_DEFECTO,
                        help="Excel de seguimiento (se amplía si ya existe).")
    parser.add_argument("--config", type=Path, default=RUTA_CONFIG_POR_DEFECTO,
                        help="Fichero de configuración del proceso.")
    parser.add_argument("--proveedor", choices=["reglas", "anthropic", "gemini"],
                        help="Clasificador a usar. Por defecto, el que tenga credenciales.")
    parser.add_argument("--estado", type=Path, default=ESTADO_POR_DEFECTO,
                        help="Registro de correos ya procesados.")
    parser.add_argument("--reiniciar-estado", action="store_true",
                        help="Ignora el registro previo y reprocesa todos los correos.")
    parser.add_argument("--sin-estado", action="store_true",
                        help="No lee ni escribe el registro de procesados.")
    parser.add_argument("-v", "--verboso", action="store_true", help="Muestra el detalle.")
    return parser


def _resumen_por_consola(resultado: ResultadoTriaje, salida: Path, informe: Path) -> None:
    print()
    print(f"  Correos leídos ................. {resultado.correos_leidos}")
    if resultado.ya_procesados:
        print(f"  Ya procesados (sin repetir) .... {len(resultado.ya_procesados)}")
    print(f"  Descartados .................... {len(resultado.descartes)}")
    print(f"  Filas en el seguimiento ........ {len(resultado.filas)}")
    print(f"    · automáticas ................ {len(resultado.automaticas)}")
    print(f"    · para revisión humana ....... {len(resultado.para_revision)}")
    print(f"  Clasificado por ................ {resultado.proveedor}")
    if resultado.llamadas_ia:
        print(f"  Llamadas al modelo ............. {resultado.llamadas_ia}")
        print(f"  Coste estimado ................. USD {coste_estimado(resultado):.4f}")
    print(f"  Duración ....................... {resultado.segundos:.1f} s")
    print()
    print(f"  Excel:   {salida}")
    print(f"  Informe: {informe}")
    print()


def main(argv: list[str] | None = None) -> int:
    args = construir_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verboso else logging.INFO,
        format="%(levelname)s · %(message)s",
    )

    try:
        config = cargar_config(args.config)
    except ErrorDeConfiguracion as exc:
        print(f"Error en la configuración: {exc}", file=sys.stderr)
        return 2

    try:
        correos = leer_correos(args.entrada)
    except (FileNotFoundError, ValueError) as exc:
        print(f"Error leyendo los correos: {exc}", file=sys.stderr)
        return 2

    try:
        proveedor = crear_proveedor(args.proveedor)
    except ErrorDeProveedor as exc:
        print(f"Error preparando el clasificador: {exc}", file=sys.stderr)
        return 2

    registro_procesados = None
    if not args.sin_estado:
        if args.reiniciar_estado and args.estado.exists():
            args.estado.unlink()
        registro_procesados = RegistroProcesados(args.estado)

    resultado = ejecutar(correos, config, proveedor, registro_procesados)

    escribir(resultado, args.salida)
    informe = escribir_informe(resultado, args.salida.parent / "informe_ejecucion.md")
    if registro_procesados:
        registro_procesados.guardar()

    _resumen_por_consola(resultado, args.salida, informe)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
