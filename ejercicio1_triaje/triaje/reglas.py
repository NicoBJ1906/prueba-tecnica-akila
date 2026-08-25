"""Todo lo que se resuelve sin inteligencia artificial.

Este módulo es deliberadamente el más grande del pipeline. Cada función de aquí
es una decisión que NO se delega a un modelo: filtrar automáticos, extraer el
apartamento, detectar asuntos legales, aplicar la rúbrica de urgencia y asignar
responsable. Todas son baratas, instantáneas, deterministas y auditables — un
modelo de lenguaje no las haría mejor, y sí las haría más caras y más opacas.

El clasificador por reglas (`clasificar_por_reglas`) cumple además una segunda
función: es el modo de respaldo. Si no hay proveedor de IA disponible, o si
falla, el pipeline sigue funcionando entero con la misma forma de salida.
"""

from __future__ import annotations

import re
import unicodedata

from .config import Config
from .modelos import Asunto, Clasificacion, Correo

# Formas habituales de nombrar un apartamento en un correo real:
# "apartamento 1105", "apto 803", "el 906", "Torre 2 apto 1105".
PATRONES_APARTAMENTO = (
    re.compile(r"\bapto\.?\s*(?:n[oº°]?\.?\s*)?(\d{3,4})\b", re.IGNORECASE),
    re.compile(r"\bapartamento\s*(?:n[oº°]?\.?\s*)?(\d{3,4})\b", re.IGNORECASE),
    re.compile(r"\bunidad\s*(?:n[oº°]?\.?\s*)?(\d{3,4})\b", re.IGNORECASE),
    # "(el 906)" o "el 1502": solo con artículo delante, para no capturar
    # cualquier número de tres cifras que aparezca en el texto.
    re.compile(r"\bel\s+(\d{3,4})\b", re.IGNORECASE),
)

PATRON_TORRE = re.compile(r"\btorre\s*(\d{1,2})\b", re.IGNORECASE)

# "soy Ana Gómez", "mi nombre es Carlos Medina"
PATRON_FIRMA = re.compile(
    r"\b(?:soy|mi nombre es|me llamo)\s+([A-ZÁÉÍÓÚÑ][\wáéíóúñ]+(?:\s+[A-ZÁÉÍÓÚÑ][\wáéíóúñ]+){0,2})"
)

PARTICULAS = {"de", "del", "la", "las", "los", "y", "da", "van"}


def sin_tildes(texto: str) -> str:
    """Normaliza para comparar: 'crédito' y 'credito' deben coincidir."""
    descompuesto = unicodedata.normalize("NFD", texto.lower())
    return "".join(c for c in descompuesto if unicodedata.category(c) != "Mn")


def contiene_alguna(texto: str, terminos: tuple[str, ...]) -> str | None:
    """Devuelve el primer término encontrado, o None. Ignora tildes y mayúsculas."""
    normalizado = sin_tildes(texto)
    for termino in terminos:
        if sin_tildes(termino) in normalizado:
            return termino
    return None


# --------------------------------------------------------------------------
# Extracción
# --------------------------------------------------------------------------

def extraer_apartamento(correo: Correo) -> str:
    """Número de apartamento y torre, si el correo los menciona.

    Una expresión regular resuelve esto con precisión total y coste cero. Pedirle
    a un modelo que "extraiga el número de apartamento" sería pagar por una
    respuesta menos fiable.
    """
    texto = correo.texto
    numero = ""
    for patron in PATRONES_APARTAMENTO:
        encontrado = patron.search(texto)
        if encontrado:
            numero = encontrado.group(1)
            break

    if not numero:
        return ""

    torre = PATRON_TORRE.search(texto)
    return f"Torre {torre.group(1)} Apto {numero}" if torre else f"Apto {numero}"


def _titular(nombre: str) -> str:
    partes = [p for p in re.split(r"[\s._-]+", nombre) if p]
    return " ".join(
        p.lower() if p.lower() in PARTICULAS else p.capitalize() for p in partes
    )


def extraer_cliente(correo: Correo) -> str:
    """Nombre del remitente: primero la firma del cuerpo, luego el correo.

    La firma es más fiable que la dirección ("soy Ana Gómez" frente a
    `ana.gomez83@gmail.com`), así que se prueba primero.
    """
    firma = PATRON_FIRMA.search(correo.cuerpo)
    if firma:
        return _titular(firma.group(1))

    usuario, _, dominio = correo.remitente.partition("@")
    usuario = re.sub(r"\d+", "", usuario)

    # Buzones de empresa: no hay una persona detrás, se usa la organización.
    if usuario.lower() in {"gerencia", "info", "contacto", "ventas", "comercial", "admin"}:
        organizacion = dominio.split(".")[0] if dominio else usuario
        return _titular(organizacion)

    nombre = _titular(usuario)
    return nombre or correo.remitente


def detectar_tema(correo: Correo, config: Config) -> str:
    """Tema de negocio del correo, por palabras clave configurables.

    Se recorre en el orden en que están escritos los temas en `config.toml`: los
    más específicos (desistimiento) van antes que los genéricos (comercial).
    """
    texto = correo.texto
    for tema, palabras in config.temas.items():
        if contiene_alguna(texto, palabras):
            return tema
    return "otro"


# Un correo con dos peticiones distintas casi siempre las separa con un giro
# como estos. Sin uno de ellos, dos temas detectados suelen ser el mismo asunto
# nombrado de dos maneras, no dos peticiones.
CONECTORES_SEGUNDA_PETICION = (
    "por otro lado", "además", "ademas", "también", "tambien", "aparte",
    "adicionalmente", "otra cosa", "solo una cosa", "por cierto",
    "de otro lado", "aprovecho para",
)


def detectar_temas(correo: Correo, config: Config) -> list[str]:
    """Temas presentes, ordenados por dónde aparecen en el correo.

    El asunto va al principio de `correo.texto`, así que el tema que da título
    al correo queda primero de forma natural: es el que manda cuando hay varios.
    """
    normalizado = sin_tildes(correo.texto)
    posiciones: dict[str, int] = {}
    for tema, palabras in config.temas.items():
        indices = [
            normalizado.find(sin_tildes(p))
            for p in palabras
            if sin_tildes(p) in normalizado
        ]
        if indices:
            posiciones[tema] = min(indices)

    if not posiciones:
        return ["otro"]
    return sorted(posiciones, key=posiciones.get)


def tiene_segunda_peticion(correo: Correo) -> bool:
    """¿El correo cambia de asunto a mitad de camino?"""
    return contiene_alguna(correo.cuerpo, CONECTORES_SEGUNDA_PETICION) is not None


ORDEN_URGENCIA = {"Baja": 0, "Media": 1, "Alta": 2}


def elevar_urgencia(actual: str, minima: str) -> str:
    """Sube la urgencia hasta un mínimo, nunca la baja."""
    return actual if ORDEN_URGENCIA[actual] >= ORDEN_URGENCIA[minima] else minima


def evaluar_urgencia(correo: Correo, config: Config) -> str:
    """Aplica la rúbrica de urgencia definida por la empresa.

    La urgencia no es una opinión del sistema: es una tabla que la empresa
    mantiene en `config.toml`. La IA aplica esta misma rúbrica, no la suya.
    """
    texto = correo.texto
    if contiene_alguna(texto, config.urgencia_alta):
        return "Alta"
    if contiene_alguna(texto, config.urgencia_media):
        return "Media"
    return "Baja"


# --------------------------------------------------------------------------
# Filtros previos: qué correos ni siquiera llegan a clasificarse
# --------------------------------------------------------------------------

def es_remitente_automatico(correo: Correo, config: Config) -> str | None:
    """Detecta notificaciones de máquinas. Devuelve el patrón que coincidió."""
    remitente = correo.remitente.lower()
    for patron in config.remitentes_automaticos:
        if patron in remitente:
            return patron
    return contiene_alguna(correo.cuerpo, config.frases_automaticas)


def es_cortesia(correo: Correo, config: Config) -> bool:
    """Agradecimiento sin nada que hacer.

    Se exige que el cuerpo sea corto: un "muchas gracias" al final de una
    petición larga no convierte el correo en cortesía. El correo de Claudia
    Rojas ("Muchas gracias… ¿el 1203 incluye parqueadero?") es exactamente ese
    caso y debe seguir su curso.
    """
    cuerpo = correo.cuerpo.strip()
    if len(cuerpo) > config.cortesia_longitud_maxima:
        return False
    if contiene_alguna(cuerpo, config.cortesia_frases) is None:
        return False
    # Si además pregunta algo, no es una despedida.
    return "?" not in cuerpo and "¿" not in cuerpo


def requiere_revision_obligatoria(correo: Correo, config: Config) -> str | None:
    """Asuntos legales o financieros: siempre los ve una persona."""
    return contiene_alguna(correo.texto, config.palabras_revision)


def es_ambiguo(correo: Correo, config: Config) -> bool:
    """Correo sin información suficiente para decidir nada.

    Sin tema reconocible, sin apartamento y con un asunto vacío o genérico, no
    hay nada que un modelo pueda deducir sin inventárselo: el correo de Carlos
    Medina ("lo que hablamos la vez pasada sigue en pie?") es el ejemplo. La
    respuesta correcta es pasárselo a una persona, no adivinar.
    """
    asunto = correo.asunto.strip().lower()
    asunto_vacio = not asunto or asunto in {"sin asunto", "pregunta", "consulta", "info", "(sin asunto)"}
    return (
        asunto_vacio
        and detectar_tema(correo, config) == "otro"
        and not extraer_apartamento(correo)
    )


def categoria_remitente(correo: Correo, config: Config) -> str:
    """Relación del remitente con la empresa: condiciona el responsable."""
    temas = detectar_temas(correo, config)
    if "alianza" in temas:
        return "tercero"
    if extraer_apartamento(correo):
        return "cliente"
    if "comercial" in temas:
        return "prospecto"
    return "desconocido"


# --------------------------------------------------------------------------
# Clasificador determinista (respaldo y línea base)
# --------------------------------------------------------------------------

# Tipo de petición que corresponde a cada tema cuando nada indica lo contrario.
# Partir del tema, y no de palabras sueltas en todo el correo, evita que la
# queja del parqueadero convierta una cotización en incidencia.
TIPO_POR_TEMA = {
    "comercial": "Pedido",
    "alianza": "Pedido",
    "escrituracion": "Pedido",
    "acabados": "Pedido",
    # Preguntar si el apartamento incluye parqueadero es una consulta; que el
    # parqueadero esté inundado es una incidencia. Lo decide la señal, no el tema.
    "zonas_comunes": "Consulta",
    "desistimiento": "Reclamación",
    "entrega": "Consulta",
    "credito": "Consulta",
    "otro": "Consulta",
}

# Un cliente inconforme o desatendido: manda sobre el tipo que sugiera el tema.
SENIALES_RECLAMACION = (
    "reclamo", "reclamación", "reclamacion", "queja", "no quedó", "no quedo",
    "nadie me contesta", "nadie me responde", "nadie me dice", "nadie me ha dicho",
    "llevo tres semanas", "llevo dos semanas", "sigo esperando", "inconforme",
    "mal estado", "incumplimiento", "no me han respondido", "es inaceptable",
)

# Algo del inmueble o del proyecto que está mal.
SENIALES_INCIDENCIA = (
    "inundado", "daño", "dano", "avería", "averia", "no funciona", "roto",
    "filtración", "filtracion", "gotera", "falla", "estaba mal", "deberían revisar",
    "deberian revisar",
)


def tipo_de_asunto(texto: str, tema: str, es_principal: bool) -> str:
    """Tipo de petición de un asunto concreto.

    Las señales de reclamación solo se aplican al asunto principal: quien se
    queja lo hace de lo que motiva el correo, no de todo lo que menciona.
    """
    if es_principal and contiene_alguna(texto, SENIALES_RECLAMACION):
        return "Reclamación"
    if tema == "desistimiento":
        return "Reclamación"
    if contiene_alguna(texto, SENIALES_INCIDENCIA) and tema in {"zonas_comunes", "acabados"}:
        return "Incidencia"
    return TIPO_POR_TEMA.get(tema, "Consulta")


def clasificar_por_reglas(correo: Correo, config: Config) -> Clasificacion:
    """Clasificación sin IA: la línea base y el modo de respaldo.

    Produce exactamente el mismo tipo de resultado que el proveedor de IA, de
    modo que el resto del pipeline no sabe ni le importa de dónde viene la
    clasificación. La confianza que asigna es deliberadamente moderada: sin
    comprensión del texto, lo honesto es admitir que puede equivocarse y dejar
    que el umbral mande a revisión lo que no esté claro.
    """
    temas = detectar_temas(correo, config)
    urgencia = evaluar_urgencia(correo, config)

    # Dos temas detectados no bastan para abrir dos filas: hacen falta indicios
    # de que el correo cambia de petición. Sin ellos se trabaja sobre el tema
    # principal, que es el que da título al correo.
    if len(temas) > 1 and not tiene_segunda_peticion(correo):
        temas = temas[:1]
    else:
        temas = temas[:2]

    asuntos = []
    for indice, tema in enumerate(temas):
        es_principal = indice == 0
        asuntos.append(
            Asunto(
                tipo=tipo_de_asunto(correo.texto, tema, es_principal),
                urgencia=urgencia if es_principal else "Media",
                tema=tema,
                accion=config.accion_de(tema),
                # Un tema reconocido da más garantías que un "otro" por descarte.
                confianza=0.75 if tema != "otro" else 0.5,
            )
        )

    return Clasificacion(
        asuntos=tuple(asuntos),
        fuente="reglas",
        notas="Clasificación por palabras clave, sin modelo de lenguaje.",
    )
