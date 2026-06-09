-- =============================================================================
-- PROJETO BI OMIE 2026
-- Script: 16_add_soft_delete_staging.sql
-- Descrição: Adiciona colunas de soft delete em Contas a Pagar e Contas a Receber.
--            Permite refletir exclusões físicas do Omie sem perder auditoria.
--            (Cancelados continuam intactos com status_titulo = 'CANCELADO'.)
-- Depende de: scripts 04 (CP) e 06 (CR)
-- Execute: psql -U postgres -d bi_omie -f 16_add_soft_delete_staging.sql
--
-- Idempotente: pode ser executado sobre a base existente sem recriar tabelas.
-- =============================================================================

-- CONTAS A PAGAR
ALTER TABLE staging.stg_fato_contas_pagar
    ADD COLUMN IF NOT EXISTS excluido      BOOLEAN   NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS data_exclusao TIMESTAMP NULL;

CREATE INDEX IF NOT EXISTS idx_stg_cp_excluido
    ON staging.stg_fato_contas_pagar (id_empresa, excluido);

-- CONTAS A RECEBER
ALTER TABLE staging.stg_fato_contas_receber
    ADD COLUMN IF NOT EXISTS excluido      BOOLEAN   NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS data_exclusao TIMESTAMP NULL;

CREATE INDEX IF NOT EXISTS idx_stg_cr_excluido
    ON staging.stg_fato_contas_receber (id_empresa, excluido);
