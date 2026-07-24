# Prueba Técnica — Análisis de Cuentas por Cobrar (CxC)

Solución a la prueba técnica para el cargo **Analista 2 – Evolución, Automatización y Mejora de Procesos**.

El proyecto analiza el comportamiento histórico de las Cuentas por Cobrar generadas en la operación
bancaria, construye una **sábana analítica** con SQL, entrena un **modelo de probabilidad de pago**
y entrega un **dashboard en Power BI** con un informe ejecutivo para usuarios de negocio.

## Estructura del repositorio

```
prueba-tecnica-cxc/
├── README.md
├── requirements.txt
├── .gitignore
├── data/
│   └── base_datos_historica.db      # Fuente SQLite original (21.739 CxC)
├── docs/
│   ├── documentacion.md             # Informe general
│   └── img/                         # Gráficas del EDA (01–10 PNG)
├── powerbi/
│   └── dashboard.pbix               # Dashboard Power BI (5 páginas)
└── src/
    ├── config.py                    # Rutas y constantes centralizadas
    ├── db_manager.py                # Clase GestorBaseDatos (conexión + catálogo de queries SQL)
    ├── constructor_sabana.py        # Clase ConstructorSabana (Actividad 1)
    ├── explorador_eda.py            # Clase ExploradorEDA (Actividad 1)
    ├── modelo_probabilidad.py       # Clase ModeloProbabilidadPago (Actividad 2)
    ├── main_actividad1.py           # Orquestador Actividad 1
    ├── main_actividad2.py           # Orquestador Actividad 2
    ├── main_actividad3.py           # Clase ExportadorPowerBI + orquestador Actividad 3
    ├── sql/
    │   └── queries.sql              # TODA la transformación de datos (9 queries nombradas)
    ├── data/                        # Sábana y datasets procesados (salidas generadas)
    ├── modelo/
    │   └── modelo.pkl               # Pipeline completo serializado (joblib)
    └── metricas/
        └── metricas_modelo.csv      # Métricas CV + test + matriz de confusión
```

## Requisitos

- Python 3.12+ (desarrollado con 3.12)
- Power BI Desktop (solo para abrir el dashboard)

## Instrucciones de ejecución

**1. Clonar el repositorio**

```bash
git clone <url-del-repositorio>
cd prueba-tecnica-cxc
```

**2. Crear y activar el entorno virtual**

```bash
python -m venv venv
# Windows
venv\Scripts\activate
# Mac/Linux
source venv/bin/activate
```

**3. Instalar dependencias**

```bash
pip install -r requirements.txt
```

**4. Ejecutar los scripts en orden**

```bash
python src/main_actividad1.py   # Sábana analítica + EDA
python src/main_actividad2.py   # Modelo de probabilidad de pago
python src/main_actividad3.py   # Datasets para Power BI
```

Cada script imprime su avance en consola y deja sus salidas en `src/data/`, `src/modelo/`,
`src/metricas/` y `docs/img/`.

**5. Dashboard**

Abrir `powerbi/dashboard.pbix` con Power BI Desktop.

## Metodología y documentación

Toda la documentación del proyecto está consolidada en un único informe:

- **[docs/documentacion.md](docs/documentacion.md)** — paso a paso del desarrollo, descripción de cada archivo de código, hallazgos del EDA, resultados del modelo, análisis visual de las gráficas, resultados del dashboard e informe ejecutivo con hipótesis, métricas, conclusiones y recomendaciones.

## Flujo de trabajo Git

Cada actividad se desarrolló en su propia rama (`actividad-1`, `actividad-2`, `actividad-3`)
con merge a `main` al finalizar, según lo requerido por la prueba.
