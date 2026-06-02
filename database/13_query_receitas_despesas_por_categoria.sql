-- =============================================================================
-- PROJETO BI OMIE 2026
-- Script: 13_query_receitas_despesas_por_categoria.sql
-- Descrição: Total de receitas e despesas por categoria em um mês específico
-- Parâmetro: ajuste sk_data_ini e sk_data_fim conforme o mês desejado
-- =============================================================================

SELECT
    CASE
        WHEN f.natureza = 'C' THEN 'RECEITA'
        WHEN f.natureza = 'D' THEN 'DESPESA'
    END                                     AS tipo,
    f.cod_categoria,
    c.descricao                             AS descricao_categoria,
    c.tipo_categoria,
    SUM(f.valor_rateio)                     AS total
FROM dw.fact_movimento_financeiro f
LEFT JOIN dw.dim_categoria c ON c.sk_categoria = f.sk_categoria
WHERE COALESCE(f.sk_data_pagamento, f.sk_data_vencimento) BETWEEN 20260101 AND 20260131
  AND f.is_transferencia = 'N'
  AND f.status_titulo IN ('LIQUIDADO', 'RECEBIDO', 'PAGO')
GROUP BY
    f.natureza,
    f.cod_categoria,
    c.descricao,
    c.tipo_categoria
ORDER BY
    tipo,
    total DESC;
