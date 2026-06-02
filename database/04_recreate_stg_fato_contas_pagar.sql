-- =============================================================================
-- PROJETO BI OMIE 2026
-- Script: 04_recreate_stg_fato_contas_pagar.sql
-- Descrição: Recria stg_fato_contas_pagar com colunas que o pipeline espera
-- Execute: psql -U postgres -d bi_omie -f 04_recreate_stg_fato_contas_pagar.sql
-- =============================================================================

DROP TABLE IF EXISTS staging.stg_fato_contas_pagar CASCADE;

CREATE TABLE staging.stg_fato_contas_pagar (
    id                              BIGSERIAL       PRIMARY KEY,
    id_empresa                      INTEGER         NOT NULL REFERENCES config.empresas(id),
    -- Identificação
    codigo_lancamento_omie          BIGINT,
    codigo_lancamento_integracao    VARCHAR(60),
    codigo_tipo_documento           VARCHAR(50),
    numero_documento_fiscal         VARCHAR(60),
    numero_parcela                  VARCHAR(10),
    codigo_barras_ficha_compensacao VARCHAR(100),
    -- Fornecedor/Cliente
    codigo_cliente_fornecedor       VARCHAR(60),
    -- Conta corrente
    id_conta_corrente               VARCHAR(50),
    -- Flags de controle
    bloqueado                       BOOLEAN,
    conta_pagar_cadastro_baixa      BOOLEAN,
    -- Retenções
    retem_cofins                    BOOLEAN,
    retem_csll                      BOOLEAN,
    retem_inss                      BOOLEAN,
    retem_ir                        BOOLEAN,
    retem_iss                       BOOLEAN,
    retem_pis                       BOOLEAN,
    -- Datas
    data_emissao                    DATE,
    data_entrada                    DATE,
    data_vencimento                 DATE,
    data_previsao                   DATE,
    -- Valor
    valor_documento                 NUMERIC(18,2),
    -- Status e classificação
    status_titulo                   VARCHAR(20),
    id_origem                       VARCHAR(20),
    -- Info de auditoria
    info_importado_api              BOOLEAN,
    info_data_alteracao             DATE,
    info_data_inclusao              DATE,
    info_hora_alteracao             VARCHAR(10),
    info_hora_inclusao              VARCHAR(10),
    info_usuario_alteracao          VARCHAR(100),
    info_usuario_inclusao           VARCHAR(100),
    -- Categorias e distribuição (JSON)
    json_categorias                 TEXT,
    json_distribuicao               TEXT,
    -- Metadados
    dt_extracao                     TIMESTAMP       NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_stg_cp_empresa    ON staging.stg_fato_contas_pagar(id_empresa);
CREATE INDEX idx_stg_cp_vencimento ON staging.stg_fato_contas_pagar(data_vencimento);
CREATE INDEX idx_stg_cp_status     ON staging.stg_fato_contas_pagar(status_titulo);
CREATE INDEX idx_stg_cp_cod_omie   ON staging.stg_fato_contas_pagar(codigo_lancamento_omie);
