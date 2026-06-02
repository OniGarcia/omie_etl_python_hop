-- =============================================================================
-- PROJETO BI OMIE 2026
-- Script: 05_criar_tabelas_pagar_categorias_departamentos.sql
-- Descrição: Cria tabelas de categorias e departamentos do Contas a Pagar
-- Execute: psql -U postgres -d bi_omie -f 05_criar_tabelas_pagar_categorias_departamentos.sql
-- =============================================================================

DROP TABLE IF EXISTS staging.stg_fato_contas_pagar_categorias CASCADE;

CREATE TABLE staging.stg_fato_contas_pagar_categorias (
    id                      BIGSERIAL       PRIMARY KEY,
    id_empresa              INTEGER         NOT NULL REFERENCES config.empresas(id),
    codigo_lancamento_omie  BIGINT,
    codigo_categoria        VARCHAR(50),
    percentual              NUMERIC(10,4),
    valor                   NUMERIC(18,2),
    dt_extracao             TIMESTAMP       NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_stg_cp_cat_empresa  ON staging.stg_fato_contas_pagar_categorias(id_empresa);
CREATE INDEX idx_stg_cp_cat_lancamento ON staging.stg_fato_contas_pagar_categorias(codigo_lancamento_omie);

DROP TABLE IF EXISTS staging.stg_fato_contas_pagar_departamentos CASCADE;

CREATE TABLE staging.stg_fato_contas_pagar_departamentos (
    id                      BIGSERIAL       PRIMARY KEY,
    id_empresa              INTEGER         NOT NULL REFERENCES config.empresas(id),
    codigo_lancamento_omie  BIGINT,
    ccoddep                 VARCHAR(50),
    cdesdep                 VARCHAR(200),
    nperdep                 NUMERIC(10,4),
    nvaldep                 NUMERIC(18,2),
    dt_extracao             TIMESTAMP       NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_stg_cp_dep_empresa  ON staging.stg_fato_contas_pagar_departamentos(id_empresa);
CREATE INDEX idx_stg_cp_dep_lancamento ON staging.stg_fato_contas_pagar_departamentos(codigo_lancamento_omie);
