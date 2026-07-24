"""Explorador EDA: análisis descriptivo y visualizaciones de la sábana de CxC.

Genera las gráficas del análisis exploratorio en docs/img/ y un resumen
estadístico en consola/CSV. Los hallazgos se interpretan en docs/documentacion.md.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # sin ventana gráfica: solo exportar archivos

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns

sns.set_theme(style="whitegrid", palette="deep")

COLOR_ESTADOS = {"PAGADO": "#2e7d32", "PARCIAL": "#f9a825", "PENDIENTE": "#c62828"}


class ExploradorEDA:
    """Produce las visualizaciones y estadísticos del análisis exploratorio."""

    def __init__(self, sabana: pd.DataFrame, dir_img: Path):
        self._df = sabana.copy()
        self._dir_img = Path(dir_img)
        self._dir_img.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------- utilidades
    def _guardar(self, fig: plt.Figure, nombre: str) -> Path:
        ruta = self._dir_img / f"{nombre}.png"
        fig.tight_layout()
        fig.savefig(ruta, dpi=130)
        plt.close(fig)
        return ruta

    # ---------------------------------------------------------------- figuras
    def grafico_estados(self) -> Path:
        """Distribución del portafolio por estado de pago (conteo y valor)."""
        resumen = self._df.groupby("estado_pago").agg(
            n_cxc=("id_cxc", "count"), vlr_original=("vlr_original", "sum")
        ).reindex(["PAGADO", "PARCIAL", "PENDIENTE"])
        fig, ejes = plt.subplots(1, 2, figsize=(11, 4))
        colores = [COLOR_ESTADOS[e] for e in resumen.index]
        ejes[0].bar(resumen.index, resumen["n_cxc"], color=colores)
        ejes[0].set_title("CxC por estado de pago (conteo)")
        ejes[0].set_ylabel("Número de CxC")
        for i, v in enumerate(resumen["n_cxc"]):
            ejes[0].text(i, v, f"{v:,.0f}", ha="center", va="bottom", fontsize=9)
        ejes[1].bar(resumen.index, resumen["vlr_original"] / 1e6, color=colores)
        ejes[1].set_title("Valor original por estado (millones)")
        ejes[1].set_ylabel("Valor original (MM)")
        for i, v in enumerate(resumen["vlr_original"] / 1e6):
            ejes[1].text(i, v, f"{v:,.1f}", ha="center", va="bottom", fontsize=9)
        return self._guardar(fig, "01_estados_pago")

    def grafico_distribucion_montos(self) -> Path:
        """Distribución del valor original (escala logarítmica)."""
        fig, eje = plt.subplots(figsize=(9, 4))
        sns.histplot(self._df["vlr_original"], bins=60, log_scale=True, ax=eje, color="#1565c0")
        eje.set_title("Distribución del valor original de las CxC (escala log)")
        eje.set_xlabel("Valor original")
        eje.set_ylabel("Frecuencia")
        return self._guardar(fig, "02_distribucion_montos")

    def grafico_recuperacion_por_monto(self) -> Path:
        """% de CxC pagadas y % de valor recuperado por rango de monto."""
        resumen = self._df.groupby("rango_monto").agg(
            pct_pagadas=("pagado_total", "mean"),
            pct_valor=("vlr_pagado", "sum"),
            vlr=("vlr_original", "sum"),
        )
        resumen["pct_valor"] = resumen["pct_valor"] / resumen["vlr"]
        fig, eje = plt.subplots(figsize=(9, 4))
        x = range(len(resumen))
        eje.bar([i - 0.2 for i in x], resumen["pct_pagadas"] * 100, width=0.4,
                label="% CxC pagadas", color="#2e7d32")
        eje.bar([i + 0.2 for i in x], resumen["pct_valor"] * 100, width=0.4,
                label="% valor recuperado", color="#1565c0")
        eje.set_xticks(list(x), resumen.index, rotation=15)
        eje.set_ylabel("%")
        eje.set_title("Recuperación por rango de monto")
        eje.legend()
        return self._guardar(fig, "03_recuperacion_por_monto")

    def grafico_evolucion_mensual(self) -> Path:
        """Creación mensual de CxC y tasa de recuperación por cohorte."""
        resumen = self._df.groupby("periodo_creacion").agg(
            n_cxc=("id_cxc", "count"),
            vlr=("vlr_original", "sum"),
            pagado=("vlr_pagado", "sum"),
        )
        resumen["pct_recuperado"] = resumen["pagado"] / resumen["vlr"] * 100
        fig, eje = plt.subplots(figsize=(11, 4.5))
        eje.bar(resumen.index, resumen["n_cxc"], color="#90a4ae", label="CxC creadas")
        eje.set_ylabel("CxC creadas")
        eje.tick_params(axis="x", rotation=45)
        eje2 = eje.twinx()
        eje2.plot(resumen.index, resumen["pct_recuperado"], color="#c62828",
                  marker="o", label="% valor recuperado")
        eje2.set_ylabel("% valor recuperado (cohorte)")
        eje2.set_ylim(0, 105)
        eje.set_title("Creación mensual de CxC y recuperación por cohorte")
        lineas1, etiquetas1 = eje.get_legend_handles_labels()
        lineas2, etiquetas2 = eje2.get_legend_handles_labels()
        eje.legend(lineas1 + lineas2, etiquetas1 + etiquetas2, loc="upper left")
        return self._guardar(fig, "04_evolucion_mensual")

    def grafico_top_transacciones(self, top_n: int = 10) -> Path:
        """Top transacciones por valor pendiente (dónde está el riesgo)."""
        resumen = (
            self._df.groupby("tipo_transaccion")
            .agg(pendiente=("vlr_pendiente_pago", "sum"), pct_pagadas=("pagado_total", "mean"))
            .nlargest(top_n, "pendiente")
            .sort_values("pendiente")
        )
        fig, eje = plt.subplots(figsize=(10, 5))
        barras = eje.barh(resumen.index, resumen["pendiente"] / 1e6, color="#c62828")
        eje.set_xlabel("Valor pendiente (MM)")
        eje.set_title(f"Top {top_n} tipos de transacción por valor pendiente")
        for barra, pct in zip(barras, resumen["pct_pagadas"]):
            eje.text(barra.get_width(), barra.get_y() + barra.get_height() / 2,
                     f"  {pct*100:.0f}% pagadas", va="center", fontsize=8)
        return self._guardar(fig, "05_top_transacciones_pendiente")

    def grafico_dias_hasta_pago(self) -> Path:
        """Distribución de días entre creación y último pago (CxC con pago)."""
        con_pago = self._df.loc[self._df["dias_creacion_a_pago"].notna()]
        fig, eje = plt.subplots(figsize=(9, 4))
        sns.histplot(con_pago["dias_creacion_a_pago"], bins=50, ax=eje, color="#00695c")
        mediana = con_pago["dias_creacion_a_pago"].median()
        eje.axvline(mediana, color="#c62828", linestyle="--",
                    label=f"Mediana: {mediana:.0f} días")
        eje.set_title("Días entre creación y último pago (CxC con algún pago)")
        eje.set_xlabel("Días")
        eje.legend()
        return self._guardar(fig, "06_dias_hasta_pago")

    def grafico_pago_por_antiguedad(self) -> Path:
        """% de CxC totalmente pagadas según rango de antigüedad."""
        resumen = self._df.groupby("rango_antiguedad")["pagado_total"].mean() * 100
        fig, eje = plt.subplots(figsize=(9, 4))
        eje.bar(resumen.index, resumen.values, color="#4527a0")
        eje.set_ylabel("% CxC pagadas")
        eje.set_title("Proporción de CxC pagadas por antigüedad a la fecha de corte")
        for i, v in enumerate(resumen.values):
            eje.text(i, v, f"{v:.1f}%", ha="center", va="bottom", fontsize=9)
        return self._guardar(fig, "07_pago_por_antiguedad")

    # ---------------------------------------------------------------- resumen
    def resumen_estadistico(self) -> pd.DataFrame:
        """Estadísticos descriptivos de las variables numéricas clave."""
        columnas = ["vlr_original", "vlr_pagado", "vlr_pendiente_pago",
                    "tasa_recuperacion", "dias_creacion_a_pago", "antiguedad_dias",
                    "n_cxc_cliente"]
        return self._df[columnas].describe().T.round(2)

    def generar_todo(self) -> list[Path]:
        """Ejecuta todas las visualizaciones y devuelve las rutas generadas."""
        return [
            self.grafico_estados(),
            self.grafico_distribucion_montos(),
            self.grafico_recuperacion_por_monto(),
            self.grafico_evolucion_mensual(),
            self.grafico_top_transacciones(),
            self.grafico_dias_hasta_pago(),
            self.grafico_pago_por_antiguedad(),
        ]
