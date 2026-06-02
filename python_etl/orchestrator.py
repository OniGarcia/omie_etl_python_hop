import logging
from database import get_db_connection, get_db_transaction
from omie_client import OmieClient
from extractors import EXTRACTOR_MAPPING

logger = logging.getLogger("ETLOrchestrator")

def registrar_inicio_lote(cursor, company_id: int) -> int:
    """Insere um registro de execução 'INICIADO' e retorna o ID gerado."""
    cursor.execute(
        """
        INSERT INTO config.etl_execucao (id_empresa, entidade, status, dt_inicio)
        VALUES (%s, 'LOTE', 'INICIADO', NOW())
        RETURNING id
        """
        , (company_id,)
    )
    return cursor.fetchone()[0]

def registrar_fim_lote(cursor, log_id: int, status: str, linhas: int = 0, mensagem: str = None):
    """Atualiza o registro de execução com o resultado final (SUCESSO ou ERRO)."""
    cursor.execute(
        """
        UPDATE config.etl_execucao
        SET status = %s, dt_fim = NOW(), linhas = %s, mensagem = %s
        WHERE id = %s
        """
        , (status, linhas, mensagem, log_id)
    )

def executar_etl_empresa(conn, company_id: int, company_name: str, app_key: str, app_secret: str, dry_run: bool = False):
    """Orquestra a extração e carga para uma única empresa de forma isolada e transacional (ACID)."""
    logger.info(f"=== Iniciando ETL para a empresa: {company_name} (ID: {company_id}) ===")
    
    # 1. Registrar o início do lote de execução
    with conn.cursor() as cursor:
        log_id = registrar_inicio_lote(cursor, company_id)
    conn.commit()  # Commita o início para que fique visível imediatamente

    client = OmieClient(app_key, app_secret)
    all_extracted_data = {}
    
    try:
        # FASE A: Extração (Download de todas as APIs para a memória)
        # Se falhar aqui, o banco ainda não foi tocado (DELETE/INSERT)
        for name, extractor_class in EXTRACTOR_MAPPING.items():
            logger.info(f"[{company_name}] Executando fetch de {name}...")
            extractor = extractor_class(client, company_id)
            records = extractor.fetch()
            all_extracted_data[name] = (extractor, records)
            logger.info(f"[{company_name}] {len(records)} registros baixados com sucesso para {name}.")

        if dry_run:
            logger.info(f"=== [DRY RUN] Download concluído para {company_name}. Nenhuma alteração feita no banco. ===")
            with conn.cursor() as cursor:
                registrar_fim_lote(cursor, log_id, "SUCESSO", 0, "[DRY RUN] Validação de credenciais e download OK.")
            conn.commit()
            return

        # FASE B: Carga Transacional (Buffer -> Clear -> Insert)
        # Executado dentro de uma transação PostgreSQL (Tudo ou Nada)
        total_rows_inserted = 0
        with get_db_transaction(conn):
            with conn.cursor() as cursor:
                for name, (extractor, records) in all_extracted_data.items():
                    logger.info(f"[{company_name}] Limpando staging para {name}...")
                    extractor.clean_staging(cursor)
                    
                    logger.info(f"[{company_name}] Inserindo novos dados para {name}...")
                    rows = extractor.save(cursor, records)
                    total_rows_inserted += rows
                    logger.info(f"[{company_name}] {rows} registros salvos em staging para {name}.")
        
        # FASE C: Confirmar Sucesso
        with conn.cursor() as cursor:
            registrar_fim_lote(cursor, log_id, "SUCESSO", total_rows_inserted)
        conn.commit()
        logger.info(f"=== ETL finalizado com SUCESSO para {company_name}. Total de linhas inseridas no staging: {total_rows_inserted} ===")

    except Exception as e:
        logger.error(f"Erro crítico no processamento da empresa {company_name} (ID: {company_id}): {e}", exc_info=True)
        # Registra o erro no log
        try:
            with conn.cursor() as cursor:
                registrar_fim_lote(cursor, log_id, "ERRO", 0, str(e))
            conn.commit()
        except Exception as log_err:
            logger.error(f"Falha ao registrar log de erro no banco: {log_err}")
        
        # Propaga a exceção para que o orchestrador saiba que a empresa falhou
        raise e

def rodar_lote_completo(dry_run: bool = False):
    """Loop principal que busca as empresas ativas e executa o ETL para cada uma."""
    logger.info("Iniciando lote completo de execução ETL Omie...")
    
    empresas_ativas = []
    
    # 1. Busca empresas ativas
    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("SELECT id, nome_empresa, omie_app_key, omie_app_secret FROM config.empresas WHERE ativo = TRUE ORDER BY id")
            rows = cursor.fetchall()
            for r in rows:
                empresas_ativas.append({
                    "id": r[0],
                    "nome": r[1],
                    "key": r[2],
                    "secret": r[3]
                })

    logger.info(f"Encontradas {len(empresas_ativas)} empresas ativas para processamento.")

    sucessos = 0
    falhas = 0

    # 2. Executa cada empresa em uma conexão isolada
    for emp in empresas_ativas:
        try:
            with get_db_connection() as conn:
                executar_etl_empresa(
                    conn=conn,
                    company_id=emp["id"],
                    company_name=emp["nome"],
                    app_key=emp["key"],
                    app_secret=emp["secret"],
                    dry_run=dry_run
                )
            sucessos += 1
        except Exception:
            # Captura a falha para que uma empresa não derrube a execução das demais
            falhas += 1
            logger.error(f"Falha ao processar empresa {emp['nome']}. Prosseguindo para as próximas...")

    logger.info(f"Lote de extração concluído: {sucessos} sucessos, {falhas} falhas.")

    # 3. Execução da Procedure de Carga do Data Warehouse (dw)
    # Roda apenas se pelo menos uma empresa foi carregada e não estamos em modo dry run
    if sucessos > 0 and not dry_run:
        logger.info("Iniciando carga do Data Warehouse (dw.sp_load_fact_movimento_financeiro)...")
        try:
            with get_db_connection() as conn:
                conn.autocommit = True  # Autocommit mode para evitar locks de subtransação na procedure
                with conn.cursor() as cursor:
                    logger.info("Executando CALL dw.sp_load_fact_movimento_financeiro()...")
                    cursor.execute("CALL dw.sp_load_fact_movimento_financeiro()")
            logger.info("Carga do Data Warehouse finalizada com SUCESSO!")
        except Exception as e:
            logger.error(f"Falha crítica ao atualizar o Data Warehouse (Procedure dw): {e}", exc_info=True)
            raise e
    else:
        if dry_run:
            logger.info("[DRY RUN] Carga de DW pulada.")
        else:
            logger.warning("Nenhuma empresa foi carregada com sucesso. Carga do DW cancelada para preservar dados existentes.")
            
    if falhas > 0:
        raise Exception(f"Lote de ETL finalizado com {falhas} falhas nas empresas.")
