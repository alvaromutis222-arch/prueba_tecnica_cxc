-- ============================================================================
-- queries.sql — Transformaciones SQL para la sábana analítica de CxC
-- Prueba Técnica | Analista 2 – Evolución, Automatización y Mejora de Procesos
--
-- Convención: cada query está delimitada por un marcador "-- name: <nombre>".
-- El orquestador Python (src/db_manager.py) parsea este archivo y ejecuta
-- cada query por su nombre. Toda la lógica de transformación vive aquí (SQL);
-- Python solo orquesta, exporta y documenta.
--
-- Supuestos aplicados (ver docs/documentacion.md):
--   S1. Una CxC está PAGADA si vlr_pendiente_pago = 0; PARCIAL si tiene pagos
--       pero saldo > 0; PENDIENTE si no registra ningún pago (vlr_pagado = 0).
--   S2. Para CxC sin pago (vlr_pagado = 0), f_ultimo_pago no representa un
--       pago real (placeholder de extracción) y se trata como NULL.
--   S3. La fecha de corte (foto) de cada registro es la partición year/month/day.
--   S4. Los rangos de monto se definen con umbrales de negocio fijos para que
--       sean estables y comunicables (no dependen de la muestra).
-- ============================================================================


-- name: perfil_general
-- Conteos globales y totales del portafolio (verificación inicial).
SELECT
    COUNT(*)                                            AS total_registros,
    COUNT(DISTINCT num_cta)                             AS clientes_unicos,
    COUNT(DISTINCT cod_trn)                             AS tipos_transaccion,
    COUNT(DISTINCT cod_apli_prod)                       AS productos,
    MIN(f_creacion)                                     AS f_creacion_min,
    MAX(f_creacion)                                     AS f_creacion_max,
    ROUND(SUM(vlr_original), 2)                         AS vlr_original_total,
    ROUND(SUM(vlr_pagado), 2)                           AS vlr_pagado_total,
    ROUND(SUM(vlr_pendiente_pago), 2)                   AS vlr_pendiente_total,
    ROUND(SUM(vlr_pagado) * 100.0 / SUM(vlr_original), 2) AS pct_recuperado_global
FROM tabla1;


-- name: calidad_datos
-- Validaciones de calidad: nulos, negativos, consistencia contable y fechas.
SELECT
    SUM(CASE WHEN vlr_original IS NULL OR vlr_pagado IS NULL
              OR vlr_pendiente_pago IS NULL THEN 1 ELSE 0 END)      AS nulos_en_valores,
    SUM(CASE WHEN vlr_original <= 0 THEN 1 ELSE 0 END)              AS vlr_original_no_positivo,
    SUM(CASE WHEN vlr_pagado < 0 OR vlr_pendiente_pago < 0
             THEN 1 ELSE 0 END)                                     AS valores_negativos,
    SUM(CASE WHEN ABS(vlr_original - vlr_pagado - vlr_pendiente_pago) > 0.01
             THEN 1 ELSE 0 END)                                     AS inconsistencia_contable,
    SUM(CASE WHEN vlr_pagado > 0 AND f_ultimo_pago < f_creacion
             THEN 1 ELSE 0 END)                                     AS pago_antes_de_creacion,
    SUM(CASE WHEN vlr_pagado = 0 AND f_ultimo_pago > 0
             THEN 1 ELSE 0 END)                                     AS fecha_pago_sin_pago
FROM tabla1;


-- name: particiones
-- Distribución de registros por partición de extracción (fecha de corte).
SELECT year, month, day, COUNT(*) AS registros
FROM tabla1
GROUP BY year, month, day
ORDER BY year, month, day;


-- name: sabana_cxc
-- ============================================================================
-- SÁBANA ANALÍTICA: una fila por CxC con variables originales, derivadas,
-- reglas de negocio y métricas de comportamiento del cliente.
-- ============================================================================
WITH base AS (
    SELECT
        ROWID                                            AS id_cxc,
        cod_apli_prod,
        descri_cod_apli_prod                             AS producto,
        num_cta,
        cod_trn,
        descri_cod_trn                                   AS tipo_transaccion,
        vlr_original,
        vlr_pagado,
        vlr_pendiente_pago,
        -- Conversión de fechas YYYYMMDD (entero) a formato ISO
        DATE(SUBSTR(PRINTF('%08d', f_creacion), 1, 4) || '-' ||
             SUBSTR(PRINTF('%08d', f_creacion), 5, 2) || '-' ||
             SUBSTR(PRINTF('%08d', f_creacion), 7, 2))   AS fecha_creacion,
        -- S2: la fecha de último pago solo es válida si existió un pago real
        CASE WHEN vlr_pagado > 0 THEN
            DATE(SUBSTR(PRINTF('%08d', f_ultimo_pago), 1, 4) || '-' ||
                 SUBSTR(PRINTF('%08d', f_ultimo_pago), 5, 2) || '-' ||
                 SUBSTR(PRINTF('%08d', f_ultimo_pago), 7, 2))
        END                                              AS fecha_ultimo_pago,
        -- S3: fecha de corte = partición de extracción
        DATE(PRINTF('%04d-%02d-%02d', year, month, day)) AS fecha_corte
    FROM tabla1
),
derivadas AS (
    SELECT
        *,
        -- Regla de negocio S1: estado de pago
        CASE
            WHEN vlr_pendiente_pago <= 0 THEN 'PAGADO'
            WHEN vlr_pagado > 0          THEN 'PARCIAL'
            ELSE 'PENDIENTE'
        END                                              AS estado_pago,
        CASE WHEN vlr_pendiente_pago <= 0 THEN 1 ELSE 0 END AS pagado_total,
        CASE WHEN vlr_pagado > 0 THEN 1 ELSE 0 END          AS con_algun_pago,
        -- Tasa de recuperación: proporción del valor original ya pagada
        ROUND(vlr_pagado * 1.0 / vlr_original, 4)        AS tasa_recuperacion,
        -- Días entre creación y último pago (solo si hubo pago real)
        CAST(JULIANDAY(fecha_ultimo_pago) - JULIANDAY(fecha_creacion) AS INTEGER)
                                                         AS dias_creacion_a_pago,
        -- Antigüedad de la CxC a la fecha de corte
        CAST(JULIANDAY(fecha_corte) - JULIANDAY(fecha_creacion) AS INTEGER)
                                                         AS antiguedad_dias,
        -- Variables de calendario
        STRFTIME('%Y-%m', fecha_creacion)                AS periodo_creacion,
        CAST(STRFTIME('%Y', fecha_creacion) AS INTEGER)  AS anio_creacion,
        CAST(STRFTIME('%m', fecha_creacion) AS INTEGER)  AS mes_creacion,
        CAST(STRFTIME('%w', fecha_creacion) AS INTEGER)  AS dia_semana_creacion,
        -- S4: rango de monto con umbrales de negocio fijos
        CASE
            WHEN vlr_original < 1000   THEN '1. BAJO (<1K)'
            WHEN vlr_original < 5000   THEN '2. MEDIO (1K-5K)'
            WHEN vlr_original < 20000  THEN '3. ALTO (5K-20K)'
            ELSE                            '4. MUY ALTO (>20K)'
        END                                              AS rango_monto
    FROM base
),
enriquecida AS (
    SELECT
        *,
        -- Rango de antigüedad (buckets operativos de cartera)
        CASE
            WHEN antiguedad_dias <= 30  THEN '1. 0-30 dias'
            WHEN antiguedad_dias <= 60  THEN '2. 31-60 dias'
            WHEN antiguedad_dias <= 90  THEN '3. 61-90 dias'
            WHEN antiguedad_dias <= 180 THEN '4. 91-180 dias'
            ELSE                             '5. >180 dias'
        END                                              AS rango_antiguedad,
        -- Velocidad de pago (buckets sobre días hasta el último pago)
        CASE
            WHEN dias_creacion_a_pago IS NULL THEN 'SIN PAGO'
            WHEN dias_creacion_a_pago <= 30   THEN '1. 0-30 dias'
            WHEN dias_creacion_a_pago <= 60   THEN '2. 31-60 dias'
            WHEN dias_creacion_a_pago <= 90   THEN '3. 61-90 dias'
            WHEN dias_creacion_a_pago <= 180  THEN '4. 91-180 dias'
            ELSE                                   '5. >180 dias'
        END                                              AS velocidad_pago,
        -- Métricas de comportamiento histórico del cliente (ventana por cuenta)
        COUNT(*)        OVER (PARTITION BY num_cta)      AS n_cxc_cliente,
        ROUND(SUM(vlr_original) OVER (PARTITION BY num_cta), 2)
                                                         AS vlr_total_cliente,
        ROUND(AVG(tasa_recuperacion) OVER (PARTITION BY num_cta), 4)
                                                         AS tasa_recuperacion_cliente,
        ROUND(AVG(pagado_total * 1.0) OVER (PARTITION BY num_cta), 4)
                                                         AS pct_pagadas_cliente
    FROM derivadas
)
SELECT * FROM enriquecida;


-- name: metricas_por_transaccion
-- Comportamiento de pago por tipo de transacción.
SELECT
    cod_trn,
    descri_cod_trn                                       AS tipo_transaccion,
    COUNT(*)                                             AS n_cxc,
    ROUND(SUM(vlr_original), 2)                          AS vlr_original,
    ROUND(SUM(vlr_pagado), 2)                            AS vlr_pagado,
    ROUND(SUM(vlr_pendiente_pago), 2)                    AS vlr_pendiente,
    ROUND(SUM(vlr_pagado) * 100.0 / SUM(vlr_original), 2)    AS pct_recuperacion_valor,
    ROUND(AVG(CASE WHEN vlr_pendiente_pago <= 0 THEN 1.0 ELSE 0 END) * 100, 2)
                                                         AS pct_cxc_pagadas,
    ROUND(AVG(vlr_original), 2)                          AS ticket_promedio,
    ROUND(AVG(CASE WHEN vlr_pagado > 0 THEN
        JULIANDAY(DATE(SUBSTR(PRINTF('%08d', f_ultimo_pago),1,4) || '-' ||
                       SUBSTR(PRINTF('%08d', f_ultimo_pago),5,2) || '-' ||
                       SUBSTR(PRINTF('%08d', f_ultimo_pago),7,2))) -
        JULIANDAY(DATE(SUBSTR(PRINTF('%08d', f_creacion),1,4) || '-' ||
                       SUBSTR(PRINTF('%08d', f_creacion),5,2) || '-' ||
                       SUBSTR(PRINTF('%08d', f_creacion),7,2))) END), 1)
                                                         AS dias_promedio_pago
FROM tabla1
GROUP BY cod_trn, descri_cod_trn
ORDER BY vlr_original DESC;


-- name: metricas_por_producto
-- Comportamiento de pago por producto bancario.
SELECT
    cod_apli_prod,
    descri_cod_apli_prod                                 AS producto,
    COUNT(*)                                             AS n_cxc,
    ROUND(SUM(vlr_original), 2)                          AS vlr_original,
    ROUND(SUM(vlr_pagado), 2)                            AS vlr_pagado,
    ROUND(SUM(vlr_pendiente_pago), 2)                    AS vlr_pendiente,
    ROUND(SUM(vlr_pagado) * 100.0 / SUM(vlr_original), 2)    AS pct_recuperacion_valor,
    ROUND(AVG(CASE WHEN vlr_pendiente_pago <= 0 THEN 1.0 ELSE 0 END) * 100, 2)
                                                         AS pct_cxc_pagadas,
    ROUND(AVG(vlr_original), 2)                          AS ticket_promedio
FROM tabla1
GROUP BY cod_apli_prod, descri_cod_apli_prod
ORDER BY vlr_original DESC;


-- name: metricas_por_rango_monto
-- Comportamiento de pago por rango de monto (umbrales S4).
SELECT
    CASE
        WHEN vlr_original < 1000   THEN '1. BAJO (<1K)'
        WHEN vlr_original < 5000   THEN '2. MEDIO (1K-5K)'
        WHEN vlr_original < 20000  THEN '3. ALTO (5K-20K)'
        ELSE                            '4. MUY ALTO (>20K)'
    END                                                  AS rango_monto,
    COUNT(*)                                             AS n_cxc,
    ROUND(SUM(vlr_original), 2)                          AS vlr_original,
    ROUND(SUM(vlr_pagado), 2)                            AS vlr_pagado,
    ROUND(SUM(vlr_pendiente_pago), 2)                    AS vlr_pendiente,
    ROUND(SUM(vlr_pagado) * 100.0 / SUM(vlr_original), 2)    AS pct_recuperacion_valor,
    ROUND(AVG(CASE WHEN vlr_pendiente_pago <= 0 THEN 1.0 ELSE 0 END) * 100, 2)
                                                         AS pct_cxc_pagadas
FROM tabla1
GROUP BY rango_monto
ORDER BY rango_monto;


-- name: metricas_por_periodo
-- Evolución mensual de creación y recuperación de CxC.
SELECT
    STRFTIME('%Y-%m', DATE(SUBSTR(PRINTF('%08d', f_creacion),1,4) || '-' ||
                           SUBSTR(PRINTF('%08d', f_creacion),5,2) || '-' ||
                           SUBSTR(PRINTF('%08d', f_creacion),7,2)))
                                                         AS periodo_creacion,
    COUNT(*)                                             AS n_cxc,
    ROUND(SUM(vlr_original), 2)                          AS vlr_original,
    ROUND(SUM(vlr_pagado), 2)                            AS vlr_pagado,
    ROUND(SUM(vlr_pendiente_pago), 2)                    AS vlr_pendiente,
    ROUND(SUM(vlr_pagado) * 100.0 / SUM(vlr_original), 2)    AS pct_recuperacion_valor,
    ROUND(AVG(CASE WHEN vlr_pendiente_pago <= 0 THEN 1.0 ELSE 0 END) * 100, 2)
                                                         AS pct_cxc_pagadas
FROM tabla1
GROUP BY periodo_creacion
ORDER BY periodo_creacion;


-- name: features_modelo
-- ============================================================================
-- FEATURES PARA EL MODELO (Actividad 2). Se ejecuta contra la base de salida
-- src/data/sabana_cxc.db (producto de la Actividad 1).
-- Las métricas de cliente se recalculan en modo LEAVE-ONE-OUT: el
-- comportamiento histórico de la cuenta EXCLUYE la CxC evaluada, para no
-- filtrar el resultado propio dentro de sus predictores (fuga de información).
-- ============================================================================
SELECT
    id_cxc,
    pagado_total,
    estado_pago,
    vlr_original,
    vlr_pendiente_pago,
    producto,
    tipo_transaccion,
    cod_trn,
    rango_monto,
    mes_creacion,
    dia_semana_creacion,
    antiguedad_dias,
    n_cxc_cliente,
    -- Proporción de las DEMÁS CxC del cliente totalmente pagadas
    CASE WHEN COUNT(*) OVER (PARTITION BY num_cta) > 1 THEN
        ROUND((SUM(pagado_total) OVER (PARTITION BY num_cta) - pagado_total) * 1.0
              / (COUNT(*) OVER (PARTITION BY num_cta) - 1), 4)
    END                                                  AS pct_pagadas_cliente_loo,
    -- Tasa de recuperación promedio de las DEMÁS CxC del cliente
    CASE WHEN COUNT(*) OVER (PARTITION BY num_cta) > 1 THEN
        ROUND((SUM(tasa_recuperacion) OVER (PARTITION BY num_cta) - tasa_recuperacion)
              / (COUNT(*) OVER (PARTITION BY num_cta) - 1), 4)
    END                                                  AS tasa_recuperacion_cliente_loo
FROM sabana_cxc;


-- name: dataset_powerbi
-- ============================================================================
-- DATASET PARA POWER BI (Actividad 3). Se ejecuta contra src/data/sabana_cxc.db
-- después de que la Actividad 2 haya cargado la tabla 'predicciones_cxc'.
-- Une la sábana con las salidas del modelo y agrega la banda de probabilidad.
-- ============================================================================
SELECT
    s.*,
    p.prob_pago,
    p.valor_esperado_recuperar,
    p.valor_en_riesgo,
    CASE
        WHEN p.prob_pago < 0.2 THEN '1. MUY BAJA (<20%)'
        WHEN p.prob_pago < 0.4 THEN '2. BAJA (20-40%)'
        WHEN p.prob_pago < 0.6 THEN '3. MEDIA (40-60%)'
        WHEN p.prob_pago < 0.8 THEN '4. ALTA (60-80%)'
        ELSE                        '5. MUY ALTA (>80%)'
    END                                                  AS banda_probabilidad
FROM sabana_cxc s
LEFT JOIN predicciones_cxc p ON p.id_cxc = s.id_cxc;


-- name: distribucion_estados
-- Resumen del portafolio por estado de pago (regla S1).
SELECT
    CASE
        WHEN vlr_pendiente_pago <= 0 THEN 'PAGADO'
        WHEN vlr_pagado > 0          THEN 'PARCIAL'
        ELSE 'PENDIENTE'
    END                                                  AS estado_pago,
    COUNT(*)                                             AS n_cxc,
    ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM tabla1), 2) AS pct_cxc,
    ROUND(SUM(vlr_original), 2)                          AS vlr_original,
    ROUND(SUM(vlr_pagado), 2)                            AS vlr_pagado,
    ROUND(SUM(vlr_pendiente_pago), 2)                    AS vlr_pendiente
FROM tabla1
GROUP BY estado_pago
ORDER BY n_cxc DESC;
