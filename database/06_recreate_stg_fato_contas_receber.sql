-- =============================================================================
-- PROJETO BI OMIE 2026
-- Script: 06_recreate_stg_fato_contas_receber.sql
-- Descrição: Recria stg_fato_contas_receber com colunas que o pipeline espera
-- Execute: psql -U postgres -d bi_omie -f 06_recreate_stg_fato_contas_receber.sql
-- =============================================================================

DROP TABLE IF EXISTS staging.stg_fato_contas_receber CASCADE;

CREATE TABLE staging.stg_fato_contas_receber (
    id                              BIGSERIAL       PRIMARY KEY,
    id_empresa                      INTEGER         NOT NULL REFERENCES config.empresas(id),
    -- Identificação
    codigo_lancamento_omie          BIGINT,
    codigo_lancamento_integracao    VARCHAR(60),
    codigo_tipo_documento           VARCHAR(50),
    numero_documento                VARCHAR(60),
    numero_documento_fiscal         VARCHAR(60),
    -- Fornecedor/Cliente
    codigo_cliente_fornecedor       BIGINT,
    -- Categoria e conta corrente
    codigo_categoria                VARCHAR(50),
    id_conta_corrente               BIGINT,
    codigo_barras_ficha_compensacao VARCHAR(100),
    -- Flags de retenção
    retem_pis                       VARCHAR(10),
    retem_cofins                    VARCHAR(10),
    retem_csll                      VARCHAR(10),
    retem_ir                        VARCHAR(10),
    retem_iss                       VARCHAR(10),
    retem_inss                      VARCHAR(10),
    -- Datas
    data_vencimento                 TIMESTAMP,
    data_emissao                    TIMESTAMP,
    data_previsao                   TIMESTAMP,
    data_registro                   TIMESTAMP,
    -- Valor
    valor_documento                 NUMERIC(18,2),
    -- Status e classificação
    status_titulo                   VARCHAR(20),
    tipo_agrupamento                VARCHAR(10),
    id_origem                       VARCHAR(20),
    -- Info importado API
    cimpapi                         VARCHAR(5),
    -- Info de auditoria (nomes curtos da API)
    dinc                            TIMESTAMP,
    hinc                            VARCHAR(10),
    uinc                            VARCHAR(100),
    dalt                            TIMESTAMP,
    halt                            VARCHAR(10),
    ualt                            VARCHAR(100),
    -- Categorias e distribuição (JSON)
    json_categorias                 TEXT,
    json_distribuicao               TEXT,
    -- Metadados
    dt_extracao                     TIMESTAMP       NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_stg_cr_empresa    ON staging.stg_fato_contas_receber(id_empresa);
CREATE INDEX idx_stg_cr_vencimento ON staging.stg_fato_contas_receber(data_vencimento);
CREATE INDEX idx_stg_cr_status     ON staging.stg_fato_contas_receber(status_titulo);
CREATE INDEX idx_stg_cr_cod_omie   ON staging.stg_fato_contas_receber(codigo_lancamento_omie);
