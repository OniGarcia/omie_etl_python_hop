WITH pagar AS (
    SELECT
        p.id_empresa,
        pc.codigo_categoria,
        SUM(pc.valor) AS total_pagar
    FROM staging.stg_fato_contas_pagar p
    JOIN staging.stg_fato_lancamentos_cc lcc
        ON lcc.id_empresa  = p.id_empresa
       AND lcc.ncodlanccp  = p.codigo_lancamento_omie
    JOIN staging.stg_fato_contas_pagar_categorias pc
        ON pc.id_empresa             = p.id_empresa
       AND pc.codigo_lancamento_omie = p.codigo_lancamento_omie
    WHERE lcc.ddtlanc >= '2026-01-01'
      AND lcc.ddtlanc  < '2026-02-01'
    GROUP BY p.id_empresa, pc.codigo_categoria
),
receber AS (
    SELECT
        r.id_empresa,
        rc.codigo_categoria,
        SUM(rc.valor) AS total_receber
    FROM staging.stg_fato_contas_receber r
    JOIN staging.stg_fato_lancamentos_cc lcc
        ON lcc.id_empresa  = r.id_empresa
       AND lcc.ncodlanccr  = r.codigo_lancamento_omie
    JOIN staging.stg_fato_contas_receber_categorias rc
        ON rc.id_empresa             = r.id_empresa
       AND rc.codigo_lancamento_omie = r.codigo_lancamento_omie
    WHERE lcc.ddtlanc >= '2026-01-01'
      AND lcc.ddtlanc  < '2026-02-01'
    GROUP BY r.id_empresa, rc.codigo_categoria
),
unificado AS (
    SELECT
        COALESCE(p.id_empresa,       r.id_empresa)       AS id_empresa,
        COALESCE(p.codigo_categoria, r.codigo_categoria) AS codigo_categoria,
        COALESCE(p.total_pagar,   0)                     AS total_pagar,
        COALESCE(r.total_receber, 0)                     AS total_receber
    FROM pagar p
    FULL OUTER JOIN receber r
        ON r.id_empresa       = p.id_empresa
       AND r.codigo_categoria = p.codigo_categoria
)
SELECT
    e.nome_empresa           AS empresa,
    u.codigo_categoria,
    c.descricao              AS categoria,
    c.tipo_categoria,
    c.natureza,
    u.total_pagar,
    u.total_receber,
    (u.total_receber - u.total_pagar) AS saldo
FROM unificado u
JOIN config.empresas e
    ON e.id = u.id_empresa
LEFT JOIN staging.stg_cad_categorias c
    ON c.id_empresa = u.id_empresa
   AND c.codigo     = u.codigo_categoria
ORDER BY e.nome_empresa, u.codigo_categoria;
