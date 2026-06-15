-- =============================================================================
-- PROJETO BI OMIE 2026
-- Script: 14_query_dre_mensal.sql
-- Descrição: Query de referência para o DRE — Demonstrativo de Resultado
--            Retorna movimentos liquidados por (natureza, grupo, categoria,
--            entidade, ano_mes) com suporte a filtro de Centro de Custo.
-- Uso: base para o endpoint /api/dre em python_etl/app.py
-- Parâmetros (substituir antes de executar manualmente):
--   :sk_ini         — data inicial no formato YYYYMMDD (ex: 20260101)
--   :sk_fim         — data final  no formato YYYYMMDD (ex: 20261231)
--   :cod_depart     — código do departamento (NULL para todos)
-- =============================================================================

-- -------------------------------------------------------
-- 1) SALDO INICIAL ACUMULADO
--    Soma de todas as transações liquidadas ANTES do período.
--    Receitas somam (+), Despesas subtraem (-).
-- -------------------------------------------------------
SELECT
    COALESCE(
        SUM(
            CASE WHEN f.natureza = 'C' THEN  f.valor_rateio
                 WHEN f.natureza = 'D' THEN -f.valor_rateio
            END
        ),
        0
    ) AS saldo_inicial
FROM dw.fact_movimento_financeiro f
WHERE f.sk_data_pagamento < :sk_ini
  AND f.is_transferencia = 'N'
  AND f.status_titulo IN ('LIQUIDADO', 'RECEBIDO', 'PAGO')
  AND (:cod_depart IS NULL OR f.cod_departamento = :cod_depart);


-- -------------------------------------------------------
-- 2) MOVIMENTOS DO PERÍODO — BASE DO DRE
--    Hierarquia:
--      natureza (C=Receita / D=Despesa)
--      → grupo (categoria pai via categoria_superior)
--      → categoria filha
--      → entidade (fornecedor/cliente)
--    Agregação por mês (YYYYMM extraído do sk_data_pagamento YYYYMMDD).
-- -------------------------------------------------------
SELECT
    f.natureza,

    -- Grupo: descrição da categoria-pai (totalizadora)
    COALESCE(
        (
            SELECT s_pai.descricao
            FROM   staging.stg_cad_categorias s_pai
            WHERE  s_pai.codigo      = s_filho.categoria_superior
              AND  s_pai.id_empresa  = f.id_empresa
            LIMIT  1
        ),
        c.tipo_categoria,   -- fallback: tipo_categoria da própria categoria
        c.descricao         -- último recurso: própria descrição
    )                                               AS descricao_grupo,

    -- Código da categoria-pai (para agrupar corretamente)
    COALESCE(s_filho.categoria_superior, f.cod_categoria)
                                                    AS cod_grupo,

    -- Categoria filha
    f.cod_categoria,
    c.descricao                                     AS descricao_categoria,

    -- Entidade (fornecedor ou cliente)
    f.cod_entidade,
    COALESCE(e.nome_fantasia, e.razao_social, f.cod_entidade)
                                                    AS nome_entidade,

    -- Mês no formato YYYYMM
    (f.sk_data_pagamento / 100)::INTEGER            AS ano_mes,

    SUM(f.valor_rateio)                             AS total

FROM dw.fact_movimento_financeiro f

LEFT JOIN dw.dim_categoria c
       ON c.sk_categoria = f.sk_categoria

LEFT JOIN dw.dim_entidade e
       ON e.sk_entidade = f.sk_entidade

-- Busca o registro de staging para obter categoria_superior
LEFT JOIN LATERAL (
    SELECT s.categoria_superior
    FROM   staging.stg_cad_categorias s
    WHERE  s.codigo     = f.cod_categoria
      AND  s.id_empresa = f.id_empresa
    LIMIT  1
) s_filho ON TRUE

WHERE
    f.sk_data_pagamento BETWEEN :sk_ini AND :sk_fim
    AND f.is_transferencia = 'N'
    AND f.status_titulo IN ('LIQUIDADO', 'RECEBIDO', 'PAGO')
    AND (:cod_depart IS NULL OR f.cod_departamento = :cod_depart)

GROUP BY
    f.natureza,
    s_filho.categoria_superior,
    c.tipo_categoria,
    c.descricao,
    f.cod_categoria,
    f.cod_entidade,
    e.nome_fantasia,
    e.razao_social,
    (f.sk_data_pagamento / 100)::INTEGER,
    f.id_empresa

ORDER BY
    f.natureza DESC,    -- 'C' (Receita) antes de 'D' (Despesa)
    cod_grupo,
    f.cod_categoria,
    ano_mes;
