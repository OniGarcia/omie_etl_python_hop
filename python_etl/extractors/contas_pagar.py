import json
from datetime import datetime
from psycopg2.extras import execute_values
from extractors.base import BaseExtractor

def parse_date(date_str):
    if not date_str:
        return None
    for fmt in ('%d/%m/%Y', '%Y-%m-%d', '%Y-%m-%d %H:%M:%S'):
        try:
            return datetime.strptime(date_str, fmt).date()
        except ValueError:
            continue
    return date_str

def parse_bool(val):
    if val is None:
        return None
    if isinstance(val, bool):
        return val
    if isinstance(val, str):
        val_lower = val.strip().lower()
        if val_lower in ('s', 'sim', 'true', '1', 'y', 'yes'):
            return True
        if val_lower in ('n', 'nao', 'não', 'false', '0', 'no'):
            return False
    return bool(val)

class ContasPagarExtractor(BaseExtractor):
    def fetch(self, filtro: dict = None) -> list:
        extra_params = {"apenas_importado_api": "N"}
        if filtro and "registro_de" in filtro:
            extra_params["filtrar_por_registro_de"] = filtro["registro_de"]
        return self.client.fetch_paginated(
            endpoint="financas/contapagar",
            call_name="ListarContasPagar",
            list_key="conta_pagar_cadastro",
            extra_params=extra_params
        )

    def _build_rows(self, raw_records):
        """Monta as tuplas de linhas a partir dos registros brutos da API."""
        db_pagar_rows = []
        db_categorias_rows = []
        db_departamentos_rows = []

        for record in raw_records:
            codigo_lancamento_omie = record.get("codigo_lancamento_omie")
            if not codigo_lancamento_omie:
                continue

            info = record.get("info", {})
            categorias_list = record.get("categorias", [])
            distribuicao_list = record.get("distribuicao", [])

            db_pagar_rows.append((
                self.company_id,
                codigo_lancamento_omie,
                record.get("codigo_lancamento_integracao"),
                record.get("codigo_tipo_documento"),
                record.get("numero_documento_fiscal"),
                record.get("numero_parcela"),
                record.get("codigo_barras_ficha_compensacao"),
                record.get("codigo_cliente_fornecedor"),
                record.get("id_conta_corrente"),
                parse_bool(record.get("bloqueado")),
                parse_bool(record.get("baixa_bloqueada")),
                parse_bool(record.get("retem_cofins")),
                parse_bool(record.get("retem_csll")),
                parse_bool(record.get("retem_inss")),
                parse_bool(record.get("retem_ir")),
                parse_bool(record.get("retem_iss")),
                parse_bool(record.get("retem_pis")),
                parse_date(record.get("data_emissao")),
                parse_date(record.get("data_entrada")),
                parse_date(record.get("data_vencimento")),
                parse_date(record.get("data_previsao")),
                record.get("valor_documento"),
                record.get("status_titulo"),
                record.get("id_origem"),
                parse_bool(info.get("cImpAPI")),
                parse_date(info.get("dAlt")),
                parse_date(info.get("dInc")),
                info.get("hAlt"),
                info.get("hInc"),
                info.get("uAlt"),
                info.get("uInc"),
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

        return db_pagar_rows, db_categorias_rows, db_departamentos_rows

    def clean_staging(self, cursor):
        cursor.execute("DELETE FROM staging.stg_fato_contas_pagar_categorias WHERE id_empresa = %s", (self.company_id,))
        cursor.execute("DELETE FROM staging.stg_fato_contas_pagar_departamentos WHERE id_empresa = %s", (self.company_id,))
        cursor.execute("DELETE FROM staging.stg_fato_contas_pagar WHERE id_empresa = %s", (self.company_id,))

    def save(self, cursor, raw_records: list) -> int:
        if not raw_records:
            return 0
        db_pagar_rows, db_categorias_rows, db_departamentos_rows = self._build_rows(raw_records)
        if not db_pagar_rows:
            return 0
        self._insert_pai(cursor, db_pagar_rows)
        self._insert_filhas(cursor, db_categorias_rows, db_departamentos_rows)
        return len(db_pagar_rows)

    def upsert(self, cursor, raw_records: list) -> int:
        """UPSERT incremental: atualiza registros existentes e insere novos.
        Para as tabelas filhas (rateio), apaga e reinseere apenas os lançamentos do lote."""
        if not raw_records:
            return 0
        db_pagar_rows, db_categorias_rows, db_departamentos_rows = self._build_rows(raw_records)
        if not db_pagar_rows:
            return 0

        # Apaga filhas apenas dos lançamentos presentes neste lote
        codigos = [row[1] for row in db_pagar_rows]
        cursor.execute(
            "DELETE FROM staging.stg_fato_contas_pagar_categorias WHERE id_empresa = %s AND codigo_lancamento_omie = ANY(%s)",
            (self.company_id, codigos)
        )
        cursor.execute(
            "DELETE FROM staging.stg_fato_contas_pagar_departamentos WHERE id_empresa = %s AND codigo_lancamento_omie = ANY(%s)",
            (self.company_id, codigos)
        )

        query_upsert = """
            INSERT INTO staging.stg_fato_contas_pagar (
                id_empresa, codigo_lancamento_omie, codigo_lancamento_integracao,
                codigo_tipo_documento, numero_documento_fiscal, numero_parcela,
                codigo_barras_ficha_compensacao, codigo_cliente_fornecedor,
                id_conta_corrente, bloqueado, conta_pagar_cadastro_baixa,
                retem_cofins, retem_csll, retem_inss, retem_ir, retem_iss, retem_pis,
                data_emissao, data_entrada, data_vencimento, data_previsao,
                valor_documento, status_titulo, id_origem, info_importado_api,
                info_data_alteracao, info_data_inclusao, info_hora_alteracao,
                info_hora_inclusao, info_usuario_alteracao, info_usuario_inclusao,
                json_categorias, json_distribuicao
            ) VALUES %s
            ON CONFLICT (id_empresa, codigo_lancamento_omie) DO UPDATE SET
                codigo_lancamento_integracao    = EXCLUDED.codigo_lancamento_integracao,
                codigo_tipo_documento           = EXCLUDED.codigo_tipo_documento,
                numero_documento_fiscal         = EXCLUDED.numero_documento_fiscal,
                numero_parcela                  = EXCLUDED.numero_parcela,
                codigo_barras_ficha_compensacao = EXCLUDED.codigo_barras_ficha_compensacao,
                codigo_cliente_fornecedor       = EXCLUDED.codigo_cliente_fornecedor,
                id_conta_corrente               = EXCLUDED.id_conta_corrente,
                bloqueado                       = EXCLUDED.bloqueado,
                conta_pagar_cadastro_baixa      = EXCLUDED.conta_pagar_cadastro_baixa,
                retem_cofins                    = EXCLUDED.retem_cofins,
                retem_csll                      = EXCLUDED.retem_csll,
                retem_inss                      = EXCLUDED.retem_inss,
                retem_ir                        = EXCLUDED.retem_ir,
                retem_iss                       = EXCLUDED.retem_iss,
                retem_pis                       = EXCLUDED.retem_pis,
                data_emissao                    = EXCLUDED.data_emissao,
                data_entrada                    = EXCLUDED.data_entrada,
                data_vencimento                 = EXCLUDED.data_vencimento,
                data_previsao                   = EXCLUDED.data_previsao,
                valor_documento                 = EXCLUDED.valor_documento,
                status_titulo                   = EXCLUDED.status_titulo,
                id_origem                       = EXCLUDED.id_origem,
                info_importado_api              = EXCLUDED.info_importado_api,
                info_data_alteracao             = EXCLUDED.info_data_alteracao,
                info_data_inclusao              = EXCLUDED.info_data_inclusao,
                info_hora_alteracao             = EXCLUDED.info_hora_alteracao,
                info_hora_inclusao              = EXCLUDED.info_hora_inclusao,
                info_usuario_alteracao          = EXCLUDED.info_usuario_alteracao,
                info_usuario_inclusao           = EXCLUDED.info_usuario_inclusao,
                json_categorias                 = EXCLUDED.json_categorias,
                json_distribuicao               = EXCLUDED.json_distribuicao,
                excluido                        = FALSE,
                data_exclusao                   = NULL,
                dt_extracao                     = NOW()
        """
        execute_values(cursor, query_upsert, db_pagar_rows)
        self._insert_filhas(cursor, db_categorias_rows, db_departamentos_rows)
        return len(db_pagar_rows)

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
            UPDATE staging.stg_fato_contas_pagar
            SET excluido = TRUE, data_exclusao = NOW()
            WHERE id_empresa = %s AND excluido = FALSE
              AND NOT (codigo_lancamento_omie = ANY(%s))
            """,
            (self.company_id, codigos)
        )
        return cursor.rowcount

    def _insert_pai(self, cursor, db_pagar_rows):
        query = """
            INSERT INTO staging.stg_fato_contas_pagar (
                id_empresa, codigo_lancamento_omie, codigo_lancamento_integracao,
                codigo_tipo_documento, numero_documento_fiscal, numero_parcela,
                codigo_barras_ficha_compensacao, codigo_cliente_fornecedor,
                id_conta_corrente, bloqueado, conta_pagar_cadastro_baixa,
                retem_cofins, retem_csll, retem_inss, retem_ir, retem_iss, retem_pis,
                data_emissao, data_entrada, data_vencimento, data_previsao,
                valor_documento, status_titulo, id_origem, info_importado_api,
                info_data_alteracao, info_data_inclusao, info_hora_alteracao,
                info_hora_inclusao, info_usuario_alteracao, info_usuario_inclusao,
                json_categorias, json_distribuicao
            ) VALUES %s
        """
        execute_values(cursor, query, db_pagar_rows)

    def _insert_filhas(self, cursor, db_categorias_rows, db_departamentos_rows):
        if db_categorias_rows:
            execute_values(cursor, """
                INSERT INTO staging.stg_fato_contas_pagar_categorias (
                    id_empresa, codigo_lancamento_omie, codigo_categoria, percentual, valor
                ) VALUES %s
            """, db_categorias_rows)

        if db_departamentos_rows:
            execute_values(cursor, """
                INSERT INTO staging.stg_fato_contas_pagar_departamentos (
                    id_empresa, codigo_lancamento_omie, ccoddep, cdesdep, nperdep, nvaldep
                ) VALUES %s
            """, db_departamentos_rows)
