from psycopg2.extras import execute_values
from extractors.base import BaseExtractor

class DepartamentosExtractor(BaseExtractor):
    def fetch(self, filtro: dict = None) -> list:
        return self.client.fetch_paginated(
            endpoint="geral/departamentos",
            call_name="ListarDepartamentos",
            list_key="departamentos"
        )

    def clean_staging(self, cursor):
        cursor.execute("DELETE FROM staging.stg_cad_departamentos WHERE id_empresa = %s", (self.company_id,))

    def save(self, cursor, raw_records: list) -> int:
        if not raw_records:
            return 0

        db_rows = []
        for record in raw_records:
            db_rows.append((
                self.company_id,
                record.get("codigo"),
                record.get("descricao"),
                record.get("estrutura"),
                record.get("inativo")
            ))

        query = """
            INSERT INTO staging.stg_cad_departamentos (
                id_empresa, codigo, descricao, estrutura, inativo
            ) VALUES %s
        """
        
        execute_values(cursor, query, db_rows)
        return len(db_rows)
