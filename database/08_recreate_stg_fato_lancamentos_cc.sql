-- =============================================================================
-- PROJETO BI OMIE 2026
-- Script: 08_recreate_stg_fato_lancamentos_cc.sql
-- Descrição: Recria stg_fato_lancamentos_cc com colunas que o pipeline espera
-- Execute: psql -U postgres -d bi_omie -f 08_recreate_stg_fato_lancamentos_cc.sql
-- =============================================================================

DROP TABLE IF EXISTS staging.stg_fato_lancamentos_cc_categorias CASCADE;
DROP TABLE IF EXISTS staging.stg_fato_lancamentos_cc_departamentos CASCADE;
DROP TABLE IF EXISTS staging.stg_fato_lancamentos_cc CASCADE;

CREATE TABLE staging.stg_fato_lancamentos_cc (
    id                  BIGSERIAL       PRIMARY KEY,
    id_empresa          INTEGER         NOT NULL REFERENCES config.empresas(id),
    ncodlanc            BIGINT,
    ncodagrup           BIGINT,
    ccodintlanc         VARCHAR(60),
    ddtlanc             TIMESTAMP,
    ncodcc              BIGINT,
    nvalorlanc          NUMERIC(18,2),
    ccodcateg           VARCHAR(50),
    cnumdoc             VARCHAR(60),
    cobs                TEXT,
    ctipo               VARCHAR(10),
    ncodcliente         BIGINT,
    ncodprojeto         BIGINT,
    cnatureza           VARCHAR(10),
    corigem             VARCHAR(20),
    ddtconc             TIMESTAMP,
    chrconc             VARCHAR(10),
    cusconc             VARCHAR(100),
    cidentlanc          VARCHAR(100),
    ncodcomprador       BIGINT,
    ncodvendedor        BIGINT,
    ncodlanccr          BIGINT,
    ncodlanccp          BIGINT,
    dinc                TIMESTAMP,
    hinc                VARCHAR(10),
    uinc                VARCHAR(100),
    dalt                TIMESTAMP,
    halt                VARCHAR(10),
    ualt                VARCHAR(100),
    cimpapi             VARCHAR(5),
    ncodccdestino       BIGINT,
    json_distribuicao   TEXT,
    json_categorias     TEXT,
    dt_extracao         TIMESTAMP       NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_stg_lcc_empresa  ON staging.stg_fato_lancamentos_cc(id_empresa);
CREATE INDEX idx_stg_lcc_data     ON staging.stg_fato_lancamentos_cc(ddtlanc);
CREATE INDEX idx_stg_lcc_cc       ON staging.stg_fato_lancamentos_cc(ncodcc);
CREATE INDEX idx_stg_lcc_lancamento ON staging.stg_fato_lancamentos_cc(ncodlanc);

-- Categorias dos lançamentos CC (1:N)
CREATE TABLE staging.stg_fato_lancamentos_cc_categorias (
    id                  BIGSERIAL       PRIMARY KEY,
    id_empresa          INTEGER         NOT NULL REFERENCES config.empresas(id),
    ncodlanc            BIGINT,
    ccodcategoria       VARCHAR(50),
    npercentual         NUMERIC(10,4),
    nvalor              NUMERIC(18,2),
    dt_extracao         TIMESTAMP       NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_stg_lcc_cat_empresa ON staging.stg_fato_lancamentos_cc_categorias(id_empresa);
CREATE INDEX idx_stg_lcc_cat_lanc    ON staging.stg_fato_lancamentos_cc_categorias(ncodlanc);

-- Departamentos dos lançamentos CC (1:N)
CREATE TABLE staging.stg_fato_lancamentos_cc_departamentos (
    id                  BIGSERIAL       PRIMARY KEY,
    id_empresa          INTEGER         NOT NULL REFERENCES config.empresas(id),
    ncodlanc            BIGINT,
    ccoddep             VARCHAR(50),
    cdesdep             VARCHAR(200),
    nperdep             NUMERIC(10,4),
    nvaldep             NUMERIC(18,2),
    dt_extracao         TIMESTAMP       NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_stg_lcc_dep_empresa ON staging.stg_fato_lancamentos_cc_departamentos(id_empresa);
CREATE INDEX idx_stg_lcc_dep_lanc    ON staging.stg_fato_lancamentos_cc_departamentos(ncodlanc);
