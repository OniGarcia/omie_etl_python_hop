#!/bin/bash

# Script para executar o master workflow do Hop
# Uso: ./executar_master_hop.sh [ID_EMPRESA] [API_KEY] [API_SECRET]
# Padrão (se não passar args): executa com BC MAIS (id=1)

# Configurações
HOP_HOME="/c/hop"
PROJECT_DIR="C:/Users/jonatas.garcia/OneDrive - Conjel Contabilidade e Controladoria Ss Ltda/_PROJETOS/PROJETO_BI_OMIE_2026/ETL_Omie_Unificado"
WORKFLOW="wf_master_extracao_completa.hwf"

# Parâmetros padrão (BC MAIS)
ID_EMPRESA="${1:-1}"
API_KEY="${2:-6980025353301}"
API_SECRET="${3:-5bdd9e4cbf4774cba1612095ca029443}"

echo "=========================================="
echo "Executando Master Workflow do Hop"
echo "=========================================="
echo "Empresa ID: $ID_EMPRESA"
echo "API Key: $API_KEY"
echo "Workflow: $WORKFLOW"
echo ""

# Executar o workflow
"${HOP_HOME}/hop-run.sh" \
  -r local \
  -f "${PROJECT_DIR}/${WORKFLOW}" \
  -p P_API_KEY="${API_KEY}" \
  -p P_API_SECRET="${API_SECRET}" \
  -p P_ID_EMPRESA="${ID_EMPRESA}"

echo ""
echo "=========================================="
echo "Execução concluída!"
echo "Verifique os dados em:"
echo "  - Database: bi_omie"
echo "  - Schemas: staging.stg_*"
echo "  - Filter: WHERE id_empresa = $ID_EMPRESA"
echo "=========================================="
