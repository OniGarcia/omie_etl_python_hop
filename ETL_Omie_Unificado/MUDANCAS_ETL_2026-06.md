# Mudanças no ETL Multi-Empresa — Junho 2026

## Problema identificado

O pipeline estava iterando corretamente sobre as 2 empresas ativas (`config.empresas`), mas **todas as extrações usavam sempre as credenciais e o id da empresa 1 (BC MAIS)**. A empresa 3 (ACIBALC) nunca recebia dados reais.

### Causa raiz

O loop de orquestração passava os dados da empresa como **parâmetros** (`P_ID_EMPRESA`, `P_API_KEY`, `P_API_SECRET`), mas as 24 pipelines folha liam **variáveis estáticas de projeto** (`VAR_OMIE_KEY`, `VAR_OMIE_SECRET`, `VAR_ID_EMPRESA`) — fixadas no `project-config.json` com os valores da empresa 1.

Consequências diretas:
- ACIBALC: zero dados em qualquer tabela (staging, dimensões, DW)
- DELETEs de limpeza apagavam sempre `id_empresa=1`, independente da empresa em processamento
- Guard rows nulas chegavam ao staging quando a API retornava resposta vazia (timeout de 10s muito curto para endpoints financeiros)
- `dw.fact_movimento_financeiro`: 0 linhas para ambas as empresas

---

## O que foi alterado

### Arquivo novo: `SetVarsEmpresa.hpl`

Pipeline bridge criada para traduzir os parâmetros da empresa corrente nas variáveis que as 24 pipelines folha já leem.

**Fluxo:** `Generate Row (1 linha)` → `Get Parameters (lê ${P_API_KEY}, ${P_API_SECRET}, ${P_ID_EMPRESA})` → `Set Variables (publica VAR_OMIE_KEY, VAR_OMIE_SECRET, VAR_ID_EMPRESA com escopo ROOT_WORKFLOW)`

O escopo `ROOT_WORKFLOW` garante que as variáveis sejam herdadas por todos os sub-workflows filhos sem precisar alterar nenhuma das 24 pipelines existentes.

---

### `wf_master_extracao_completa.hwf` — reescrito

**Fluxo anterior:**
```
Start → wf_extracao_categorias → ... → wf_carga_dw → Success
```

**Fluxo novo:**
```
Start → SetVarsEmpresa → LogInicio → wf_extracao_categorias → wf_extracao_departamentos
      → wf_extracao_clientes → wf_extracao_contas_correntes → wf_extracao_contas_pagar
      → wf_extracao_contas_receber → wf_extracao_lancamentos_cc → wf_extracao_movimentos
      → validar_cc_nao_vazia → wf_carga_dw → LogFim → Success
```

Mudanças específicas:
- `SetVarsEmpresa` como primeiro passo — sem ele nenhuma extração usa as credenciais corretas
- `LogInicio` / `LogFim` — INSERT em `config.etl_execucao` registrando início e fim por empresa
- `validar_cc_nao_vazia` — SQL corrigido de `COUNT(*)` para `COUNT(*) FILTER (WHERE ncodlanc IS NOT NULL)`, evitando que guard rows nulas passem a validação e disparem a carga DW com dados inválidos

---

### `ExecutarTodasEmpresas.hpl` — adicionado tratamento de resultado

- Campo `execution_result_target_transform` configurado para `Log Resultado Empresa`
- Adicionado transform `WriteToLog` com campos `P_ID_EMPRESA`, `execution_result`, `execution_errors`, `execution_time`
- Adicionado hop conectando `Executar Master por Empresa → Log Resultado Empresa`

Efeito: a falha de uma empresa é registrada no log e o loop continua processando as demais. Antes, uma falha abortava o lote inteiro.

---

### `APIContasPagar/wf_listar_contas_pagar2.hwf` — DELETE triplicado removido

O arquivo tinha 3 instruções `DELETE FROM staging.stg_fato_contas_pagar WHERE id_empresa = ${VAR_ID_EMPRESA}` idênticas consecutivas. Reduzido para 1.

---

### Pipelines financeiras — FilterRows + timeouts

Alterações aplicadas em 4 arquivos:

| Arquivo | Chave de filtro | Timeout anterior | Timeout novo |
|---------|----------------|-----------------|--------------|
| `APIContasPagar/listarContasPagar2.hpl` | `codigo_lancamento_omie IS NOT NULL` | 10 000 ms | 60 000 ms |
| `APIContasReceber/ListarReceber.hpl` | `codigo_lancamento_omie IS NOT NULL` | 10 000 ms | 60 000 ms |
| `APILancamentosCC/ListarLancamentosCC.hpl` | `nCodLanc IS NOT NULL` | sem timeout | 60 000 ms |
| `APIListarMovimentos/listarMovimentos.hpl` | `nCodTitulo IS NOT NULL` | 10 000 ms | 60 000 ms |

Em cada uma: transform `FilterRows` inserido entre o `JsonInput`/`Meta Dados` e o `TableOutput`, descartando linhas onde a chave natural é nula. Isso elimina as "guard rows" que o Hop gera quando a API retorna resposta vazia.

---

### Supabase — migration `config.etl_execucao`

Tabela criada no schema `config` para auditoria de execuções:

```sql
CREATE TABLE IF NOT EXISTS config.etl_execucao (
  id           bigserial PRIMARY KEY,
  id_empresa   integer NOT NULL,
  entidade     text NOT NULL,     -- 'LOTE', 'contas_pagar', etc.
  status       text NOT NULL,     -- 'INICIADO' | 'SUCESSO' | 'ERRO'
  linhas       bigint,
  mensagem     text,
  dt_inicio    timestamptz NOT NULL DEFAULT now(),
  dt_fim       timestamptz
);
```

RLS desabilitada (schema `config` é operacional, não exposto ao frontend).

---

## O que NÃO foi alterado

- As 24 pipelines folha que leem `${VAR_OMIE_KEY}`, `${VAR_OMIE_SECRET}`, `${VAR_ID_EMPRESA}` — a estratégia bridge as preserva intactas
- A procedure `dw.sp_load_fact_movimento_financeiro` — já estava correta e multi-empresa
- A RPC `public.criar_empresa` e o cadastro de empresas — não tinham relação com o problema

---

## Resultado esperado após as mudanças

### Durante a execução

```
SetVarsEmpresa - Set variable VAR_OMIE_KEY to value [6980025353301]   ← empresa 1
SetVarsEmpresa - Set variable VAR_ID_EMPRESA to value [1]
...
SetVarsEmpresa - Set variable VAR_OMIE_KEY to value [5375094624900]   ← empresa 3
SetVarsEmpresa - Set variable VAR_ID_EMPRESA to value [3]
```

Cada empresa usa suas próprias credenciais. Os DELETEs de staging limpam apenas o `id_empresa` corrente.

### Staging (após execução)

```sql
SELECT id_empresa, COUNT(*) FILTER (WHERE codigo_lancamento_omie IS NOT NULL) AS reais,
       COUNT(*) FILTER (WHERE codigo_lancamento_omie IS NULL) AS nulas
FROM staging.stg_fato_contas_pagar
GROUP BY id_empresa;
```

Esperado: linhas reais para `id_empresa = 1` e `id_empresa = 3`, coluna `nulas = 0` para ambas.

### DW

```sql
SELECT id_empresa, COUNT(*), SUM(valor_documento)
FROM dw.fact_movimento_financeiro
GROUP BY id_empresa;
```

Esperado: 2 linhas, uma por empresa, ambas com `count > 0`.

### Log de auditoria

```sql
SELECT id_empresa, entidade, status, dt_inicio, dt_fim
FROM config.etl_execucao
ORDER BY dt_inicio DESC;
```

Esperado: 1 registro `INICIADO` e 1 `SUCESSO` para cada empresa (ou `ERRO` se a API falhou para aquela empresa, com o lote continuando normalmente).

---

## Verificação de isolamento

Para confirmar que uma empresa não interfere na outra: invalidar temporariamente as credenciais da empresa 3 em `config.empresas`, rodar o lote e verificar que:
- `id_empresa = 1` mantém/atualiza seus dados normalmente
- `id_empresa = 3` aparece como `ERRO` em `config.etl_execucao`
- O pipeline completa sem abortar
