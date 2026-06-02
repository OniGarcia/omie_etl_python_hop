-- =============================================================================
-- PROJETO BI OMIE 2026
-- Script: 07_criar_tabelas_receber_categorias_departamentos.sql
-- Descrição: Cria tabelas de categorias e departamentos do Contas a Receber
-- Execute: psql -U postgres -d bi_omie -f 07_criar_tabelas_receber_categorias_departamentos.sql
-- =============================================================================

DROP TABLE IF EXISTS staging.stg_fato_contas_receber_categorias CASCADE;

CREATE TABLE staging.stg_fato_contas_receber_categorias (
    id                      BIGSERIAL       PRIMARY KEY,
    id_empresa              INTEGER         NOT NULL REFERENCES config.empresas(id),
    codigo_lancamento_omie  BIGINT,
    codigo_categoria        VARCHAR(50),
    percentual              NUMERIC(10,4),
    valor                   NUMERIC(18,2),
    dt_extracao             TIMESTAMP       NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_stg_cr_cat_empresa    ON staging.stg_fato_contas_receber_categorias(id_empresa);
CREATE INDEX idx_stg_cr_cat_lancamento ON staging.stg_fato_contas_receber_categorias(codigo_lancamento_omie);

DROP TABLE IF EXISTS staging.stg_fato_contas_receber_departamentos CASCADE;

CREATE TABLE staging.stg_fato_contas_receber_departamentos (
    id                      BIGSERIAL       PRIMARY KEY,
    id_empresa              INTEGER         NOT NULL REFERENCES config.empresas(id),
    codigo_lancamento_omie  BIGINT,
    ccoddep                 VARCHAR(50),
    cdesdep                 VARCHAR(200),
    nperdep                 NUMERIC(10,4),
    nvaldep                 NUMERIC(18,2),
    dt_extracao             TIMESTAMP       NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_stg_cr_dep_empresa    ON staging.stg_fato_contas_receber_departamentos(id_empresa);
CREATE INDEX idx_stg_cr_dep_lancamento ON staging.stg_fato_contas_receber_departamentos(codigo_lancamento_omie);
