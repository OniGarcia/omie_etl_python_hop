-- =============================================================================
-- PROJETO BI OMIE 2026
-- Script: 14_criar_etl_watermark.sql
-- Descrição: Cria tabela de controle de watermark para carga incremental (CDC)
-- Execute: psql -U postgres -d bi_omie -f 14_criar_etl_watermark.sql
--
-- Lógica:
--   - Cada (id_empresa, entidade) tem uma linha com a data da última carga OK.
--   - NULL em ultima_data_ok → full backfill automático (empresa nova / primeira vez).
--   - Atualizado pelo ETL em Python após FASE C (SUCESSO) de cada empresa.
-- =============================================================================

CREATE TABLE IF NOT EXISTS config.etl_watermark (
    id_empresa      INTEGER     NOT NULL REFERENCES config.empresas(id),
    entidade        TEXT        NOT NULL,       -- 'contas_pagar' | 'contas_receber' | 'lancamentos_cc'
    ultima_data_ok  DATE,                       -- data até a qual os dados foram carregados com sucesso
    ultima_execucao TIMESTAMPTZ,                -- timestamp da última execução bem-sucedida
    PRIMARY KEY (id_empresa, entidade)
);

COMMENT ON TABLE  config.etl_watermark              IS 'Controle de watermark por empresa+entidade para carga incremental (CDC)';
COMMENT ON COLUMN config.etl_watermark.ultima_data_ok IS 'NULL = nunca carregado; preenchido = data base para o próximo filtro incremental';
