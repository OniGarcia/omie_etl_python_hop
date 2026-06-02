#!/bin/bash
#
# executar_todas_empresas.sh
# --------------------------------------------------------------------------
# Roda o master de extracao UMA VEZ POR EMPRESA, cada uma em um processo
# hop-run ISOLADO (JVM propria, variaveis proprias).
#
# Por que assim: o loop multi-empresa dentro de um unico processo Hop
# (wf_executar_todas_empresas -> WorkflowExecutor) vaza variaveis entre as
# iteracoes (escopo ROOT_WORKFLOW do SetVarsEmpresa). Resultado observado:
# a 2a iteracao rodava com o id_empresa da 1a e o "Truncate Tabelas"
# (DELETE WHERE id_empresa = X) APAGAVA os dados que a 1a iteracao acabou
# de carregar. Rodando 1 empresa por processo, nao ha vazamento nem
# truncate cruzado.
#
# Fonte da verdade das credenciais: config.empresas (Supabase).
# Como nao ha psql local, a lista fica embutida aqui. Ao adicionar/remover
# empresa em config.empresas, atualize o array EMPRESAS abaixo.
#   Formato de cada item:  "ID|APP_KEY|APP_SECRET|NOME"
# --------------------------------------------------------------------------

set -u

HOP_RUN="/c/hop/hop/hop-run.sh"
HOP_PROJECT="ETL_Omie_Unificado"
RUN_CONFIG="local"
PROJECT_DIR="C:/Projetos/PROJETO_BI_OMIE_2026/ETL_Omie_Unificado"
WORKFLOW="wf_master_extracao_completa.hwf"

# Empresas ativas (espelha config.empresas WHERE ativo = true)
EMPRESAS=(
  "1|6980025353301|5bdd9e4cbf4774cba1612095ca029443|BC MAIS"
  "3|5375094624900|d8837838db35237ffd7e360a2a84fe2f|ASSOCIACAO EMPRESARIAL BC E CAMBORIU"
)

echo "=========================================="
echo "Extracao OMIE - loop isolado por empresa"
echo "Projeto: ${HOP_PROJECT}   Workflow: ${WORKFLOW}"
echo "Total de empresas: ${#EMPRESAS[@]}"
echo "=========================================="

falhas=0
sucessos=0

for item in "${EMPRESAS[@]}"; do
  IFS='|' read -r ID_EMPRESA API_KEY API_SECRET NOME <<< "$item"

  echo ""
  echo "------------------------------------------"
  echo ">> Empresa id=${ID_EMPRESA}  (${NOME})"
  echo "   Inicio: $(date '+%Y-%m-%d %H:%M:%S')"
  echo "------------------------------------------"

  "${HOP_RUN}" \
    -j "${HOP_PROJECT}" \
    -r "${RUN_CONFIG}" \
    -f "${PROJECT_DIR}/${WORKFLOW}" \
    -p "P_ID_EMPRESA=${ID_EMPRESA}" \
    -p "P_API_KEY=${API_KEY}" \
    -p "P_API_SECRET=${API_SECRET}"

  rc=$?
  if [ $rc -eq 0 ]; then
    echo ">> Empresa id=${ID_EMPRESA} (${NOME}): OK (rc=0)"
    sucessos=$((sucessos + 1))
  else
    echo ">> Empresa id=${ID_EMPRESA} (${NOME}): FALHOU (rc=${rc})"
    falhas=$((falhas + 1))
  fi
done

echo ""
echo "=========================================="
echo "Resumo: ${sucessos} sucesso(s), ${falhas} falha(s)"
echo "Verifique: staging.stg_* WHERE id_empresa = <id>"
echo "=========================================="

# rc != 0 se qualquer empresa falhou (util para agendador/CI)
[ $falhas -eq 0 ]
