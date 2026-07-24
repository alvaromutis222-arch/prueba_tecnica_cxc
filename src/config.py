"""Configuración central del proyecto: rutas y constantes compartidas."""

from pathlib import Path

# Raíz del proyecto (carpeta que contiene src/, data/, docs/, powerbi/)
RAIZ_PROYECTO = Path(__file__).resolve().parent.parent

# Rutas de entrada
RUTA_BD = RAIZ_PROYECTO / "data" / "base_datos_historica.db"
RUTA_QUERIES = RAIZ_PROYECTO / "src" / "sql" / "queries.sql"

# Rutas de salida
DIR_DATOS_SALIDA = RAIZ_PROYECTO / "src" / "data"
DIR_MODELO = RAIZ_PROYECTO / "src" / "modelo"
DIR_METRICAS = RAIZ_PROYECTO / "src" / "metricas"
DIR_DOCS = RAIZ_PROYECTO / "docs"
DIR_IMG = RAIZ_PROYECTO / "docs" / "img"
DIR_POWERBI = RAIZ_PROYECTO / "powerbi"

# Archivos de salida principales
RUTA_SABANA_CSV = DIR_DATOS_SALIDA / "sabana_cxc.csv"
RUTA_SABANA_DB = DIR_DATOS_SALIDA / "sabana_cxc.db"
RUTA_MODELO_PKL = DIR_MODELO / "modelo.pkl"
RUTA_METRICAS_CSV = DIR_METRICAS / "metricas_modelo.csv"
RUTA_PREDICCIONES_CSV = DIR_DATOS_SALIDA / "predicciones_cxc.csv"

# Semilla global para reproducibilidad
SEMILLA = 42


def asegurar_directorios() -> None:
    """Crea los directorios de salida si no existen."""
    for directorio in (DIR_DATOS_SALIDA, DIR_MODELO, DIR_METRICAS, DIR_IMG, DIR_POWERBI):
        directorio.mkdir(parents=True, exist_ok=True)
