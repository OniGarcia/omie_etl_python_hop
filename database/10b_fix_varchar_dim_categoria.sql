-- =============================================================================
-- PROJETO BI OMIE 2026
-- Script: 10b_fix_varchar_dim_categoria.sql
-- Descrição: Corrige tamanho de colunas VARCHAR(50) que eram pequenas para
--            os dados reais do Omie em dim_categoria e fact_movimento_financeiro.
-- Execute: psql -U postgres -d bi_omie -f 10b_fix_varchar_dim_categoria.sql
-- Depois: CALL dw.sp_load_fact_movimento_financeiro();
-- =============================================================================

ALTER TABLE dw.dim_categoria
    ALTER COLUMN cod_categoria  TYPE TEXT,
    ALTER COLUMN tipo_categoria TYPE TEXT,
    ALTER COLUMN natureza       TYPE TEXT;

ALTER TABLE dw.fact_movimento_financeiro
    ALTER COLUMN cod_categoria   TYPE TEXT,
    ALTER COLUMN cod_departamento TYPE TEXT;

-- Recria o unique index (necessário pois o tipo da coluna mudou)
DROP INDEX IF EXISTS dw.idx_fmf_natural_key;
CREATE UNIQUE INDEX idx_fmf_natural_key ON dw.fact_movimento_financeiro
    (id_empresa, origem, codigo_lancamento_omie, COALESCE(cod_categoria, ''));
