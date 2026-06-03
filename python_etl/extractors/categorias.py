import json
from psycopg2.extras import execute_values
from extractors.base import BaseExtractor

def int_or_none(val):
    if val is None or val == "":
        return None
    try:
        return int(val)
    except (ValueError, TypeError):
        return None

class CategoriasExtractor(BaseExtractor):
    def fetch(self) -> list:
        return self.client.fetch_paginated(
            endpoint="geral/categorias",
            call_name="ListarCategorias",
            list_key="categoria_cadastro"
        )

    def clean_staging(self, cursor):
        cursor.execute("DELETE FROM staging.stg_cad_categorias WHERE id_empresa = %s", (self.company_id,))

    def save(self, cursor, raw_records: list) -> int:
        if not raw_records:
            return 0

        db_rows = []
        for record in raw_records:
            # Serializa dados_dre para JSON string se houver
            dados_dre_raw = record.get("dados_dre")
            dados_dre_str = json.dumps(dados_dre_raw) if dados_dre_raw else None

            db_rows.append((
                self.company_id,
                record.get("codigo"),
                record.get("descricao"),
                record.get("descricao_padrao"),
                record.get("descricao_dre"),
                record.get("tipo_categoria"),
                record.get("categoria_superior"),
                record.get("natureza"),
                record.get("conta_despesa"),
                record.get("conta_receita"),
                record.get("conta_inativa"),
                int_or_none(record.get("id_conta_contabil")),
                record.get("tag_conta_contabil"),
                record.get("totalizadora"),
                record.get("definida_pelo_usuario"),
                record.get("transferencia"),
                record.get("nao_exibir"),
                dados_dre_str
            ))

        query = """
            INSERT INTO staging.stg_cad_categorias (
                id_empresa, codigo, descricao, descricao_padrao, descricao_dre,
                tipo_categoria, categoria_superior, natureza, conta_despesa,
                conta_receita, conta_inativa, id_conta_contabil, tag_conta_contabil,
                totalizadora, definida_pelo_usuario, transferencia, nao_exibir,
                json_dados_dre
            ) VALUES %s
        """
        
        execute_values(cursor, query, db_rows)
        return len(db_rows)
