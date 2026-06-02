@echo off
REM Script para executar o master workflow do Hop (Windows)
REM Uso: executar_master_hop.bat [ID_EMPRESA] [API_KEY] [API_SECRET]
REM Padrão: executa com BC MAIS (id=1)

setlocal enabledelayedexpansion

set HOP_HOME=C:\hop
set WORKFLOW=wf_master_extracao_completa.hwf

REM Parâmetros (padrão = BC MAIS)
set ID_EMPRESA=%1
if "%ID_EMPRESA%"=="" set ID_EMPRESA=1

set API_KEY=%2
if "%API_KEY%"=="" set API_KEY=6980025353301

set API_SECRET=%3
if "%API_SECRET%"=="" set API_SECRET=5bdd9e4cbf4774cba1612095ca029443

echo ==========================================
echo Executando Master Workflow do Hop
echo ==========================================
echo Empresa ID: !ID_EMPRESA!
echo API Key: !API_KEY!
echo Workflow: !WORKFLOW!
echo.

REM Mudar para a pasta do projeto
cd /d "%cd%\ETL_Omie_Unificado" || (echo Erro: pasta ETL_Omie_Unificado nao encontrada && exit /b 1)

REM Executar o workflow (do diretório do projeto)
"%HOP_HOME%\hop-run.bat" ^
  -r local ^
  -f "!WORKFLOW!" ^
  -p P_API_KEY=!API_KEY! ^
  -p P_API_SECRET=!API_SECRET! ^
  -p P_ID_EMPRESA=!ID_EMPRESA!

echo.
echo ==========================================
echo Execução concluída!
echo Verifique os dados em:
echo   - Database: bi_omie
echo   - Schemas: staging.stg_*
echo   - Filter: WHERE id_empresa = !ID_EMPRESA!
echo ==========================================
pause
