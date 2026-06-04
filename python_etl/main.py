import sys
import argparse
import logging
from config import Config
from orchestrator import rodar_lote_completo, executar_etl_empresa
from database import get_db_connection

def setup_logging():
    """Configura o sistema de logging do python."""
    level = getattr(logging, Config.LOG_LEVEL, logging.INFO)
    
    # Formato do log com timestamps e nível
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    # Handler para console (stdout)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    
    # Handler para arquivo
    file_handler = logging.FileHandler("etl_execution.log", encoding="utf-8")
    file_handler.setFormatter(formatter)
    
    # Logger raiz
    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)

def main():
    parser = argparse.ArgumentParser(description="Orquestrador de ETL OMIE 2026 em Python")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Executa o download e validação das APIs, mas não grava dados nem limpa tabelas."
    )
    parser.add_argument(
        "--company-id",
        type=int,
        help="Executa o ETL apenas para uma empresa específica pelo ID de cadastro."
    )
    parser.add_argument(
        "--modo",
        choices=["incremental", "full"],
        default="incremental",
        help="Modo de carga: 'incremental' (padrão, só o que mudou) ou 'full' (reconciliação completa)."
    )

    args = parser.parse_args()

    setup_logging()
    logger = logging.getLogger("ETLMain")

    logger.info("=====================================================================")
    logger.info("Iniciando Orquestrador ETL Omie em Python")
    logger.info(f"Modo de Carga: {args.modo.upper()}")
    logger.info(f"Modo Dry Run: {args.dry_run}")
    if args.company_id:
        logger.info(f"Executando apenas para empresa ID: {args.company_id}")
    logger.info("=====================================================================")

    try:
        if args.company_id:
            # Executa apenas para uma empresa específica
            with get_db_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(
                        "SELECT nome_empresa, omie_app_key, omie_app_secret FROM config.empresas WHERE id = %s",
                        (args.company_id,)
                    )
                    row = cursor.fetchone()
                    if not row:
                        logger.error(f"Empresa com ID {args.company_id} não encontrada no banco.")
                        sys.exit(1)

                    company_name, app_key, app_secret = row

                executar_etl_empresa(
                    conn=conn,
                    company_id=args.company_id,
                    company_name=company_name,
                    app_key=app_key,
                    app_secret=app_secret,
                    dry_run=args.dry_run,
                    modo=args.modo
                )

                # Executa o DW para a empresa piloto (se não for dry-run)
                if not args.dry_run:
                    logger.info("Iniciando processamento DW...")
                    conn.autocommit = True
                    with conn.cursor() as cursor:
                        cursor.execute("CALL dw.sp_load_fact_movimento_financeiro()")
                    logger.info("DW atualizado com sucesso!")
        else:
            # Executa o lote completo (todas as empresas ativas)
            rodar_lote_completo(dry_run=args.dry_run, modo=args.modo)
            
        logger.info("Processo finalizado com sucesso!")
        sys.exit(0)
        
    except Exception as e:
        logger.critical(f"Processo abortado devido a uma falha fatal: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
