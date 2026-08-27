"""Tipos de datos que atraviesan el pipeline de triaje.

Son inmutables a propósito: cada etapa produce datos nuevos en lugar de mutar
los de la anterior, de modo que el recorrido de un correo se puede reconstruir
entero a partir del resultado.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime

# Taxonomía cerrada. Está aquí y no en la configuración porque cambiarla implica
# cambiar el Excel de seguimiento y los informes: no es un parámetro operativo.
TIPOS = ("Consulta", "Incidencia", "Pedido", "Reclamación")
URGENCIAS = ("Alta", "Media", "Baja")

# Qué relación tiene el remitente con la empresa. Condiciona el responsable.
CATEGORIAS = ("cliente", "prospecto", "tercero", "desconocido")

# Estado de cada fila en el Excel: es la señal que la persona usa para saber
# dónde tiene que mirar.
ESTADO_AUTOMATICO = "Automático"
ESTADO_REVISION = "Revisión humana"
ESTADO_SIN_ACCION = "Sin acción"
ESTADO_DESCARTADO = "Descartado"


@dataclass(frozen=True)
class Correo:
    """Un correo entrante, ya normalizado."""

    fecha_recepcion: datetime
    remitente: str
    asunto: str
    cuerpo: str

    def _huella(self, *partes: str) -> str:
        return hashlib.sha256("|".join(partes).encode("utf-8")).hexdigest()[:12]

    @property
    def id(self) -> str:
        """Identidad exacta del correo, fecha incluida.

        Es la base de la idempotencia: dos ejecuciones sobre el mismo correo
        producen el mismo identificador, así que la segunda no vuelve a
        escribirlo en el Excel.
        """
        return self._huella(
            self.fecha_recepcion.isoformat(),
            self.remitente.strip().lower(),
            self.asunto.strip(),
            self.cuerpo.strip(),
        )

    @property
    def huella_del_dia(self) -> str:
        """Identidad del mensaje dentro de una misma jornada, sin la hora.

        Sirve para detectar el duplicado que describe el enunciado: el mismo
        mensaje aparece dos veces en el buzón con horas distintas. Se acota al
        día a propósito — que un cliente reenvíe el mismo texto una semana
        después no es un duplicado, es una reiteración, y merece su propia fila.
        """
        return self._huella(
            self.fecha_recepcion.date().isoformat(),
            self.remitente.strip().lower(),
            self.asunto.strip().lower(),
            " ".join(self.cuerpo.split()).lower(),
        )

    @property
    def texto(self) -> str:
        """Asunto y cuerpo juntos, para las búsquedas por palabra clave."""
        return f"{self.asunto}\n{self.cuerpo}"


@dataclass(frozen=True)
class Asunto:
    """Una petición identificada dentro de un correo.

    Un correo puede traer más de una (una cotización y, de paso, una queja del
    parqueadero). Cada asunto acaba siendo una fila del Excel, porque cada uno
    tiene su propio responsable y su propio cierre.
    """

    tipo: str
    urgencia: str
    tema: str
    accion: str
    confianza: float = 1.0

    def __post_init__(self) -> None:
        if self.tipo not in TIPOS:
            raise ValueError(f"Tipo no permitido: {self.tipo!r}. Válidos: {TIPOS}")
        if self.urgencia not in URGENCIAS:
            raise ValueError(f"Urgencia no permitida: {self.urgencia!r}. Válidas: {URGENCIAS}")
        if not 0.0 <= self.confianza <= 1.0:
            raise ValueError(f"Confianza fuera de rango: {self.confianza}")


@dataclass(frozen=True)
class Clasificacion:
    """Lo que devuelve la etapa de clasificación, venga de la IA o de reglas."""

    asuntos: tuple[Asunto, ...]
    fuente: str  # "reglas", "anthropic", "gemini"
    notas: str = ""

    @property
    def confianza_minima(self) -> float:
        return min((a.confianza for a in self.asuntos), default=0.0)


@dataclass(frozen=True)
class FilaSeguimiento:
    """Una fila del Excel de seguimiento.

    Las seis primeras columnas son las que pide el enunciado. El resto son de
    auditoría: sin ellas nadie puede saber por qué el sistema decidió lo que
    decidió, y una automatización que no se puede auditar no se adopta.
    """

    fecha: datetime
    cliente: str
    tipo: str
    urgencia: str
    accion: str
    responsable: str
    # --- auditoría ---
    estado: str
    categoria: str
    confianza: float
    fuente: str
    id_correo: str
    remitente: str
    apartamento: str = ""
    motivo: str = ""


@dataclass(frozen=True)
class Descarte:
    """Un correo que no llega al Excel de seguimiento, y por qué."""

    correo: Correo
    motivo: str
    regla: str


@dataclass
class ResultadoTriaje:
    """Salida completa de una ejecución, lista para volcar e informar."""

    filas: list[FilaSeguimiento] = field(default_factory=list)
    descartes: list[Descarte] = field(default_factory=list)
    ya_procesados: list[Correo] = field(default_factory=list)
    correos_leidos: int = 0
    llamadas_ia: int = 0
    tokens_entrada: int = 0
    tokens_salida: int = 0
    segundos: float = 0.0
    proveedor: str = "reglas"

    @property
    def para_revision(self) -> list[FilaSeguimiento]:
        return [f for f in self.filas if f.estado == ESTADO_REVISION]

    @property
    def automaticas(self) -> list[FilaSeguimiento]:
        return [f for f in self.filas if f.estado == ESTADO_AUTOMATICO]

    @property
    def sin_accion(self) -> list[FilaSeguimiento]:
        """Filas que no piden gestión: un «gracias» sin petición detrás.

        Se cuentan aparte de las automáticas a propósito. Meterlas ahí inflaría
        el porcentaje de automatización con trabajo que nunca existió; dejarlas
        fuera del informe, en cambio, descuadraba la suma con el total de filas
        y quien lo leía tenía que adivinar dónde estaba la que faltaba.
        """
        return [f for f in self.filas if f.estado == ESTADO_SIN_ACCION]

    @property
    def porcentaje_automatizado(self) -> float:
        if not self.filas:
            return 0.0
        return len(self.automaticas) / len(self.filas) * 100
