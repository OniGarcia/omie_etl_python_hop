# Apache Hop - Setup Multi-Empresa OMIE

## Estado Atual (✅ CONCLUÍDO)

### 1. Banco de Dados
- ✅ Banco `bi_omie` criado no PostgreSQL Docker (localhost:5432)
- ✅ Schemas criados: `config`, `staging`
- ✅ Tabelas de staging criadas (12 tabelas)
- ✅ Tabela `config.empresas` para armazenar credenciais

### 2. Variáveis do Projeto (project-config.json)
Atualizadas para apontar ao novo banco:

```json
{
  "VAR_DB_HOST": "localhost",
  "VAR_DB_NAME": "bi_omie",           // ✅ ATUALIZADO
  "VAR_DB_PORT": "5432",
  "VAR_DB_USER": "postgres",
  "VAR_DB_PASS": "password",          // ✅ ATUALIZADO (Docker password)
  "VAR_OMIE_KEY": "6980025353301",   // ✅ ATUALIZADO (BC MAIS)
  "VAR_OMIE_SECRET": "5bdd9e4cbf...", // ✅ ATUALIZADO (BC MAIS)
  "VAR_ID_EMPRESA": "1"               // BC MAIS
}
```

### 3. Conexão PostgreSQL
- Nome: `Stg_Omie_Generic`
- Usa variáveis para host, porta, usuário, senha, nome do banco
- ✅ Testada e funcionando

---

## Progresso Completado

### ✅ Fase 1: Padronização de Workflows (CONCLUÍDO)
Garantir que **TODOS** os 9 workflows tenham parâmetros dinâmicos:

**Workflows atualmente SEM parâmetros:**
- `wf_extracao_contas_correntes.hwf`
- `wf_extracao_departamento.hwf`
- `wf_extracao_clientes.hwf`
- `wf_listar_contas_pagar2.hwf`
- `wf_extracao_receber.hwf`
- `wf_extracao_contacorrente.hwf` (lançamentos CC)
- `wf_listar_movimentos.hwf`
- `wf_listar_lancamentos_cc.hwf`

**O que fazer:**
Adicionar os 3 parâmetros em CADA workflow:
```
P_API_KEY        (String, default: ${VAR_OMIE_KEY})
P_API_SECRET     (String, default: ${VAR_OMIE_SECRET})
P_ID_EMPRESA     (Integer, default: ${VAR_ID_EMPRESA})
```

### ✅ Fase 2: Master Workflow (CONCLUÍDO)
Criado `wf_master_extracao_completa.hwf` que:

1. ✅ Executa todos os 8 workflows de extração em sequência
2. ✅ Aceita 3 parâmetros dinâmicos: `P_API_KEY`, `P_API_SECRET`, `P_ID_EMPRESA`
3. ✅ Passa os parâmetros para cada workflow filho
4. ✅ Cada workflow executa com isolamento por `id_empresa`

**Fluxo:**
```
Start
  ├─ wf_extracao_categorias
  ├─ wf_extracao_departamentos
  ├─ wf_extracao_clientes
  ├─ wf_extracao_contas_correntes
  ├─ wf_extracao_contas_pagar
  ├─ wf_extracao_contas_receber
  ├─ wf_extracao_lancamentos_cc
  ├─ wf_extracao_movimentos
  ├─ wf_extracao_lancamentos_cc_historico
  └─ Success
```

### Fase 3: Executar e Testar (PRIORIDADE MÉDIA)
- Testar extração de 1 empresa (BC MAIS) por completo
- Validar dados em `staging.*`
- Adicionar 2ª empresa em `config.empresas` e rodar novamente

### Fase 4: Dimensões (PRIORIDADE BAIXA)
Após staging funcionar, criar os 4 workflows de dimensão:
- `CargaDimCategorias.hpl`
- `CargaDimContaCorrente.hpl`
- `CargaDimDepartamentos.hpl`
- `CargaDimClientes.hpl`

---

## Checklist de Próximas Ações

### ✅ Concluído
- [x] Atualizar project-config.json para apontar ao banco bi_omie
- [x] Adicionar parâmetros aos 7 workflows faltando
- [x] Criar `wf_master_extracao_completa.hwf`

### ✅ Conexão Corrigida (CONCLUÍDO)
- [x] Encontrado e corrigido: `wf_listar_lancamentos_cc.hwf` e `wf_listar_movimentos.hwf` usando hardcoded `Stg_Omie_Mais_Itajai`
- [x] Atualizado para `Stg_Omie_Generic` (bi_omie database)
- [x] TRUNCATE statements atualizados para usar staging.stg_* (novo schema)

### Imediato (PRÓXIMO)
- [ ] Testar master workflow com BC MAIS (P_ID_EMPRESA=1)
- [ ] Validar dados em `staging.*` para BC MAIS
- [ ] Confirmar isolamento: SELECT COUNT(*) FROM staging.stg_cad_categorias WHERE id_empresa = 1;

### Curto prazo
- [ ] Adicionar 2ª empresa em `config.empresas`
- [ ] Executar master para 2 empresas
- [ ] Validar isolamento de dados (cada empresa vê seus dados)

### Médio prazo
- [ ] Criar script Python/Bash que itera `config.empresas` e executa master para cada empresa
- [ ] Criar as 4 dimensões (SCD Type 2)
- [ ] Testar full pipeline: staging → dimensions

---

## Credenciais de Teste

**Empresa: BC MAIS** (id=1)
- App Key: `6980025353301`
- App Secret: `5bdd9e4cbf4774cba1612095ca029443`
- Status: Ativo

Para adicionar nova empresa:
```sql
INSERT INTO config.empresas 
  (nome_empresa, omie_app_key, omie_app_secret, ativo) 
VALUES 
  ('NOVA EMPRESA', 'app_key_aqui', 'app_secret_aqui', TRUE);
```

---

## Estrutura Final Esperada

```
ETL_Omie_Unificado/
├── wf_master_extracao_completa.hwf          (novo - master por empresa)
├── APICategorias/
│   ├── CargaListarCategorias.hpl
│   ├── ProcessoPaginasCategorias.hpl
│   └── wf_extracao_categorias.hwf (✅ tem parâmetros)
├── APIContasCorrentes/
│   ├── listarContasCorrentesv2.hpl
│   └── wf_extracao_contas_correntes.hwf (❌ adicionar parâmetros)
├── APIDepartamentos/
│   ├── CargaListarDepartamentos.hpl
│   ├── ProcessoPaginasDepartamentos.hpl
│   └── wf_extracao_departamento.hwf (❌ adicionar parâmetros)
├── APIListarClientes/
│   ├── ListarClientes.hpl
│   ├── ProcessoPaginasClientes.hpl
│   └── wf_extracao_clientes.hwf (❌ adicionar parâmetros)
├── APIContasPagar/
│   ├── listarContasPagar2.hpl
│   ├── ProcessoPaginasContasPagar2.hpl
│   └── wf_listar_contas_pagar2.hwf (❌ adicionar parâmetros)
├── APIContasReceber/
│   ├── ListarReceber.hpl
│   ├── processaPaginasReceber.hpl
│   ├── ProcessarCategoriasReceber.hpl
│   ├── ProcessarDistribuicaoReceber.hpl
│   └── wf_extracao_receber.hwf (❌ adicionar parâmetros)
├── APILancamentosCC/
│   ├── ListarLancamentosCC.hpl
│   ├── ProcessoPaginasCC.hpl
│   ├── ProcessarCategoriasCC.hpl
│   ├── ProcessarDistribuicaoCC.hpl
│   ├── wf_extracao_contacorrente.hwf (❌ adicionar parâmetros)
├── APIListarMovimentos/
│   ├── listarMovimentos.hpl
│   ├── loopAPIListarMovimentos.hpl
│   ├── processaPaginasListaMovimentos.hpl
│   └── wf_listar_movimentos.hwf (❌ adicionar parâmetros)
├── APIListarLancamentosCC/
│   ├── ListarLancamentosCC.hpl
│   ├── loopAPIListarLancamentosCC.hpl
│   ├── processoPaginasLancamentosCC.hpl
│   └── wf_listar_lancamentos_cc.hwf (❌ adicionar parâmetros)
├── Dimensoes/
│   ├── CargaDimCategorias.hpl
│   ├── CargaDimContaCorrente.hpl
│   ├── CargaDimDepartamentos.hpl
│   └── CargaDimClientes.hpl
└── metadata/
    └── rdbms/Stg_Omie_Generic.json (✅ atualizado)
```

---

## Comando para Testar Conexão no Hop

No Hop, abra qualquer pipeline e:
1. Clique em "Tools" → "Test DB Connections"
2. Selecione "Stg_Omie_Generic"
3. Clique "Test"
4. Deve aparecer: "Connection successful"

Se falhar, verifique:
- Docker container `postgres_db` rodando: `docker ps | grep postgres_db`
- Banco criado: `docker exec -i postgres_db psql -U postgres -c "\l"`
- Credenciais em `project-config.json`
