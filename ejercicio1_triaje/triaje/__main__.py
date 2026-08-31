"""Línea de comandos del triaje.

    python -m triaje                          # usa las rutas por defecto
    python -m triaje --proveedor anthropic    # fuerza el clasificador con IA
    python -m triaje --reiniciar-estado       # vuelve a procesar todo
    python -m triaje --buzon                  # lee un buzón real por IMAP
    python -m triaje --buzon --vigilar 30     # y lo revisa cada 30 segundos

Se ejecuta desde `ejercicio1_triaje/`.
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
import time
from pathlib import Path

from .buzon import CARPETA_POR_DEFECTO, ErrorDeBuzon, leer_buzon
from .config import RUTA_CONFIG_POR_DEFECTO, ErrorDeConfiguracion, cargar_config
from .estado import RegistroProcesados
from .excel import coste_estimado, escribir
from .informe import escribir_informe
from .localizar import NOMBRE_POR_DEFECTO, resolver
from .modelos import ResultadoTriaje
from .pipeline import ejecutar, leer_correos
from .proveedores import ErrorDeProveedor, crear_proveedor

RAIZ = Path(__file__).resolve().parents[2]
CORREOS_POR_DEFECTO = RAIZ / "data" / "correos_clientes.csv"
SALIDA_POR_DEFECTO = RAIZ / "ejercicio1_triaje" / "salida" / "seguimiento.xlsx"
ESTADO_POR_DEFECTO = RAIZ / "ejercicio1_triaje" / "salida" / "estado.json"

# Fallos seguidos que aguanta la vigilancia antes de rendirse.
FALLOS_SEGUIDOS_TOLERADOS = 5


def construir_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m triaje",
        description="Triaje de correos de clientes y volcado al Excel de seguimiento.",
    )
    parser.add_argument("--entrada", type=Path, default=CORREOS_POR_DEFECTO,
                        help="CSV de correos a procesar.")
    parser.add_argument("--salida", type=Path, default=None,
                        help="Excel de seguimiento (se amplía si ya existe). "
                             "Por defecto, junto al ejercicio.")
    parser.add_argument("--buscar-excel", nargs="?", const=NOMBRE_POR_DEFECTO,
                        metavar="NOMBRE",
                        help="Busca el Excel por nombre en OneDrive, Documentos y "
                             "Escritorio, y escribe el seguimiento ahí. Funciona "
                             "igual en Windows y macOS.")
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

    buzon = parser.add_argument_group(
        "buzón real (opcional)",
        "Lee de un buzón por IMAP en lugar del CSV. Necesita TRIAJE_IMAP_USUARIO y "
        "TRIAJE_IMAP_CLAVE en el entorno. Solo lee: no marca como leído ni archiva.",
    )
    buzon.add_argument("--auto", action="store_true",
                       help="Modo desatendido: lee el buzón, deduce el servidor por "
                            "el dominio del correo, localiza el Excel por nombre y "
                            "vigila cada minuto. Equivale a --buzon --buscar-excel "
                            "--vigilar 60 con la carpeta de TRIAJE_IMAP_CARPETA.")
    buzon.add_argument("--buzon", action="store_true",
                       help="Toma los correos del buzón en vez de --entrada.")
    buzon.add_argument("--dias", type=int, default=1,
                       help="Días hacia atrás que se leen del buzón (por defecto 1).")
    buzon.add_argument("--carpeta", default=CARPETA_POR_DEFECTO,
                       help="Carpeta IMAP a leer (por defecto INBOX).")
    buzon.add_argument("--servidor", default=None,
                       help="Servidor IMAP. Por defecto TRIAJE_IMAP_SERVIDOR, "
                            "o imap.gmail.com si tampoco está definida.")
    buzon.add_argument("--permitir-inbox", action="store_true",
                       help="Permite leer INBOX. Sin esto se exige una carpeta "
                            "o etiqueta dedicada, para no descargar la bandeja entera.")
    buzon.add_argument("--vigilar", type=int, metavar="SEGUNDOS",
                       help="Repite la lectura cada N segundos y amplía el Excel. "
                            "Se detiene con Ctrl+C.")
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

    if args.auto:
        args.buzon = True
        args.carpeta = os.environ.get("TRIAJE_IMAP_CARPETA", "").strip() or args.carpeta
        if args.carpeta.strip().upper() == CARPETA_POR_DEFECTO:
            print(
                "Falta indicar qué carpeta del buzón alimenta el triaje.\n"
                '    export TRIAJE_IMAP_CARPETA="Akila"\n'
                "Se pide a propósito: leer la bandeja de entrada volcaría todo el "
                "correo personal al Excel.",
                file=sys.stderr,
            )
            return 2
        if args.buscar_excel is None:
            args.buscar_excel = NOMBRE_POR_DEFECTO
        if args.vigilar is None:
            args.vigilar = 60

    if args.salida is None:
        args.salida = resolver(args.buscar_excel) if args.buscar_excel else SALIDA_POR_DEFECTO
        if args.buscar_excel:
            print(f"\n  Excel localizado: {args.salida}")

    try:
        config = cargar_config(args.config)
    except ErrorDeConfiguracion as exc:
        print(f"Error en la configuración: {exc}", file=sys.stderr)
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

    if not args.vigilar:
        return _una_pasada(args, config, proveedor, registro_procesados)

    # Modo vigilancia: el registro de procesados se mantiene vivo entre vueltas,
    # así que cada pasada solo añade al Excel los correos que llegaron nuevos.
    print(f"\n  Vigilando el buzón cada {args.vigilar} s. Ctrl+C para parar.\n")
    fallos = 0
    try:
        while True:
            if _una_pasada(args, config, proveedor, registro_procesados) == 0:
                fallos = 0
            else:
                # Un corte de red o el Excel abierto un momento no deben apagar
                # un proceso pensado para estar todo el día en marcha. Si el
                # fallo persiste, es de configuración y ahí sí se para.
                fallos += 1
                if fallos >= FALLOS_SEGUIDOS_TOLERADOS:
                    print(f"  {fallos} intentos fallidos seguidos. Se detiene.",
                          file=sys.stderr)
                    return 2
                print(f"  Reintentando en {args.vigilar} s "
                      f"({fallos}/{FALLOS_SEGUIDOS_TOLERADOS}).", file=sys.stderr)
            time.sleep(args.vigilar)
    except KeyboardInterrupt:
        print("\n  Vigilancia detenida.\n")
        return 0


def _obtener_correos(args: argparse.Namespace) -> list:
    """Del buzón o del CSV, según lo pedido. Devuelve siempre objetos `Correo`."""
    if args.buzon:
        return leer_buzon(dias=args.dias, carpeta=args.carpeta,
                          servidor=args.servidor,
                          permitir_inbox=args.permitir_inbox)
    return leer_correos(args.entrada)


def _una_pasada(args, config, proveedor, registro_procesados) -> int:
    """Lee, clasifica y vuelca una vez. Es lo que el modo vigilancia repite."""
    try:
        correos = _obtener_correos(args)
    except ErrorDeBuzon as exc:
        print(f"Error leyendo el buzón: {exc}", file=sys.stderr)
        return 2
    except (FileNotFoundError, ValueError) as exc:
        print(f"Error leyendo los correos: {exc}", file=sys.stderr)
        return 2

    resultado = ejecutar(correos, config, proveedor, registro_procesados)

    try:
        escribir(resultado, args.salida)
        informe = escribir_informe(resultado, args.salida.parent / "informe_ejecucion.md")
    except OSError as exc:
        # Lo más habitual: el fichero está abierto en Excel, que en Windows lo
        # bloquea. No se pierde nada: el registro de procesados se guarda
        # después, así que estos correos se vuelven a procesar al reintentar.
        print(f"No se pudo escribir en {args.salida}: {exc}\n"
              "Si lo tienes abierto en Excel, ciérralo y vuelve a ejecutar. "
              "Ningún correo se ha perdido.", file=sys.stderr)
        return 2
    if registro_procesados:
        registro_procesados.guardar()

    _resumen_por_consola(resultado, args.salida, informe)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
