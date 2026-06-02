from psycopg2.extras import execute_values
from extractors.base import BaseExtractor

class ClientesExtractor(BaseExtractor):
    def fetch(self) -> list:
        return self.client.fetch_paginated(
            endpoint="geral/clientes",
            call_name="ListarClientes",
            list_key="clientes_cadastro"
        )

    def clean_staging(self, cursor):
        cursor.execute("DELETE FROM staging.stg_cad_clientes WHERE id_empresa = %s", (self.company_id,))

    def save(self, cursor, raw_records: list) -> int:
        if not raw_records:
            return 0

        db_rows = []
        for record in raw_records:
            db_rows.append((
                self.company_id,
                record.get("codigo_cliente_omie"),
                record.get("cnpj_cpf"),
                record.get("nome_fantasia"),
                record.get("razao_social"),
                record.get("email"),
                record.get("telefone1_ddd"),
                record.get("telefone1_numero"),
                record.get("cidade"),
                record.get("estado"),
                record.get("inativo")
            ))

        query = """
            INSERT INTO staging.stg_cad_clientes (
                id_empresa, codigo_cliente_omie, cnpj_cpf, nome_fantasia,
                razao_social, email, telefone1_ddd, telefone1_numero,
                cidade, estado, inativo
            ) VALUES %s
        """
        
        execute_values(cursor, query, db_rows)
        return len(db_rows)
