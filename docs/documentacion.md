# Informe General — Análisis y Modelo de Probabilidad de Pago de Cuentas por Cobrar (CxC)

**Cargo:** Analista 2 – Evolución, Automatización y Mejora de Procesos
**Fuente:** `data/base_datos_historica.db` (SQLite) · tabla `tabla1` · 21.739 CxC · cortes oct–nov 2025

Este documento es el informe unificado del proyecto. Describe el paso a paso de lo que se
hizo en cada actividad, qué encontramos en los datos, cómo interpretamos los resultados, qué
decisiones se tomaron y por qué, y qué muestra el dashboard de Power BI. Los archivos de
código fuente (`.py` y `.sql`) se encuentran en la carpeta `src/` del repositorio.

---

## Índice

1. [Contexto y objetivo](#1-contexto-y-objetivo)
2. [Entorno y arquitectura de la solución](#2-entorno-y-arquitectura-de-la-solución)
3. [Actividad 1 — Exploración y sábana analítica](#3-actividad-1--exploración-y-sábana-analítica)
4. [Actividad 2 — Modelo de probabilidad de pago](#4-actividad-2--modelo-de-probabilidad-de-pago)
5. [Actividad 3 — Dataset y dashboard Power BI](#5-actividad-3--dataset-y-dashboard-power-bi)
6. [Resultados visualizados en el dashboard](#6-resultados-visualizados-en-el-dashboard)
7. [Informe ejecutivo](#7-informe-ejecutivo)
8. [Supuestos, limitaciones y próximos pasos](#8-supuestos-limitaciones-y-próximos-pasos)
9. [Reproducción local](#9-reproducción-local)

---

## 1. Contexto y objetivo

La operación bancaria genera diariamente **cuentas por cobrar (CxC)** por cargos fiscales,
comisiones y cobros de servicio. Una fracción se recupera de inmediato; otra parcialmente,
de forma tardía o nunca. El área de negocio conoce el saldo total pendiente, pero no sabe
qué parte tiene posibilidades reales de recuperarse ni dónde concentrar los esfuerzos de
cobranza para maximizar el retorno.

El proyecto responde a esa necesidad con tres entregables:

1. **Sábana analítica:** una tabla enriquecida con una fila por CxC, variables derivadas y
   reglas de negocio construida directamente sobre los datos históricos originales.
2. **Modelo de probabilidad de pago:** estima para cada CxC la probabilidad de que sea
   pagada en su totalidad, y con ella el valor esperado a recuperar y el valor en riesgo
   del saldo pendiente.
3. **Dashboard Power BI de 5 páginas:** lleva los hallazgos y las predicciones del modelo a
   usuarios de negocio sin conocimiento técnico.

---

## 2. Entorno y arquitectura de la solución

### Entorno de ejecución

El proyecto corre sobre Python 3.12 con un único entorno virtual. Las dependencias están
congeladas en `requirements.txt` para garantizar que cualquier evaluador reproduzca
exactamente las mismas versiones (pandas, scikit-learn, matplotlib, seaborn, joblib).
Todas las operaciones aleatorias del proyecto usan una semilla global (`SEMILLA = 42`),
lo que hace que los resultados sean 100 % reproducibles entre ejecuciones.

### Control de versiones

Cada actividad se desarrolló en su propia rama de trabajo (`actividad-1`, `actividad-2`,
`actividad-3`) con *merge* a `main` al cierre de cada una. El repositorio solo incluye
código fuente, los datos originales y los entregables finales; las carpetas generadas
en ejecución (`venv/`, `__pycache__/`, outputs intermedios) están excluidas del control de
versiones.

### Decisión central de arquitectura

Desde el inicio se tomó la decisión de que **toda la lógica de transformación de datos
vive en SQL** y Python solo orquesta: conecta, ejecuta las consultas, valida los resultados
y exporta los archivos. Esta separación es deliberada por dos razones:

- El SQL es auditable y portable: cualquier analista puede leerlo y ejecutarlo en otro motor
  de base de datos (PostgreSQL, BigQuery, Redshift) sin reescribir nada.
- El código Python queda limpio de lógica de datos y puede ser reutilizado o testeado de
  forma independiente.

### Archivos del proyecto

| Archivo | Qué hace |
|---|---|
| `src/sql/queries.sql` | Las 9 consultas SQL nombradas: toda la lógica de negocio |
| `src/config.py` | Rutas y constantes centralizadas (una sola fuente de verdad) |
| `src/db_manager.py` | Clase `GestorBaseDatos`: conexión a SQLite + catálogo de queries |
| `src/constructor_sabana.py` | Clase `ConstructorSabana`: construye, valida y exporta la sábana |
| `src/explorador_eda.py` | Clase `ExploradorEDA`: 7 gráficas del análisis exploratorio |
| `src/modelo_probabilidad.py` | Clase `ModeloProbabilidadPago`: entrena, evalúa y aplica el modelo |
| `src/main_actividad1.py` | Orquestador de la Actividad 1 (punto de entrada) |
| `src/main_actividad2.py` | Orquestador de la Actividad 2 |
| `src/main_actividad3.py` | Clase `ExportadorPowerBI` + orquestador de la Actividad 3 |

---

## 3. Actividad 1 — Exploración y sábana analítica

### Qué se hizo

La Actividad 1 tiene tres propósitos: verificar que los datos son confiables, entender la
estructura del portafolio y construir una tabla analítica enriquecida ("sábana") que sirva
de base para el modelo y el dashboard.

**`config.py`** centraliza en un único lugar todas las rutas del proyecto resueltas de forma
relativa desde la raíz. Ningún otro módulo tiene rutas quemadas como texto literal. Si el
proyecto se mueve a otra máquina o directorio, solo este archivo necesita atención.

**`db_manager.py` — clase `GestorBaseDatos`** es el único punto de acceso a la base de datos.
Gestiona la conexión a SQLite de forma automática (la abre al entrar y la cierra
garantizadamente al salir, incluso si ocurre un error). También parsea el archivo
`queries.sql` al iniciarse, construye un catálogo de consultas por nombre y permite
ejecutarlas con una sola línea. Si se pide una consulta que no existe, el error incluye la
lista de nombres válidos para facilitar la depuración.

**`queries.sql`** contiene las 9 consultas del proyecto marcadas con un identificador
(`-- name: nombre`). Se ejecutan tres de verificación inicial antes de construir la sábana:

- *Perfil general* — recuento global del portafolio: totales, clientes, tipos de transacción
  y productos.
- *Calidad de datos* — auditoría de nulos, valores negativos, inconsistencias contables
  y anomalías de fechas.
- *Particiones* — distribución de registros por fecha de corte.

Luego se ejecuta la consulta principal `sabana_cxc`, que produce la tabla analítica completa
en tres capas: primero se convierten las fechas del formato entero original (`YYYYMMDD`) al
formato ISO estándar; luego se derivan las variables de negocio fila a fila (estado de pago,
tasa de recuperación, días hasta el pago, antigüedad, rangos de monto y variables de
calendario); finalmente se agregan buckets operativos de cartera y métricas de comportamiento
del cliente calculadas con funciones de ventana sobre todas las CxC del mismo cliente.

Finalmente se ejecutan 5 consultas agregadas que calculan los mismos KPIs de recuperación
agrupados por tipo de transacción, producto, rango de monto, período y estado de pago.

**`constructor_sabana.py` — clase `ConstructorSabana`** recibe el resultado de la consulta
SQL, aplica cuatro validaciones de integridad antes de exportar (unicidad del identificador,
tasa de recuperación en rango válido, estados de pago dentro de los valores esperados y
antigüedad no negativa) y exporta la sábana en dos formatos: CSV con codificación UTF-8 BOM
para compatibilidad con Excel y Power BI, y SQLite para que la Actividad 2 pueda seguir
transformando en SQL directamente.

**`explorador_eda.py` — clase `ExploradorEDA`** produce 7 gráficas del análisis exploratorio
guardadas en `docs/img/`. La clase trabaja en modo de solo exportación (sin abrir ventanas)
para que el script sea compatible con entornos de servidor o ejecución automatizada.

**`main_actividad1.py`** encadena todo el flujo anterior en 5 pasos con impresión auditable
en consola y es el único punto de entrada de la Actividad 1.

### Qué encontramos en los datos

**La fuente es limpia.** La auditoría de calidad no encontró nulos en los campos de valor,
ni valores negativos, ni inconsistencias entre el valor original y la suma de pagado más
pendiente. Esto da confianza en los datos para el análisis.

**Una anomalía:** 1.747 registros tienen un valor de fecha de último pago registrado aunque
no tienen ningún pago asociado (`vlr_pagado = 0`). Se determinó que esa fecha no representa
un pago real sino un *placeholder* del sistema de extracción y se trató como ausente para
todos los análisis. Esta decisión quedó documentada como supuesto S2.

**La fuente es un portafolio en corte diario.** Los 21.739 registros no son una sola foto
sino 32 fotos diarias (del 11 de octubre al 11 de noviembre de 2025), cada una con
aproximadamente 680 CxC. Cada registro corresponde a la foto del día de su partición.

**Composición del portafolio:**

| Estado | CxC | % | Valor original | Saldo pendiente |
|---|---|---|---|---|
| PAGADO | 17.333 | 79,7 % | $119,5 MM | $0 |
| PARCIAL | 2.680 | 12,3 % | $13,0 MM | $8,1 MM |
| PENDIENTE | 1.726 | 8,0 % | $9,2 MM | $9,2 MM |
| **Total** | **21.739** | **100 %** | **$141,6 MM** | **$22,2 MM** |

La recuperación global es 84,3 % del valor original, pero el saldo pendiente de $22,2 MM
no está distribuido uniformemente — está muy concentrado en ciertos tipos de transacción
y ciertos perfiles de cliente.

### Hallazgos del análisis exploratorio (H1–H7)

| # | Hallazgo | Implicación |
|---|---|---|
| **H1** | El **tipo de transacción** es el factor más discriminante del pago: entre los tipos con más de 100 CxC, el porcentaje de pagadas va del 36,7 % al 98,1 % | No todas las CxC son iguales: el tipo determina estructuralmente el riesgo |
| **H2** | Los **montos muy altos (>$20K)** se recuperan peor: 69 % pagadas vs ~80 % del resto | El riesgo unitario por CxC crece con el monto; requiere gestión diferenciada |
| **H3** | El **comportamiento del cliente es "todo o nada"**: el 59,8 % de las 800 cuentas paga todas sus CxC y el 18,4 % casi ninguna; solo el 21,5 % es mixto | Conocer el historial del cliente casi predice el resultado de cada CxC individual |
| **H4** | El **recaudo es lento**: mediana de 98 días y media de 114 días entre creación del cobro y pago | Hay margen para acelerar el proceso con gestión oportuna temprana |
| **H5** | **No hay estacionalidad**: el mes ni el día de semana de creación no afectan el pago | No tiene sentido organizar la cobranza por calendario |
| **H6** | **La cartera es madura**: todas las CxC tienen al menos 90 días de antigüedad a la fecha de corte | El desenlace observado es confiable; hay poca censura temporal |
| **H7** | Las **CxC parciales** ya recuperaron en promedio el 64 % de su valor ($4,8 MM pagados sobre $13 MM originales), con $8,1 MM de saldo aún pendiente | Las parciales tienen historial de pago; no son equivalentes a las totalmente pendientes |

Estos hallazgos guiaron directamente las decisiones de modelado: usar el historial del
cliente como predictor principal (H3), aplicar transformación logarítmica al valor original
(H2), no incluir el calendario como predictor relevante (H5) y confiar en que el desenlace
observado es representativo del comportamiento real (H6).

### Lo que muestran las gráficas del EDA

**`01_estados_pago.png` — Distribución del portafolio por estado de pago**
La comparación entre los dos paneles revela algo importante: en conteo el grupo PENDIENTE
(1.747 CxC, 8 %) parece pequeño, pero en valor representa $14,1 MM de los $141,6 MM del
portafolio. Las CxC PARCIALES, en cambio, son más numerosas (2.669) pero su valor original
($21,5 MM) ya está en gran parte recuperado. La vista de valor cambia la lectura del riesgo.

**`02_distribucion_montos.png` — Distribución de montos en escala logarítmica**
En escala logarítmica la distribución muestra una forma aproximadamente simétrica con centro
alrededor de $1.000–$3.000, lo que confirma que la mayoría de las CxC son de monto moderado.
Sin embargo, se observa una cola derecha real: hay decenas de CxC por encima de $50.000 y
algunos casos aislados cerca de $100.000. Esta asimetría en escala natural (donde esos valores
extremos dominarían cualquier promedio) justificó aplicar transformación logarítmica al monto
antes de entrenarlo en el modelo.

**`03_recuperacion_por_monto.png` — Recuperación por rango de monto**
El gráfico muestra dos barras por segmento: % de CxC pagadas (verde) y % del valor recuperado
(azul). En todos los segmentos la barra azul supera a la verde, lo que significa que el valor
se recupera en mayor proporción que las cuentas completas — porque los pagos parciales también
suman al valor cobrado. Lo más relevante ocurre en el segmento MUY ALTO (>$20K): la brecha
entre azul y verde se estrecha, indicando que en montos grandes no solo bajan las cuentas
pagadas en su totalidad, sino que incluso la recuperación de valor es menor que en el resto.

**`04_evolucion_mensual.png` — Creación mensual y recuperación por cohorte**
Los primeros y últimos meses visibles (oct-2024 y ago-2025) muestran barras más bajas porque
son meses incompletos dentro de la ventana de extracción — no indican una caída real en la
originación. Entre nov-2024 y jun-2025 la originación es completamente estable (~2.200–2.500
CxC por mes). La línea de recuperación (rojo) oscila entre 80 % y 85 % sin ninguna tendencia
ni quiebre — no hay un mes donde la cartera haya empeorado. Esto descarta explicaciones
estacionales o de deterioro reciente.

**`05_top_transacciones_pendiente.png` — Dónde está concentrado el riesgo**
CARGO FISCAL TRANSACCIONAL encabeza el ranking con $5,3 MM de saldo pendiente y un 78 % de
pago — el mayor problema en términos absolutos por su volumen. Sin embargo, el caso más
llamativo es **TRANSFERENCIA CANAL FISICO**: aunque su saldo no es el más grande, tiene solo
el **37 % de pago** — el peor de los 71 tipos con datos suficientes. COMISION CONSULTA SALDO
(68 %) y COMISION TRANSFERENCIA EXTERNA B (69 %) también muestran tasas estructuralmente
bajas. En contraste, PAGO SERVICIO ELECTRONICO tiene 92 % de pago pero aun así aparece en
el top 10 de saldo pendiente, simplemente por su volumen de CxC. Estos patrones sugieren
causas de proceso distintas según el tipo.

**`06_dias_hasta_pago.png` — Velocidad de pago**
La distribución de días hasta el pago no tiene la forma esperada de "la mayoría paga rápido".
En cambio, las frecuencias son relativamente uniformes desde el día 0 hasta el día 98
(mediana, marcada con línea roja), lo que indica que los pagos llegan de forma dispersa
durante los primeros 3 meses. A partir de ahí la distribución cae de forma gradual pero hay
una cola larga que llega hasta los 350 días. Esto implica que esperar no convierte a los
morosos en pagadores: quien no ha pagado a los 100 días tiene cada vez menos probabilidad
de hacerlo, y la distribución plana al inicio sugiere que no hay un "momento natural" de pago
que la gestión pueda anticipar.

**`07_pago_por_antiguedad.png` — El efecto de la antigüedad**
El gráfico muestra únicamente tres rangos (61–90 días, 91–180 días y >180 días), lo que
confirma que no hay ninguna CxC con menos de 61 días de antigüedad en el portafolio — toda
la cartera es madura. Lo más significativo es que los tres rangos tienen tasas casi idénticas
(81,7 %, 79,5 % y 79,7 %): esperar más tiempo no mejora ni empeora la recuperación. Las CxC
que no se pagaron a los 61 días tienen exactamente la misma probabilidad de pagarse que las
que llevan más de 180 días. Esto implica que el tiempo ya no es un factor de recuperación
en esta cartera — la decisión de pago ya fue tomada.

### Salidas generadas

- `src/data/sabana_cxc.csv` y `sabana_cxc.db` — sábana completa (21.739 × 29 columnas)
- `src/data/metricas_por_transaccion.csv`, `_producto.csv`, `_rango_monto.csv`, `_periodo.csv`, `distribucion_estados.csv`
- `docs/img/01_estados_pago.png` a `07_pago_por_antiguedad.png` — gráficas del EDA

---

## 4. Actividad 2 — Modelo de probabilidad de pago

### Qué se hizo

La Actividad 2 toma la sábana generada en la Actividad 1 y construye un modelo que estime
la probabilidad de pago total de cada CxC. Esta probabilidad se usa luego para calcular
cuánto del saldo pendiente se espera recuperar y cuánto está en riesgo.

**Definición del objetivo:** se eligió como variable a predecir si la CxC fue pagada en su
totalidad (saldo final = 0). Esta definición es precisa y operativamente relevante: es el
evento que libera la CxC de la gestión activa. Una alternativa como "algún pago" sería ambigua
porque mezclaría cuentas casi cerradas con abonos del 10 %.

**Control de fuga de información:** antes de construir el modelo se identificaron y
descartaron todas las variables que contienen información del desenlace, es decir, que no
estarían disponibles en el momento de evaluar una CxC nueva. Se excluyeron el valor pagado,
el saldo pendiente, la tasa de recuperación, el estado de pago y la fecha del último pago.
Incluir cualquiera de estas variables sería hacer trampa: el modelo vería el resultado antes
de predecirlo.

**Historial del cliente en modo leave-one-out:** el hallazgo H3 indicaba que el comportamiento
del cliente es el predictor más fuerte. Sin embargo, si se calculara el promedio de pago
del cliente incluyendo la CxC que se está evaluando, esa CxC estaría usando su propio
resultado para predecirse a sí misma. Para evitarlo, se calculó el historial del cliente
excluyendo siempre la CxC evaluada — usando solo las demás CxC del mismo cliente. Este
cálculo se realizó directamente en SQL con funciones de ventana. Se incluyeron dos métricas:
el porcentaje de las otras CxC del cliente que fueron totalmente pagadas y la tasa de
recuperación promedio de esas otras CxC.

**`modelo_probabilidad.py` — clase `ModeloProbabilidadPago`** encapsula todo el ciclo de
modelado:

- *Preparación de datos:* el valor original se transforma a escala logarítmica porque su
  distribución tiene una cola muy larga (mínimo ~$50, máximo ~$447.000); sin esta
  transformación los modelos lineales quedan dominados por los valores extremos. El mes y
  el día de semana se convierten a categorías para que el modelo no interprete "julio > enero".

- *Preprocesamiento diferenciado por tipo de variable:* las variables numéricas se estandarizan;
  las categóricas de baja cardinalidad (producto, rango de monto, mes, día) se codifican con
  one-hot; y el tipo de transacción — que tiene 71 categorías únicas — se codifica con
  target encoding con validación cruzada interna. Se eligió target encoding para este campo
  porque el one-hot generaría 71 columnas y muchas categorías tienen muy pocas CxC,
  lo que produciría sobreajuste en las categorías pequeñas. El target encoder reemplaza
  cada categoría por su tasa de pago histórica suavizada.

- *Comparación de tres metodologías:* se compararon regresión logística (modelo base
  interpretable), random forest y gradient boosting, usando validación cruzada de 5 folds
  con AUC-ROC como métrica. La partición de entrenamiento/prueba fue 80/20 estratificada
  para mantener la proporción de clases en ambos conjuntos.

- *Evaluación en conjunto de prueba independiente:* el modelo ganador se evaluó sobre el 20 %
  de datos nunca vistos durante el entrenamiento. Se calcularon AUC-ROC, precisión, recall,
  F1, exactitud y la puntuación de Brier (esta última mide qué tan calibradas están las
  probabilidades, es decir, si cuando el modelo dice "80 % de probabilidad" ese porcentaje
  corresponde a la realidad).

- *Scoring del portafolio completo:* el modelo ganador se aplicó a las 21.739 CxC para
  asignar una probabilidad de pago individual a cada una, y a partir de esa probabilidad
  se calculó el valor esperado a recuperar (`prob × saldo pendiente`) y el valor en riesgo
  (`(1 − prob) × saldo pendiente`).

**`main_actividad2.py`** encadena los 5 pasos del modelado con impresión auditable en
consola.

### Resultados del modelo

**Comparación de metodologías (validación cruzada 5-fold):**

| Modelo | AUC-ROC promedio | Desviación |
|---|---|---|
| Gradient Boosting | **0,9911** | ±0,0020 |
| Random Forest | 0,9886 | ±0,0019 |
| Regresión Logística | 0,9805 | ±0,0030 |

Se seleccionó **Gradient Boosting** por el mejor AUC consistente entre los 5 folds, su
manejo nativo de no linealidades (el efecto del monto es de cola, no lineal) y las
probabilidades mejor calibradas. Tres modelos muy cercanos en AUC indica que la señal en
los datos es fuerte y robusta.

**Evaluación sobre el conjunto de prueba (20 % nunca visto):**

| Métrica | Valor | Interpretación |
|---|---|---|
| AUC-ROC | **0,9926** | Ordena casi perfectamente pagadoras vs no pagadoras |
| Precisión | **98,7 %** | De 100 CxC marcadas como "va a pagar", ~99 realmente pagan |
| Recall | **100,0 %** | Ninguna CxC pagadora queda sin identificar |
| F1 | 0,9935 | Equilibrio entre precisión y recall |
| Exactitud | 0,9897 | El 98,9 % de las clasificaciones son correctas |
| Brier | **0,0085** | Probabilidades muy bien calibradas (0 = perfecto, 1 = peor posible) |
| Matriz: VN/FP/FN/VP | 838 / 45 / 0 / 3.465 | Cero falsos negativos: ninguna pagadora se clasifica como riesgo |

**¿Es creíble un AUC de 0,99?** Sí, y se verificó antes de aceptarlo:

1. Se revisaron uno a uno los predictores incluidos — ninguno contiene información del
   desenlace (el valor pagado, el saldo o el estado de pago están excluidos).
2. La explicación es estructural: el portafolio es extremadamente bimodal por cliente.
   Cuando se conoce que un cliente pagó el 95 % de sus CxC anteriores, es casi seguro que
   también pagará la actual. El historial LOO captura exactamente esa señal.
3. **Prueba de sensibilidad:** se entrenó el mismo modelo *sin* incluir las variables de
   historial del cliente. El AUC bajó de 0,99 a **0,916**. Esto confirma dos cosas: el
   modelo sin esas variables ya es fuerte (la información de tipo de transacción y monto
   es poderosa), y el historial del cliente es el que produce el salto adicional. Si hubiera
   fuga de datos, el modelo *sin* las variables sospechosas no funcionaría; aquí sigue
   siendo muy bueno.

**Estimación económica sobre el saldo pendiente ($22,2 MM):**

| Concepto | Valor | % del saldo |
|---|---|---|
| Valor esperado a recuperar | $179.854 | 0,8 % |
| Valor en riesgo | $22.010.146 | 99,2 % |

Esta cifra es conservadora: solo cuenta el pago total de las CxC con saldo, no proyecta
recuperaciones parciales adicionales. Sin embargo, el mensaje es claro: la cartera pendiente
está en manos de clientes con historial sistemático de no pago.

### Lo que muestran las gráficas del modelo

**`08_curva_roc.png` — Curva ROC del modelo**
La curva sube casi verticalmente desde el origen hasta el punto (0, 1) antes de moverse hacia
la derecha. Visualmente, la curva prácticamente pega al borde superior izquierdo del gráfico,
sin dejar espacio entre ella y la esquina — la forma característica de un modelo con AUC muy
alto (0,99). La diagonal punteada representa el rendimiento de un modelo aleatorio; la
distancia entre esa diagonal y la curva del modelo ilustra la ganancia real de usar el modelo
frente a no usarlo.

**`09_matriz_confusion.png` — Errores del modelo**
El resultado más llamativo es el cero en la celda de falsos negativos (fila "Paga", columna
"No paga"): el modelo no cometió ni un solo error del tipo "predecir que no paga cuando
realmente sí paga". En términos operativos esto significa que ninguna CxC pagadora quedaría
fuera de la gestión de cobro por un error del modelo. Los 45 falsos positivos (no pagadoras
clasificadas como pagadoras) representan una pérdida menor: solo se les daría un trato de
"bajo riesgo" a clientes que en realidad no van a pagar, lo que equivale a destinar un
esfuerzo mínimo en el lugar equivocado.

**`10_distribucion_probabilidades.png` — Separación entre clases**
Esta gráfica es la evidencia visual más contundente de la calidad del modelo. Las CxC que
realmente no pagan (rojo) tienen probabilidades estimadas concentradas casi exclusivamente
cerca de cero — la densidad cae a prácticamente cero antes de llegar a 0,1. Las CxC que
realmente pagan (verde) tienen probabilidades concentradas casi exclusivamente cerca de uno,
con un pico muy agudo en 0,95–1,0. Las dos distribuciones no se solapan en ningún punto del
eje. Esta separación perfecta es la imagen directa de por qué el recall es 100 % (cero
falsos negativos) y por qué las probabilidades son confiables para calcular valor esperado y
valor en riesgo sin necesidad de ajuste adicional.

### Salidas generadas

- `src/data/predicciones_cxc.csv` — probabilidad de pago, valor esperado y valor en riesgo para las 21.739 CxC
- `src/modelo/modelo.pkl` — pipeline completo serializado y listo para producción
- `src/metricas/metricas_modelo.csv` — tabla comparativa de todos los modelos + métricas de test
- `docs/img/08_curva_roc.png`, `09_matriz_confusion.png`, `10_distribucion_probabilidades.png`

---

## 5. Actividad 3 — Dataset y dashboard Power BI

### Qué se hizo

**`main_actividad3.py` — clase `ExportadorPowerBI`** une los resultados del modelo con la
sábana analítica y genera el CSV final que alimenta el dashboard. Primero carga las
predicciones del modelo como una tabla dentro de la misma base SQLite de la sábana; luego
ejecuta un join SQL que combina las 29 columnas de la sábana con la probabilidad de pago,
el valor esperado, el valor en riesgo y una nueva columna que clasifica cada CxC en una
banda de probabilidad (Muy Baja, Baja, Media, Alta, Muy Alta). Finalmente valida que
ninguna CxC haya quedado sin probabilidad asignada antes de exportar el archivo.

**Resultado:** `src/data/dataset_powerbi.csv` — 21.739 filas × 33 columnas, único insumo
del dashboard.

**Distribución por banda de probabilidad (solo CxC con saldo pendiente):**

| Banda | CxC con saldo | Saldo pendiente |
|---|---|---|
| MUY BAJA (<20 %) | 4.072 | $21,9 MM (98,7 %) |
| BAJA (20–40 %) | 115 | $126 K |
| MEDIA (40–60 %) | 102 | $83 K |
| ALTA (60–80 %) | 64 | $59 K |
| MUY ALTA (>80 %) | 63 | $53 K |

El 92 % de las CxC con saldo está en la banda MUY BAJA, lo que explica que el valor en
riesgo sea el 99,2 % del saldo total.

### Construcción del dashboard

**Problema del separador decimal.** El equipo usa configuración regional en español (la coma
es el separador decimal), pero el CSV exportado usa punto. Sin corrección, Power BI leía
valores como `27.0` como `270` y transformaba el campo `periodo_creacion` ("2025-03") en
una fecha incorrecta. Se resolvió forzando la cultura inglesa (`en-US`) en el paso de
tipado de Power Query, especificado columna por columna.

**Identificadores como texto.** Los campos `id_cxc`, `num_cta`, `cod_trn` y `cod_apli_prod`
se importaron como Texto aunque contienen números. Son códigos, no cantidades: si se dejan
como numéricos, Power BI los agrega por defecto (suma de id_cxc), los muestra con notación
científica o abrevia números de cuenta largos. Como texto, se comportan correctamente como
etiquetas.

**Tabla Calendario.** Se creó con DAX para poder analizar tendencias temporales continuas.
Cubre desde la fecha de creación más antigua hasta la fecha de corte más reciente del
portafolio y se relacionó con la tabla principal por la fecha de creación de la CxC.

**14 medidas DAX** agrupadas en una tabla `_Medidas` separada de los datos. Se optó por
centralizar las medidas en su propia tabla para que no aparezcan mezcladas con las columnas
de datos en el panel de campos. Las medidas cubren: conteos, sumas de valor (original,
pagado, pendiente), porcentajes de recuperación, promedios operativos (ticket, días de pago)
y los indicadores del modelo (valor esperado, valor en riesgo, probabilidad ponderada por
saldo).

**Página Menú como página de aterrizaje.** Se configuró la página Menú para que sea la
primera pantalla al abrir el informe. Contiene un navegador de páginas automático que
genera un botón por cada página visible y se actualiza solo si se agrega o elimina una
página en el futuro.

---

## 6. Resultados visualizados en el dashboard

### Menú

Portada del informe con título y navegación por botones a las 4 páginas de análisis.
Es la primera pantalla que ve cualquier usuario al abrir el archivo `.pbix`.

---

### Página 1 — Resumen del Portafolio

Visión general del estado del portafolio completo.

**Indicadores globales del portafolio:**

| Indicador | Valor |
|---|---|
| Total de CxC | 21.739 |
| Valor original total | $141,6 MM |
| Valor recuperado | $119,4 MM |
| % de recuperación | **84,3 %** |
| Saldo pendiente | **$22,2 MM** |
| % CxC completamente pagadas | **79,7 %** |

**Distribución por estado de pago:** el anillo muestra que casi 8 de cada 10 CxC están
completamente pagadas; el 12,3 % tiene pagos parciales y el 8 % no tiene ningún pago.
En términos de valor, las PAGADAS concentran el 84 % del valor original del portafolio.

**Recuperación por rango de monto:** el segmento de montos muy altos (>$20K) muestra una
tasa de pago notablemente inferior (~69 %) comparado con los demás segmentos (~78–81 %).
Esto confirma el hallazgo H2 del EDA: las CxC de mayor valor unitario presentan mayor
riesgo de no recuperación.

---

### Página 2 — Comportamiento por Transacción y Producto

Desagregación del comportamiento de pago por las dimensiones operativas del negocio.

**Top 10 tipos de transacción por saldo pendiente:** los tres tipos con mayor valor por
recuperar son CARGO FISCAL TRANSACCIONAL, COBRO SERVICIO TRANSPORTE y COMISION TRANSFERENCIA
EXTERNA B. Estos tipos concentran la mayor parte del riesgo operativo y deben ser la
primera prioridad de gestión de cobranza.

**Comportamiento por producto y rango de monto:** las cuentas CORRIENTE muestran mejor
desempeño de pago que las de AHORRO en todos los rangos de monto. El efecto del monto es
consistente dentro de ambos productos: a mayor monto, menor porcentaje de pago.

**Indicadores operativos clave:**

| Indicador | Valor | Qué significa |
|---|---|---|
| Ticket Promedio | $6.510 | Valor unitario medio de cada CxC |
| Días Promedio de Pago | 114 días | Tiempo medio entre creación y pago |

El plazo medio de 114 días indica que el proceso de cobro es lento. En términos de gestión,
hay una ventana de oportunidad en los primeros 30–60 días para intervenir antes de que la
CxC madure en su estado de no pago.

---

### Página 3 — Modelo y Riesgo

Resultados del modelo de probabilidad de pago aplicados a la cartera vigente.

**Indicadores económicos del saldo pendiente ($22,2 MM):**

| Indicador | Valor |
|---|---|
| Valor Esperado a Recuperar | **$179.854 (0,8 %)** |
| Valor en Riesgo | **$22.010.146 (99,2 %)** |
| % Saldo en Riesgo | **99,2 %** |
| Probabilidad de Pago Ponderada | **0,8 %** |

La probabilidad ponderada de 0,8 % significa que, en promedio, las CxC con saldo pendiente
tienen una probabilidad muy baja de pagarse. Este no es el promedio simple de probabilidades
sino el promedio ponderado por el saldo de cada CxC, de modo que las cuentas con mayor deuda
pesan más en el cálculo.

**Distribución de CxC con saldo por banda de probabilidad:** la gran mayoría (4.072 de 4.416
CxC con saldo) cae en la banda MUY BAJA, lo que concentra casi todo el riesgo económico.
Las bandas ALTA y MUY ALTA suman solo 127 CxC pero representan ~$112.000 de saldo con alta
probabilidad de recuperarse con gestión mínima.

**Composición esperado vs riesgo por banda:** en la banda MUY BAJA, la casi totalidad del
saldo es valor en riesgo con una fracción mínima de valor esperado. En las bandas ALTA y
MUY ALTA la proporción se invierte — son las candidatas naturales a gestión prioritaria de
bajo costo.

**Lectura operativa:** priorizar la cobranza por valor en riesgo (no por antigüedad) concentra
el esfuerzo donde el impacto económico es mayor. Las CxC más antiguas no son necesariamente
las de mayor riesgo; las de mayor saldo y menor probabilidad de pago sí lo son.

---

### Página 4 — Tendencias Temporales

Análisis del comportamiento del portafolio a lo largo del tiempo.

**Originación mensual:** durante los 10 meses del período se crearon aproximadamente
2.300 CxC por mes de forma estable. No hay picos ni caídas que sugieran cambios en la
operación o en los criterios de registro.

**Recuperación por cohorte:** el porcentaje de valor recuperado por mes de creación oscila
entre el 79 % y el 86 %, sin tendencia clara hacia arriba ni hacia abajo. Esto confirma el
hallazgo H5: no hay estacionalidad y no hay "meses malos" sistemáticos.

**Saldo pendiente por cohorte:** cada mes de originación aporta aproximadamente $2 MM de
saldo vigente al portafolio. La distribución es homogénea entre cohortes — no hay una
cosecha reciente que explique el saldo acumulado. El saldo pendiente de $22,2 MM es
estructural: proviene de un patrón sostenido de no pago a lo largo de todos los períodos,
no de un deterioro puntual reciente.

---

## 7. Informe ejecutivo

### El problema

El área conoce el saldo total pendiente del portafolio de CxC, pero no tiene visibilidad
sobre qué parte tiene posibilidades reales de recuperarse ni cómo priorizar la gestión
de cobranza para maximizar el retorno económico.

### La solución implementada

Se desarrolló un pipeline analítico de extremo a extremo: auditoría de calidad de datos,
construcción de sábana analítica en SQL, modelo de probabilidad de pago (gradient boosting
seleccionado por validación cruzada frente a random forest y regresión logística), estimación
económica individual y dashboard de 5 páginas para usuarios de negocio.

### Hipótesis planteadas y veredicto

| Hipótesis | Veredicto |
|---|---|
| H1. El tipo de transacción determina el comportamiento de pago | **Confirmada** — es el predictor estructural más fuerte |
| H2. Los montos muy grandes se recuperan peor | **Confirmada** — el segmento >$20K paga un 10–15 % menos que el resto |
| H3. El historial de pago del cliente anticipa el resultado de cada CxC | **Confirmada** — eleva el AUC del modelo del 0,92 al 0,99 |
| H4. El mes o día de semana de creación influye en el pago | **Descartada** — peso prácticamente nulo en el modelo |

### La fotografía del portafolio hoy

El portafolio muestra una recuperación saludable a nivel global (84,3 %) pero con un
núcleo problemático de $22,2 MM en manos de clientes con patrón histórico de no pago.
El modelo asigna a ese saldo una probabilidad ponderada de recuperación del 0,8 %,
lo que implica que **sin una intervención diferenciada, $22 MM permanecerán como saldo
incobrable**.

La estimación de $180 K de valor esperado es el piso: no incluye recuperaciones parciales
(que históricamente aportan ~64 % del valor de las CxC parciales) ni el efecto de las
acciones de cobranza que aún no han ocurrido.

### Recomendaciones operativas

1. **Priorizar por valor en riesgo, no por antigüedad.** La variable `valor_en_riesgo`
   combina el saldo pendiente con la probabilidad de no pago y ordena las CxC por impacto
   económico real.

2. **Gestión diferenciada por banda de probabilidad:**
   - Bandas ALTA y MUY ALTA (~$112 K en 127 CxC): recordatorio automático de bajo costo
     — estas cuentas tienen alta probabilidad de pago espontáneo.
   - Banda MUY BAJA (~$22 MM en 4.072 CxC): estrategia activa — acuerdos de pago,
     débito programado, evaluación de castigo contable para cuentas sin expectativa real
     de recuperación.

3. **Intervenir los tipos de transacción de alto riesgo.** Los tipos con bajo porcentaje
   de pago y alto saldo pendiente (cargos fiscales transaccionales, cobros de transporte,
   comisiones de transferencia externa) sugieren un problema de proceso, no solo de cliente.
   Revisar el flujo de cobro de esos tipos específicos.

4. **Regla temprana por cliente.** Dado el comportamiento "todo o nada" del cliente (H3),
   la primera CxC impaga de una cuenta es la señal más temprana de riesgo. Activar la
   gestión del cliente completo desde el primer incumplimiento.

5. **Controles diferenciados para montos >$20K.** Validación de saldo antes de generar la
   CxC, cuotas parciales programadas o garantías adicionales para el segmento de mayor
   valor unitario.

6. **Monitoreo mensual.** Actualizar el dashboard con cada nueva foto del portafolio y
   recalificar las CxC con el modelo para detectar deterioros o mejoras a tiempo.

---

## 8. Supuestos, limitaciones y próximos pasos

### Supuestos aplicados

| Código | Supuesto | Argumento |
|---|---|---|
| S1 | El estado de pago se deriva de los campos de valor (PAGADO si saldo = 0; PARCIAL si hubo algún pago pero queda saldo; PENDIENTE si no hay ningún pago) | No existe un campo de estado en la fuente original; la regla es inequívoca y auditabe en SQL |
| S2 | Los registros con fecha de último pago registrada pero sin valor pagado se tratan como "sin fecha de pago" | La auditoría detectó 1.747 casos: la fecha es un placeholder del sistema de extracción, no un pago real |
| S3 | La fecha de corte de cada CxC es la fecha de su partición de extracción (`year/month/day`) | Es la única referencia temporal disponible para identificar a qué foto pertenece cada registro |
| S4 | Los rangos de monto usan umbrales fijos de negocio ($1K, $5K, $20K) en lugar de cuantiles estadísticos | Los umbrales fijos son estables en el tiempo, comunicables y comparables entre períodos; los cuantiles cambian con cada muestra |
| S5 | Toda transformación de datos se realiza en SQL; Python solo orquesta | Mayor auditabilidad y portabilidad a cualquier motor de base de datos |
| S6 | Moneda única y homogénea en todo el portafolio | La fuente no incluye campo de moneda ni tipo de cambio |
| S7 | El identificador de cada CxC es su posición interna en la tabla fuente (ROWID) | La fuente no tiene un campo explícito de id_cxc |

### Limitaciones

- **Censura temporal:** el desenlace de pago se observa a la fecha de corte, no al cierre
  definitivo de la CxC. Aunque la madurez mínima de 90 días mitiga este riesgo, algunas
  CxC clasificadas como pendientes podrían pagarse después del corte.
- **Solo pago total:** el modelo estima la probabilidad de pago completo; no proyecta
  recuperaciones parciales adicionales sobre las CxC en estado PARCIAL.
- **Sin variables de gestión:** no se dispone de información sobre llamadas de cobranza,
  acuerdos de pago previos ni historial de contacto con el cliente.
- **Historial de pagos simplificado:** `f_ultimo_pago` captura solo la fecha del último
  pago, no el flujo completo de abonos. Un cliente que hace múltiples pagos parciales no
  se distingue de uno que hizo un solo abono.

### Próximos pasos

1. **Modelo de tasa de recuperación para CxC parciales** — complementaría el modelo actual
   estimando qué porcentaje adicional se recuperará de las cuentas en estado PARCIAL, lo que
   refinaría el valor esperado total del portafolio.
2. **Incorporar variables de gestión y perfil del cliente** — el historial de llamadas,
   acuerdos previos y datos sociodemográficos mejorarían la precisión del modelo.
3. **Backtesting con la siguiente foto mensual** — comparar las predicciones actuales con
   el desenlace real del mes siguiente y recalibrar el modelo si el AUC baja significativamente.
4. **Industrialización del pipeline** — orquestación automática de los tres scripts al
   recibir una nueva foto del portafolio y publicación del dashboard en Power BI Service
   con actualización programada.

---

## 9. Reproducción local

```bash
# 1. Clonar el repositorio
git clone <url-del-repositorio>
cd prueba-tecnica-cxc

# 2. Crear y activar el entorno virtual
python -m venv venv
venv\Scripts\activate        # Windows
source venv/bin/activate     # Mac / Linux

# 3. Instalar dependencias
pip install -r requirements.txt

# 4. Ejecutar las tres actividades en orden
python src/main_actividad1.py   # sábana analítica + EDA
python src/main_actividad2.py   # modelo + scoring del portafolio
python src/main_actividad3.py   # dataset final para Power BI

# 5. Abrir el dashboard
# Abrir powerbi/dashboard.pbix con Power BI Desktop.
```

Con la semilla global `SEMILLA = 42`, todas las operaciones aleatorias (partición train/test,
validación cruzada, inicialización de modelos) producen exactamente los mismos resultados en
cada ejecución. Los archivos de salida generados por los scripts (sábana analítica, predicciones,
modelo serializado, métricas y gráficas) están incluidos en el repositorio como evidencia de
los resultados obtenidos; al ejecutar los scripts se regeneran con valores idénticos.
