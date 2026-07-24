"""Actividad 3 — Preparación del dataset para el dashboard Power BI.

Flujo:
  1. Carga las predicciones del modelo (Actividad 2) como tabla SQL en la
     base de la sábana.
  2. Ejecuta la query 'dataset_powerbi' (join sábana + modelo + banda de
     probabilidad) — transformación en SQL.
  3. Exporta el dataset consolidado que alimenta powerbi/dashboard.pbix.

Requiere haber ejecutado antes main_actividad1.py y main_actividad2.py.
Ejecución: python src/main_actividad3.py
"""

from __future__ import annotations

import sqlite3

import pandas as pd

import config
from db_manager import GestorBaseDatos

RUTA_DATASET_POWERBI = config.DIR_DATOS_SALIDA / "dataset_powerbi.csv"


class ExportadorPowerBI:
    """Consolida sábana + resultados del modelo en el dataset del dashboard."""

    def __init__(self) -> None:
        config.asegurar_directorios()
        faltantes = [r for r in (config.RUTA_SABANA_DB, config.RUTA_PREDICCIONES_CSV)
                     if not r.exists()]
        if faltantes:
            raise FileNotFoundError(
                "Ejecute primero las actividades 1 y 2. Falta: "
                + ", ".join(str(r) for r in faltantes)
            )

    def cargar_predicciones_en_bd(self) -> int:
        """Persiste las predicciones como tabla SQL para el join."""
        predicciones = pd.read_csv(config.RUTA_PREDICCIONES_CSV)
        columnas = ["id_cxc", "prob_pago", "valor_esperado_recuperar", "valor_en_riesgo"]
        with sqlite3.connect(config.RUTA_SABANA_DB) as conexion:
            predicciones[columnas].to_sql("predicciones_cxc", conexion,
                                          if_exists="replace", index=False)
        return len(predicciones)

    def exportar_dataset(self) -> pd.DataFrame:
        """Ejecuta el join en SQL y exporta el CSV que consume Power BI."""
        with GestorBaseDatos(config.RUTA_SABANA_DB, config.RUTA_QUERIES) as gestor:
            dataset = gestor.ejecutar_query_nombrada("dataset_powerbi")
        assert dataset["prob_pago"].notna().all(), "CxC sin probabilidad asignada"
        dataset.to_csv(RUTA_DATASET_POWERBI, index=False, encoding="utf-8-sig")
        return dataset


class OrquestadorActividad3:
    """Coordina la generación del insumo del dashboard."""

    def ejecutar(self) -> None:
        print("=" * 70)
        exportador = ExportadorPowerBI()
        print("PASO 1 | Carga de predicciones en la base de la sábana")
        n = exportador.cargar_predicciones_en_bd()
        print(f"  {n:,} predicciones cargadas en tabla 'predicciones_cxc'")

        print("\nPASO 2 | Join SQL y exportación del dataset Power BI")
        dataset = exportador.exportar_dataset()
        print(f"  {len(dataset):,} filas x {len(dataset.columns)} columnas")
        print(f"  Exportado a: {RUTA_DATASET_POWERBI}")

        print("\n  Distribución por banda de probabilidad (CxC con saldo):")
        con_saldo = dataset[dataset["vlr_pendiente_pago"] > 0]
        resumen = con_saldo.groupby("banda_probabilidad").agg(
            n_cxc=("id_cxc", "count"),
            saldo=("vlr_pendiente_pago", "sum"),
            esperado=("valor_esperado_recuperar", "sum"),
        ).round(0)
        print(resumen.to_string())
        print("\n[OK] Actividad 3 completada. Abra powerbi/dashboard.pbix "
              "(guía en powerbi/guia_dashboard.md).")


if __name__ == "__main__":
    OrquestadorActividad3().ejecutar()
