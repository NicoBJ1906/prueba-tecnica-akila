"""La única etapa del pipeline que puede usar un modelo de lenguaje.

Hay tres proveedores intercambiables y todos devuelven exactamente el mismo
tipo (`Clasificacion`), de modo que el resto del sistema no sabe cuál se usó:

- `reglas`    — sin IA. Funciona siempre, sin credenciales y sin coste.
- `anthropic` — Claude Haiku con salida estructurada.
- `gemini`    — Gemini Flash, alternativa sin coste en su plan gratuito.

Que el modo `reglas` sea un proveedor de pleno derecho y no un apaño es
deliberado: quien clone el repositorio puede ejecutar el proceso completo sin
credenciales, y si el proveedor de IA falla en producción, el sistema degrada
en lugar de detenerse.

Las credenciales se leen solo de variables de entorno. Nunca se escriben en el
código ni en la configuración.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from .config import Config
from .modelos import TIPOS, URGENCIAS, Asunto, Clasificacion, Correo
from .reglas import clasificar_por_reglas

RUTA_PROMPT = Path(__file__).resolve().parents[1] / "prompts" / "clasificacion.md"

# Haiku es la opción correcta para una clasificación de este tamaño: la tarea
# está acotada por un esquema cerrado y una rúbrica explícita, así que un modelo
# mayor no clasificaría mejor, solo costaría más. El coste de los 15 correos de
# la muestra queda por debajo de un centavo de dólar.
MODELO_ANTHROPIC = "claude-haiku-4-5"
MODELO_GEMINI = "gemini-2.5-flash"
MAX_TOKENS = 1024


class ErrorDeProveedor(RuntimeError):
    """El proveedor no pudo entregar una clasificación utilizable."""


class Proveedor(Protocol):
    """Contrato común. El pipeline solo conoce esto."""

    nombre: str

    def clasificar(self, correo: Correo, config: Config) -> Clasificacion: ...


def esquema_respuesta(config: Config) -> dict:
    """Esquema JSON con enums cerrados.

    Es el primer guardrail y el más eficaz: el modelo no puede devolver un tipo,
    una urgencia o un tema que no existan, así que ninguna respuesta —ni siquiera
    una provocada por un intento de manipulación— puede romper el Excel.
    """
    temas = sorted(set(config.temas) | {"otro"})
    return {
        "type": "object",
        "properties": {
            "asuntos": {
                "type": "array",
                "minItems": 1,
                "maxItems": 3,
                "items": {
                    "type": "object",
                    "properties": {
                        "tipo": {"type": "string", "enum": list(TIPOS)},
                        "urgencia": {"type": "string", "enum": list(URGENCIAS)},
                        "tema": {"type": "string", "enum": temas},
                        "accion": {"type": "string"},
                        "confianza": {"type": "number", "minimum": 0, "maximum": 1},
                    },
                    "required": ["tipo", "urgencia", "tema", "accion", "confianza"],
                    "additionalProperties": False,
                },
            },
            "notas": {"type": "string"},
        },
        "required": ["asuntos", "notas"],
        "additionalProperties": False,
    }


def _bloques_del_prompt() -> tuple[str, str]:
    """Extrae las plantillas SYSTEM y USER del prompt versionado."""
    texto = RUTA_PROMPT.read_text(encoding="utf-8")
    bloques = re.findall(r"```\n(.*?)```", texto, re.DOTALL)
    if len(bloques) < 2:
        raise ErrorDeProveedor(
            f"El prompt {RUTA_PROMPT.name} debe contener los bloques SYSTEM y USER."
        )
    return bloques[0].strip(), bloques[1].strip()


def construir_prompt(correo: Correo, config: Config) -> tuple[str, str]:
    """Rellena el prompt con la rúbrica vigente y el correo a clasificar."""
    sistema, usuario = _bloques_del_prompt()

    sistema = sistema.format(
        tipos=", ".join(TIPOS),
        urgencias=", ".join(URGENCIAS),
        temas=", ".join(sorted(set(config.temas) | {"otro"})),
        rubrica_alta=", ".join(config.urgencia_alta[:8]),
        rubrica_media=", ".join(config.urgencia_media[:8]),
    )
    usuario = usuario.format(
        fecha=correo.fecha_recepcion.strftime("%Y-%m-%d %H:%M"),
        remitente=correo.remitente,
        asunto=correo.asunto or "(sin asunto)",
        cuerpo=correo.cuerpo,
    )
    return sistema, usuario


def interpretar_respuesta(bruto: str, fuente: str) -> Clasificacion:
    """Valida la respuesta del modelo antes de dejarla entrar en el sistema.

    El esquema cerrado hace improbable una respuesta inválida, pero improbable
    no es imposible: aquí se comprueba de todas formas. Cualquier fallo levanta
    `ErrorDeProveedor`, y el pipeline responde cayendo a reglas y marcando la
    fila para revisión, nunca escribiendo un dato en el que no se puede confiar.
    """
    try:
        datos = json.loads(bruto)
    except json.JSONDecodeError as exc:
        raise ErrorDeProveedor(f"La respuesta no es JSON válido: {exc}") from exc

    if not isinstance(datos, dict) or "asuntos" not in datos:
        raise ErrorDeProveedor("La respuesta no contiene la clave 'asuntos'.")

    crudos = datos["asuntos"]
    if not isinstance(crudos, list) or not crudos:
        raise ErrorDeProveedor("'asuntos' debe ser una lista con al menos un elemento.")

    asuntos = []
    for item in crudos[:3]:
        if not isinstance(item, dict):
            raise ErrorDeProveedor(f"Asunto con formato inesperado: {item!r}")
        try:
            # El constructor de Asunto revalida los enums: si el modelo se
            # saltara el esquema, la excepción salta aquí.
            asuntos.append(
                Asunto(
                    tipo=item["tipo"],
                    urgencia=item["urgencia"],
                    tema=item["tema"],
                    accion=str(item["accion"]).strip(),
                    confianza=float(item["confianza"]),
                )
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise ErrorDeProveedor(f"Asunto inválido ({exc}): {item!r}") from exc

    return Clasificacion(
        asuntos=tuple(asuntos),
        fuente=fuente,
        notas=str(datos.get("notas", "")).strip(),
    )


@dataclass
class ProveedorReglas:
    """Clasificación determinista. Sin credenciales, sin coste, sin latencia."""

    nombre: str = "reglas"

    def clasificar(self, correo: Correo, config: Config) -> Clasificacion:
        return clasificar_por_reglas(correo, config)


@dataclass
class ProveedorAnthropic:
    """Claude Haiku con salida estructurada.

    `cliente` existe para poder probar la construcción de la petición sin
    credenciales ni red: los tests inyectan un doble. En uso normal se deja sin
    tocar y el proveedor crea el cliente real.
    """

    nombre: str = "anthropic"
    modelo: str = MODELO_ANTHROPIC
    cliente: object | None = None
    tokens_entrada: int = 0
    tokens_salida: int = 0
    llamadas: int = 0

    def __post_init__(self) -> None:
        if self.cliente is not None:
            return

        try:
            import anthropic
        except ImportError as exc:
            raise ErrorDeProveedor(
                "Falta el paquete 'anthropic'. Instálalo con:\n"
                "    pip install anthropic\n"
                "o ejecuta el pipeline con --proveedor reglas, que no requiere nada."
            ) from exc

        if not os.environ.get("ANTHROPIC_API_KEY"):
            raise ErrorDeProveedor(
                "Falta la variable de entorno ANTHROPIC_API_KEY.\n"
                "Nunca escribas la clave en el código ni en config.toml."
            )

        self.cliente = anthropic.Anthropic()

    def clasificar(self, correo: Correo, config: Config) -> Clasificacion:
        sistema, usuario = construir_prompt(correo, config)
        try:
            respuesta = self.cliente.messages.create(
                model=self.modelo,
                max_tokens=MAX_TOKENS,
                system=sistema,
                messages=[{"role": "user", "content": usuario}],
                output_config={
                    "format": {"type": "json_schema", "schema": esquema_respuesta(config)}
                },
            )
        except Exception as exc:
            # Cualquier fallo del proveedor (red, cuota, autenticación) se
            # traduce al error propio del pipeline, que sabe degradar a reglas.
            if isinstance(exc, ErrorDeProveedor):
                raise
            raise ErrorDeProveedor(f"Error llamando a la API de Anthropic: {exc}") from exc

        self.llamadas += 1
        self.tokens_entrada += respuesta.usage.input_tokens
        self.tokens_salida += respuesta.usage.output_tokens

        texto = next((b.text for b in respuesta.content if b.type == "text"), "")
        return interpretar_respuesta(texto, self.nombre)


@dataclass
class ProveedorGemini:
    """Gemini Flash. Alternativa con plan gratuito, mismo contrato."""

    nombre: str = "gemini"
    modelo: str = MODELO_GEMINI
    tokens_entrada: int = 0
    tokens_salida: int = 0
    llamadas: int = 0

    def __post_init__(self) -> None:
        try:
            from google import genai  # noqa: F401
        except ImportError as exc:
            raise ErrorDeProveedor(
                "Falta el paquete 'google-genai'. Instálalo con:\n"
                "    pip install google-genai"
            ) from exc

        if not os.environ.get("GEMINI_API_KEY"):
            raise ErrorDeProveedor("Falta la variable de entorno GEMINI_API_KEY.")

        from google import genai

        self._cliente = genai.Client()

    def clasificar(self, correo: Correo, config: Config) -> Clasificacion:
        sistema, usuario = construir_prompt(correo, config)
        try:
            respuesta = self._cliente.models.generate_content(
                model=self.modelo,
                contents=usuario,
                config={
                    "system_instruction": sistema,
                    "response_mime_type": "application/json",
                    "response_json_schema": esquema_respuesta(config),
                    "max_output_tokens": MAX_TOKENS,
                },
            )
        except Exception as exc:  # el SDK no expone una jerarquía estable
            raise ErrorDeProveedor(f"Error de la API de Gemini: {exc}") from exc

        self.llamadas += 1
        uso = getattr(respuesta, "usage_metadata", None)
        if uso:
            self.tokens_entrada += getattr(uso, "prompt_token_count", 0) or 0
            self.tokens_salida += getattr(uso, "candidates_token_count", 0) or 0

        return interpretar_respuesta(respuesta.text or "", self.nombre)


PROVEEDORES = {
    "reglas": ProveedorReglas,
    "anthropic": ProveedorAnthropic,
    "gemini": ProveedorGemini,
}


def crear_proveedor(nombre: str | None = None) -> Proveedor:
    """Elige proveedor por parámetro, por entorno o por lo que haya disponible.

    Sin configuración explícita, se prefiere el proveedor cuya credencial esté
    presente y se cae a `reglas` si no hay ninguna. Así el comando de la
    documentación funciona igual en la máquina de quien evalúa que en la de
    quien lo desarrolló, con o sin credenciales.
    """
    nombre = (nombre or os.environ.get("TRIAJE_LLM") or "").strip().lower()

    if nombre:
        if nombre not in PROVEEDORES:
            raise ErrorDeProveedor(
                f"Proveedor desconocido: {nombre!r}. Opciones: {', '.join(PROVEEDORES)}"
            )
        return PROVEEDORES[nombre]()

    if os.environ.get("ANTHROPIC_API_KEY"):
        return ProveedorAnthropic()
    if os.environ.get("GEMINI_API_KEY"):
        return ProveedorGemini()
    return ProveedorReglas()
