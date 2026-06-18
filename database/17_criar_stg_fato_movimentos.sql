-- =============================================================================
-- PROJETO BI OMIE 2026
-- Script: 17_criar_stg_fato_movimentos.sql
-- Descrição: Staging dos Movimentos Financeiros (endpoint financas/mf -> ListarMovimentos).
--            Fonte da DATA REAL DE BAIXA (dDtPagamento) por título, inclusive em
--            baixas agrupadas (vários títulos quitados num único movimento bancário),
--            cenário em que o lançamento de conta corrente referencia apenas um dos
--            títulos e os "irmãos" ficam sem vínculo via ncodlanccp/ncodlanccr.
--
--            Granularidade: 1 linha por ocorrência de movimento (um título pode
--            aparecer em mais de uma linha: lançamento original + baixa). A view
--            unificada agrega por título tomando MAX(ddtpagamento).
-- =============================================================================

DROP TABLE IF EXISTS staging.stg_fato_movimentos CASCADE;

CREATE TABLE staging.stg_fato_movimentos (
    id              BIGSERIAL   PRIMARY KEY,
    id_empresa      INTEGER     NOT NULL REFERENCES config.empresas(id),
    -- Identificação do título
    ncodtitulo      BIGINT,                 -- = codigo_lancamento_omie de CP/CR
    ncodtitrepet    BIGINT,
    ccodcateg       VARCHAR(50),
    cgrupo          VARCHAR(40),            -- CONTA_A_PAGAR | CONTA_A_RECEBER ...
    cnatureza       VARCHAR(5),             -- P=Pagar | R=Receber
    cstatus         VARCHAR(20),            -- PAGO | RECEBIDO | A PAGAR ...
    ctipo           VARCHAR(20),
    corigem         VARCHAR(20),            -- MANP | BAXP | BAXR ...
    -- Datas (a chave do projeto: ddtpagamento = data real de baixa)
    ddtemissao      DATE,
    ddtvenc         DATE,
    ddtprevisao     DATE,
    ddtpagamento    DATE,
    ddtregistro     DATE,
    -- Relacionamentos
    ncodcc          BIGINT,
    ncodcliente     BIGINT,
    ccpfcnpjcliente VARCHAR(20),
    -- Medidas
    nvalortitulo    NUMERIC(18,2),
    nvalpago        NUMERIC(18,2),
    nvalaberto      NUMERIC(18,2),
    nvalliquido     NUMERIC(18,2),
    cliquidado      VARCHAR(5),
    -- Metadados
    dt_extracao     TIMESTAMP   NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_stg_mov_empresa     ON staging.stg_fato_movimentos(id_empresa);
CREATE INDEX idx_stg_mov_titulo      ON staging.stg_fato_movimentos(id_empresa, ncodtitulo);
CREATE INDEX idx_stg_mov_pagamento   ON staging.stg_fato_movimentos(ddtpagamento);
CREATE INDEX idx_stg_mov_natureza    ON staging.stg_fato_movimentos(cnatureza);
