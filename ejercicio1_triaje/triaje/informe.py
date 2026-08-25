"""Informe de ejecución en Markdown.

Un proceso automático que no cuenta lo que hizo no se puede supervisar. Este
informe se escribe en cada ejecución junto al Excel y responde a las preguntas
que hará quien tenga que confiar en el sistema: qué entró, qué se descartó y
por qué, cuánto quedó pendiente de una persona, y cuánto costó.
"""

from __future__ import annotations

import collections
from datetime import datetime
from pathlib import Path

from .excel import coste_estimado
from .modelos import ResultadoTriaje


def _tabla(cabeceras: tuple[str, ...], filas: list[tuple]) -> str:
    if not filas:
        return "_Ninguno._\n"
    lineas = [
        "| " + " | ".join(cabeceras) + " |",
        "|" + "|".join("---" for _ in cabeceras) + "|",
    ]
    lineas += ["| " + " | ".join(str(c) for c in fila) + " |" for fila in filas]
    return "\n".join(lineas) + "\n"


def componer(resultado: ResultadoTriaje) -> str:
    por_tipo = collections.Counter(f.tipo for f in resultado.filas)
    por_urgencia = collections.Counter(f.urgencia for f in resultado.filas)
    por_responsable = collections.Counter(f.responsable for f in resultado.filas)
    por_regla = collections.Counter(d.regla for d in resultado.descartes)

    coste = coste_estimado(resultado)
    coste_texto = f"USD {coste:.4f}" if coste else "USD 0 (sin llamadas de pago)"

    partes = [
        "# Informe de ejecución del triaje",
        "",
        f"Generado el {datetime.now():%Y-%m-%d %H:%M}.",
        "",
        "## Qué pasó con cada correo",
        "",
        _tabla(
            ("Etapa", "Correos"),
            [
                ("Leídos del origen", resultado.correos_leidos),
                ("Ya procesados en ejecuciones previas", len(resultado.ya_procesados)),
                ("Descartados antes de clasificar", len(resultado.descartes)),
                ("Filas generadas en el seguimiento", len(resultado.filas)),
                ("  · resueltas automáticamente", len(resultado.automaticas)),
                ("  · enviadas a revisión humana", len(resultado.para_revision)),
            ],
        ),
        "",
        f"**Automatización efectiva: {resultado.porcentaje_automatizado:.0f} %** de las filas "
        "quedaron listas sin intervención.",
        "",
        "## Descartes (y por qué)",
        "",
        _tabla(("Regla", "Correos"), sorted(por_regla.items())),
        "",
    ]

    if resultado.descartes:
        partes += [
            "Detalle:",
            "",
            _tabla(
                ("Remitente", "Asunto", "Motivo"),
                [(d.correo.remitente, d.correo.asunto or "—", d.motivo) for d in resultado.descartes],
            ),
            "",
        ]

    partes += [
        "## Cola de revisión humana",
        "",
        _tabla(
            ("Cliente", "Tipo", "Urgencia", "Motivo"),
            [(f.cliente, f.tipo, f.urgencia, f.motivo) for f in resultado.para_revision],
        ),
        "",
        "## Distribución del trabajo",
        "",
        "**Por tipo**",
        "",
        _tabla(("Tipo", "Filas"), sorted(por_tipo.items())),
        "",
        "**Por urgencia**",
        "",
        _tabla(("Urgencia", "Filas"), sorted(por_urgencia.items())),
        "",
        "**Por responsable**",
        "",
        _tabla(("Responsable", "Filas"), sorted(por_responsable.items())),
        "",
        "## Coste y rendimiento",
        "",
        _tabla(
            ("Métrica", "Valor"),
            [
                ("Clasificador", resultado.proveedor),
                ("Llamadas al modelo", resultado.llamadas_ia),
                ("Tokens de entrada", resultado.tokens_entrada),
                ("Tokens de salida", resultado.tokens_salida),
                ("Coste estimado", coste_texto),
                ("Duración", f"{resultado.segundos:.1f} s"),
            ],
        ),
    ]

    return "\n".join(partes) + "\n"


def escribir_informe(resultado: ResultadoTriaje, ruta: str | Path) -> Path:
    ruta = Path(ruta)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text(componer(resultado), encoding="utf-8")
    return ruta
