"""Gestor de base de datos: conexión SQLite y ejecución de queries nombradas.

Las transformaciones viven en src/sql/queries.sql; esta clase solo orquesta:
parsea el archivo, resuelve queries por nombre y las ejecuta contra SQLite,
devolviendo DataFrames listos para exportar o analizar.
"""

from __future__ import annotations

import re
import sqlite3
from pathlib import Path

import pandas as pd


class GestorBaseDatos:
    """Encapsula la conexión a SQLite y el catálogo de queries nombradas.

    Uso:
        with GestorBaseDatos(ruta_bd, ruta_queries) as gestor:
            df = gestor.ejecutar_query_nombrada("sabana_cxc")
    """

    MARCADOR_NOMBRE = re.compile(r"^--\s*name:\s*(\w+)\s*$", re.MULTILINE)

    def __init__(self, ruta_bd: Path, ruta_queries: Path | None = None):
        if not Path(ruta_bd).exists():
            raise FileNotFoundError(f"No se encontró la base de datos: {ruta_bd}")
        self._ruta_bd = Path(ruta_bd)
        self._conexion: sqlite3.Connection | None = None
        self._catalogo: dict[str, str] = {}
        if ruta_queries is not None:
            self.cargar_catalogo_queries(ruta_queries)

    # ------------------------------------------------------------------ ciclo
    def conectar(self) -> None:
        if self._conexion is None:
            self._conexion = sqlite3.connect(self._ruta_bd)

    def cerrar(self) -> None:
        if self._conexion is not None:
            self._conexion.close()
            self._conexion = None

    def __enter__(self) -> "GestorBaseDatos":
        self.conectar()
        return self

    def __exit__(self, *args) -> None:
        self.cerrar()

    @property
    def conexion(self) -> sqlite3.Connection:
        if self._conexion is None:
            raise RuntimeError("La conexión no está abierta; use conectar() o un bloque with.")
        return self._conexion

    # -------------------------------------------------------------- catálogo
    def cargar_catalogo_queries(self, ruta_queries: Path) -> None:
        """Parsea el .sql y registra cada query bajo su marcador '-- name:'."""
        contenido = Path(ruta_queries).read_text(encoding="utf-8")
        partes = self.MARCADOR_NOMBRE.split(contenido)
        # partes = [preambulo, nombre1, sql1, nombre2, sql2, ...]
        for i in range(1, len(partes) - 1, 2):
            self._catalogo[partes[i]] = partes[i + 1].strip()
        if not self._catalogo:
            raise ValueError(f"No se encontraron queries con marcador '-- name:' en {ruta_queries}")

    @property
    def queries_disponibles(self) -> list[str]:
        return sorted(self._catalogo)

    # ------------------------------------------------------------- ejecución
    def ejecutar_query_nombrada(self, nombre: str) -> pd.DataFrame:
        """Ejecuta una query del catálogo y devuelve el resultado como DataFrame."""
        if nombre not in self._catalogo:
            raise KeyError(
                f"Query '{nombre}' no existe. Disponibles: {self.queries_disponibles}"
            )
        return pd.read_sql_query(self._catalogo[nombre], self.conexion)

    def ejecutar_sql(self, sql: str) -> pd.DataFrame:
        """Ejecuta SQL arbitrario (uso puntual en exploración)."""
        return pd.read_sql_query(sql, self.conexion)
