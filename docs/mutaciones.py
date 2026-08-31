"""Pruebas de mutación: rompe el código a propósito y mira si los tests lo notan.

Una mutación que SOBREVIVE (los tests siguen en verde con el código roto) señala
una zona sin cobertura real. Es la única forma honesta de saber si 198 pruebas
verdes significan algo.

Se ejecuta desde cualquier sitio: las rutas se resuelven a partir de este fichero.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ORIGEN = Path(__file__).resolve().parents[1]

# La copia se hace fuera del repositorio: dentro, `copytree` acabaría copiándose
# a sí misma y el repo se quedaría con una carpeta que no debería versionarse.
TRABAJO = Path(tempfile.gettempdir()) / "mutaciones-akila"

# El intérprete del entorno virtual si existe; si no, el que ejecuta esto.
# La ruta de los ejecutables cambia entre Windows (Scripts) y el resto (bin).
_VENV_UNIX = ORIGEN / ".venv" / "bin" / "python"
_VENV_WIN = ORIGEN / ".venv" / "Scripts" / "python.exe"
PY = next((c for c in (_VENV_UNIX, _VENV_WIN) if c.exists()), Path(sys.executable))

# Solo los tests que no levantan navegador: 1,3 s frente a 3 min.
TESTS = [
    "ejercicio1_triaje/tests",
    "ejercicio2_dashboard/tests/test_etl.py",
    "ejercicio2_dashboard/tests/test_metricas.py",
]

# (nombre, fichero, texto original, texto mutado)
MUTACIONES = [
    # --- Consolidación: el corazón de la entrega ---
    ("consolidar: invierte la prioridad vendido/disponible",
     "ejercicio2_dashboard/dashboard/etl.py",
     'ascending=[False, False, False],', 'ascending=[True, False, False],'),
    ("consolidar: se queda con la venta MÁS ANTIGUA",
     "ejercicio2_dashboard/dashboard/etl.py",
     'ascending=[False, False, False],', 'ascending=[False, True, False],'),
    ("consolidar: rompe el desempate por id",
     "ejercicio2_dashboard/dashboard/etl.py",
     'ascending=[False, False, False],', 'ascending=[False, False, True],'),
    ("consolidar: se queda con la última fila en vez de la primera",
     "ejercicio2_dashboard/dashboard/etl.py",
     'keep="first"', 'keep="last"'),

    # --- Métricas ---
    ("ritmo: ventana de 12 semanas a 3",
     "ejercicio2_dashboard/dashboard/metricas.py",
     "SEMANAS_RITMO_RECIENTE = 12", "SEMANAS_RITMO_RECIENTE = 3"),
    ("tipos_vendidos: % sobre el total del proyecto, no sobre lo vendido",
     "ejercicio2_dashboard/dashboard/metricas.py",
     'tabla["porcentaje"] = tabla["unidades_vendidas"] / len(vendidos) * 100',
     'tabla["porcentaje"] = tabla["unidades_vendidas"] / len(df) * 100'),
    ("ventas_por_semana: deja de rellenar las semanas sin ventas",
     "ejercicio2_dashboard/dashboard/metricas.py",
     "if incluir_semanas_vacias and len(agrupado) > 1:",
     "if False and incluir_semanas_vacias and len(agrupado) > 1:"),
    ("avance_acumulado: deja de acumular el valor",
     "ejercicio2_dashboard/dashboard/metricas.py",
     'valor_cop=serie["valor_cop"].cumsum(),', 'valor_cop=serie["valor_cop"],'),
    ("avance_por_torre: % sobre el proyecto, no sobre la torre",
     "ejercicio2_dashboard/dashboard/metricas.py",
     'tabla["porcentaje"] = tabla["vendidos"] / tabla["total"] * 100\n    return tabla[columnas].sort_values("torre"',
     'tabla["porcentaje"] = tabla["vendidos"] / tabla["total"].sum() * 100\n    return tabla[columnas].sort_values("torre"'),
    ("insights: reporta diferencias irrelevantes (umbral a 0)",
     "ejercicio2_dashboard/dashboard/metricas.py",
     "PUNTOS_DIFERENCIA_RELEVANTE = 10", "PUNTOS_DIFERENCIA_RELEVANTE = 0"),
    ("insights: señala grupos diminutos como tendencia",
     "ejercicio2_dashboard/dashboard/metricas.py",
     "MINIMO_UNIDADES_CELDA = 15", "MINIMO_UNIDADES_CELDA = 1"),
    ("insights: deja de limitar el número de tarjetas",
     "ejercicio2_dashboard/dashboard/metricas.py",
     "MAXIMO_HALLAZGOS = 4", "MAXIMO_HALLAZGOS = 99"),
    ("insights: deja de ordenar por gravedad",
     "ejercicio2_dashboard/dashboard/metricas.py",
     "ordenados = sorted(hallazgos, key=lambda h: ORDEN_TONOS.get(h.tono, 9))",
     "ordenados = list(reversed(hallazgos))"),
    ("cohortes_entrega: cuenta las filas sin fecha de entrega",
     "ejercicio2_dashboard/dashboard/metricas.py",
     'entregas = df.dropna(subset=["fecha_entrega"])', "entregas = df"),
    ("avance_por_altura: mete los pisos medios en la franja baja",
     "ejercicio2_dashboard/dashboard/metricas.py",
     '[(1, 7, "Bajos · 1-7"), (8, 15, "Medios · 8-15"), (16, 99, "Altos · 16+")]',
     '[(1, 15, "Bajos · 1-7"), (8, 15, "Medios · 8-15"), (16, 99, "Altos · 16+")]'),
    ("composicion_pago: incluye también los disponibles",
     "ejercicio2_dashboard/dashboard/metricas.py",
     'vendidos = _vendidos(df).dropna(subset=["forma_pago"])',
     'vendidos = df.dropna(subset=["forma_pago"])'),
    ("formato_cop: confunde millones con miles de millones",
     "ejercicio2_dashboard/dashboard/metricas.py",
     "if valor >= 1_000_000_000:", "if valor >= 1_000_000:"),

    # --- Validación de esquema ---
    ("validar_esquema: deja pasar un CSV vacío",
     "ejercicio2_dashboard/dashboard/etl.py",
     "if df.empty:", "if False and df.empty:"),
    ("validar_esquema: deja pasar vendidos sin fecha de venta",
     "ejercicio2_dashboard/dashboard/etl.py",
     "if not vendidos_sin_fecha.empty:", "if False and not vendidos_sin_fecha.empty:"),
]


def correr_tests(cwd: Path) -> bool:
    """True si TODOS los tests pasan."""
    r = subprocess.run(
        [str(PY), "-m", "pytest", *TESTS, "-q", "--no-header", "-x"],
        cwd=cwd, capture_output=True, text=True,
    )
    return r.returncode == 0


def main() -> int:
    if TRABAJO.exists():
        shutil.rmtree(TRABAJO)
    shutil.copytree(ORIGEN, TRABAJO,
                    ignore=shutil.ignore_patterns(".venv", ".git", "__pycache__",
                                                  ".pytest_cache", ".ruff_cache",
                                                  "mutaciones-akila", "mut1"))

    print("Comprobando que la copia parte en verde…")
    if not correr_tests(TRABAJO):
        print("ERROR: la copia sin mutar ya falla. Abortando.")
        return 1
    print("OK: copia limpia en verde.\n")

    sobreviven, detectadas, invalidas = [], [], []

    for nombre, rel, viejo, nuevo in MUTACIONES:
        fichero = TRABAJO / rel
        original = fichero.read_text()
        if viejo not in original:
            invalidas.append(nombre)
            print(f"[?] MUTACIÓN INVÁLIDA (patrón no encontrado): {nombre}")
            continue

        fichero.write_text(original.replace(viejo, nuevo, 1))
        paso = correr_tests(TRABAJO)
        fichero.write_text(original)  # restaurar siempre

        if paso:
            sobreviven.append(nombre)
            print(f"[!] SOBREVIVE  {nombre}")
        else:
            detectadas.append(nombre)
            print(f"[ok] detectada  {nombre}")

    total = len(sobreviven) + len(detectadas)
    print("\n" + "=" * 70)
    print(f"Mutaciones válidas: {total} · detectadas: {len(detectadas)} · "
          f"SOBREVIVEN: {len(sobreviven)}")
    if total:
        print(f"Tasa de detección: {len(detectadas) / total * 100:.0f} %")
    if sobreviven:
        print("\nZONAS SIN COBERTURA REAL:")
        for s in sobreviven:
            print(f"  - {s}")
    if invalidas:
        print(f"\n(Inválidas, revisar el patrón: {len(invalidas)})")
        for i in invalidas:
            print(f"  - {i}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
