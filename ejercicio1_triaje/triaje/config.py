"""Carga de la configuración operativa (`config.toml`).

Se usa `tomllib`, que forma parte de la biblioteca estándar desde Python 3.11:
la configuración del proceso no justifica añadir una dependencia externa, y el
formato es legible y editable por quien opera el proceso sin saber programar.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path

RUTA_CONFIG_POR_DEFECTO = Path(__file__).resolve().parents[1] / "config.toml"

SECCIONES_REQUERIDAS = (
    "general",
    "remitentes_automaticos",
    "revision_obligatoria",
    "cortesia",
    "urgencia",
    "temas",
    "responsables",
    "responsables_por_tipo",
    "acciones",
)


class ErrorDeConfiguracion(ValueError):
    """La configuración está incompleta o mal formada."""


@dataclass(frozen=True)
class Config:
    """Vista tipada de `config.toml`."""

    umbral_confianza: float
    antiguedad_maxima_dias: int
    remitentes_automaticos: tuple[str, ...]
    frases_automaticas: tuple[str, ...]
    palabras_revision: tuple[str, ...]
    motivo_revision: str
    cortesia_longitud_maxima: int
    cortesia_frases: tuple[str, ...]
    urgencia_alta: tuple[str, ...]
    urgencia_media: tuple[str, ...]
    temas: dict[str, tuple[str, ...]]
    responsables: dict[str, str]
    responsables_por_tipo: dict[str, str]
    acciones: dict[str, str]

    def responsable_de(self, tema: str, tipo: str) -> str:
        """Quién atiende un asunto: por tema, y si no se conoce, por tipo."""
        if tema in self.responsables:
            return self.responsables[tema]
        if tipo in self.responsables_por_tipo:
            return self.responsables_por_tipo[tipo]
        return self.responsables.get("otro", "Servicio al Cliente")

    def accion_de(self, tema: str) -> str:
        return self.acciones.get(tema, self.acciones.get("otro", "Revisar el correo"))


def cargar_config(ruta: str | Path = RUTA_CONFIG_POR_DEFECTO) -> Config:
    ruta = Path(ruta)
    if not ruta.exists():
        raise ErrorDeConfiguracion(f"No se encontró la configuración en {ruta}.")

    try:
        with ruta.open("rb") as fichero:
            datos = tomllib.load(fichero)
    except tomllib.TOMLDecodeError as exc:
        raise ErrorDeConfiguracion(
            f"El fichero {ruta.name} tiene un error de formato: {exc}"
        ) from exc

    faltantes = [s for s in SECCIONES_REQUERIDAS if s not in datos]
    if faltantes:
        raise ErrorDeConfiguracion(
            f"Faltan secciones en {ruta.name}: {', '.join(faltantes)}."
        )

    temas_sin_responsable = [
        t for t in datos["temas"] if t not in datos["responsables"]
    ]
    if temas_sin_responsable:
        raise ErrorDeConfiguracion(
            "Estos temas no tienen responsable asignado en [responsables]: "
            + ", ".join(temas_sin_responsable)
        )

    def minusculas(valores) -> tuple[str, ...]:
        return tuple(v.lower() for v in valores)

    return Config(
        umbral_confianza=float(datos["general"]["umbral_confianza"]),
        antiguedad_maxima_dias=int(datos["general"].get("antiguedad_maxima_dias", 0)),
        remitentes_automaticos=minusculas(datos["remitentes_automaticos"]["patrones"]),
        frases_automaticas=minusculas(datos["remitentes_automaticos"].get("frases", [])),
        palabras_revision=minusculas(datos["revision_obligatoria"]["palabras"]),
        motivo_revision=datos["revision_obligatoria"].get(
            "motivo", "Requiere validación de una persona."
        ),
        cortesia_longitud_maxima=int(datos["cortesia"]["longitud_maxima_caracteres"]),
        cortesia_frases=minusculas(datos["cortesia"]["frases"]),
        urgencia_alta=minusculas(datos["urgencia"]["alta"]),
        urgencia_media=minusculas(datos["urgencia"]["media"]),
        temas={k: minusculas(v) for k, v in datos["temas"].items()},
        responsables=dict(datos["responsables"]),
        responsables_por_tipo=dict(datos["responsables_por_tipo"]),
        acciones=dict(datos["acciones"]),
    )
