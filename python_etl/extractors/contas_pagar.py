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
    def fetch(self) -> list:
        return self.client.fetch_paginated(
            endpoint="financas/contapagar",
            call_name="ListarContasPagar",
            list_key="conta_pagar_cadastro"
        )

    def clean_staging(self, cursor):
        # Remove registros das tabelas filhas primeiro por causa das FKs
        cursor.execute("DELETE FROM staging.stg_fato_contas_pagar_categorias WHERE id_empresa = %s", (self.company_id,))
        cursor.execute("DELETE FROM staging.stg_fato_contas_pagar_departamentos WHERE id_empresa = %s", (self.company_id,))
        cursor.execute("DELETE FROM staging.stg_fato_contas_pagar WHERE id_empresa = %s", (self.company_id,))

    def save(self, cursor, raw_records: list) -> int:
        if not raw_records:
            return 0

        db_pagar_rows = []
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

            # Prepara a linha da tabela pai
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
                parse_bool(record.get("baixa_bloqueada")),  # conta_pagar_cadastro_baixa
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

            # Prepara as linhas das categorias (filha 1)
            for cat in categorias_list:
                db_categorias_rows.append((
                    self.company_id,
                    codigo_lancamento_omie,
                    cat.get("codigo_categoria"),
                    cat.get("percentual"),
                    cat.get("valor")
                ))

            # Prepara as linhas dos departamentos (filha 2)
            for dep in distribuicao_list:
                db_departamentos_rows.append((
                    self.company_id,
                    codigo_lancamento_omie,
                    dep.get("ccoddep"),
                    dep.get("cdesdep"),
                    dep.get("nperdep"),
                    dep.get("nvaldep")
                ))

        # 1. Inserção na tabela Pai
        query_pagar = """
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
        execute_values(cursor, query_pagar, db_pagar_rows)

        # 2. Inserção nas Categorias
        if db_categorias_rows:
            query_cat = """
                INSERT INTO staging.stg_fato_contas_pagar_categorias (
                    id_empresa, codigo_lancamento_omie, codigo_categoria, percentual, valor
                ) VALUES %s
            """
            execute_values(cursor, query_cat, db_categorias_rows)

        # 3. Inserção nos Departamentos
        if db_departamentos_rows:
            query_dep = """
                INSERT INTO staging.stg_fato_contas_pagar_departamentos (
                    id_empresa, codigo_lancamento_omie, ccoddep, cdesdep, nperdep, nvaldep
                ) VALUES %s
            """
            execute_values(cursor, query_dep, db_departamentos_rows)

        return len(db_pagar_rows)
