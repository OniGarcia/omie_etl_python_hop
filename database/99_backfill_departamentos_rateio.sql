-- =============================================================================
-- PROJETO BI OMIE 2026
-- Script: 99_backfill_departamentos_rateio.sql
-- Descrição: Backfill pontual do rateio de departamentos em Contas a Pagar e
--            Contas a Receber, aproveitando o json_distribuicao JÁ gravado nos
--            pais (sem nova chamada à API Omie).
--
-- Contexto: os extratores contas_pagar.py / contas_receber.py liam os campos do
--           rateio em minúsculas (ccoddep/...), mas a Omie devolve em camelCase
--           (cCodDep/cDesDep/nPerDep/nValDep). As linhas filhas foram criadas
--           com valores NULL. Este script as reconstrói a partir do JSON bruto.
--
-- Pré-requisito: correção dos extratores já aplicada (go-forward).
-- Execute: psql -U postgres -d bi_omie -f 99_backfill_departamentos_rateio.sql
-- Depois:  CALL dw.sp_load_fact_movimento_financeiro();
-- =============================================================================

BEGIN;

-- -----------------------------------------------------------------------------
-- CONTAS A PAGAR
-- -----------------------------------------------------------------------------
TRUNCATE TABLE staging.stg_fato_contas_pagar_departamentos RESTART IDENTITY;

INSERT INTO staging.stg_fato_contas_pagar_departamentos (
    id_empresa, codigo_lancamento_omie, ccoddep, cdesdep, nperdep, nvaldep
)
SELECT
    cp.id_empresa,
    cp.codigo_lancamento_omie,
    d."cCodDep",
    d."cDesDep",
    d."nPerDep",
    d."nValDep"
FROM staging.stg_fato_contas_pagar cp
CROSS JOIN LATERAL jsonb_to_recordset(cp.json_distribuicao::jsonb)
    AS d("cCodDep" VARCHAR, "cDesDep" VARCHAR, "nPerDep" NUMERIC, "nValDep" NUMERIC)
WHERE cp.json_distribuicao IS NOT NULL;

-- -----------------------------------------------------------------------------
-- CONTAS A RECEBER
-- -----------------------------------------------------------------------------
TRUNCATE TABLE staging.stg_fato_contas_receber_departamentos RESTART IDENTITY;

INSERT INTO staging.stg_fato_contas_receber_departamentos (
    id_empresa, codigo_lancamento_omie, ccoddep, cdesdep, nperdep, nvaldep
)
SELECT
    cr.id_empresa,
    cr.codigo_lancamento_omie,
    d."cCodDep",
    d."cDesDep",
    d."nPerDep",
    d."nValDep"
FROM staging.stg_fato_contas_receber cr
CROSS JOIN LATERAL jsonb_to_recordset(cr.json_distribuicao::jsonb)
    AS d("cCodDep" VARCHAR, "cDesDep" VARCHAR, "nPerDep" NUMERIC, "nValDep" NUMERIC)
WHERE cr.json_distribuicao IS NOT NULL;

-- -----------------------------------------------------------------------------
-- Verificação rápida (deve mostrar com_ccoddep ≈ linhas)
-- -----------------------------------------------------------------------------
-- SELECT 'cp' t, count(*) linhas, count(*) FILTER (WHERE ccoddep IS NOT NULL) com_ccoddep
-- FROM staging.stg_fato_contas_pagar_departamentos
-- UNION ALL
-- SELECT 'cr', count(*), count(*) FILTER (WHERE ccoddep IS NOT NULL)
-- FROM staging.stg_fato_contas_receber_departamentos;

COMMIT;

-- NOTA: o catálogo staging.stg_cad_departamentos NÃO é coberto aqui (não há JSON
-- bruto armazenado). É preciso re-executar a extração de 'departamentos' (full)
-- após a correção do list_key, e em seguida rodar a SP de carga do DW.
