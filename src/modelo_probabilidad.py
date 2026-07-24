"""Modelo de probabilidad de pago de Cuentas por Cobrar (Actividad 2).

Clase ModeloProbabilidadPago:
  - Variable objetivo: pagado_total (1 si vlr_pendiente_pago = 0).
  - Compara tres metodologías por validación cruzada (AUC): regresión
    logística, random forest y gradient boosting; selecciona la mejor.
  - Evalúa en un conjunto de prueba independiente (AUC-ROC, precisión,
    recall, F1, matriz de confusión, Brier).
  - Genera la probabilidad individual de pago de cada CxC y estima el
    valor esperado a recuperar y el valor en riesgo del saldo pendiente.
  - Exporta el pipeline entrenado (.pkl) y las métricas (.csv).
"""

from __future__ import annotations

from pathlib import Path

import joblib
import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    ConfusionMatrixDisplay,
    RocCurveDisplay,
    accuracy_score,
    brier_score_loss,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import StratifiedKFold, cross_val_score, train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler, TargetEncoder


class ModeloProbabilidadPago:
    """Entrena, evalúa y aplica el modelo de probabilidad de pago de CxC."""

    OBJETIVO = "pagado_total"
    # Predictores disponibles ANTES de conocer el desenlace de la CxC evaluada
    NUMERICAS = [
        "vlr_original_log",
        "antiguedad_dias",
        "n_cxc_cliente",
        "pct_pagadas_cliente_loo",
        "tasa_recuperacion_cliente_loo",
    ]
    CATEGORICAS_BAJA_CARD = ["producto", "rango_monto", "mes_creacion", "dia_semana_creacion"]
    CATEGORICA_ALTA_CARD = ["tipo_transaccion"]

    def __init__(self, features: pd.DataFrame, semilla: int = 42):
        self._semilla = semilla
        self._datos = self._preparar_datos(features)
        self._pipeline_ganador: Pipeline | None = None
        self._nombre_ganador: str | None = None
        self._comparacion_cv: pd.DataFrame | None = None
        self._metricas_test: dict[str, float] | None = None
        self._matriz_confusion: np.ndarray | None = None
        self._particiones: dict[str, pd.DataFrame | pd.Series] = {}

    # ------------------------------------------------------------ preparación
    def _preparar_datos(self, features: pd.DataFrame) -> pd.DataFrame:
        """Transformaciones mínimas de modelación (la sábana ya viene de SQL)."""
        datos = features.copy()
        # El monto tiene cola larga (máx ~447K): escala log para los lineales
        datos["vlr_original_log"] = np.log1p(datos["vlr_original"])
        # Meses y días de semana son categorías cíclicas, no magnitudes
        datos["mes_creacion"] = datos["mes_creacion"].astype(str)
        datos["dia_semana_creacion"] = datos["dia_semana_creacion"].astype(str)
        return datos

    @property
    def predictores(self) -> list[str]:
        return self.NUMERICAS + self.CATEGORICAS_BAJA_CARD + self.CATEGORICA_ALTA_CARD

    def _construir_preprocesador(self) -> ColumnTransformer:
        """Preprocesamiento por tipo de variable.

        tipo_transaccion (71 categorías) usa TargetEncoder con validación
        cruzada interna, que evita el sobreajuste del one-hot masivo y captura
        la relación categoría→pago sin fuga de información.
        """
        return ColumnTransformer([
            ("numericas", StandardScaler(), self.NUMERICAS),
            ("categoricas", OneHotEncoder(handle_unknown="ignore", sparse_output=False),
             self.CATEGORICAS_BAJA_CARD),
            ("alta_cardinalidad",
             TargetEncoder(cv=StratifiedKFold(n_splits=5, shuffle=True,
                                              random_state=self._semilla)),
             self.CATEGORICA_ALTA_CARD),
        ])

    def _candidatos(self) -> dict[str, Pipeline]:
        """Las tres metodologías comparadas (ver justificación en docs)."""
        prep = self._construir_preprocesador
        return {
            "regresion_logistica": Pipeline([
                ("prep", prep()),
                ("clf", LogisticRegression(max_iter=2000, random_state=self._semilla)),
            ]),
            "random_forest": Pipeline([
                ("prep", prep()),
                ("clf", RandomForestClassifier(
                    n_estimators=400, min_samples_leaf=5, n_jobs=-1,
                    random_state=self._semilla)),
            ]),
            "gradient_boosting": Pipeline([
                ("prep", prep()),
                ("clf", HistGradientBoostingClassifier(
                    max_iter=300, learning_rate=0.08, max_leaf_nodes=31,
                    random_state=self._semilla)),
            ]),
        }

    # ------------------------------------------------------------ entrenamiento
    def entrenar(self, proporcion_test: float = 0.2) -> pd.DataFrame:
        """Divide train/test, compara candidatos por CV y ajusta el ganador."""
        X = self._datos[self.predictores]
        y = self._datos[self.OBJETIVO]
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=proporcion_test, stratify=y, random_state=self._semilla
        )
        self._particiones = {"X_train": X_train, "X_test": X_test,
                             "y_train": y_train, "y_test": y_test}

        cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=self._semilla)
        filas = []
        for nombre, pipeline in self._candidatos().items():
            aucs = cross_val_score(pipeline, X_train, y_train, cv=cv,
                                   scoring="roc_auc", n_jobs=1)
            filas.append({"modelo": nombre, "auc_cv_media": aucs.mean(),
                          "auc_cv_desv": aucs.std()})
        self._comparacion_cv = (
            pd.DataFrame(filas).sort_values("auc_cv_media", ascending=False)
            .reset_index(drop=True)
        )
        self._nombre_ganador = self._comparacion_cv.loc[0, "modelo"]
        self._pipeline_ganador = self._candidatos()[self._nombre_ganador]
        self._pipeline_ganador.fit(X_train, y_train)
        return self._comparacion_cv

    # ---------------------------------------------------------------- evaluación
    def evaluar(self, umbral: float = 0.5) -> dict[str, float]:
        """Métricas sobre el conjunto de prueba (nunca visto en entrenamiento)."""
        X_test, y_test = self._particiones["X_test"], self._particiones["y_test"]
        probabilidades = self._pipeline_ganador.predict_proba(X_test)[:, 1]
        predicciones = (probabilidades >= umbral).astype(int)
        self._metricas_test = {
            "auc_roc": roc_auc_score(y_test, probabilidades),
            "precision": precision_score(y_test, predicciones),
            "recall": recall_score(y_test, predicciones),
            "f1": f1_score(y_test, predicciones),
            "accuracy": accuracy_score(y_test, predicciones),
            "brier": brier_score_loss(y_test, probabilidades),
        }
        self._matriz_confusion = confusion_matrix(y_test, predicciones)
        return self._metricas_test

    def graficar_evaluacion(self, dir_img: Path) -> list[Path]:
        """ROC, matriz de confusión y distribución de probabilidades."""
        dir_img = Path(dir_img)
        X_test, y_test = self._particiones["X_test"], self._particiones["y_test"]
        probabilidades = self._pipeline_ganador.predict_proba(X_test)[:, 1]
        rutas = []

        fig, eje = plt.subplots(figsize=(6, 5))
        RocCurveDisplay.from_predictions(y_test, probabilidades, ax=eje,
                                         name=self._nombre_ganador)
        eje.plot([0, 1], [0, 1], "k--", linewidth=0.8)
        eje.set_title("Curva ROC — conjunto de prueba")
        fig.tight_layout()
        rutas.append(dir_img / "08_curva_roc.png")
        fig.savefig(rutas[-1], dpi=130); plt.close(fig)

        fig, eje = plt.subplots(figsize=(5.5, 5))
        ConfusionMatrixDisplay(self._matriz_confusion,
                               display_labels=["No paga", "Paga"]).plot(
            ax=eje, colorbar=False, values_format=",d")
        eje.set_title("Matriz de confusión (umbral 0,5)")
        fig.tight_layout()
        rutas.append(dir_img / "09_matriz_confusion.png")
        fig.savefig(rutas[-1], dpi=130); plt.close(fig)

        fig, eje = plt.subplots(figsize=(8, 4))
        eje.hist(probabilidades[y_test == 1], bins=40, alpha=0.65,
                 label="Pagadas (real)", color="#2e7d32", density=True)
        eje.hist(probabilidades[y_test == 0], bins=40, alpha=0.65,
                 label="No pagadas (real)", color="#c62828", density=True)
        eje.set_xlabel("Probabilidad de pago estimada")
        eje.set_ylabel("Densidad")
        eje.set_title("Separación de clases — conjunto de prueba")
        eje.legend()
        fig.tight_layout()
        rutas.append(dir_img / "10_distribucion_probabilidades.png")
        fig.savefig(rutas[-1], dpi=130); plt.close(fig)
        return rutas

    # ---------------------------------------------------------------- aplicación
    def generar_probabilidades(self) -> pd.DataFrame:
        """Probabilidad individual de pago para TODAS las CxC de la sábana."""
        probabilidades = self._pipeline_ganador.predict_proba(
            self._datos[self.predictores])[:, 1]
        resultado = self._datos[["id_cxc", "estado_pago", "vlr_original",
                                 "vlr_pendiente_pago", "producto",
                                 "tipo_transaccion", "rango_monto"]].copy()
        resultado["prob_pago"] = np.round(probabilidades, 4)
        return resultado

    @staticmethod
    def estimar_recuperacion(predicciones: pd.DataFrame) -> pd.DataFrame:
        """Valor esperado a recuperar y valor en riesgo del saldo pendiente.

        Sobre el saldo aún pendiente de cada CxC:
          valor_esperado = prob_pago x vlr_pendiente
          valor_en_riesgo = (1 - prob_pago) x vlr_pendiente
        Las CxC ya pagadas tienen saldo 0 y no aportan a ninguna de las dos.
        """
        resultado = predicciones.copy()
        resultado["valor_esperado_recuperar"] = np.round(
            resultado["prob_pago"] * resultado["vlr_pendiente_pago"], 2)
        resultado["valor_en_riesgo"] = np.round(
            (1 - resultado["prob_pago"]) * resultado["vlr_pendiente_pago"], 2)
        return resultado

    # ---------------------------------------------------------------- exportes
    def exportar_modelo(self, ruta_pkl: Path) -> None:
        joblib.dump(self._pipeline_ganador, ruta_pkl)

    def exportar_metricas(self, ruta_csv: Path) -> pd.DataFrame:
        """Consolida comparación CV + métricas de test en un único CSV."""
        cv = self._comparacion_cv.copy()
        cv.insert(0, "etapa", "validacion_cruzada_5fold")
        test = pd.DataFrame([
            {"etapa": "test_holdout_20pct", "modelo": self._nombre_ganador,
             "metrica": nombre, "valor": round(valor, 4)}
            for nombre, valor in self._metricas_test.items()
        ])
        vn, fp, fn, vp = self._matriz_confusion.ravel()
        confusion = pd.DataFrame([
            {"etapa": "test_holdout_20pct", "modelo": self._nombre_ganador,
             "metrica": nombre, "valor": int(valor)}
            for nombre, valor in
            [("verdaderos_negativos", vn), ("falsos_positivos", fp),
             ("falsos_negativos", fn), ("verdaderos_positivos", vp)]
        ])
        cv_largo = cv.melt(id_vars=["etapa", "modelo"], var_name="metrica",
                           value_name="valor")
        cv_largo["valor"] = cv_largo["valor"].round(4)
        metricas = pd.concat([cv_largo, test, confusion], ignore_index=True)
        metricas.to_csv(ruta_csv, index=False, encoding="utf-8-sig")
        return metricas

    # --------------------------------------------------------- sensibilidad
    def prueba_sensibilidad(self) -> dict[str, float]:
        """Entrena sin las features de historial LOO para cuantificar su aporte.

        Si el AUC cae significativamente al quitar n_cxc_cliente,
        pct_pagadas_cliente_loo y tasa_recuperacion_cliente_loo, las features
        son realmente informativas y no hay fuga de datos en el LOO.
        """
        NUMERICAS_BASE = ["vlr_original_log", "antiguedad_dias"]
        X_train = self._particiones["X_train"]
        X_test  = self._particiones["X_test"]
        y_train = self._particiones["y_train"]
        y_test  = self._particiones["y_test"]

        cols_base = NUMERICAS_BASE + self.CATEGORICAS_BAJA_CARD + self.CATEGORICA_ALTA_CARD
        prep_base = ColumnTransformer([
            ("numericas",       StandardScaler(),
             NUMERICAS_BASE),
            ("categoricas",     OneHotEncoder(handle_unknown="ignore", sparse_output=False),
             self.CATEGORICAS_BAJA_CARD),
            ("alta_cardinalidad",
             TargetEncoder(cv=StratifiedKFold(n_splits=5, shuffle=True,
                                              random_state=self._semilla)),
             self.CATEGORICA_ALTA_CARD),
        ])
        pipeline_base = Pipeline([
            ("prep", prep_base),
            ("clf",  HistGradientBoostingClassifier(
                max_iter=300, learning_rate=0.08, max_leaf_nodes=31,
                random_state=self._semilla)),
        ])
        pipeline_base.fit(X_train[cols_base], y_train)
        proba_base = pipeline_base.predict_proba(X_test[cols_base])[:, 1]
        return {
            "auc_sin_historial_loo": round(roc_auc_score(y_test, proba_base), 4),
            "auc_con_historial_loo": round(self._metricas_test["auc_roc"], 4),
        }

    # ---------------------------------------------------------------- lectura
    @property
    def nombre_ganador(self) -> str:
        return self._nombre_ganador

    @property
    def metricas_test(self) -> dict[str, float]:
        return self._metricas_test
