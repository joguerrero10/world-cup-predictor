"""
Registro de proveedores.

Orden de prioridad:
  1. football_data_org  (API externa principal)
  2. world_bank         (datos macro, siempre activo)
  3. local_csv          (respaldo / arranque en frío)

Cada proveedor se puede desactivar con PROVIDER_<NAME>_ENABLED=false.
"""
from __future__ import annotations

import os

from .base import BaseProvider
from .football_data_org import FootballDataProvider
from .local_csv import LocalCsvProvider
from .world_bank import WorldBankProvider

_ALL: list[BaseProvider] = [
    FootballDataProvider(),
    WorldBankProvider(),
    LocalCsvProvider(),
]


def get_providers(data_type: str = "matches") -> list[BaseProvider]:
    """
    Devuelve lista de proveedores disponibles para el tipo de dato pedido,
    filtrados por variable de entorno PROVIDER_<NAME>_ENABLED.

    Prioridad preservada: API externa → macro → CSV.
    """
    result: list[BaseProvider] = []
    for p in _ALL:
        env_key = f"PROVIDER_{p.name.upper()}_ENABLED"
        if os.getenv(env_key, "true").lower() == "false":
            continue
        if p.is_available():
            result.append(p)
    return result


def get_provider(name: str) -> BaseProvider | None:
    for p in _ALL:
        if p.name == name:
            return p
    return None
