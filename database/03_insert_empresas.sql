-- =============================================================================
-- PROJETO BI OMIE 2026
-- Script: 03_insert_empresas.sql
-- Descrição: Carga inicial de empresas na tabela config.empresas
-- Execute: psql -U postgres -d bi_omie -f 03_insert_empresas.sql
-- =============================================================================

-- Adiciona coluna codigo_empresa_omie caso não exista
ALTER TABLE config.empresas ADD COLUMN IF NOT EXISTS codigo_empresa_omie VARCHAR(50);

-- -----------------------------------------------------------------------------
-- Empresas cadastradas
-- -----------------------------------------------------------------------------
INSERT INTO config.empresas (id, nome_empresa, omie_app_key, omie_app_secret, codigo_empresa_omie, ativo)
VALUES
    (1, 'BC MAIS', '6980025353301', '5bdd9e4cbf4774cba1612095ca029443', NULL, TRUE)
ON CONFLICT (id) DO UPDATE SET
    nome_empresa        = EXCLUDED.nome_empresa,
    omie_app_key        = EXCLUDED.omie_app_key,
    omie_app_secret     = EXCLUDED.omie_app_secret,
    codigo_empresa_omie = EXCLUDED.codigo_empresa_omie,
    ativo               = EXCLUDED.ativo;

-- Para adicionar novas empresas, copie o bloco acima com novo id e credenciais

SELECT id, nome_empresa, omie_app_key, ativo FROM config.empresas ORDER BY id;
