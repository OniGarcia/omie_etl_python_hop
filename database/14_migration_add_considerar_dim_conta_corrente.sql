-- =============================================================================
-- PROJETO BI OMIE 2026
-- Script: 14_migration_add_considerar_dim_conta_corrente.sql
-- Descrição: Adiciona campo `considerar` à dw.dim_conta_corrente.
--            Este campo é configuração manual de negócio e NUNCA é sobrescrito
--            pelo ETL (ausente do SET clause na sp_load_fact_movimento_financeiro).
-- Execute: psql -U postgres -d bi_omie -f 14_migration_add_considerar_dim_conta_corrente.sql
-- =============================================================================

ALTER TABLE dw.dim_conta_corrente
    ADD COLUMN IF NOT EXISTS considerar BOOLEAN NOT NULL DEFAULT TRUE;

COMMENT ON COLUMN dw.dim_conta_corrente.considerar
    IS 'Flag manual: TRUE = saldos e movimentações desta conta são considerados nas análises. Nunca sobrescrito pelo ETL.';

-- Verificação pós-execução
SELECT cod_conta_corrente, descricao, considerar
FROM   dw.dim_conta_corrente
ORDER  BY cod_conta_corrente;
