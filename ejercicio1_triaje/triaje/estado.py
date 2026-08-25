"""Memoria de lo ya procesado, para que ejecutar dos veces no duplique nada.

El enunciado menciona que hoy "a veces se le duplica una entrada". Un proceso
automático que se ejecute cada mañana tiene ese mismo riesgo multiplicado: basta
con lanzarlo dos veces, o con que el export de correos se solape un día, para
llenar el seguimiento de filas repetidas.

La huella de cada correo (`Correo.id`) se calcula a partir de su contenido, así
que la solución es un registro persistente de huellas ya vistas.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from .modelos import Correo


class RegistroProcesados:
    """Conjunto persistente de correos ya volcados al seguimiento."""

    def __init__(self, ruta: str | Path) -> None:
        self.ruta = Path(ruta)
        self._vistos: dict[str, str] = {}
        self._cargar()

    def _cargar(self) -> None:
        if not self.ruta.exists():
            return
        try:
            datos = json.loads(self.ruta.read_text(encoding="utf-8"))
            self._vistos = dict(datos.get("procesados", {}))
        except (json.JSONDecodeError, OSError):
            # Un registro corrupto no debe impedir el triaje del día: se avisa
            # por el informe y se empieza de cero. El coste de equivocarse aquí
            # es alguna fila repetida, no un correo perdido.
            self._vistos = {}

    def ya_procesado(self, correo: Correo) -> bool:
        return correo.id in self._vistos

    def marcar(self, correo: Correo) -> None:
        self._vistos[correo.id] = datetime.now().isoformat(timespec="seconds")

    def guardar(self) -> None:
        self.ruta.parent.mkdir(parents=True, exist_ok=True)
        contenido = {
            "actualizado": datetime.now().isoformat(timespec="seconds"),
            "procesados": self._vistos,
        }
        self.ruta.write_text(
            json.dumps(contenido, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def __len__(self) -> int:
        return len(self._vistos)

    def __bool__(self) -> bool:
        """Un registro recién creado sigue siendo un registro.

        Sin esto, `__len__` haría que un registro vacío se evaluara como falso y
        la primera ejecución no anotaría nada, dejando el proceso sin memoria
        justo cuando más falta hace.
        """
        return True
