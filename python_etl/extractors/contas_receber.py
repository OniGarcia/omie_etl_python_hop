import json
from datetime import datetime
from psycopg2.extras import execute_values
from extractors.base import BaseExtractor

def int_or_none(val):
    if val is None or val == "":
        return None
    try:
        return int(val)
    except (ValueError, TypeError):
        return None

def parse_timestamp(dt_str):
    if not dt_str:
        return None
    for fmt in ('%d/%m/%Y %H:%M:%S', '%d/%m/%Y', '%Y-%m-%d %H:%M:%S', '%Y-%m-%d'):
        try:
            return datetime.strptime(dt_str, fmt)
        except ValueError:
            continue
    return dt_str

class ContasReceberExtractor(BaseExtractor):
    def fetch(self, filtro: dict = None) -> list:
        extra_params = {"apenas_importado_api": "N"}
        if filtro and "registro_de" in filtro:
            extra_params["filtrar_por_registro_de"] = filtro["registro_de"]
        return self.client.fetch_paginated(
            endpoint="financas/contareceber",
            call_name="ListarContasReceber",
            list_key="conta_receber_cadastro",
            extra_params=extra_params
        )

    def _build_rows(self, raw_records):
        db_receber_rows = []
        db_categorias_rows = []
        db_departamentos_rows = []

        for record in raw_records:
            codigo_lancamento_omie = record.get("codigo_lancamento_omie")
            if not codigo_lancamento_omie:
                continue

            info = record.get("info", {})
            categorias_list = record.get("categorias", [])
            distribuicao_list = record.get("distribuicao", [])

            db_receber_rows.append((
                self.company_id,
                codigo_lancamento_omie,
                record.get("codigo_lancamento_integracao"),
                record.get("codigo_tipo_documento"),
                record.get("numero_documento"),
                record.get("numero_documento_fiscal"),
                int_or_none(record.get("codigo_cliente_fornecedor")),
                record.get("codigo_categoria"),
                int_or_none(record.get("id_conta_corrente")),
                record.get("codigo_barras_ficha_compensacao"),
                record.get("retem_pis"),
                record.get("retem_cofins"),
                record.get("retem_csll"),
                record.get("retem_ir"),
                record.get("retem_iss"),
                record.get("retem_inss"),
                parse_timestamp(record.get("data_vencimento")),
                parse_timestamp(record.get("data_emissao")),
                parse_timestamp(record.get("data_previsao")),
                parse_timestamp(record.get("data_registro")),
                record.get("valor_documento"),
                record.get("status_titulo"),
                record.get("tipo_agrupamento"),
                record.get("id_origem"),
                info.get("cImpAPI"),
                parse_timestamp(info.get("dInc")),
                info.get("hInc"),
                info.get("uInc"),
                parse_timestamp(info.get("dAlt")),
                info.get("hAlt"),
                info.get("uAlt"),
                json.dumps(categorias_list) if categorias_list else None,
                json.dumps(distribuicao_list) if distribuicao_list else None
            ))

            for cat in categorias_list:
                db_categorias_rows.append((
                    self.company_id,
                    codigo_lancamento_omie,
                    cat.get("codigo_categoria"),
                    cat.get("percentual"),
                    cat.get("valor")
                ))

            for dep in distribuicao_list:
                db_departamentos_rows.append((
                    self.company_id,
                    codigo_lancamento_omie,
                    dep.get("ccoddep"),
                    dep.get("cdesdep"),
                    dep.get("nperdep"),
                    dep.get("nvaldep")
                ))

        return db_receber_rows, db_categorias_rows, db_departamentos_rows

    def clean_staging(self, cursor):
        cursor.execute("DELETE FROM staging.stg_fato_contas_receber_categorias WHERE id_empresa = %s", (self.company_id,))
        cursor.execute("DELETE FROM staging.stg_fato_contas_receber_departamentos WHERE id_empresa = %s", (self.company_id,))
        cursor.execute("DELETE FROM staging.stg_fato_contas_receber WHERE id_empresa = %s", (self.company_id,))

    def save(self, cursor, raw_records: list) -> int:
        if not raw_records:
            return 0
        db_receber_rows, db_categorias_rows, db_departamentos_rows = self._build_rows(raw_records)
        if not db_receber_rows:
            return 0
        self._insert_pai(cursor, db_receber_rows)
        self._insert_filhas(cursor, db_categorias_rows, db_departamentos_rows)
        return len(db_receber_rows)

    def upsert(self, cursor, raw_records: list) -> int:
        """UPSERT incremental: atualiza registros existentes e insere novos.
        Filhas (categorias/departamentos) são apagadas e reinseridas por lançamento."""
        if not raw_records:
            return 0
        db_receber_rows, db_categorias_rows, db_departamentos_rows = self._build_rows(raw_records)
        if not db_receber_rows:
            return 0

        codigos = [row[1] for row in db_receber_rows]
        cursor.execute(
            "DELETE FROM staging.stg_fato_contas_receber_categorias WHERE id_empresa = %s AND codigo_lancamento_omie = ANY(%s)",
            (self.company_id, codigos)
        )
        cursor.execute(
            "DELETE FROM staging.stg_fato_contas_receber_departamentos WHERE id_empresa = %s AND codigo_lancamento_omie = ANY(%s)",
            (self.company_id, codigos)
        )

        query_upsert = """
            INSERT INTO staging.stg_fato_contas_receber (
                id_empresa, codigo_lancamento_omie, codigo_lancamento_integracao,
                codigo_tipo_documento, numero_documento, numero_documento_fiscal,
                codigo_cliente_fornecedor, codigo_categoria, id_conta_corrente,
                codigo_barras_ficha_compensacao, retem_pis, retem_cofins, retem_csll,
                retem_ir, retem_iss, retem_inss, data_vencimento, data_emissao,
                data_previsao, data_registro, valor_documento, status_titulo,
                tipo_agrupamento, id_origem, cimpapi, dinc, hinc, uinc, dalt,
                halt, ualt, json_categorias, json_distribuicao
            ) VALUES %s
            ON CONFLICT (id_empresa, codigo_lancamento_omie) DO UPDATE SET
                codigo_lancamento_integracao    = EXCLUDED.codigo_lancamento_integracao,
                codigo_tipo_documento           = EXCLUDED.codigo_tipo_documento,
                numero_documento                = EXCLUDED.numero_documento,
                numero_documento_fiscal         = EXCLUDED.numero_documento_fiscal,
                codigo_cliente_fornecedor       = EXCLUDED.codigo_cliente_fornecedor,
                codigo_categoria                = EXCLUDED.codigo_categoria,
                id_conta_corrente               = EXCLUDED.id_conta_corrente,
                codigo_barras_ficha_compensacao = EXCLUDED.codigo_barras_ficha_compensacao,
                retem_pis                       = EXCLUDED.retem_pis,
                retem_cofins                    = EXCLUDED.retem_cofins,
                retem_csll                      = EXCLUDED.retem_csll,
                retem_ir                        = EXCLUDED.retem_ir,
                retem_iss                       = EXCLUDED.retem_iss,
                retem_inss                      = EXCLUDED.retem_inss,
                data_vencimento                 = EXCLUDED.data_vencimento,
                data_emissao                    = EXCLUDED.data_emissao,
                data_previsao                   = EXCLUDED.data_previsao,
                data_registro                   = EXCLUDED.data_registro,
                valor_documento                 = EXCLUDED.valor_documento,
                status_titulo                   = EXCLUDED.status_titulo,
                tipo_agrupamento                = EXCLUDED.tipo_agrupamento,
                id_origem                       = EXCLUDED.id_origem,
                cimpapi                         = EXCLUDED.cimpapi,
                dinc                            = EXCLUDED.dinc,
                hinc                            = EXCLUDED.hinc,
                uinc                            = EXCLUDED.uinc,
                dalt                            = EXCLUDED.dalt,
                halt                            = EXCLUDED.halt,
                ualt                            = EXCLUDED.ualt,
                json_categorias                 = EXCLUDED.json_categorias,
                json_distribuicao               = EXCLUDED.json_distribuicao,
                excluido                        = FALSE,
                data_exclusao                   = NULL,
                dt_extracao                     = NOW()
        """
        execute_values(cursor, query_upsert, db_receber_rows)
        self._insert_filhas(cursor, db_categorias_rows, db_departamentos_rows)
        return len(db_receber_rows)

    def reconcile(self, cursor, raw_records: list) -> int:
        """Soft-delete: marca como excluído o que existe no staging mas NÃO veio do Omie.
        Pressupõe que raw_records seja a lista COMPLETA atual da empresa (fetch full)."""
        codigos = [r.get("codigo_lancamento_omie") for r in raw_records
                   if r.get("codigo_lancamento_omie")]
        if not codigos:
            # Guarda de segurança: lista vazia (ex.: falha/empresa sem dados) NÃO marca tudo.
            return 0
        cursor.execute(
            """
            UPDATE staging.stg_fato_contas_receber
            SET excluido = TRUE, data_exclusao = NOW()
            WHERE id_empresa = %s AND excluido = FALSE
              AND NOT (codigo_lancamento_omie = ANY(%s))
            """,
            (self.company_id, codigos)
        )
        return cursor.rowcount

    def _insert_pai(self, cursor, db_receber_rows):
        execute_values(cursor, """
            INSERT INTO staging.stg_fato_contas_receber (
                id_empresa, codigo_lancamento_omie, codigo_lancamento_integracao,
                codigo_tipo_documento, numero_documento, numero_documento_fiscal,
                codigo_cliente_fornecedor, codigo_categoria, id_conta_corrente,
                codigo_barras_ficha_compensacao, retem_pis, retem_cofins, retem_csll,
                retem_ir, retem_iss, retem_inss, data_vencimento, data_emissao,
                data_previsao, data_registro, valor_documento, status_titulo,
                tipo_agrupamento, id_origem, cimpapi, dinc, hinc, uinc, dalt,
                halt, ualt, json_categorias, json_distribuicao
            ) VALUES %s
        """, db_receber_rows)

    def _insert_filhas(self, cursor, db_categorias_rows, db_departamentos_rows):
        if db_categorias_rows:
            execute_values(cursor, """
                INSERT INTO staging.stg_fato_contas_receber_categorias (
                    id_empresa, codigo_lancamento_omie, codigo_categoria, percentual, valor
                ) VALUES %s
            """, db_categorias_rows)

        if db_departamentos_rows:
            execute_values(cursor, """
                INSERT INTO staging.stg_fato_contas_receber_departamentos (
                    id_empresa, codigo_lancamento_omie, ccoddep, cdesdep, nperdep, nvaldep
                ) VALUES %s
            """, db_departamentos_rows)
