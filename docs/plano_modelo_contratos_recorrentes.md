# Plano de Implementação — Mapeamento e Projeção de Contratos Recorrentes

Este plano descreve detalhadamente a estratégia para extrair os dados de **Contratos de Serviço Recorrentes** da API Omie, carregá-los no Staging e projetar as **Provisões de Receitas Futuras** dentro do Data Warehouse (DW).

---

## 1. Visão Geral da Arquitetura

Como o Omie não gera títulos financeiros (`Contas a Receber`) para meses futuros antes do faturamento real do contrato, a solução consiste em extrair as definições dos contratos ativos e **projetar matematicamente as parcelas futuras** no banco de dados do DW.

```
┌────────────────────────┐
│     API Omie           │  -> servicos/contrato/ListarContratos
└──────────┬─────────────┘
           │ (ETL Python)
           ▼
┌────────────────────────┐
│     Staging PostgreSQL │  -> staging.stg_fato_contratos
└──────────┬─────────────┘
           │ (SQL Transform / CROSS JOIN LATERAL / generate_series)
           ▼
┌────────────────────────┐
│   Data Warehouse (DW)  │  -> dw.fact_previsao_faturamento (ou fact_movimento_financeiro)
└────────────────────────┘
```

---

## 2. Etapa 1: Extração e Staging (Python ETL)

### 2.1. Criação das Tabelas de Staging no PostgreSQL

Devemos criar as tabelas para armazenar o cabeçalho do contrato, seus departamentos (rateio) e itens de serviço.

```sql
-- Tabela principal de contratos
CREATE TABLE staging.stg_fato_contratos (
    id_empresa INTEGER NOT NULL,
    codigo_contrato_omie BIGINT NOT NULL,
    codigo_contrato_integracao VARCHAR(100),
    numero_contrato VARCHAR(50),
    codigo_cliente BIGINT,
    data_inicio DATE NOT NULL,              -- dVigInicial da API
    data_fim DATE,                          -- dVigFinal da API
    dia_faturamento INTEGER NOT NULL,       -- nDiaFat da API (ex: 5, 10, 15)
    periodicidade VARCHAR(2) NOT NULL,      -- cPeriodicidade (M=Mensal, A=Anual, etc.)
    status_contrato VARCHAR(2) NOT NULL,    -- cStatus (A=Ativo, S=Suspenso, C=Cancelado)
    valor_mensal NUMERIC(15, 2) NOT NULL,   -- nValUnit ou soma dos itens
    json_departamentos JSONB,
    json_itens JSONB,
    dt_extracao TIMESTAMP DEFAULT NOW(),
    CONSTRAINT pk_stg_fato_contratos PRIMARY KEY (id_empresa, codigo_contrato_omie)
);

-- Tabela filha para rateio por departamento
CREATE TABLE staging.stg_fato_contratos_departamentos (
    id_empresa INTEGER NOT NULL,
    codigo_contrato_omie BIGINT NOT NULL,
    codigo_departamento VARCHAR(20) NOT NULL,
    descricao_departamento VARCHAR(100),
    percentual_rateio NUMERIC(5, 2) NOT NULL,
    valor_rateio NUMERIC(15, 2) NOT NULL,
    CONSTRAINT pk_stg_fato_contratos_dept PRIMARY KEY (id_empresa, codigo_contrato_omie, codigo_departamento)
);
```

### 2.2. Desenvolvimento do Extrator Python

Será criado o arquivo `python_etl/extractors/contratos.py` estendendo `BaseExtractor`.

```python
# python_etl/extractors/contratos.py
from extractors.base import BaseExtractor
import json

class ContratosExtractor(BaseExtractor):
    def fetch(self, filtro: dict = None) -> list:
        # endpoint: servicos/contrato
        # call_name: ListarContratos
        # list_key: contrato_cadastro
        extra_params = {"apenas_importado_api": "N"}
        return self.client.fetch_paginated(
            endpoint="servicos/contrato",
            call_name="ListarContratos",
            list_key="contrato_cadastro",
            extra_params=extra_params
        )

    def clean_staging(self, cursor):
        cursor.execute("DELETE FROM staging.stg_fato_contratos_departamentos WHERE id_empresa = %s", (self.company_id,))
        cursor.execute("DELETE FROM staging.stg_fato_contratos WHERE id_empresa = %s", (self.company_id,))

    def save(self, cursor, raw_records: list) -> int:
        if not raw_records:
            return 0
            
        db_contratos = []
        db_departamentos = []
        
        for record in raw_records:
            cabecalho = record.get("cabecalho", {})
            codigo_contrato = cabecalho.get("nCodContrato")
            if not codigo_contrato:
                continue
                
            # Parsing dos campos
            # Ex: cabecalho.get("dVigInicial"), cabecalho.get("dVigFinal"), etc.
            # Gravação em lote com execute_values...
            
        # Execução das queries de inserção...
        return len(db_contratos)
```

---

## 3. Etapa 2: Lógica de Projeção no DW (SQL)

A projeção de faturamento futuro gerará linhas virtuais para cada mês/vencimento que está entre o mês atual (ou `data_inicio` do contrato) e o `data_fim` (ou uma janela máxima configurável, ex: 12 ou 24 meses caso o contrato seja indeterminado).

### 3.1. Abordagem A: Nova Tabela Fato Dedicada (Recomendada)
Para evitar misturar dados reais/contábeis com projeções simuladas de longo prazo, criamos uma tabela fato separada: `dw.fact_previsao_faturamento_contratos`.

```sql
CREATE TABLE dw.fact_previsao_faturamento_contratos (
    id SERIAL PRIMARY KEY,
    sk_empresa INTEGER NOT NULL,
    sk_entidade INTEGER NOT NULL,          -- Cliente do contrato
    sk_categoria INTEGER NOT NULL,
    sk_departamento INTEGER NOT NULL,
    sk_data_previsao_faturamento INTEGER,  -- YYYYMMDD da previsão
    data_previsao_faturamento DATE NOT NULL,
    valor_previsto NUMERIC(15, 2) NOT NULL,
    numero_contrato VARCHAR(50),
    codigo_contrato_omie BIGINT NOT NULL,
    dt_carga TIMESTAMP DEFAULT NOW()
);
```

### 3.2. Script SQL de Geração das Provisões (Projeção em Lote)

Utilizamos o recurso `generate_series` do PostgreSQL associado a um `CROSS JOIN LATERAL` para expandir cada contrato de acordo com a periodicidade mensal até o término da vigência:

```sql
INSERT INTO dw.fact_previsao_faturamento_contratos (
    sk_empresa, sk_entidade, sk_categoria, sk_departamento,
    sk_data_previsao_faturamento, data_previsao_faturamento,
    valor_previsto, numero_contrato, codigo_contrato_omie
)
SELECT 
    e.sk_empresa,
    c.sk_entidade,
    c.sk_categoria,
    c.sk_departamento,
    TO_CHAR(proj.data_vencimento, 'YYYYMMDD')::INTEGER as sk_data_previsao_faturamento,
    proj.data_vencimento as data_previsao_faturamento,
    c.valor_rateio as valor_previsto,
    c.numero_contrato,
    c.codigo_contrato_omie
FROM (
    SELECT 
        con.id_empresa,
        con.numero_contrato,
        con.codigo_contrato_omie,
        -- Busca os Surrogate Keys na dimensão
        COALESCE(dim_cli.sk_entidade, 0) as sk_entidade,
        COALESCE(dim_cat.sk_categoria, 0) as sk_categoria,
        COALESCE(dim_dep.sk_departamento, 0) as sk_departamento,
        con.data_inicio,
        -- Se não tiver fim, projeta por até 24 meses à frente a partir de hoje
        COALESCE(con.data_fim, CURRENT_DATE + INTERVAL '24 months') as data_limite,
        con.dia_faturamento,
        -- Valor rateado por departamento
        (con.valor_mensal * COALESCE(dep.percentual_rateio, 100.0) / 100.0) as valor_rateio
    FROM staging.stg_fato_contratos con
    LEFT JOIN staging.stg_fato_contratos_departamentos dep 
        ON con.id_empresa = dep.id_empresa AND con.codigo_contrato_omie = dep.codigo_contrato_omie
    LEFT JOIN dw.dim_entidade dim_cli 
        ON con.id_empresa = dim_cli.id_empresa AND con.codigo_cliente = dim_cli.codigo_entidade_omie
    -- Adicionar joins para categorias e departamentos
    WHERE con.status_contrato = 'A' -- Apenas contratos Ativos
) c
CROSS JOIN LATERAL (
    -- Gera uma linha para cada mês entre o início e a data limite
    SELECT 
        LEAST(
            -- Garante que se o vencimento cair em dia inexistente (Ex: 30 de Fev), ajusta para o último dia do mês
            (date_trunc('month', mes.data_mes) + (c.dia_faturamento - 1) * INTERVAL '1 day')::date,
            (date_trunc('month', mes.data_mes) + INTERVAL '1 month' - INTERVAL '1 day')::date
        ) AS data_vencimento
    FROM generate_series(
        -- Começa a projetar a partir do mês atual para evitar provisões de datas passadas
        date_trunc('month', GREATEST(c.data_inicio, CURRENT_DATE))::date,
        date_trunc('month', c.data_limite)::date,
        '1 month'::interval
    ) AS mes(data_mes)
) proj
-- Evita duplicar registros para parcelas que já foram de fato faturadas e existem no Contas a Receber real
WHERE NOT EXISTS (
    SELECT 1 
    FROM dw.fact_movimento_financeiro real
    WHERE real.id_empresa = c.id_empresa
      AND real.origem = 'CR'
      -- Relaciona pelo código/vínculo do contrato e mês/ano de faturamento correspondente
      AND real.codigo_lancamento_omie = c.codigo_contrato_omie -- caso o ID de origem seja mapeado
      AND date_trunc('month', real.data_vencimento) = date_trunc('month', proj.data_vencimento)
);
```

---

## 4. Plano de Verificação

### 4.1. Testes Automatizados
* Criar teste em `python_etl/test_etl.py` mockando o payload de `ListarContratos`.
* Validar se a paginação de contratos manipula corretamente contratos com e sem data final (`dVigFinal` nulo).

### 4.2. Validação de Regras de Negócio (SQL)
* **Contrato sem fim (`dVigFinal` nulo):** Verificar se a projeção limita a 24 meses futuros para não estourar o limite de linhas.
* **Ajuste de Fevereiro/Meses Curtos:** Validar se um contrato com `dia_faturamento = 31` projeta o vencimento correto para `28/02` ou `29/02` em anos bissextos (a fórmula `LEAST` com `date_trunc` resolve isso).
* **Prevenção de Duplicidade:** Validar se a cláusula `NOT EXISTS` impede a sobreposição de faturamento projetado sobre faturamento real já realizado.
