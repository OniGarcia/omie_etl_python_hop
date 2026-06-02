-- =============================================================================
-- View: Saldo Atual por Conta Corrente
-- Calcula: saldo_inicial + soma de todos os lançamentos CC realizados
-- =============================================================================
CREATE OR REPLACE VIEW dw.vw_saldo_contas_correntes AS
WITH movimentos AS (
    SELECT
        id_empresa,
        ncodcc,
        SUM(CASE WHEN ctipo = 'ENT' THEN nvalorlanc ELSE -nvalorlanc END) AS total_movimentos
    FROM staging.stg_fato_lancamentos_cc
    GROUP BY id_empresa, ncodcc
)
SELECT
    cc.id_empresa,
    cc.n_cod_cc,
    cc.descricao,
    cc.codigo_banco,
    cc.numero_conta_corrente,
    cc.tipo,
    cc.saldo_inicial,
    COALESCE(m.total_movimentos, 0)                              AS total_movimentos,
    cc.saldo_inicial + COALESCE(m.total_movimentos, 0)          AS saldo_atual
FROM staging.stg_cad_contas_correntes cc
LEFT JOIN movimentos m
    ON cc.id_empresa = m.id_empresa
   AND cc.n_cod_cc   = m.ncodcc
WHERE cc.ativo = 'S';


-- =============================================================================
-- View: Evolução Diária do Saldo por Conta Corrente
-- Calcula: saldo_inicial + movimentos acumulados até cada dia
-- =============================================================================
CREATE OR REPLACE VIEW dw.vw_saldo_contas_correntes_diario AS
WITH movimentos_diarios AS (
    SELECT
        id_empresa,
        ncodcc,
        ddtlanc::DATE                                                            AS data_lancamento,
        SUM(CASE WHEN ctipo = 'ENT' THEN nvalorlanc ELSE -nvalorlanc END)       AS movimento_dia
    FROM staging.stg_fato_lancamentos_cc
    GROUP BY id_empresa, ncodcc, ddtlanc::DATE
),
saldo_acumulado AS (
    SELECT
        id_empresa,
        ncodcc,
        data_lancamento,
        movimento_dia,
        SUM(movimento_dia) OVER (
            PARTITION BY id_empresa, ncodcc
            ORDER BY data_lancamento
            ROWS UNBOUNDED PRECEDING
        )                                                                        AS movimentos_acumulados
    FROM movimentos_diarios
)
SELECT
    cc.id_empresa,
    cc.n_cod_cc,
    cc.descricao,
    cc.codigo_banco,
    cc.numero_conta_corrente,
    sa.data_lancamento,
    sa.movimento_dia,
    cc.saldo_inicial + sa.movimentos_acumulados                                  AS saldo_final_dia
FROM saldo_acumulado sa
JOIN staging.stg_cad_contas_correntes cc
    ON sa.id_empresa = cc.id_empresa
   AND sa.ncodcc     = cc.n_cod_cc;
