-- =============================================================================
-- PROJETO BI OMIE 2026
-- Script: 12_sp_load_fact_movimento_financeiro.sql
-- Descrição: Stored Procedure de carga Full Reload da fact_movimento_financeiro
-- Depende de: scripts 10 e 11 (dw criado, view criada)
-- Execute: psql -U postgres -d bi_omie -f 12_sp_load_fact_movimento_financeiro.sql
--
-- Uso:  CALL dw.sp_load_fact_movimento_financeiro();
--
-- Sequência de execução:
--   1. Refresh das dimensões via UPSERT (não destrutivo)
--   2. TRUNCATE da tabela fato (Full Reload desde 01/01/2022)
--   3. INSERT a partir da view unificada com lookup de surrogate keys
-- =============================================================================

CREATE OR REPLACE PROCEDURE dw.sp_load_fact_movimento_financeiro()
LANGUAGE plpgsql AS $$
DECLARE
    v_rows_inserted BIGINT;
BEGIN

    RAISE NOTICE '[%] Iniciando sp_load_fact_movimento_financeiro', NOW();

    -- =========================================================================
    -- 1. REFRESH DAS DIMENSÕES
    -- UPSERT: insere novos registros e atualiza os existentes.
    -- Não faz DELETE para preservar SKs de entidades removidas no Omie.
    -- =========================================================================

    -- dim_empresa (fonte: config.empresas)
    INSERT INTO dw.dim_empresa (id_empresa, nome_empresa, nome_fantasia, cnpj, ativo)
    SELECT id, nome_empresa, nome_fantasia, cnpj, ativo
    FROM   config.empresas
    ON CONFLICT (id_empresa) DO UPDATE
        SET nome_empresa  = EXCLUDED.nome_empresa,
            nome_fantasia = EXCLUDED.nome_fantasia,
            cnpj          = EXCLUDED.cnpj,
            ativo         = EXCLUDED.ativo,
            dt_carga      = NOW();

    RAISE NOTICE '[%] dim_empresa: OK', NOW();

    -- dim_categoria (fonte: staging.stg_cad_categorias)
    -- DISTINCT ON garante 1 linha por código, priorizando a extração mais recente
    INSERT INTO dw.dim_categoria (cod_categoria, descricao, tipo_categoria, natureza)
    SELECT DISTINCT ON (codigo)
        codigo, descricao, tipo_categoria, natureza
    FROM   staging.stg_cad_categorias
    WHERE  codigo IS NOT NULL
    ORDER  BY codigo, dt_extracao DESC
    ON CONFLICT (cod_categoria) DO UPDATE
        SET descricao      = EXCLUDED.descricao,
            tipo_categoria = EXCLUDED.tipo_categoria,
            natureza       = EXCLUDED.natureza,
            dt_carga       = NOW();

    RAISE NOTICE '[%] dim_categoria: OK', NOW();

    -- dim_departamento (fonte: staging.stg_cad_departamentos)
    INSERT INTO dw.dim_departamento (cod_departamento, descricao, estrutura)
    SELECT DISTINCT ON (codigo)
        codigo, descricao, estrutura
    FROM   staging.stg_cad_departamentos
    WHERE  codigo IS NOT NULL
    ORDER  BY codigo, dt_extracao DESC
    ON CONFLICT (cod_departamento) DO UPDATE
        SET descricao  = EXCLUDED.descricao,
            estrutura  = EXCLUDED.estrutura,
            dt_carga   = NOW();

    RAISE NOTICE '[%] dim_departamento: OK', NOW();

    -- dim_entidade — clientes/fornecedores (fonte: staging.stg_cad_clientes)
    INSERT INTO dw.dim_entidade (cod_entidade, nome_fantasia, razao_social, cnpj_cpf, cidade, estado)
    SELECT DISTINCT ON (codigo_cliente_omie)
        codigo_cliente_omie::VARCHAR,
        nome_fantasia, razao_social, cnpj_cpf, cidade, estado
    FROM   staging.stg_cad_clientes
    WHERE  codigo_cliente_omie IS NOT NULL
    ORDER  BY codigo_cliente_omie, dt_extracao DESC
    ON CONFLICT (cod_entidade) DO UPDATE
        SET nome_fantasia = EXCLUDED.nome_fantasia,
            razao_social  = EXCLUDED.razao_social,
            cnpj_cpf      = EXCLUDED.cnpj_cpf,
            cidade        = EXCLUDED.cidade,
            estado        = EXCLUDED.estado,
            dt_carga      = NOW();

    RAISE NOTICE '[%] dim_entidade: OK', NOW();

    -- dim_conta_corrente (fonte: staging.stg_cad_contas_correntes)
    INSERT INTO dw.dim_conta_corrente (cod_conta_corrente, descricao, codigo_banco, numero_conta, tipo)
    SELECT DISTINCT ON (n_cod_cc)
        n_cod_cc::VARCHAR,
        descricao, codigo_banco, numero_conta_corrente, tipo
    FROM   staging.stg_cad_contas_correntes
    WHERE  n_cod_cc IS NOT NULL
    ORDER  BY n_cod_cc, dt_extracao DESC
    ON CONFLICT (cod_conta_corrente) DO UPDATE
        SET descricao    = EXCLUDED.descricao,
            codigo_banco = EXCLUDED.codigo_banco,
            numero_conta = EXCLUDED.numero_conta,
            tipo         = EXCLUDED.tipo,
            dt_carga     = NOW();

    RAISE NOTICE '[%] dim_conta_corrente: OK', NOW();

    -- =========================================================================
    -- 2. FULL RELOAD DA TABELA FATO
    -- =========================================================================
    TRUNCATE TABLE dw.fact_movimento_financeiro RESTART IDENTITY;

    RAISE NOTICE '[%] fact_movimento_financeiro truncada (Full Reload)', NOW();

    -- =========================================================================
    -- 3. INSERÇÃO COM LOOKUP DE SURROGATE KEYS
    --
    -- sk_data_*: calculado como TO_CHAR(date,'YYYYMMDD')::INTEGER — mesmo
    --            formato de dim_data.sk_data, dispensando JOIN à dim_data.
    -- sk_*:      lookup via LEFT JOIN às dimensões pelo código natural.
    --            LEFT JOIN preserva linhas mesmo se a dimensão ainda não
    --            tiver o código (ex: categoria nova não extraída no cad.).
    -- =========================================================================
    INSERT INTO dw.fact_movimento_financeiro (
        id_empresa,
        origem,
        codigo_lancamento_omie,
        sk_empresa,
        sk_data_emissao,
        sk_data_vencimento,
        sk_data_pagamento,
        sk_categoria,
        sk_departamento,
        sk_entidade,
        sk_conta_corrente,
        cod_categoria,
        cod_departamento,
        cod_entidade,
        cod_conta_corrente,
        tipo_movimento,
        natureza,
        status_titulo,
        is_transferencia,
        data_emissao,
        data_vencimento,
        data_pagamento,
        valor_documento,
        valor_rateio,
        percentual_rateio,
        dt_carga
    )
    SELECT
        v.id_empresa,
        v.origem,
        v.codigo_lancamento_omie,
        -- Surrogate Keys
        de.sk_empresa,
        TO_CHAR(v.data_emissao,    'YYYYMMDD')::INTEGER     AS sk_data_emissao,
        TO_CHAR(v.data_vencimento, 'YYYYMMDD')::INTEGER     AS sk_data_vencimento,
        TO_CHAR(v.data_pagamento,  'YYYYMMDD')::INTEGER     AS sk_data_pagamento,
        dc.sk_categoria,
        dd.sk_departamento,
        den.sk_entidade,
        dcc.sk_conta_corrente,
        -- Códigos naturais
        v.cod_categoria,
        v.cod_departamento,
        v.cod_entidade,
        v.cod_conta_corrente,
        -- Atributos
        v.tipo_movimento,
        v.natureza,
        v.status_titulo,
        v.is_transferencia,
        -- Datas
        v.data_emissao,
        v.data_vencimento,
        v.data_pagamento,
        -- Medidas
        v.valor_documento,
        v.valor_rateio,
        v.percentual_rateio,
        NOW()
    FROM dw.vw_movimento_financeiro_unificado v
    LEFT JOIN dw.dim_empresa        de  ON de.id_empresa         = v.id_empresa
    LEFT JOIN dw.dim_categoria      dc  ON dc.cod_categoria       = v.cod_categoria
    LEFT JOIN dw.dim_departamento   dd  ON dd.cod_departamento    = v.cod_departamento
    LEFT JOIN dw.dim_entidade       den ON den.cod_entidade       = v.cod_entidade
    LEFT JOIN dw.dim_conta_corrente dcc ON dcc.cod_conta_corrente = v.cod_conta_corrente
    ON CONFLICT (id_empresa, origem, codigo_lancamento_omie, COALESCE(cod_categoria, ''))
    DO NOTHING;

    GET DIAGNOSTICS v_rows_inserted = ROW_COUNT;

    RAISE NOTICE '[%] Carga concluída. Linhas inseridas: %', NOW(), v_rows_inserted;

END;
$$;

-- =============================================================================
-- Verificação pós-carga (execute manualmente para validar)
-- =============================================================================
-- CALL dw.sp_load_fact_movimento_financeiro();
--
-- SELECT origem, tipo_movimento, COUNT(*) AS qtd, SUM(valor_rateio) AS total
-- FROM   dw.fact_movimento_financeiro
-- GROUP  BY origem, tipo_movimento
-- ORDER  BY origem, tipo_movimento;
