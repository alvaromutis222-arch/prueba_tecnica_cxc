"""Constructor de la sábana analítica de CxC.

Ejecuta la transformación SQL 'sabana_cxc' y las métricas agregadas, y
persiste los resultados en CSV (para Power BI / modelo) y en una base
SQLite de salida (activo de datos consultable).
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd

from db_manager import GestorBaseDatos


class ConstructorSabana:
    """Orquesta la construcción y exportación de la sábana analítica."""

    METRICAS_AGREGADAS = (
        "metricas_por_transaccion",
        "metricas_por_producto",
        "metricas_por_rango_monto",
        "metricas_por_periodo",
        "distribucion_estados",
    )

    def __init__(self, gestor: GestorBaseDatos, dir_salida: Path):
        self._gestor = gestor
        self._dir_salida = Path(dir_salida)
        self._sabana: pd.DataFrame | None = None

    @property
    def sabana(self) -> pd.DataFrame:
        if self._sabana is None:
            raise RuntimeError("La sábana no está construida; llame a construir().")
        return self._sabana

    def construir(self) -> pd.DataFrame:
        """Ejecuta la transformación SQL principal y valida el resultado."""
        self._sabana = self._gestor.ejecutar_query_nombrada("sabana_cxc")
        self._validar()
        return self._sabana

    def _validar(self) -> None:
        """Controles mínimos de integridad sobre la sábana construida."""
        df = self.sabana
        assert df["id_cxc"].is_unique, "id_cxc duplicado en la sábana"
        assert (df["tasa_recuperacion"].between(0, 1)).all(), "tasa_recuperacion fuera de [0,1]"
        assert df["estado_pago"].isin(["PAGADO", "PARCIAL", "PENDIENTE"]).all(), \
            "estado_pago con categorías inesperadas"
        assert (df["antiguedad_dias"] >= 0).all(), "antigüedad negativa"

    def exportar(self, ruta_csv: Path, ruta_db: Path) -> None:
        """Exporta la sábana a CSV y a una base SQLite de salida."""
        self._dir_salida.mkdir(parents=True, exist_ok=True)
        self.sabana.to_csv(ruta_csv, index=False, encoding="utf-8-sig")
        with sqlite3.connect(ruta_db) as conexion:
            self.sabana.to_sql("sabana_cxc", conexion, if_exists="replace", index=False)

    def exportar_metricas_agregadas(self) -> dict[str, pd.DataFrame]:
        """Ejecuta y exporta las vistas agregadas (insumo de EDA y Power BI)."""
        resultados: dict[str, pd.DataFrame] = {}
        for nombre in self.METRICAS_AGREGADAS:
            df = self._gestor.ejecutar_query_nombrada(nombre)
            df.to_csv(self._dir_salida / f"{nombre}.csv", index=False, encoding="utf-8-sig")
            resultados[nombre] = df
        return resultados

    def resumen_cobertura(self) -> pd.DataFrame:
        """Cobertura (% no nulo) de los campos clave de la sábana."""
        CAMPOS = [
            "id_cxc", "estado_pago", "vlr_original", "vlr_pendiente_pago",
            "tasa_recuperacion", "producto", "tipo_transaccion",
            "fecha_creacion", "antiguedad_dias",
        ]
        df = self.sabana[CAMPOS]
        total = len(df)
        cobertura = pd.DataFrame({
            "campo": CAMPOS,
            "no_nulos": df.notna().sum().values,
            "cobertura_pct": (df.notna().mean() * 100).round(2).values,
        })
        cobertura["total"] = total
        return cobertura
