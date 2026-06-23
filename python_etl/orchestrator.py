import logging
from datetime import date, timedelta
from database import get_db_connection, get_db_transaction
from omie_client import OmieClient
from extractors import EXTRACTOR_MAPPING, FATO_MAPPING
from config import Config

logger = logging.getLogger("ETLOrchestrator")

FATO_ENTIDADES = set(FATO_MAPPING.keys())

# Entidades que refletem exclusões físicas do Omie via soft delete.
# Para detectar exclusão é necessária a lista COMPLETA atual do Omie (o registro
# excluído some da API), por isso essas entidades fazem fetch full a cada run.
RECONCILE_ENTIDADES = {"contas_pagar", "contas_receber"}


# =============================================================================
# Funções de auditoria (config.etl_execucao)
# =============================================================================

def registrar_inicio_lote(cursor, company_id: int, modo: str = "incremental") -> int:
    cursor.execute(
        """
        INSERT INTO config.etl_execucao (id_empresa, entidade, status, modo, dt_inicio)
        VALUES (%s, 'LOTE', 'INICIADO', %s, NOW())
        RETURNING id
        """,
        (company_id, modo)
    )
    return cursor.fetchone()[0]

def registrar_fim_lote(cursor, log_id: int, status: str, linhas: int = 0, mensagem: str = None):
    cursor.execute(
        """
        UPDATE config.etl_execucao
        SET status = %s, dt_fim = NOW(), linhas = %s, mensagem = %s
        WHERE id = %s
        """,
        (status, linhas, mensagem, log_id)
    )


# =============================================================================
# Funções de watermark (config.etl_watermark)
# =============================================================================

def ler_watermarks(cursor, company_id: int) -> dict:
    """Retorna {entidade: ultima_data_ok (date ou None)} para a empresa."""
    cursor.execute(
        "SELECT entidade, ultima_data_ok FROM config.etl_watermark WHERE id_empresa = %s",
        (company_id,)
    )
    return {row[0]: row[1] for row in cursor.fetchall()}

def atualizar_watermark(cursor, company_id: int, entidade: str, data_ok: date):
    cursor.execute(
        """
        INSERT INTO config.etl_watermark (id_empresa, entidade, ultima_data_ok, ultima_execucao)
        VALUES (%s, %s, %s, NOW())
        ON CONFLICT (id_empresa, entidade) DO UPDATE
        SET ultima_data_ok  = EXCLUDED.ultima_data_ok,
            ultima_execucao = NOW()
        """,
        (company_id, entidade, data_ok)
    )


# =============================================================================
# Lógica de filtros incrementais
# =============================================================================

def _construir_filtros(watermarks: dict, modo: str) -> dict:
    """Retorna {entidade: filtro_dict} para cada entidade fato.

    - modo='full': todos os filtros ausentes → full reload em tudo.
    - modo='incremental': entidades sem watermark → full; com watermark → filtro.
    """
    if modo == "full":
        return {}

    today = date.today()
    filtros = {}
    for name in FATO_ENTIDADES:
        if name in RECONCILE_ENTIDADES:
            continue  # fetch full a cada run para permitir reconciliação de exclusões
        wm = watermarks.get(name)
        if wm is None:
            continue  # sem watermark = full reload para esta entidade
        if name == "lancamentos_cc":
            data_inicio = today - timedelta(days=Config.CC_WINDOW_DAYS)
            filtros[name] = {"data_de": data_inicio.strftime('%d/%m/%Y')}
        else:
            data_inicio = wm - timedelta(days=Config.INCREMENTAL_OVERLAP_DAYS)
            filtros[name] = {"registro_de": data_inicio.strftime('%d/%m/%Y')}
    return filtros


# =============================================================================
# Orquestrador por empresa
# =============================================================================

def executar_etl_empresa(conn, company_id: int, company_name: str, app_key: str, app_secret: str,
                         dry_run: bool = False, modo: str = "incremental"):
    """Orquestra a extração e carga para uma única empresa de forma isolada e transacional (ACID)."""
    logger.info(f"=== Iniciando ETL [{modo.upper()}] para empresa: {company_name} (ID: {company_id}) ===")

    with conn.cursor() as cursor:
        log_id = registrar_inicio_lote(cursor, company_id, modo)
    conn.commit()

    client = OmieClient(app_key, app_secret)
    all_extracted_data = {}

    try:
        # Lê watermarks somente no modo incremental
        watermarks = {}
        if modo == "incremental":
            with conn.cursor() as cursor:
                watermarks = ler_watermarks(cursor, company_id)
            logger.info(f"[{company_name}] Watermarks: { {k: str(v) for k, v in watermarks.items()} }")

        filtros = _construir_filtros(watermarks, modo)

        # FASE A: Extração (download das APIs para memória; banco não é tocado ainda)
        for name, extractor_class in EXTRACTOR_MAPPING.items():
            filtro = filtros.get(name)
            modo_extracao = "INCREMENTAL" if filtro else "FULL"
            logger.info(f"[{company_name}] Fetch {name} [{modo_extracao}]...")
            extractor = extractor_class(client, company_id)
            records = extractor.fetch(filtro=filtro)
            all_extracted_data[name] = (extractor, records, filtro)
            logger.info(f"[{company_name}] {len(records)} registros baixados para {name}.")

        if dry_run:
            logger.info(f"=== [DRY RUN] Download OK para {company_name}. Sem alterações no banco. ===")
            with conn.cursor() as cursor:
                registrar_fim_lote(cursor, log_id, "SUCESSO", 0, "[DRY RUN] Validação de credenciais e download OK.")
            conn.commit()
            return

        # FASE B: Carga transacional (Buffer → Clear/Upsert → Insert)
        # Tudo dentro de uma transação PostgreSQL — rollback automático em caso de erro
        total_rows_inserted = 0
        with get_db_transaction(conn):
            with conn.cursor() as cursor:
                for name, (extractor, records, filtro) in all_extracted_data.items():
                    reconcilia = (name in RECONCILE_ENTIDADES and modo == "incremental")
                    usar_upsert = (name in FATO_ENTIDADES and filtro is not None and modo == "incremental")
                    if reconcilia:
                        logger.info(f"[{company_name}] UPSERT + reconciliação de exclusões para {name}...")
                        rows = extractor.upsert(cursor, records)
                        n_exc = extractor.reconcile(cursor, records)
                        logger.info(f"[{company_name}] {name}: {n_exc} registros marcados como excluídos.")
                    elif usar_upsert:
                        logger.info(f"[{company_name}] UPSERT incremental para {name}...")
                        rows = extractor.upsert(cursor, records)
                    else:
                        logger.info(f"[{company_name}] Full reload para {name}...")
                        extractor.clean_staging(cursor)
                        rows = extractor.save(cursor, records)
                    total_rows_inserted += rows
                    logger.info(f"[{company_name}] {rows} registros salvos para {name}.")

        # FASE C: Confirmar sucesso + atualizar watermarks
        today = date.today()
        with conn.cursor() as cursor:
            registrar_fim_lote(cursor, log_id, "SUCESSO", total_rows_inserted)
            for entidade in FATO_ENTIDADES:
                atualizar_watermark(cursor, company_id, entidade, today)
        conn.commit()
        logger.info(
            f"=== ETL finalizado com SUCESSO para {company_name}. "
            f"Total de linhas no staging: {total_rows_inserted} ==="
        )

    except Exception as e:
        logger.error(f"Erro crítico no processamento de {company_name} (ID: {company_id}): {e}", exc_info=True)
        try:
            with conn.cursor() as cursor:
                registrar_fim_lote(cursor, log_id, "ERRO", 0, str(e))
            conn.commit()
        except Exception as log_err:
            logger.error(f"Falha ao registrar log de erro no banco: {log_err}")
        raise e


# =============================================================================
# Lote completo (todas as empresas ativas)
# =============================================================================

def rodar_lote_completo(dry_run: bool = False, modo: str = "incremental", empresa_ids: list = None):
    """Loop principal: busca empresas ativas e executa ETL para cada uma.

    empresa_ids: lista opcional de IDs de empresas a processar. None = todas as ativas.
    """
    if empresa_ids:
        logger.info(f"Iniciando lote [{modo.upper()}] para empresas selecionadas: {empresa_ids}...")
    else:
        logger.info(f"Iniciando lote completo [{modo.upper()}]...")

    empresas_ativas = []
    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            if empresa_ids:
                cursor.execute(
                    "SELECT id, nome_empresa, omie_app_key, omie_app_secret "
                    "FROM config.empresas WHERE ativo = TRUE AND id = ANY(%s) ORDER BY id",
                    (empresa_ids,)
                )
            else:
                cursor.execute(
                    "SELECT id, nome_empresa, omie_app_key, omie_app_secret "
                    "FROM config.empresas WHERE ativo = TRUE ORDER BY id"
                )
            for r in cursor.fetchall():
                empresas_ativas.append({"id": r[0], "nome": r[1], "key": r[2], "secret": r[3]})

    logger.info(f"Encontradas {len(empresas_ativas)} empresas ativas para processamento.")

    sucessos = 0
    falhas = 0

    for emp in empresas_ativas:
        try:
            with get_db_connection() as conn:
                executar_etl_empresa(
                    conn=conn,
                    company_id=emp["id"],
                    company_name=emp["nome"],
                    app_key=emp["key"],
                    app_secret=emp["secret"],
                    dry_run=dry_run,
                    modo=modo
                )
            sucessos += 1
        except Exception:
            falhas += 1
            logger.error(f"Falha ao processar empresa {emp['nome']}. Prosseguindo para as próximas...")

    logger.info(f"Lote de extração concluído: {sucessos} sucessos, {falhas} falhas.")

    # Carga do DW: roda apenas se ao menos uma empresa foi carregada e não é dry-run
    if sucessos > 0 and not dry_run:
        logger.info("Iniciando carga do Data Warehouse (dw.sp_load_fact_movimento_financeiro)...")
        try:
            with get_db_connection() as conn:
                conn.autocommit = True
                with conn.cursor() as cursor:
                    logger.info("Executando CALL dw.sp_load_fact_movimento_financeiro()...")
                    cursor.execute("CALL dw.sp_load_fact_movimento_financeiro()")
            logger.info("Carga do Data Warehouse finalizada com SUCESSO!")
        except Exception as e:
            logger.error(f"Falha crítica ao atualizar o Data Warehouse: {e}", exc_info=True)
            raise e
    else:
        if dry_run:
            logger.info("[DRY RUN] Carga de DW pulada.")
        else:
            logger.warning(
                "Nenhuma empresa foi carregada com sucesso. "
                "Carga do DW cancelada para preservar dados existentes."
            )

    if falhas > 0:
        raise Exception(f"Lote de ETL finalizado com {falhas} falhas nas empresas.")
