from psycopg2.extras import execute_values
from extractors.base import BaseExtractor

class ContasCorrentesExtractor(BaseExtractor):
    def fetch(self, filtro: dict = None) -> list:
        return self.client.fetch_paginated(
            endpoint="geral/contacorrente",
            call_name="ListarContasCorrentes",
            list_key="ListarContasCorrentes"
        )

    def clean_staging(self, cursor):
        cursor.execute("DELETE FROM staging.stg_cad_contas_correntes WHERE id_empresa = %s", (self.company_id,))

    def save(self, cursor, raw_records: list) -> int:
        if not raw_records:
            return 0

        db_rows = []
        for record in raw_records:
            db_rows.append((
                self.company_id,
                record.get("nCodCC"),
                record.get("cCodCCInt"),
                record.get("descricao"),
                # codigo_banco não mapeado no original, deixamos nulo
                None,
                record.get("codigo_agencia"),
                record.get("numero_conta_corrente"),
                record.get("tipo"),
                record.get("saldo_inicial")
            ))

        query = """
            INSERT INTO staging.stg_cad_contas_correntes (
                id_empresa, n_cod_cc, c_cod_cc_int, descricao,
                codigo_banco, codigo_agencia, numero_conta_corrente,
                tipo, saldo_inicial
            ) VALUES %s
        """
        
        execute_values(cursor, query, db_rows)
        return len(db_rows)
