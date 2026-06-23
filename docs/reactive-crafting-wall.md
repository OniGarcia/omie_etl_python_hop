# Plano: Conciliação de Datas de Pagamento com Omie (data_pagamento)

## Contexto

Durante a análise de divergências entre o Fluxo de Caixa exportado do Omie (FLUXO BC.xlsx) e o dashboard DRE da aplicação, foram identificados e corrigidos três bugs na view `dw.vw_movimento_financeiro_unificado`:

| Bug | Descrição | Status |
|-----|-----------|--------|
| 1 | `ncodccdestino IS NOT NULL` avaliava `0` como verdadeiro → todos os CC marcados como `is_transferencia='S'` | ✅ Corrigido |
| 2 | `ctipo='ENT'` não reconhecia créditos CC com `ctipo='REND'` (Rendimentos) | ✅ Corrigido |
| 3 | `data_pagamento` usava `data_previsao` do CR/CP em vez da data real do banco (CC ddtlanc) | ✅ Parcialmente corrigido |

### Estado atual após Bug 3

A view foi atualizada para usar `MIN(ddtlanc)` da tabela `stg_fato_lancamentos_cc` como `data_pagamento` (via subquery agrupada com fallback para `data_previsao`). Isso corrigiu março, abril e maio:

| Mês | Excel Omie | DB (atual) | Diferença | Situação |
|-----|-----------|-----------|-----------|----------|
| Jan | R$92.500 | R$97.500 | +R$5k | ⚠️ residual |
| Fev | R$137.500 | R$132.500 | -R$5k | ⚠️ residual |
| Mar | R$157.500 | R$157.500 | 0 | ✅ |
| Abr | R$155.000 | R$155.000 | 0 | ✅ |
| Mai | R$200.000 | R$200.000 | 0 | ✅ |

### Causa do resíduo de Jan/Fev

CR `2801253171` (R$5.000):
- `data_previsao` = 31/dez/2025 (vencimento em dezembro)
- CC ddtlanc = 09/jan/2026 (crédito bancário em janeiro)
- Omie Fluxo de Caixa: exibe em **dezembro** (usa a data informada pelo usuário no registro da baixa)
- Nosso DB: exibe em **janeiro** (usa CC ddtlanc)

O Omie registra a "data de recebimento" no próprio campo do título CR/CP quando o usuário lança a baixa. Esse campo provavelmente é retornado pela API como `data_pagamento` mas **não é capturado** atualmente.

---

## Objetivo do plano

Capturar o campo `data_pagamento` da API Omie para CR e CP, armazená-lo no staging, e usá-lo como fonte primária de `data_pagamento` na view (substituindo o lookup via CC ddtlanc, que passa a ser fallback secundário).

---

## Arquivos a modificar

### 1. Schema migration — adicionar coluna `data_pagamento`

Criar migration no Supabase via `apply_migration`:

```sql
-- staging.stg_fato_contas_receber
ALTER TABLE staging.stg_fato_contas_receber
  ADD COLUMN IF NOT EXISTS data_pagamento TIMESTAMP;

-- staging.stg_fato_contas_pagar
ALTER TABLE staging.stg_fato_contas_pagar
  ADD COLUMN IF NOT EXISTS data_pagamento DATE;
```

Arquivo de referência para documentação: criar `database/17_add_data_pagamento_staging.sql`.

---

### 2. Extrator CR — `python_etl/extractors/contas_receber.py`

**Campo da API Omie:** `data_pagamento` (campo de nível raiz no response de `ListarContasReceber`).  
Quando o CR está com `status_titulo = 'RECEBIDO'`, a API retorna a data efetiva de recebimento nesse campo.

**Mudanças:**

a) Em `_build_rows()`, adicionar captura do campo (linha ~69, após `data_previsao`):
```python
parse_timestamp(record.get("data_pagamento")),   # ← NOVO (após data_previsao)
```

b) Em `_insert_pai()` (linha ~213), adicionar coluna na lista INSERT:
```
..., data_previsao, data_registro, data_pagamento, valor_documento, ...
```

c) Em `upsert()` (linha ~141), adicionar coluna na lista INSERT e no bloco `DO UPDATE SET`:
```
# INSERT list
..., data_previsao, data_registro, data_pagamento, valor_documento, ...

# DO UPDATE SET
data_pagamento = EXCLUDED.data_pagamento,
```

---

### 3. Extrator CP — `python_etl/extractors/contas_pagar.py`

**Campo da API Omie:** `data_pagamento` (campo de nível raiz no response de `ListarContasPagar`).  
Quando o CP está com `status_titulo = 'PAGO'/'LIQUIDADO'`, retorna a data efetiva de pagamento.

**Mudanças:**

a) Em `_build_rows()`, adicionar captura do campo (linha ~77, após `data_previsao`):
```python
parse_date(record.get("data_pagamento")),   # ← NOVO (após data_previsao)
```

b) Em `_insert_pai()`, adicionar coluna na lista INSERT:
```
..., data_previsao, data_pagamento, valor_documento, ...
```

c) Em `upsert()`, adicionar coluna na lista INSERT e no bloco `DO UPDATE SET`:
```
data_pagamento = EXCLUDED.data_pagamento,
```

---

### 4. View — `database/11_view_movimento_financeiro_unificado.sql`

Atualizar a lógica de `data_pagamento` em CP e CR para usar três camadas de prioridade:

**CP branch:**
```sql
COALESCE(
    -- 1ª prioridade: data efetiva de pagamento registrada pelo usuário no Omie
    cp.data_pagamento,
    -- 2ª prioridade: data do lançamento bancário (CC baixa)
    cc_baixa_cp.ddtlanc::DATE,
    -- 3ª prioridade: data_previsao (fallback)
    CASE WHEN cp.status_titulo IN ('LIQUIDADO', 'RECEBIDO', 'PAGO')
         THEN cp.data_previsao
         ELSE NULL
    END
) AS data_pagamento,
```

**CR branch:**
```sql
COALESCE(
    -- 1ª prioridade: data efetiva de recebimento registrada pelo usuário no Omie
    cc_baixa_cr.ddtlanc::DATE,   -- mantém CC como 1ª se data_pagamento CR não existir no schema
    ...
) AS data_pagamento,
```

Atenção: manter a subquery agrupada de CC ddtlanc — ela já foi validada e corrigiu Mar/Abr/Mai:
```sql
LEFT JOIN (
    SELECT id_empresa, ncodlanccr, MIN(ddtlanc) AS ddtlanc
    FROM   staging.stg_fato_lancamentos_cc
    WHERE  ncodlanccr IS NOT NULL
    GROUP  BY id_empresa, ncodlanccr
) cc_baixa_cr ON ...
```

---

### 5. Stored Procedure — `database/12_sp_load_fact_movimento_financeiro.sql`

Não requer mudança de lógica — ela lê da view. Porém, após validar as mudanças acima, executar a SP para recarregar o fact table com os novos valores.

---

## Ordem de execução

```
1. Apply migration: ADD COLUMN data_pagamento (CR + CP staging)
2. Editar contas_receber.py  — capturar data_pagamento
3. Editar contas_pagar.py    — capturar data_pagamento
4. Editar 11_view_*.sql      — atualizar COALESCE com 3 camadas
5. Apply migration: CREATE OR REPLACE VIEW (view atualizada)
6. Rodar ETL full ou incremental para re-extrair CR/CP com data_pagamento
7. CALL dw.sp_load_fact_movimento_financeiro()
8. Verificar totais Jan-Mai vs Excel
```

---

## Verificação final

Query de validação (empresa 1, jan-mai 2026):

```sql
SELECT
    TO_CHAR(d.data_completa, 'YYYY-MM') AS mes,
    ROUND(SUM(CASE WHEN f.natureza='C' THEN f.valor_rateio ELSE 0 END)::numeric,2) AS receitas,
    ROUND(SUM(CASE WHEN f.natureza='D' THEN f.valor_rateio ELSE 0 END)::numeric,2) AS despesas
FROM dw.fact_movimento_financeiro f
JOIN dw.dim_data d ON d.sk_data = f.sk_data_pagamento
WHERE f.id_empresa = 1
  AND f.is_transferencia = 'N'
  AND f.status_titulo IN ('LIQUIDADO','RECEBIDO','PAGO')
  AND f.sk_data_pagamento BETWEEN 20260101 AND 20260531
GROUP BY 1 ORDER BY 1;
```

**Valores esperados (do FLUXO BC.xlsx):**

| Mês | Receitas | Despesas |
|-----|---------|---------|
| 2026-01 | R$101.790,69 | R$1.622,49 |
| 2026-02 | R$145.637,90 | R$157.444,12 |
| 2026-03 | R$157.500,00 | R$218.042,79 |
| 2026-04 | R$156.056,00 | R$20.974,54 |
| 2026-05 | R$210.438,55 | R$21.795,67 |

---

## Notas de risco

- O campo `data_pagamento` pode não existir na API Omie para todos os títulos (ex.: títulos não liquidados retornam null — correto, o COALESCE trata)
- Títulos CP com `status_titulo = 'PAGO'` vs `'LIQUIDADO'`: a API Omie usa ambos; o COALESCE já cobre os dois
- Re-extração necessária para popular o novo campo nos registros já no staging (a ETL incremental usa `INCREMENTAL_OVERLAP_DAYS=7`, que pode não cobrir histórico antigo — avaliar se necessário rodar uma extração full)
