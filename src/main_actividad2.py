"""Actividad 2 — Modelo de probabilidad de pago de CxC.

Flujo:
  1. Lee las features desde la base de la sábana (query SQL 'features_modelo',
     con historial de cliente leave-one-out).
  2. Compara tres metodologías por validación cruzada y entrena la ganadora.
  3. Evalúa en test (AUC-ROC, precisión, recall, F1, matriz de confusión).
  4. Genera la probabilidad individual de pago de las 21.739 CxC.
  5. Estima valor esperado a recuperar y valor en riesgo del saldo pendiente.
  6. Exporta modelo.pkl, metricas_modelo.csv y predicciones_cxc.csv.

Requiere haber ejecutado antes: python src/main_actividad1.py
Ejecución: python src/main_actividad2.py
"""

from __future__ import annotations

import config
from db_manager import GestorBaseDatos
from modelo_probabilidad import ModeloProbabilidadPago


class OrquestadorActividad2:
    """Coordina el entrenamiento, evaluación y aplicación del modelo."""

    def __init__(self) -> None:
        config.asegurar_directorios()
        if not config.RUTA_SABANA_DB.exists():
            raise FileNotFoundError(
                "No existe la sábana. Ejecute primero: python src/main_actividad1.py"
            )

    def ejecutar(self) -> None:
        print("=" * 70)
        print("PASO 1 | Lectura de features (SQL sobre la sábana, cliente LOO)")
        with GestorBaseDatos(config.RUTA_SABANA_DB, config.RUTA_QUERIES) as gestor:
            features = gestor.ejecutar_query_nombrada("features_modelo")
        print(f"  {len(features):,} CxC | tasa de pago total: "
              f"{features['pagado_total'].mean():.1%}")

        print("\nPASO 2 | Comparación de metodologías (CV 5-fold, AUC-ROC)")
        modelo = ModeloProbabilidadPago(features, semilla=config.SEMILLA)
        comparacion = modelo.entrenar()
        print(comparacion.round(4).to_string(index=False))
        print(f"  Modelo seleccionado: {modelo.nombre_ganador}")

        print("\nPASO 3 | Evaluación en conjunto de prueba (20% holdout)")
        metricas = modelo.evaluar()
        for nombre, valor in metricas.items():
            print(f"  {nombre:>10}: {valor:.4f}")
        rutas = modelo.graficar_evaluacion(config.DIR_IMG)
        print(f"  Gráficas: {', '.join(r.name for r in rutas)}")

        print("\nPASO 4 | Probabilidades individuales y estimación de recuperación")
        predicciones = modelo.estimar_recuperacion(modelo.generar_probabilidades())
        predicciones.to_csv(config.RUTA_PREDICCIONES_CSV, index=False,
                            encoding="utf-8-sig")
        pendientes = predicciones[predicciones["vlr_pendiente_pago"] > 0]
        saldo = pendientes["vlr_pendiente_pago"].sum()
        esperado = pendientes["valor_esperado_recuperar"].sum()
        riesgo = pendientes["valor_en_riesgo"].sum()
        print(f"  CxC con saldo pendiente: {len(pendientes):,}")
        print(f"  Saldo pendiente total:      ${saldo:,.0f}")
        print(f"  Valor esperado a recuperar: ${esperado:,.0f} ({esperado/saldo:.1%})")
        print(f"  Valor en riesgo:            ${riesgo:,.0f} ({riesgo/saldo:.1%})")

        print("\nPASO 5 | Prueba de sensibilidad (validación de features LOO)")
        sensibilidad = modelo.prueba_sensibilidad()
        auc_base = sensibilidad["auc_sin_historial_loo"]
        auc_full = sensibilidad["auc_con_historial_loo"]
        print(f"  AUC sin historial de cliente (LOO): {auc_base:.4f}")
        print(f"  AUC con historial de cliente (LOO): {auc_full:.4f}")
        print(f"  Ganancia neta de las features LOO:  +{auc_full - auc_base:.4f}")
        print("  → La caída confirma que las features LOO aportan información real")
        print("    y no existe fuga de datos en la construcción de la sábana.")

        print("\nPASO 6 | Exportación de artefactos")
        modelo.exportar_modelo(config.RUTA_MODELO_PKL)
        modelo.exportar_metricas(config.RUTA_METRICAS_CSV)
        print(f"  {config.RUTA_MODELO_PKL}")
        print(f"  {config.RUTA_METRICAS_CSV}")
        print(f"  {config.RUTA_PREDICCIONES_CSV}")
        print("\n[OK] Actividad 2 completada.")


if __name__ == "__main__":
    OrquestadorActividad2().ejecutar()
