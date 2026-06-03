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
    # Formatos comuns da API Omie para data/hora
    for fmt in ('%d/%m/%Y %H:%M:%S', '%d/%m/%Y', '%Y-%m-%d %H:%M:%S', '%Y-%m-%d'):
        try:
            return datetime.strptime(dt_str, fmt)
        except ValueError:
            continue
    return dt_str

class ContasReceberExtractor(BaseExtractor):
    def fetch(self) -> list:
        return self.client.fetch_paginated(
            endpoint="financas/contareceber",
            call_name="ListarContasReceber",
            list_key="conta_receber_cadastro"
        )

    def clean_staging(self, cursor):
        cursor.execute("DELETE FROM staging.stg_fato_contas_receber_categorias WHERE id_empresa = %s", (self.company_id,))
        cursor.execute("DELETE FROM staging.stg_fato_contas_receber_departamentos WHERE id_empresa = %s", (self.company_id,))
        cursor.execute("DELETE FROM staging.stg_fato_contas_receber WHERE id_empresa = %s", (self.company_id,))

    def save(self, cursor, raw_records: list) -> int:
        if not raw_records:
            return 0

        db_receber_rows = []
        db_categorias_rows = []
        db_departamentos_rows = []

        for record in raw_records:
            # Filtro de chave natural nula (idêntico ao FilterRows do Hop)
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

        if not db_receber_rows:
            return 0

        # 1. Inserção na Pai
        query_receber = """
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
        """
        execute_values(cursor, query_receber, db_receber_rows)

        # 2. Categorias
        if db_categorias_rows:
            query_cat = """
                INSERT INTO staging.stg_fato_contas_receber_categorias (
                    id_empresa, codigo_lancamento_omie, codigo_categoria, percentual, valor
                ) VALUES %s
            """
            execute_values(cursor, query_cat, db_categorias_rows)

        # 3. Departamentos
        if db_departamentos_rows:
            query_dep = """
                INSERT INTO staging.stg_fato_contas_receber_departamentos (
                    id_empresa, codigo_lancamento_omie, ccoddep, cdesdep, nperdep, nvaldep
                ) VALUES %s
            """
            execute_values(cursor, query_dep, db_departamentos_rows)

        return len(db_receber_rows)
