"""Localización del Excel de seguimiento por nombre de fichero.

Evita depender de rutas escritas a mano, que cambian entre Windows y macOS. Se
busca en las carpetas habituales de trabajo y, si no aparece, se crea en la
primera que exista.
"""

from __future__ import annotations

import os
from pathlib import Path

NOMBRE_POR_DEFECTO = "seguimiento.xlsx"

# Profundidad máxima al recorrer cada carpeta: suficiente para encontrarlo en una
# subcarpeta de trabajo sin recorrer un disco entero.
NIVELES = 3


def carpetas_candidatas() -> list[Path]:
    """Sitios donde suele vivir el Excel, en orden de preferencia.

    `TRIAJE_CARPETA_SEGUIMIENTO` manda sobre todo lo demás: es lo que se apunta a
    la carpeta sincronizada de OneDrive, SharePoint o Drive.
    """
    casa = Path.home()
    candidatas = []

    definida = os.environ.get("TRIAJE_CARPETA_SEGUIMIENTO", "").strip()
    if definida:
        candidatas.append(Path(definida).expanduser())

    # Nombres en español e inglés: el mismo equipo puede tener cualquiera de los
    # dos según el idioma del sistema.
    for nombre in ("OneDrive", "Documentos", "Documents", "Escritorio", "Desktop"):
        candidatas.append(casa / nombre)
    candidatas.append(casa)

    return [c for c in candidatas if c.is_dir()]


def buscar(nombre: str = NOMBRE_POR_DEFECTO) -> Path | None:
    """Devuelve la primera coincidencia del fichero, o None si no está."""
    for carpeta in carpetas_candidatas():
        for nivel in range(NIVELES):
            patron = "/".join(["*"] * nivel + [nombre]) if nivel else nombre
            try:
                for encontrado in sorted(carpeta.glob(patron)):
                    if encontrado.is_file():
                        return encontrado
            except OSError:
                continue
    return None


def resolver(nombre: str = NOMBRE_POR_DEFECTO) -> Path:
    """Ruta del Excel: la existente si aparece, y si no una nueva donde tocaría.

    Nunca falla: si no hay ninguna carpeta candidata se usa el directorio actual.
    """
    encontrado = buscar(nombre)
    if encontrado is not None:
        return encontrado

    carpetas = carpetas_candidatas()
    destino = carpetas[0] if carpetas else Path.cwd()
    return destino / nombre
