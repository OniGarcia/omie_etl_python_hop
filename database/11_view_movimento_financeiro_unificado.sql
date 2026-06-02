-- =============================================================================
-- PROJETO BI OMIE 2026
-- Script: 11_view_movimento_financeiro_unificado.sql
-- Descrição: View de unificação CP + CR + CC para carga da tabela fato
-- Depende de: script 10 (schema dw criado)
-- Execute: psql -U postgres -d bi_omie -f 11_view_movimento_financeiro_unificado.sql
--
-- Granularidade: (empresa, origem, lancamento, categoria)
-- Departamento: primary department via LATERAL LIMIT 1 (simplificação MVP quando há múltiplos)
-- data_pagamento em CP/CR: data_previsao quando status = 'LIQUIDADO'
-- =============================================================================

CREATE OR REPLACE VIEW dw.vw_movimento_financeiro_unificado AS

-- =============================================================================
-- CONTAS A PAGAR
-- Tabelas: stg_fato_contas_pagar (script 04)
--          stg_fato_contas_pagar_categorias (script 05)
--          stg_fato_contas_pagar_departamentos (script 05)
-- Explode por categoria; departamento = primeiro do título (LIMIT 1)
-- =============================================================================
SELECT
    cp.id_empresa,
    'CP'                                            AS origem,
    cp.codigo_lancamento_omie,
    'PAGAR'                                         AS tipo_movimento,
    'D'                                             AS natureza,
    cp.status_titulo,
    'N'                                             AS is_transferencia,
    cat.codigo_categoria                            AS cod_categoria,
    dep.ccoddep                                     AS cod_departamento,
    cp.codigo_cliente_fornecedor                    AS cod_entidade,
    cp.id_conta_corrente                            AS cod_conta_corrente,
    cp.data_emissao,
    cp.data_vencimento,
    CASE WHEN cp.status_titulo IN ('LIQUIDADO', 'RECEBIDO', 'PAGO')
         THEN cp.data_previsao
         ELSE NULL
    END                                             AS data_pagamento,
    cp.valor_documento,
    COALESCE(cat.valor,      cp.valor_documento)    AS valor_rateio,
    COALESCE(cat.percentual, 100.00)                AS percentual_rateio
FROM staging.stg_fato_contas_pagar cp
LEFT JOIN staging.stg_fato_contas_pagar_categorias cat
    ON  cat.id_empresa             = cp.id_empresa
    AND cat.codigo_lancamento_omie = cp.codigo_lancamento_omie
LEFT JOIN LATERAL (
    SELECT ccoddep
    FROM   staging.stg_fato_contas_pagar_departamentos
    WHERE  id_empresa             = cp.id_empresa
      AND  codigo_lancamento_omie = cp.codigo_lancamento_omie
    ORDER  BY id
    LIMIT  1
) dep ON TRUE

UNION ALL

-- =============================================================================
-- CONTAS A RECEBER
-- Tabelas: stg_fato_contas_receber (script 06)
--          stg_fato_contas_receber_categorias (script 07)
--          stg_fato_contas_receber_departamentos (script 07)
-- cod_categoria: prefere tabela filha de rateio; fallback no campo direto
-- =============================================================================
SELECT
    cr.id_empresa,
    'CR'                                            AS origem,
    cr.codigo_lancamento_omie,
    'RECEBER'                                       AS tipo_movimento,
    'C'                                             AS natureza,
    cr.status_titulo,
    'N'                                             AS is_transferencia,
    COALESCE(cat.codigo_categoria,
             cr.codigo_categoria)                   AS cod_categoria,
    dep.ccoddep                                     AS cod_departamento,
    cr.codigo_cliente_fornecedor::VARCHAR           AS cod_entidade,
    cr.id_conta_corrente::VARCHAR                   AS cod_conta_corrente,
    cr.data_emissao::DATE                           AS data_emissao,
    cr.data_vencimento::DATE                        AS data_vencimento,
    CASE WHEN cr.status_titulo IN ('LIQUIDADO', 'RECEBIDO', 'PAGO')
         THEN cr.data_previsao::DATE
         ELSE NULL
    END                                             AS data_pagamento,
    cr.valor_documento,
    COALESCE(cat.valor,      cr.valor_documento)    AS valor_rateio,
    COALESCE(cat.percentual, 100.00)                AS percentual_rateio
FROM staging.stg_fato_contas_receber cr
LEFT JOIN staging.stg_fato_contas_receber_categorias cat
    ON  cat.id_empresa             = cr.id_empresa
    AND cat.codigo_lancamento_omie = cr.codigo_lancamento_omie
LEFT JOIN LATERAL (
    SELECT ccoddep
    FROM   staging.stg_fato_contas_receber_departamentos
    WHERE  id_empresa             = cr.id_empresa
      AND  codigo_lancamento_omie = cr.codigo_lancamento_omie
    ORDER  BY id
    LIMIT  1
) dep ON TRUE

UNION ALL

-- =============================================================================
-- LANÇAMENTOS CONTA CORRENTE
-- Tabelas: stg_fato_lancamentos_cc (script 08)
--          stg_fato_lancamentos_cc_categorias (script 08)
--          stg_fato_lancamentos_cc_departamentos (script 08)
-- Transferências: identificadas por ncodccdestino IS NOT NULL
-- tipo_movimento: TRANSFERENCIA | CC_ENTRADA (ctipo=ENT) | CC_SAIDA
-- Todos CC são LIQUIDADO (transações realizadas no extrato)
-- =============================================================================
SELECT
    lcc.id_empresa,
    'CC'                                            AS origem,
    lcc.ncodlanc                                    AS codigo_lancamento_omie,
    CASE
        WHEN lcc.ncodccdestino IS NOT NULL  THEN 'TRANSFERENCIA'
        WHEN lcc.ctipo = 'ENT'              THEN 'CC_ENTRADA'
        ELSE                                     'CC_SAIDA'
    END                                             AS tipo_movimento,
    CASE WHEN lcc.ctipo = 'ENT' THEN 'C' ELSE 'D' END AS natureza,
    'LIQUIDADO'                                     AS status_titulo,
    CASE WHEN lcc.ncodccdestino IS NOT NULL
         THEN 'S' ELSE 'N'
    END                                             AS is_transferencia,
    COALESCE(cat.ccodcategoria, lcc.ccodcateg)      AS cod_categoria,
    dep.ccoddep                                     AS cod_departamento,
    lcc.ncodcliente::VARCHAR                        AS cod_entidade,
    lcc.ncodcc::VARCHAR                             AS cod_conta_corrente,
    lcc.ddtlanc::DATE                               AS data_emissao,
    lcc.ddtlanc::DATE                               AS data_vencimento,
    lcc.ddtlanc::DATE                               AS data_pagamento,
    ABS(lcc.nvalorlanc)                             AS valor_documento,
    COALESCE(cat.nvalor,      ABS(lcc.nvalorlanc))  AS valor_rateio,
    COALESCE(cat.npercentual, 100.00)               AS percentual_rateio
FROM staging.stg_fato_lancamentos_cc lcc
LEFT JOIN staging.stg_fato_lancamentos_cc_categorias cat
    ON  cat.id_empresa = lcc.id_empresa
    AND cat.ncodlanc   = lcc.ncodlanc
LEFT JOIN LATERAL (
    SELECT ccoddep
    FROM   staging.stg_fato_lancamentos_cc_departamentos
    WHERE  id_empresa = lcc.id_empresa
      AND  ncodlanc   = lcc.ncodlanc
    ORDER  BY id
    LIMIT  1
) dep ON TRUE;
