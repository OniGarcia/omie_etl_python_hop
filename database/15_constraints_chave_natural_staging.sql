-- =============================================================================
-- PROJETO BI OMIE 2026
-- Script: 15_constraints_chave_natural_staging.sql
-- Descrição: Adiciona UNIQUE constraints nas tabelas fato do staging para
--            habilitar UPSERT (ON CONFLICT) no modo de carga incremental.
--
-- Execute: psql -U postgres -d bi_omie -f 15_constraints_chave_natural_staging.sql
--
-- Idempotente: usa DO $$ BEGIN IF NOT EXISTS ... END $$ para não falhar
--              se a constraint já existir.
-- =============================================================================

-- stg_fato_contas_pagar → chave natural: (id_empresa, codigo_lancamento_omie)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'uq_stg_cp_empresa_lanc'
    ) THEN
        ALTER TABLE staging.stg_fato_contas_pagar
            ADD CONSTRAINT uq_stg_cp_empresa_lanc
            UNIQUE (id_empresa, codigo_lancamento_omie);
        RAISE NOTICE 'Constraint uq_stg_cp_empresa_lanc criada.';
    ELSE
        RAISE NOTICE 'Constraint uq_stg_cp_empresa_lanc já existe. Ignorada.';
    END IF;
END $$;

-- stg_fato_contas_receber → chave natural: (id_empresa, codigo_lancamento_omie)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'uq_stg_cr_empresa_lanc'
    ) THEN
        ALTER TABLE staging.stg_fato_contas_receber
            ADD CONSTRAINT uq_stg_cr_empresa_lanc
            UNIQUE (id_empresa, codigo_lancamento_omie);
        RAISE NOTICE 'Constraint uq_stg_cr_empresa_lanc criada.';
    ELSE
        RAISE NOTICE 'Constraint uq_stg_cr_empresa_lanc já existe. Ignorada.';
    END IF;
END $$;

-- stg_fato_lancamentos_cc → chave natural: (id_empresa, ncodlanc)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'uq_stg_lcc_empresa_lanc'
    ) THEN
        ALTER TABLE staging.stg_fato_lancamentos_cc
            ADD CONSTRAINT uq_stg_lcc_empresa_lanc
            UNIQUE (id_empresa, ncodlanc);
        RAISE NOTICE 'Constraint uq_stg_lcc_empresa_lanc criada.';
    ELSE
        RAISE NOTICE 'Constraint uq_stg_lcc_empresa_lanc já existe. Ignorada.';
    END IF;
END $$;
