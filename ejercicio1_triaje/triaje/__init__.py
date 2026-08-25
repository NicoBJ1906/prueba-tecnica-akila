"""Triaje automático de correos de clientes.

Sistema híbrido: las reglas de negocio se resuelven con lógica determinista y
solo la clasificación del texto puede apoyarse en un modelo de lenguaje.
"""

from .config import Config, cargar_config
from .modelos import Asunto, Clasificacion, Correo, FilaSeguimiento, ResultadoTriaje
from .pipeline import ejecutar, leer_correos

__all__ = [
    "Asunto",
    "Clasificacion",
    "Config",
    "Correo",
    "FilaSeguimiento",
    "ResultadoTriaje",
    "cargar_config",
    "ejecutar",
    "leer_correos",
]
