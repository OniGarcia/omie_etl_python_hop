"""
run_local.py — Runner interativo para uso local.

Uso direto (sem menus):
    python run_local.py --empresa 1 --modo full
    python run_local.py --empresa 1 --modo 7dias
    python run_local.py --empresa all --modo incremental
    python run_local.py --empresa 1 --modo full --dry-run

Sem argumentos: abre menus interativos para escolher empresa e modo.
"""

import sys
import argparse
import logging
from datetime import date, timedelta
from config import Config
from database import get_db_connection
from orchestrator import executar_etl_empresa, rodar_lote_completo, _construir_filtros
from extractors import FATO_MAPPING


def setup_logging():
    level = getattr(logging, Config.LOG_LEVEL, logging.INFO)
    formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(formatter)
    root = logging.getLogger()
    root.setLevel(level)
    root.addHandler(console)
    # Também grava em arquivo
    fh = logging.FileHandler("etl_local.log", encoding="utf-8")
    fh.setFormatter(formatter)
    root.addHandler(fh)


def listar_empresas() -> list[dict]:
    """Retorna todas as empresas ativas cadastradas."""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, nome_empresa FROM config.empresas WHERE ativo = TRUE ORDER BY id"
            )
            return [{"id": r[0], "nome": r[1]} for r in cur.fetchall()]


def buscar_empresa(empresa_id: int) -> dict | None:
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, nome_empresa, omie_app_key, omie_app_secret "
                "FROM config.empresas WHERE id = %s AND ativo = TRUE",
                (empresa_id,),
            )
            row = cur.fetchone()
    if not row:
        return None
    return {"id": row[0], "nome": row[1], "key": row[2], "secret": row[3]}


def menu_empresa(empresas: list[dict]) -> list[dict]:
    """Menu interativo: retorna lista de empresas selecionadas."""
    print("\n=== EMPRESAS DISPONÍVEIS ===")
    for e in empresas:
        print(f"  [{e['id']}] {e['nome']}")
    print(f"  [0] Todas as empresas")
    print()
    escolha = input("Escolha o ID da empresa (ou 0 para todas): ").strip()
    if escolha == "0":
        return empresas
    try:
        eid = int(escolha)
    except ValueError:
        print(f"Entrada inválida: '{escolha}'. Encerrando.")
        sys.exit(1)
    selecionada = next((e for e in empresas if e["id"] == eid), None)
    if not selecionada:
        print(f"Empresa ID {eid} não encontrada. Encerrando.")
        sys.exit(1)
    return [selecionada]


def menu_modo() -> str:
    """Menu interativo: retorna modo escolhido."""
    print("\n=== MODO DE CARGA ===")
    print("  [1] incremental — Apenas o que mudou desde o último run (usa watermark)")
    print("  [2] 7dias       — Reprocessa os últimos 7 dias (ignora watermark)")
    print("  [3] full        — Carga completa (todos os registros históricos)")
    print()
    escolha = input("Escolha o modo [1/2/3]: ").strip()
    mapa = {"1": "incremental", "2": "7dias", "3": "full"}
    modo = mapa.get(escolha)
    if not modo:
        print(f"Opção inválida: '{escolha}'. Encerrando.")
        sys.exit(1)
    return modo


def construir_filtros_7dias() -> dict:
    """Filtros fixos para janela de 7 dias em todas as entidades fato."""
    data_inicio = (date.today() - timedelta(days=7)).strftime("%d/%m/%Y")
    filtros = {}
    for name in FATO_MAPPING:
        if name == "lancamentos_cc":
            filtros[name] = {"data_de": data_inicio}
        else:
            filtros[name] = {"registro_de": data_inicio}
    return filtros


def rodar_empresa(emp: dict, modo: str, dry_run: bool, logger: logging.Logger):
    """Executa ETL para uma empresa com o modo escolhido."""
    from orchestrator import (
        registrar_inicio_lote, registrar_fim_lote, ler_watermarks,
        RECONCILE_ENTIDADES, FATO_ENTIDADES,
        atualizar_watermark,
    )
    from extractors import EXTRACTOR_MAPPING
    from database import get_db_transaction
    from omie_client import OmieClient

    logger.info(f"=== ETL [{modo.upper()}] — {emp['nome']} (ID: {emp['id']}) ===")

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            log_id = registrar_inicio_lote(cur, emp["id"], modo)
        conn.commit()

        client = OmieClient(emp["key"], emp["secret"])
        all_extracted = {}

        try:
            # Determina filtros conforme modo
            if modo == "full":
                filtros = {}
            elif modo == "7dias":
                filtros = construir_filtros_7dias()
            else:  # incremental
                with conn.cursor() as cur:
                    watermarks = ler_watermarks(cur, emp["id"])
                filtros = _construir_filtros(watermarks, "incremental")

            # Fase A — extração
            for name, cls in EXTRACTOR_MAPPING.items():
                filtro = filtros.get(name)
                label = "INCREMENTAL" if filtro else "FULL"
                logger.info(f"  Fetch {name} [{label}]...")
                ext = cls(client, emp["id"])
                records = ext.fetch(filtro=filtro)
                all_extracted[name] = (ext, records, filtro)
                logger.info(f"  {len(records)} registros para {name}.")

            if dry_run:
                logger.info("[DRY RUN] Download OK. Banco não alterado.")
                with conn.cursor() as cur:
                    registrar_fim_lote(cur, log_id, "SUCESSO", 0, "[DRY RUN]")
                conn.commit()
                return

            # Fase B — carga
            total = 0
            with get_db_transaction(conn):
                with conn.cursor() as cur:
                    for name, (ext, records, filtro) in all_extracted.items():
                        reconcilia = name in RECONCILE_ENTIDADES and modo == "incremental"
                        usar_upsert = name in FATO_ENTIDADES and filtro is not None
                        if reconcilia:
                            rows = ext.upsert(cur, records)
                            n_exc = ext.reconcile(cur, records)
                            logger.info(f"  {name}: {n_exc} excluídos reconciliados.")
                        elif usar_upsert:
                            rows = ext.upsert(cur, records)
                        else:
                            ext.clean_staging(cur)
                            rows = ext.save(cur, records)
                        total += rows
                        logger.info(f"  {name}: {rows} linhas salvas.")

            # Fase C — watermarks + log
            today = date.today()
            with conn.cursor() as cur:
                registrar_fim_lote(cur, log_id, "SUCESSO", total)
                for entidade in FATO_ENTIDADES:
                    atualizar_watermark(cur, emp["id"], entidade, today)
            conn.commit()
            logger.info(f"Staging OK — {total} linhas totais.")

        except Exception as e:
            logger.error(f"Erro: {e}", exc_info=True)
            try:
                with conn.cursor() as cur:
                    registrar_fim_lote(cur, log_id, "ERRO", 0, str(e))
                conn.commit()
            except Exception:
                pass
            raise


def main():
    parser = argparse.ArgumentParser(
        description="Runner local ETL Omie — escolha empresa e modo de carga."
    )
    parser.add_argument(
        "--empresa",
        help="ID da empresa (número) ou 'all' para todas. Omita para menu interativo.",
    )
    parser.add_argument(
        "--modo",
        choices=["incremental", "7dias", "full"],
        help="Modo de carga. Omita para menu interativo.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Baixa da API mas não grava no banco.",
    )
    parser.add_argument(
        "--skip-dw",
        action="store_true",
        help="Pula a recarga do DW (dw.sp_load_fact_movimento_financeiro) ao final.",
    )

    args = parser.parse_args()
    setup_logging()
    logger = logging.getLogger("ETLLocal")

    logger.info("=" * 60)
    logger.info("  ETL OMIE — runner local")
    logger.info("=" * 60)

    empresas_disponiveis = listar_empresas()
    if not empresas_disponiveis:
        logger.error("Nenhuma empresa ativa encontrada no banco.")
        sys.exit(1)

    # Resolve empresa(s)
    if args.empresa is None:
        empresas_alvo = menu_empresa(empresas_disponiveis)
    elif args.empresa.lower() == "all":
        empresas_alvo = empresas_disponiveis
    else:
        try:
            eid = int(args.empresa)
        except ValueError:
            logger.error(f"--empresa deve ser um número ou 'all', recebeu: '{args.empresa}'")
            sys.exit(1)
        emp = next((e for e in empresas_disponiveis if e["id"] == eid), None)
        if not emp:
            logger.error(f"Empresa ID {eid} não encontrada ou inativa.")
            sys.exit(1)
        empresas_alvo = [emp]

    # Resolve modo
    modo = args.modo if args.modo else menu_modo()

    # Confirmação resumo
    nomes = ", ".join(f"{e['nome']} (ID {e['id']})" for e in empresas_alvo)
    print(f"\n{'='*60}")
    print(f"  Empresa(s): {nomes}")
    print(f"  Modo:       {modo.upper()}")
    print(f"  Dry run:    {'SIM' if args.dry_run else 'NÃO'}")
    print(f"  Skip DW:    {'SIM' if args.skip_dw else 'NÃO'}")
    print(f"{'='*60}\n")

    # Busca credenciais completas
    empresas_com_credenciais = []
    for e in empresas_alvo:
        emp_full = buscar_empresa(e["id"])
        if emp_full:
            empresas_com_credenciais.append(emp_full)

    sucessos = 0
    falhas = 0
    for emp in empresas_com_credenciais:
        try:
            rodar_empresa(emp, modo, args.dry_run, logger)
            sucessos += 1
        except Exception:
            falhas += 1
            logger.error(f"Falha em {emp['nome']}. Continuando...")

    logger.info(f"Extração: {sucessos} OK, {falhas} falhas.")

    # Recarga do DW
    if sucessos > 0 and not args.dry_run and not args.skip_dw:
        logger.info("Recarregando Data Warehouse...")
        try:
            with get_db_connection() as conn:
                conn.autocommit = True
                with conn.cursor() as cur:
                    cur.execute("CALL dw.sp_load_fact_movimento_financeiro()")
            logger.info("DW atualizado com sucesso.")
        except Exception as e:
            logger.error(f"Falha ao recarregar DW: {e}", exc_info=True)
            falhas += 1
    elif args.skip_dw:
        logger.info("DW pulado (--skip-dw).")
    elif args.dry_run:
        logger.info("[DRY RUN] DW pulado.")

    sys.exit(1 if falhas > 0 else 0)


if __name__ == "__main__":
    main()
