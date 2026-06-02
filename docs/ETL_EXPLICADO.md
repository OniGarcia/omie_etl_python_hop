# ETL BI Omie 2026 — Guia Completo e Simplificado

> Objetivo deste documento: explicar, passo a passo e em linguagem simples, como os dados saem do Omie e chegam prontos para análise no Data Warehouse. Ênfase especial nos **campos de data**, que têm nomes diferentes na API, no staging e na tabela fato.

---

## Visão Geral do Pipeline

```
┌─────────────────────────────────────────────────────────────────────┐
│                          APACHE HOP (ETL)                           │
│  Chama API Omie → Recebe JSON → Salva no banco                      │
└───────────────────────────┬─────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     STAGING (schema: staging)                       │
│  Dados brutos, exatamente como vieram da API                        │
│  stg_fato_contas_pagar  |  stg_fato_contas_receber  |  stg_fato_lancamentos_cc  │
└───────────────────────────┬─────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────────┐
│                       DW (schema: dw)                               │
│  Dados transformados e prontos para análise                         │
│  dim_empresa | dim_categoria | dim_data | ...                       │
│  fact_movimento_financeiro  ← tabela principal                      │
└─────────────────────────────────────────────────────────────────────┘
```

O processo completo tem **3 etapas**:

1. **Extração** — Apache Hop chama a API Omie e salva os dados no staging
2. **Transformação** — Uma view SQL unifica CP + CR + CC e aplica regras de negócio
3. **Carga** — Uma stored procedure carrega a tabela fato com os surrogate keys

---

## Etapa 1 — Extração (Apache Hop chama a API Omie)

### O que é o Apache Hop?

É uma ferramenta visual de ETL (arrasta e solta). Cada "workflow" é um conjunto de passos que:
1. Monta um JSON de requisição
2. Faz um POST para a API REST do Omie
3. Lê a resposta JSON
4. Salva as linhas no PostgreSQL

### Como funciona a paginação

A API Omie retorna dados em páginas (máximo de 20 ou 50 registros por chamada). O Hop faz um loop automático:

```
Página 1 → salva 50 registros
Página 2 → salva 50 registros
...
Página N → retorna 0 registros → fim do loop
```

### Endpoints chamados e onde os dados vão

| Endpoint da API Omie | O que traz | Tabela de destino | Tipo |
|---|---|---|---|
| `ListarCategorias` | Categorias financeiras (ex: Salários, Aluguel) | `stg_cad_categorias` | Cadastro |
| `ListarDepartamentos` | Departamentos da empresa | `stg_cad_departamentos` | Cadastro |
| `ListarClientes` | Clientes e fornecedores | `stg_cad_clientes` | Cadastro |
| `ListarContasCorrentes` | Contas bancárias cadastradas | `stg_cad_contas_correntes` | Cadastro |
| `ListarContasPagar` | Todos os títulos a pagar | `stg_fato_contas_pagar` | Fato |
| `ListarContasReceber` | Todos os títulos a receber | `stg_fato_contas_receber` | Fato |
| `ListarLancCC` | Todos os movimentos do extrato bancário | `stg_fato_lancamentos_cc` | Fato |

> **Importante:** A extração **não usa filtro de data**. Sempre traz tudo. A cada execução completa, os dados de staging são sobrescritos com os dados mais recentes do Omie.

### Corpo da requisição (exemplo CP)

```json
{
  "call": "ListarContasPagar",
  "app_key": "6980025353301",
  "app_secret": "...",
  "param": [{
    "pagina": 1,
    "registros_por_pagina": 50,
    "apenas_importado_api": "N"
  }]
}
```

---

## Etapa 2 — Staging (dados brutos no banco)

### O que são as tabelas de staging?

São tabelas que guardam os dados **exatamente como vieram da API**, sem transformação. Se o Omie manda uma data como texto `"30/05/2026"`, ela chega como texto. Se manda em formato ISO, chega em ISO. O Hop faz o mínimo de conversão necessário.

### As 3 tabelas fato do staging

**`stg_fato_contas_pagar` (CP)**
- Cada linha = um título a pagar
- Vem da API `ListarContasPagar`
- Contém: fornecedor, valor, datas, status, categorias em JSON

**`stg_fato_contas_receber` (CR)**
- Cada linha = um título a receber
- Vem da API `ListarContasReceber`
- Contém: cliente, valor, datas, status, categorias em JSON

**`stg_fato_lancamentos_cc` (CC)**
- Cada linha = um lançamento no extrato da conta corrente
- Vem da API `ListarLancCC`
- É diferente de CP/CR: aqui são transações **já realizadas**, não títulos futuros

### Tabelas filhas (rateio por categoria)

Quando um título tem o valor dividido entre múltiplas categorias (rateio), as categorias ficam em tabelas separadas:

```
stg_fato_contas_pagar  (1 linha por título)
    └── stg_fato_contas_pagar_categorias  (N linhas por título, uma por categoria)
    └── stg_fato_contas_pagar_departamentos  (N linhas por título, um por dept.)
```

O mesmo vale para CR e CC.

---

## Campos de Data — Guia Completo

> Esta é a parte mais importante do documento. Os nomes dos campos de data na API Omie são diferentes para cada tipo de lançamento, o que gera confusão.

---

### CP — Contas a Pagar (`stg_fato_contas_pagar`)

A API CP usa nomes descritivos em português. São 4 campos de data:

| Nome na API Omie | Nome no banco (staging) | Tipo no banco | O que significa na prática |
|---|---|---|---|
| `data_emissao` | `data_emissao` | `DATE` | Quando a nota fiscal ou boleto foi emitido. É a data do documento. |
| `data_entrada` | `data_entrada` | `DATE` | Quando o título foi incluído no Omie. Nem sempre igual à emissão. |
| `data_vencimento` | `data_vencimento` | `DATE` | Data limite para pagamento. Prazo do boleto. |
| `data_previsao` | `data_previsao` | `DATE` | **A mais importante:** quando o pagamento foi (ou será) realizado. Se o título está LIQUIDADO, contém a data real do pagamento. Se ainda está ABERTO, pode conter uma previsão. |

> **Dica:** Em CP, o campo `data_previsao` é a data de pagamento efetivo. O nome "previsão" é herança do Omie, mas na prática é a data real quando o status é LIQUIDADO.

---

### CR — Contas a Receber (`stg_fato_contas_receber`)

A API CR também usa nomes descritivos, mas os campos chegam como `TIMESTAMP` (com hora), diferente do CP que é `DATE` (só data). São 6 campos de data:

| Nome na API Omie | Nome no banco (staging) | Tipo no banco | O que significa na prática |
|---|---|---|---|
| `data_emissao` | `data_emissao` | `TIMESTAMP` | Quando a nota ou duplicata foi emitida. |
| `data_vencimento` | `data_vencimento` | `TIMESTAMP` | Data limite para recebimento. Prazo de vencimento. |
| `data_previsao` | `data_previsao` | `TIMESTAMP` | **A mais importante:** quando o recebimento foi (ou será) realizado. Igual ao CP: é a data real quando status é LIQUIDADO/RECEBIDO. |
| `data_registro` | `data_registro` | `TIMESTAMP` | Data de registro formal do título no sistema. |
| `dInc` | `dinc` | `TIMESTAMP` | Data/hora de inclusão do registro (auditoria interna do Omie). |
| `dAlt` | `dalt` | `TIMESTAMP` | Data/hora da última alteração do registro (auditoria). |

> **Nota:** Os campos `dinc` e `dalt` são metadados de auditoria — servem para saber quando o Omie registrou ou modificou o lançamento internamente. Normalmente não são usados para análise financeira.

---

### CC — Lançamentos Conta Corrente (`stg_fato_lancamentos_cc`)

> **Atenção:** A API de Lançamentos CC usa uma **convenção de nomes totalmente diferente**. Em vez de nomes descritivos como `data_vencimento`, usa **notação húngara** com prefixos de tipo:
> - `d` = **d**ate (data)
> - `n` = **n**umber (número)
> - `c` = **c**har (texto)
> - `h` = **h**ora
> - `u` = **u**ser (usuário)
>
> Por isso `dDtLanc` significa **d**ate + **D**a**t**a + **Lanç**amento.

| Nome na API Omie | Nome no banco (staging) | Tipo no banco | O que significa na prática |
|---|---|---|---|
| `dDtLanc` | `ddtlanc` | `TIMESTAMP` | **O campo mais importante do CC:** Data do lançamento no extrato bancário. É quando a transação aconteceu de fato. |
| `dDtConc` | `ddtconc` | `TIMESTAMP` | Data de conciliação bancária (quando o lançamento foi confirmado/conciliado com o extrato do banco). |
| `dInc` | `dinc` | `TIMESTAMP` | Data/hora de inclusão no Omie (auditoria). |
| `dAlt` | `dalt` | `TIMESTAMP` | Data/hora da última alteração (auditoria). |

> **Por que CC só tem uma data relevante?** Porque lançamentos CC são transações **já realizadas** no extrato bancário. Não existe "vencimento futuro" ou "emissão de documento". Só existe a data em que o dinheiro entrou ou saiu da conta: `ddtlanc`.

---

## Etapa 3 — Transformação e Carga da Tabela Fato

### A View de Unificação (`vw_movimento_financeiro_unificado`)

Antes de carregar a tabela fato, uma view SQL unifica as 3 origens com `UNION ALL`:

```
CP (Contas a Pagar)    ─┐
CR (Contas a Receber)  ─┼─ UNION ALL ─→ vw_movimento_financeiro_unificado
CC (Lançamentos CC)    ─┘
```

Esta view também **explode o rateio de categorias**: se um título tem 3 categorias, vira 3 linhas na view (uma por categoria), com o valor proporcional de cada uma.

#### Regras de negócio aplicadas na view para datas

A view padroniza os campos de data das 3 origens em 3 campos únicos: `data_emissao`, `data_vencimento` e `data_pagamento`.

**Campo `data_pagamento` — regra mais importante:**

| Origem | Regra na view | Motivo |
|---|---|---|
| **CP** | `data_previsao` se status IN ('LIQUIDADO','RECEBIDO','PAGO'), senão `NULL` | Só indica pagamento quando já ocorreu |
| **CR** | `data_previsao::DATE` se status IN ('LIQUIDADO','RECEBIDO','PAGO'), senão `NULL` | Idem CP, com cast para DATE |
| **CC** | `ddtlanc::DATE` sempre | CC é sempre uma transação realizada, nunca futura |

**Como as outras datas são mapeadas:**

| Campo na view | Valor para CP | Valor para CR | Valor para CC |
|---|---|---|---|
| `data_emissao` | `data_emissao` | `data_emissao::DATE` | `ddtlanc::DATE` |
| `data_vencimento` | `data_vencimento` | `data_vencimento::DATE` | `ddtlanc::DATE` |
| `data_pagamento` | `data_previsao` (se liquidado) | `data_previsao::DATE` (se liquidado) | `ddtlanc::DATE` (sempre) |

> **Por que CC usa a mesma data para emissao, vencimento e pagamento?** Porque no extrato bancário, um lançamento representa um evento já acontecido. Não existe distinção entre "quando foi emitido" e "quando foi pago" — tudo é a data do lançamento.

---

### A Stored Procedure (`sp_load_fact_movimento_financeiro`)

A procedure executa em 3 fases toda vez que é chamada:

```
CALL dw.sp_load_fact_movimento_financeiro();
```

**Fase 1 — Atualiza as dimensões (UPSERT)**

Carrega/atualiza as 5 tabelas de dimensão:
- `dim_empresa` ← `config.empresas`
- `dim_categoria` ← `stg_cad_categorias`
- `dim_departamento` ← `stg_cad_departamentos`
- `dim_entidade` ← `stg_cad_clientes`
- `dim_conta_corrente` ← `stg_cad_contas_correntes`

Usa UPSERT (INSERT ... ON CONFLICT DO UPDATE): insere se não existe, atualiza se já existe. Nunca deleta — assim os códigos históricos são preservados.

**Fase 2 — Limpa a tabela fato (TRUNCATE)**

```sql
TRUNCATE TABLE dw.fact_movimento_financeiro RESTART IDENTITY;
```

Apaga tudo e recomeça do zero. Isso é chamado de **Full Reload** — é a estratégia mais simples e garante que os dados sempre refletem exatamente o que está no Omie hoje.

**Fase 3 — Insere a partir da view (INSERT)**

Lê a `vw_movimento_financeiro_unificado` e insere na fact, fazendo o lookup dos surrogate keys (SKs) via LEFT JOIN nas dimensões.

---

## Tabela Fato — Estrutura Completa

### `dw.fact_movimento_financeiro`

**Granularidade:** Uma linha por **(empresa + origem + lançamento + categoria)**

Se um título tem 3 categorias de rateio → 3 linhas na fact.  
Se um título não tem rateio → 1 linha na fact (percentual = 100%).

---

### Campos de Data na Tabela Fato

| Coluna na Fact | Tipo | Origem | O que representa |
|---|---|---|---|
| `data_emissao` | `DATE` | view unificada | Data de emissão do documento (nota, boleto, etc.) |
| `data_vencimento` | `DATE` | view unificada | Data de vencimento (prazo para pagar/receber) |
| `data_pagamento` | `DATE` | view unificada | Data efetiva do pagamento/recebimento. NULL se título não está liquidado. |
| `sk_data_emissao` | `INTEGER` | calculado | Chave numérica no formato YYYYMMDD. Ex: `20260530`. Usada para fazer JOIN com `dim_data`. |
| `sk_data_vencimento` | `INTEGER` | calculado | Idem, para data de vencimento. |
| `sk_data_pagamento` | `INTEGER` | calculado | Idem, para data de pagamento. NULL se não liquidado. |
| `dt_carga` | `TIMESTAMP` | `NOW()` | Momento em que a procedure rodou e inseriu o registro. Auditoria. |

**Como o sk_data é calculado:**
```sql
sk_data_emissao = TO_CHAR(data_emissao, 'YYYYMMDD')::INTEGER
-- Exemplo: 2026-05-30 → 20260530
```

Esse número é o mesmo formato da chave primária da `dim_data`, o que permite fazer JOIN sem precisar de uma conversão extra.

---

### Todas as Colunas da Tabela Fato

```
IDENTIFICAÇÃO
├── id                       Chave primária (auto-incremento)
├── id_empresa               Código da empresa (número inteiro)
├── origem                   De onde veio: 'CP', 'CR' ou 'CC'
└── codigo_lancamento_omie   Código único do lançamento no Omie

SURROGATE KEYS (chaves para JOIN com dimensões)
├── sk_empresa               → dim_empresa
├── sk_categoria             → dim_categoria
├── sk_departamento          → dim_departamento
├── sk_entidade              → dim_entidade (cliente/fornecedor)
├── sk_conta_corrente        → dim_conta_corrente
├── sk_data_emissao          → dim_data (formato YYYYMMDD)
├── sk_data_vencimento       → dim_data
└── sk_data_pagamento        → dim_data

CÓDIGOS NATURAIS (para análise direta sem JOIN)
├── cod_categoria            Código da categoria (ex: "1.01.02")
├── cod_departamento         Código do departamento
├── cod_entidade             Código do cliente/fornecedor
└── cod_conta_corrente       Código da conta bancária

ATRIBUTOS DESCRITIVOS
├── tipo_movimento           PAGAR | RECEBER | CC_ENTRADA | CC_SAIDA | TRANSFERENCIA
├── natureza                 D = Débito (saída) | C = Crédito (entrada)
├── status_titulo            LIQUIDADO | RECEBIDO | PAGO | ABERTO | CANCELADO | ...
└── is_transferencia         S = transferência entre contas próprias | N = não é

DATAS (valores reais, para filtros e cálculos)
├── data_emissao             Data de emissão do documento
├── data_vencimento          Data de vencimento
└── data_pagamento           Data de pagamento/recebimento (NULL se não liquidado)

VALORES (medidas)
├── valor_documento          Valor total do título/lançamento
├── valor_rateio             Valor desta categoria específica (pode ser parcial)
└── percentual_rateio        % desta categoria no total (100 se sem rateio)

METADADOS
└── dt_carga                 Data/hora em que esta linha foi carregada
```

---

## Exemplo Prático de Ponta a Ponta

Cenário: uma nota fiscal a pagar de R$ 1.000,00, dividida em 2 categorias, já paga.

### 1. O que vem da API Omie (JSON simplificado)

```json
{
  "codigo_lancamento_omie": 987654,
  "codigo_cliente_fornecedor": "12345",
  "data_emissao": "01/05/2026",
  "data_entrada": "02/05/2026",
  "data_vencimento": "15/05/2026",
  "data_previsao": "14/05/2026",
  "valor_documento": 1000.00,
  "status_titulo": "LIQUIDADO",
  "categorias": [
    { "codigo_categoria": "2.01.01", "valor": 600.00, "percentual": 60.00 },
    { "codigo_categoria": "2.01.02", "valor": 400.00, "percentual": 40.00 }
  ]
}
```

### 2. Como fica no staging

**Tabela principal** (`stg_fato_contas_pagar`): 1 linha

| codigo_lancamento_omie | data_emissao | data_vencimento | data_previsao | valor_documento | status_titulo |
|---|---|---|---|---|---|
| 987654 | 2026-05-01 | 2026-05-15 | 2026-05-14 | 1000.00 | LIQUIDADO |

**Tabela filha** (`stg_fato_contas_pagar_categorias`): 2 linhas

| codigo_lancamento_omie | codigo_categoria | valor | percentual |
|---|---|---|---|
| 987654 | 2.01.01 | 600.00 | 60.00 |
| 987654 | 2.01.02 | 400.00 | 40.00 |

### 3. Como a view explode em 2 linhas

A view faz um LEFT JOIN entre a tabela principal e a filha de categorias:

| origem | codigo_lancamento | cod_categoria | data_emissao | data_vencimento | data_pagamento | valor_documento | valor_rateio | percentual |
|---|---|---|---|---|---|---|---|---|
| CP | 987654 | 2.01.01 | 2026-05-01 | 2026-05-15 | 2026-05-14 | 1000.00 | 600.00 | 60.00 |
| CP | 987654 | 2.01.02 | 2026-05-01 | 2026-05-15 | 2026-05-14 | 1000.00 | 400.00 | 40.00 |

> `data_pagamento` = `data_previsao` porque status = 'LIQUIDADO'

### 4. Como a fact recebe as 2 linhas (após lookup dos SKs)

| id | origem | cod_lancamento | cod_categoria | data_emissao | sk_data_emissao | data_vencimento | sk_data_vencimento | data_pagamento | sk_data_pagamento | valor_rateio |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | CP | 987654 | 2.01.01 | 2026-05-01 | 20260501 | 2026-05-15 | 20260515 | 2026-05-14 | 20260514 | 600.00 |
| 2 | CP | 987654 | 2.01.02 | 2026-05-01 | 20260501 | 2026-05-15 | 20260515 | 2026-05-14 | 20260514 | 400.00 |

---

## Resumo dos Campos de Data por Origem

| Campo na Fact | CP (Contas a Pagar) | CR (Contas a Receber) | CC (Lançamentos CC) |
|---|---|---|---|
| `data_emissao` | `data_emissao` da API | `data_emissao` da API (cast DATE) | `ddtlanc` da API (cast DATE) |
| `data_vencimento` | `data_vencimento` da API | `data_vencimento` da API (cast DATE) | `ddtlanc` da API (cast DATE) |
| `data_pagamento` | `data_previsao` se LIQUIDADO, senão NULL | `data_previsao` se LIQUIDADO/RECEBIDO/PAGO, senão NULL | `ddtlanc` (sempre — CC é sempre transação realizada) |

---

## Perguntas Frequentes

**Q: Por que o CC usa `ddtlanc` e não `data_lancamento`?**
A API de lançamentos CC usa notação húngara: prefixo `d` = date, `Dt` = Data, `Lanc` = Lançamento. É uma convenção do sistema Omie para essa API específica.

**Q: Por que `data_pagamento` pode ser NULL na fact?**
Porque um título ainda em aberto (ABERTO, VENCIDO) não tem data de pagamento real. Colocar NULL é mais honesto do que usar `data_previsao` como se fosse uma data certa.

**Q: O que é um Surrogate Key (SK)?**
É um número inteiro gerado pelo banco para identificar uma dimensão. Por exemplo, `sk_categoria = 42` representa a categoria "2.01.01". Os SKs existem para tornar os JOINs mais rápidos (número inteiro é mais eficiente que texto).

**Q: Para datas, por que o SK é YYYYMMDD e não um ID sequencial?**
Porque `20260530` já é o próprio valor da data, sem precisar de uma tabela de lookup. É uma convenção de DW que torna o número autodescritivo.

**Q: O que significa Full Reload?**
Significa que a cada execução, a tabela fato é completamente apagada e recarregada do zero. Não existe "carga incremental" (só novos registros). Vantagem: garantia de consistência total. Desvantagem: tempo de execução maior.

**Q: Por que CP usa DATE e CR usa TIMESTAMP para as datas?**
São duas APIs diferentes do Omie, desenvolvidas em épocas diferentes, com padrões diferentes. O ETL faz o cast necessário (`::DATE`) para uniformizar na tabela fato.
