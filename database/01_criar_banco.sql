-- =============================================================================
-- PROJETO BI OMIE 2026
-- Script: 01_criar_banco.sql
-- Descrição: Criação do banco de dados e schema principal
-- =============================================================================
-- Execute como superusuário (postgres) antes de rodar os demais scripts
-- Exemplo: psql -U postgres -f 01_criar_banco.sql

-- Cria o banco (desconecte outros clientes antes se necessário)
SELECT pg_terminate_backend(pid)
FROM pg_stat_activity
WHERE datname = 'bi_omie' AND pid <> pg_backend_pid();

DROP DATABASE IF EXISTS bi_omie;
CREATE DATABASE bi_omie
    WITH OWNER = postgres
    ENCODING = 'UTF8'
    LC_COLLATE = 'Portuguese_Brazil.1252'
    LC_CTYPE = 'Portuguese_Brazil.1252'
    TEMPLATE = template0;

COMMENT ON DATABASE bi_omie IS 'Data Warehouse OMIE - Multi-empresa';
