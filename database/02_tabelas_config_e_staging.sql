-- =============================================================================
-- PROJETO BI OMIE 2026
-- Script: 02_tabelas_config_e_staging.sql
-- Descrição: Tabela de configuração de empresas + todas as tabelas staging
-- Execute conectado ao banco: psql -U postgres -d bi_omie -f 02_tabelas_config_e_staging.sql
-- =============================================================================

-- -----------------------------------------------------------------------------
-- SCHEMA
-- -----------------------------------------------------------------------------
CREATE SCHEMA IF NOT EXISTS staging;
CREATE SCHEMA IF NOT EXISTS config;

-- =============================================================================
-- CONFIG: EMPRESAS
-- Armazena as credenciais de acesso à API Omie por empresa
-- =============================================================================
CREATE TABLE config.empresas (
    id                  SERIAL          PRIMARY KEY,
    nome_empresa        VARCHAR(200)    NOT NULL,
    nome_fantasia       VARCHAR(200),
    cnpj                VARCHAR(18),
    omie_app_key        VARCHAR(100)    NOT NULL,
    omie_app_secret     VARCHAR(100)    NOT NULL,
    ativo               BOOLEAN         NOT NULL DEFAULT TRUE,
    -- Metadados
    criado_em           TIMESTAMP       NOT NULL DEFAULT NOW(),
    atualizado_em       TIMESTAMP       NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE  config.empresas               IS 'Credenciais de acesso à API Omie por empresa';
COMMENT ON COLUMN config.empresas.omie_app_key  IS 'App Key fornecida pelo Omie (única por empresa)';
COMMENT ON COLUMN config.empresas.omie_app_secret IS 'App Secret fornecida pelo Omie';

-- Trigger para manter atualizado_em automaticamente
CREATE OR REPLACE FUNCTION config.fn_set_atualizado_em()
RETURNS TRIGGER AS $$
BEGIN
    NEW.atualizado_em = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_empresas_atualizado_em
    BEFORE UPDATE ON config.empresas
    FOR EACH ROW EXECUTE FUNCTION config.fn_set_atualizado_em();

-- =============================================================================
-- STAGING: CADASTROS
-- =============================================================================

-- -----------------------------------------------------------------------------
-- stg_cad_categorias
-- Fonte: API Omie - ListarCategorias
-- -----------------------------------------------------------------------------
CREATE TABLE staging.stg_cad_categorias (
    id                      BIGSERIAL       PRIMARY KEY,
    id_empresa              INTEGER         NOT NULL REFERENCES config.empresas(id),
    -- Campos da API
    codigo                  VARCHAR(50),
    descricao               VARCHAR(500),
    descricao_padrao        VARCHAR(500),
    descricao_dre           VARCHAR(500),
    tipo_categoria          VARCHAR(50),
    categoria_superior      VARCHAR(50),
    natureza                VARCHAR(50),
    conta_despesa           VARCHAR(50),
    conta_receita           VARCHAR(50),
    conta_inativa           VARCHAR(5),
    id_conta_contabil       BIGINT,
    tag_conta_contabil      VARCHAR(500),
    totalizadora            VARCHAR(5),
    definida_pelo_usuario   VARCHAR(5),
    transferencia           VARCHAR(5),
    nao_exibir              VARCHAR(5),
    json_dados_dre          TEXT,
    -- Metadados
    dt_extracao             TIMESTAMP       NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_stg_categorias_empresa ON staging.stg_cad_categorias(id_empresa);

-- -----------------------------------------------------------------------------
-- stg_cad_departamentos
-- Fonte: API Omie - ListarDepartamentos
-- -----------------------------------------------------------------------------
CREATE TABLE staging.stg_cad_departamentos (
    id                  BIGSERIAL       PRIMARY KEY,
    id_empresa          INTEGER         NOT NULL REFERENCES config.empresas(id),
    -- Campos da API
    codigo              VARCHAR(50),
    descricao           VARCHAR(500),
    estrutura           VARCHAR(200),
    inativo             VARCHAR(5),
    -- Metadados
    dt_extracao         TIMESTAMP       NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_stg_departamentos_empresa ON staging.stg_cad_departamentos(id_empresa);

-- -----------------------------------------------------------------------------
-- stg_cad_clientes
-- Fonte: API Omie - ListarClientes
-- -----------------------------------------------------------------------------
CREATE TABLE staging.stg_cad_clientes (
    id                  BIGSERIAL       PRIMARY KEY,
    id_empresa          INTEGER         NOT NULL REFERENCES config.empresas(id),
    -- Campos da API
    codigo_cliente_omie BIGINT,
    cnpj_cpf            VARCHAR(20),
    nome_fantasia       VARCHAR(200),
    razao_social        VARCHAR(200),
    email               VARCHAR(200),
    telefone1_ddd        VARCHAR(5),
    telefone1_numero     VARCHAR(20),
    cidade              VARCHAR(100),
    estado              VARCHAR(2),
    inativo             VARCHAR(5),
    -- Metadados
    dt_extracao         TIMESTAMP       NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_stg_clientes_empresa    ON staging.stg_cad_clientes(id_empresa);
CREATE INDEX idx_stg_clientes_cod_omie   ON staging.stg_cad_clientes(codigo_cliente_omie);

-- -----------------------------------------------------------------------------
-- stg_cad_contas_correntes
-- Fonte: API Omie - ListarContasCorrentes
-- -----------------------------------------------------------------------------
CREATE TABLE staging.stg_cad_contas_correntes (
    id                      BIGSERIAL       PRIMARY KEY,
    id_empresa              INTEGER         NOT NULL REFERENCES config.empresas(id),
    -- Campos da API
    n_cod_cc                BIGINT,
    c_cod_cc_int            VARCHAR(50),
    descricao               VARCHAR(200),
    codigo_banco            VARCHAR(10),
    codigo_agencia          VARCHAR(20),
    numero_conta_corrente   VARCHAR(30),
    tipo                    VARCHAR(50),
    saldo_inicial           NUMERIC(18,2),
    ativo                   VARCHAR(5),
    -- Metadados
    dt_extracao             TIMESTAMP       NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_stg_cc_empresa ON staging.stg_cad_contas_correntes(id_empresa);

-- =============================================================================
-- STAGING: CONTAS A PAGAR
-- Fonte: API Omie - ListarContasPagar
-- =============================================================================
CREATE TABLE staging.stg_fato_contas_pagar (
    id                          BIGSERIAL       PRIMARY KEY,
    id_empresa                  INTEGER         NOT NULL REFERENCES config.empresas(id),
    -- Identificação do título
    n_cod_titulo                BIGINT,
    c_cod_int_titulo            VARCHAR(50),
    n_seq_nfe                   INTEGER,
    c_num_doc_fiscal            VARCHAR(60),
    c_num_parcela               VARCHAR(10),
    -- Fornecedor
    c_cod_for                   VARCHAR(60),        -- código do fornecedor
    n_cod_for                   BIGINT,
    -- Datas
    d_data_emissao              DATE,
    d_data_entrada              DATE,
    d_data_vencimento           DATE,
    d_data_previsao             DATE,
    d_data_pagamento            DATE,
    -- Valores
    n_valor_titulo              NUMERIC(18,2),
    n_valor_abatimento          NUMERIC(18,2),
    n_valor_desconto            NUMERIC(18,2),
    n_valor_juros               NUMERIC(18,2),
    n_valor_multa               NUMERIC(18,2),
    n_valor_pago                NUMERIC(18,2),
    -- Retenções
    n_valor_ir                  NUMERIC(18,2),
    n_valor_iss                 NUMERIC(18,2),
    n_valor_inss                NUMERIC(18,2),
    n_valor_csll                NUMERIC(18,2),
    n_valor_cofins              NUMERIC(18,2),
    n_valor_pis                 NUMERIC(18,2),
    -- Status e classificação
    c_status                    VARCHAR(20),
    c_cod_categoria             VARCHAR(50),
    c_cod_departamento          VARCHAR(50),
    n_cod_cc                    BIGINT,             -- conta corrente usada no pagamento
    c_obs                       TEXT,
    -- Metadados
    dt_extracao                 TIMESTAMP       NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_stg_cp_empresa    ON staging.stg_fato_contas_pagar(id_empresa);
CREATE INDEX idx_stg_cp_vencimento ON staging.stg_fato_contas_pagar(d_data_vencimento);
CREATE INDEX idx_stg_cp_status     ON staging.stg_fato_contas_pagar(c_status);

-- =============================================================================
-- STAGING: CONTAS A RECEBER
-- Fonte: API Omie - ListarContasReceber
-- =============================================================================
CREATE TABLE staging.stg_fato_contas_receber (
    id                          BIGSERIAL       PRIMARY KEY,
    id_empresa                  INTEGER         NOT NULL REFERENCES config.empresas(id),
    -- Identificação do título
    n_cod_titulo                BIGINT,
    c_cod_int_titulo            VARCHAR(50),
    n_seq_nfe                   INTEGER,
    c_num_doc_fiscal            VARCHAR(60),
    c_num_parcela               VARCHAR(10),
    -- Cliente
    n_cod_cli                   BIGINT,
    -- Datas
    d_data_emissao              DATE,
    d_data_vencimento           DATE,
    d_data_previsao             DATE,
    d_data_recebimento          DATE,
    -- Valores
    n_valor_titulo              NUMERIC(18,2),
    n_valor_abatimento          NUMERIC(18,2),
    n_valor_desconto            NUMERIC(18,2),
    n_valor_juros               NUMERIC(18,2),
    n_valor_multa               NUMERIC(18,2),
    n_valor_recebido            NUMERIC(18,2),
    -- Status e classificação
    c_status                    VARCHAR(20),
    c_cod_categoria             VARCHAR(50),
    c_cod_departamento          VARCHAR(50),
    n_cod_cc                    BIGINT,
    c_obs                       TEXT,
    -- Metadados
    dt_extracao                 TIMESTAMP       NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_stg_cr_empresa    ON staging.stg_fato_contas_receber(id_empresa);
CREATE INDEX idx_stg_cr_vencimento ON staging.stg_fato_contas_receber(d_data_vencimento);
CREATE INDEX idx_stg_cr_cliente    ON staging.stg_fato_contas_receber(n_cod_cli);
CREATE INDEX idx_stg_cr_status     ON staging.stg_fato_contas_receber(c_status);

-- Distribuição de categorias das contas a receber (1:N)
CREATE TABLE staging.stg_fato_contas_receber_categorias (
    id                          BIGSERIAL       PRIMARY KEY,
    id_empresa                  INTEGER         NOT NULL REFERENCES config.empresas(id),
    n_cod_titulo                BIGINT,
    c_cod_categoria             VARCHAR(50),
    n_percentual                NUMERIC(10,4),
    n_valor                     NUMERIC(18,2),
    dt_extracao                 TIMESTAMP       NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_stg_cr_cat_empresa ON staging.stg_fato_contas_receber_categorias(id_empresa);
CREATE INDEX idx_stg_cr_cat_titulo  ON staging.stg_fato_contas_receber_categorias(n_cod_titulo);

-- Distribuição de departamentos das contas a receber (1:N)
CREATE TABLE staging.stg_fato_contas_receber_departamentos (
    id                          BIGSERIAL       PRIMARY KEY,
    id_empresa                  INTEGER         NOT NULL REFERENCES config.empresas(id),
    n_cod_titulo                BIGINT,
    c_cod_departamento          VARCHAR(50),
    n_percentual                NUMERIC(10,4),
    n_valor                     NUMERIC(18,2),
    dt_extracao                 TIMESTAMP       NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_stg_cr_dep_empresa ON staging.stg_fato_contas_receber_departamentos(id_empresa);
CREATE INDEX idx_stg_cr_dep_titulo  ON staging.stg_fato_contas_receber_departamentos(n_cod_titulo);

-- =============================================================================
-- STAGING: LANÇAMENTOS CONTA CORRENTE
-- Fonte: API Omie - ListarLancamentosCC
-- =============================================================================
CREATE TABLE staging.stg_fato_lancamentos_cc (
    id                          BIGSERIAL       PRIMARY KEY,
    id_empresa                  INTEGER         NOT NULL REFERENCES config.empresas(id),
    -- Identificação
    n_cod_lanc                  BIGINT,
    n_cod_lanc_ctrl             BIGINT,
    -- Conta corrente
    n_cod_cc                    BIGINT,
    -- Datas
    d_data                      DATE,
    d_data_competencia          DATE,
    -- Descrição e tipo
    c_descricao                 VARCHAR(500),
    c_tipo                      VARCHAR(10),        -- ENT=Entrada, SAI=Saída
    c_status                    VARCHAR(20),
    -- Valor
    n_valor                     NUMERIC(18,2),
    -- Categorias e departamentos (armazenados como JSON para normalização posterior)
    json_categorias             TEXT,
    json_distribuicao           TEXT,
    -- Metadados
    dt_extracao                 TIMESTAMP       NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_stg_lcc_empresa ON staging.stg_fato_lancamentos_cc(id_empresa);
CREATE INDEX idx_stg_lcc_data    ON staging.stg_fato_lancamentos_cc(d_data);
CREATE INDEX idx_stg_lcc_cc      ON staging.stg_fato_lancamentos_cc(n_cod_cc);

-- Distribuição de categorias dos lançamentos CC (1:N)
CREATE TABLE staging.stg_fato_lancamentos_cc_categorias (
    id                          BIGSERIAL       PRIMARY KEY,
    id_empresa                  INTEGER         NOT NULL REFERENCES config.empresas(id),
    n_cod_lanc                  BIGINT,
    c_cod_categoria             VARCHAR(50),
    n_percentual                NUMERIC(10,4),
    n_valor                     NUMERIC(18,2),
    dt_extracao                 TIMESTAMP       NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_stg_lcc_cat_empresa ON staging.stg_fato_lancamentos_cc_categorias(id_empresa);
CREATE INDEX idx_stg_lcc_cat_lanc    ON staging.stg_fato_lancamentos_cc_categorias(n_cod_lanc);

-- Distribuição de departamentos dos lançamentos CC (1:N)
CREATE TABLE staging.stg_fato_lancamentos_cc_departamentos (
    id                          BIGSERIAL       PRIMARY KEY,
    id_empresa                  INTEGER         NOT NULL REFERENCES config.empresas(id),
    n_cod_lanc                  BIGINT,
    c_cod_departamento          VARCHAR(50),
    n_percentual                NUMERIC(10,4),
    n_valor                     NUMERIC(18,2),
    dt_extracao                 TIMESTAMP       NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_stg_lcc_dep_empresa ON staging.stg_fato_lancamentos_cc_departamentos(id_empresa);
CREATE INDEX idx_stg_lcc_dep_lanc    ON staging.stg_fato_lancamentos_cc_departamentos(n_cod_lanc);

-- =============================================================================
-- STAGING: MOVIMENTOS (Extrato detalhado)
-- Fonte: API Omie - ListarMovimentos
-- =============================================================================
CREATE TABLE staging.stg_fato_movimentos (
    id                          BIGSERIAL       PRIMARY KEY,
    id_empresa                  INTEGER         NOT NULL REFERENCES config.empresas(id),
    -- Identificação
    n_cod_movimento             BIGINT,
    c_tipo_documento            VARCHAR(50),
    n_num_documento             VARCHAR(60),
    -- Cliente/Fornecedor
    c_cpf_cnpj_cliente          VARCHAR(20),
    n_cod_cli_for               BIGINT,
    c_nome_cli_for              VARCHAR(200),
    -- Datas
    d_data_movimento            DATE,
    d_data_competencia          DATE,
    d_data_prevista             DATE,
    -- Valores
    n_valor_movimento           NUMERIC(18,2),
    -- Classificação
    c_desc_movimento            VARCHAR(500),
    c_cod_categoria             VARCHAR(50),
    c_cod_departamento          VARCHAR(50),
    n_cod_cc                    BIGINT,
    c_status                    VARCHAR(20),
    c_origem                    VARCHAR(20),        -- CP=Contas Pagar, CR=Contas Receber, CC=Conta Corrente
    -- Metadados
    dt_extracao                 TIMESTAMP       NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_stg_mov_empresa ON staging.stg_fato_movimentos(id_empresa);
CREATE INDEX idx_stg_mov_data    ON staging.stg_fato_movimentos(d_data_movimento);
CREATE INDEX idx_stg_mov_status  ON staging.stg_fato_movimentos(c_status);

-- =============================================================================
-- VIEW AUXILIAR: lista empresas ativas
-- =============================================================================
CREATE VIEW config.vw_empresas_ativas AS
SELECT id, nome_empresa, nome_fantasia, cnpj, omie_app_key
FROM config.empresas
WHERE ativo = TRUE
ORDER BY nome_empresa;

-- =============================================================================
-- FIM DO SCRIPT
-- =============================================================================
