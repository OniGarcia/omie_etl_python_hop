-- =============================================================================
-- PROJETO BI OMIE 2026
-- Script: 10_criar_dw_fact_movimento_financeiro.sql
-- Descrição: Cria schema dw, dimensões e tabela fato fact_movimento_financeiro
-- Depende de: scripts 01 a 08 (staging já criado)
-- Execute: psql -U postgres -d bi_omie -f 10_criar_dw_fact_movimento_financeiro.sql
--
-- NOTA: Este script usa as tabelas staging recriadas pelos scripts 04-08.
--       As colunas de sk_data são INTEGER no formato YYYYMMDD (mesmo padrão
--       de dim_data.sk_data), sem FK forçada para suportar datas fora do range.
-- =============================================================================

-- =====================
-- SCHEMA
-- =====================
CREATE SCHEMA IF NOT EXISTS dw;

-- =====================
-- dim_empresa
-- =====================
DROP TABLE IF EXISTS dw.dim_empresa CASCADE;
CREATE TABLE dw.dim_empresa (
    sk_empresa      SERIAL          PRIMARY KEY,
    id_empresa      INTEGER         NOT NULL UNIQUE,
    nome_empresa    VARCHAR(200),
    nome_fantasia   VARCHAR(200),
    cnpj            VARCHAR(18),
    ativo           BOOLEAN,
    dt_carga        TIMESTAMP       DEFAULT NOW()
);

-- =====================
-- dim_data (2022-01-01 a 2030-12-31)
-- sk_data = YYYYMMDD como INTEGER para lookup direto sem JOIN
-- =====================
DROP TABLE IF EXISTS dw.dim_data CASCADE;
CREATE TABLE dw.dim_data (
    sk_data             INTEGER     PRIMARY KEY,
    data_completa       DATE        NOT NULL UNIQUE,
    ano                 SMALLINT,
    semestre            SMALLINT,
    trimestre           SMALLINT,
    mes                 SMALLINT,
    nome_mes            VARCHAR(20),
    semana_ano          SMALLINT,
    dia                 SMALLINT,
    dia_semana          SMALLINT,
    nome_dia_semana     VARCHAR(20),
    is_fim_semana       BOOLEAN
);

INSERT INTO dw.dim_data (
    sk_data, data_completa, ano, semestre, trimestre, mes, nome_mes,
    semana_ano, dia, dia_semana, nome_dia_semana, is_fim_semana
)
SELECT
    TO_CHAR(d, 'YYYYMMDD')::INTEGER,
    d,
    EXTRACT(YEAR    FROM d)::SMALLINT,
    CASE WHEN EXTRACT(MONTH FROM d) <= 6 THEN 1 ELSE 2 END::SMALLINT,
    EXTRACT(QUARTER FROM d)::SMALLINT,
    EXTRACT(MONTH   FROM d)::SMALLINT,
    TO_CHAR(d, 'TMMonth'),
    EXTRACT(WEEK    FROM d)::SMALLINT,
    EXTRACT(DAY     FROM d)::SMALLINT,
    EXTRACT(DOW     FROM d)::SMALLINT,
    TO_CHAR(d, 'TMDay'),
    EXTRACT(DOW FROM d) IN (0, 6)
FROM generate_series('2022-01-01'::DATE, '2030-12-31'::DATE, '1 day'::INTERVAL) d;

-- =====================
-- dim_categoria
-- =====================
DROP TABLE IF EXISTS dw.dim_categoria CASCADE;
CREATE TABLE dw.dim_categoria (
    sk_categoria        SERIAL          PRIMARY KEY,
    cod_categoria       TEXT            NOT NULL UNIQUE,
    descricao           TEXT,
    tipo_categoria      TEXT,
    natureza            TEXT,
    dt_carga            TIMESTAMP       DEFAULT NOW()
);

-- =====================
-- dim_departamento
-- =====================
DROP TABLE IF EXISTS dw.dim_departamento CASCADE;
CREATE TABLE dw.dim_departamento (
    sk_departamento     SERIAL          PRIMARY KEY,
    cod_departamento    VARCHAR(50)     NOT NULL UNIQUE,
    descricao           VARCHAR(500),
    estrutura           VARCHAR(200),
    dt_carga            TIMESTAMP       DEFAULT NOW()
);

-- =====================
-- dim_entidade (clientes e fornecedores)
-- =====================
DROP TABLE IF EXISTS dw.dim_entidade CASCADE;
CREATE TABLE dw.dim_entidade (
    sk_entidade         SERIAL          PRIMARY KEY,
    cod_entidade        VARCHAR(60)     NOT NULL UNIQUE,
    nome_fantasia       VARCHAR(200),
    razao_social        VARCHAR(200),
    cnpj_cpf            VARCHAR(20),
    cidade              VARCHAR(100),
    estado              VARCHAR(2),
    dt_carga            TIMESTAMP       DEFAULT NOW()
);

-- =====================
-- dim_conta_corrente
-- =====================
DROP TABLE IF EXISTS dw.dim_conta_corrente CASCADE;
CREATE TABLE dw.dim_conta_corrente (
    sk_conta_corrente   SERIAL          PRIMARY KEY,
    cod_conta_corrente  VARCHAR(50)     NOT NULL UNIQUE,
    descricao           VARCHAR(200),
    codigo_banco        VARCHAR(10),
    numero_conta        VARCHAR(30),
    tipo                VARCHAR(50),
    considerar          BOOLEAN         NOT NULL DEFAULT TRUE,
    dt_carga            TIMESTAMP       DEFAULT NOW()
);

-- =====================
-- fact_movimento_financeiro
-- Granularidade: (empresa, origem, lancamento, categoria)
-- =====================
DROP TABLE IF EXISTS dw.fact_movimento_financeiro CASCADE;
CREATE TABLE dw.fact_movimento_financeiro (
    id                      BIGSERIAL       PRIMARY KEY,

    -- Chaves de negócio
    id_empresa              INTEGER         NOT NULL,
    origem                  VARCHAR(2)      NOT NULL,       -- CP | CR | CC
    codigo_lancamento_omie  BIGINT          NOT NULL,

    -- Surrogate Keys (INTEGER YYYYMMDD para datas — sem FK para suportar datas fora do range da dim_data)
    sk_empresa              INTEGER         REFERENCES dw.dim_empresa(sk_empresa),
    sk_data_emissao         INTEGER,
    sk_data_vencimento      INTEGER,
    sk_data_pagamento       INTEGER,
    sk_categoria            INTEGER         REFERENCES dw.dim_categoria(sk_categoria),
    sk_departamento         INTEGER         REFERENCES dw.dim_departamento(sk_departamento),
    sk_entidade             INTEGER         REFERENCES dw.dim_entidade(sk_entidade),
    sk_conta_corrente       INTEGER         REFERENCES dw.dim_conta_corrente(sk_conta_corrente),

    -- Códigos naturais (análise direta sem JOIN às dimensões)
    cod_categoria           TEXT,
    cod_departamento        TEXT,
    cod_entidade            VARCHAR(60),
    cod_conta_corrente      VARCHAR(50),

    -- Classificação do movimento
    tipo_movimento          VARCHAR(20),    -- PAGAR | RECEBER | CC_ENTRADA | CC_SAIDA | TRANSFERENCIA
    natureza                CHAR(1),        -- D=Débito | C=Crédito
    status_titulo           VARCHAR(20),
    is_transferencia        CHAR(1)         NOT NULL DEFAULT 'N',

    -- Datas
    data_emissao            DATE,
    data_vencimento         DATE,
    data_pagamento          DATE,

    -- Medidas
    valor_documento         NUMERIC(18,2),
    valor_rateio            NUMERIC(18,2),
    percentual_rateio       NUMERIC(10,4),

    -- Metadados
    dt_carga                TIMESTAMP       DEFAULT NOW()
);

-- Índices de performance
CREATE INDEX idx_fmf_empresa        ON dw.fact_movimento_financeiro(id_empresa);
CREATE INDEX idx_fmf_origem         ON dw.fact_movimento_financeiro(origem);
CREATE INDEX idx_fmf_sk_empresa     ON dw.fact_movimento_financeiro(sk_empresa);
CREATE INDEX idx_fmf_sk_data_venc   ON dw.fact_movimento_financeiro(sk_data_vencimento);
CREATE INDEX idx_fmf_sk_data_pag    ON dw.fact_movimento_financeiro(sk_data_pagamento);
CREATE INDEX idx_fmf_sk_categoria   ON dw.fact_movimento_financeiro(sk_categoria);
CREATE INDEX idx_fmf_sk_entidade    ON dw.fact_movimento_financeiro(sk_entidade);
CREATE INDEX idx_fmf_sk_cc          ON dw.fact_movimento_financeiro(sk_conta_corrente);
CREATE INDEX idx_fmf_status         ON dw.fact_movimento_financeiro(status_titulo);
CREATE INDEX idx_fmf_data_venc      ON dw.fact_movimento_financeiro(data_vencimento);
CREATE INDEX idx_fmf_data_pag       ON dw.fact_movimento_financeiro(data_pagamento);

-- Chave natural composta (evita duplicatas no full reload)
CREATE UNIQUE INDEX idx_fmf_natural_key ON dw.fact_movimento_financeiro
    (id_empresa, origem, codigo_lancamento_omie, COALESCE(cod_categoria, ''));
