"""Actividad 1 — Exploración y construcción de la sábana analítica de CxC.

Orquesta el flujo completo:
  1. Conecta a la base SQLite histórica.
  2. Ejecuta las queries de verificación (perfil, calidad, particiones).
  3. Construye la sábana analítica (transformación 100% en SQL).
  4. Exporta la sábana (CSV + SQLite) y las métricas agregadas.
  5. Genera las visualizaciones del EDA en docs/img/.

Ejecución (desde la raíz del proyecto, con el venv activo):
    python src/main_actividad1.py
"""

from __future__ import annotations

import config
from constructor_sabana import ConstructorSabana
from db_manager import GestorBaseDatos
from explorador_eda import ExploradorEDA


class OrquestadorActividad1:
    """Coordina la exploración, la construcción de la sábana y el EDA."""

    def __init__(self) -> None:
        config.asegurar_directorios()

    def ejecutar(self) -> None:
        with GestorBaseDatos(config.RUTA_BD, config.RUTA_QUERIES) as gestor:
            self._verificaciones_iniciales(gestor)
            sabana = self._construir_sabana(gestor)
        self._ejecutar_eda(sabana)
        print("\n[OK] Actividad 1 completada.")

    # ------------------------------------------------------------------ pasos
    def _verificaciones_iniciales(self, gestor: GestorBaseDatos) -> None:
        print("=" * 70)
        print("PASO 1 | Perfil general del portafolio")
        print(gestor.ejecutar_query_nombrada("perfil_general").T.to_string(header=False))
        print("\nPASO 2 | Controles de calidad de datos")
        print(gestor.ejecutar_query_nombrada("calidad_datos").T.to_string(header=False))
        print("\nPASO 3 | Particiones de extracción (fechas de corte)")
        print(gestor.ejecutar_query_nombrada("particiones").to_string(index=False))

    def _construir_sabana(self, gestor: GestorBaseDatos):
        print("\nPASO 4 | Construcción de la sábana analítica (SQL)")
        constructor = ConstructorSabana(gestor, config.DIR_DATOS_SALIDA)
        sabana = constructor.construir()
        constructor.exportar(config.RUTA_SABANA_CSV, config.RUTA_SABANA_DB)
        agregadas = constructor.exportar_metricas_agregadas()
        print(f"  Sábana: {len(sabana):,} filas x {len(sabana.columns)} columnas")
        print(f"  Exportada a: {config.RUTA_SABANA_CSV.name} y {config.RUTA_SABANA_DB.name}")
        print(f"  Métricas agregadas exportadas: {', '.join(agregadas)}")
        print("\n  Distribución por estado de pago:")
        print(agregadas["distribucion_estados"].to_string(index=False))
        print("\n  Cobertura de campos clave:")
        print(constructor.resumen_cobertura().to_string(index=False))
        return sabana

    def _ejecutar_eda(self, sabana) -> None:
        print("\nPASO 5 | Análisis exploratorio (EDA)")
        explorador = ExploradorEDA(sabana, config.DIR_IMG)
        print(explorador.resumen_estadistico().to_string())
        rutas = explorador.generar_todo()
        print(f"\n  {len(rutas)} gráficas generadas en {config.DIR_IMG}:")
        for ruta in rutas:
            print(f"   - {ruta.name}")


if __name__ == "__main__":
    OrquestadorActividad1().ejecutar()
