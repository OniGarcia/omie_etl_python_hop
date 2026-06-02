-- =============================================================================
-- PROJETO BI OMIE 2026
-- Script: 99_verificar_contagem_tabelas.sql
-- Descrição: Conta registros em todas as tabelas de staging e config
-- =============================================================================

SELECT
    schemaname                  AS schema,
    relname                     AS tabela,
    n_live_tup                  AS registros_estimados
FROM pg_stat_user_tables
WHERE schemaname IN ('staging', 'config')
ORDER BY schemaname, relname;

-- Contagem exata por tabela (mais lento, mas preciso)
SELECT 'config.empresas'                                AS tabela, COUNT(*) AS registros FROM config.empresas
UNION ALL
SELECT 'staging.stg_cad_categorias',                              COUNT(*) FROM staging.stg_cad_categorias
UNION ALL
SELECT 'staging.stg_cad_clientes',                                COUNT(*) FROM staging.stg_cad_clientes
UNION ALL
SELECT 'staging.stg_cad_contas_correntes',                        COUNT(*) FROM staging.stg_cad_contas_correntes
UNION ALL
SELECT 'staging.stg_cad_departamentos',                           COUNT(*) FROM staging.stg_cad_departamentos
UNION ALL
SELECT 'staging.stg_fato_contas_pagar',                           COUNT(*) FROM staging.stg_fato_contas_pagar
UNION ALL
SELECT 'staging.stg_fato_contas_pagar_categorias',                COUNT(*) FROM staging.stg_fato_contas_pagar_categorias
UNION ALL
SELECT 'staging.stg_fato_contas_pagar_departamentos',             COUNT(*) FROM staging.stg_fato_contas_pagar_departamentos
UNION ALL
SELECT 'staging.stg_fato_contas_receber',                         COUNT(*) FROM staging.stg_fato_contas_receber
UNION ALL
SELECT 'staging.stg_fato_contas_receber_categorias',              COUNT(*) FROM staging.stg_fato_contas_receber_categorias
UNION ALL
SELECT 'staging.stg_fato_contas_receber_departamentos',           COUNT(*) FROM staging.stg_fato_contas_receber_departamentos
UNION ALL
SELECT 'staging.stg_fato_lancamentos_cc',                         COUNT(*) FROM staging.stg_fato_lancamentos_cc
UNION ALL
SELECT 'staging.stg_fato_lancamentos_cc_categorias',              COUNT(*) FROM staging.stg_fato_lancamentos_cc_categorias
UNION ALL
SELECT 'staging.stg_fato_lancamentos_cc_departamentos',           COUNT(*) FROM staging.stg_fato_lancamentos_cc_departamentos
ORDER BY tabela;
