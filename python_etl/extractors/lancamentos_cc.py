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

class LancamentosCCExtractor(BaseExtractor):
    def fetch(self, filtro: dict = None) -> list:
        extra_params = {}
        if filtro and "data_de" in filtro:
            # Filtro incremental por DATA DE ALTERAÇÃO (dDtAltDe), conforme doc oficial do
            # ListarLancCC. Captura lançamentos novos e editados na janela; o UPSERT é
            # idempotente por (id_empresa, ncodlanc).
            extra_params["dDtAltDe"] = filtro["data_de"]
        return self.client.fetch_paginated(
            endpoint="financas/contacorrentelancamentos",
            call_name="ListarLancCC",
            list_key="listaLancamentos",
            registros_por_pagina=20,
            extra_params=extra_params,
            size_param_name="nRegPorPagina",
            page_param_name="nPagina"
        )

    def _build_rows(self, raw_records):
        db_cc_rows = []
        db_categorias_rows = []
        db_departamentos_rows = []

        for record in raw_records:
            ncodlanc = record.get("nCodLanc")
            if not ncodlanc:
                continue

            cabecalho = record.get("cabecalho", {})
            detalhes = record.get("detalhes", {})
            diversos = record.get("diversos", {})
            info = record.get("info", {})
            transferencia = record.get("transferencia", {})

            categorias_list = detalhes.get("aCodCateg", [])
            distribuicao_list = record.get("departamentos", [])

            db_cc_rows.append((
                self.company_id,
                ncodlanc,
                int_or_none(record.get("nCodAgrup")),
                record.get("cCodIntLanc"),
                parse_timestamp(cabecalho.get("dDtLanc")),
                int_or_none(cabecalho.get("nCodCC")),
                cabecalho.get("nValorLanc"),
                detalhes.get("cCodCateg"),
                detalhes.get("cNumDoc"),
                detalhes.get("cObs"),
                detalhes.get("cTipo"),
                int_or_none(detalhes.get("nCodCliente")),
                int_or_none(detalhes.get("nCodProjeto")),
                diversos.get("cNatureza"),
                diversos.get("cOrigem"),
                parse_timestamp(diversos.get("dDtConc")),
                diversos.get("cHrConc"),
                diversos.get("cUsConc"),
                diversos.get("cIdentLanc"),
                int_or_none(diversos.get("nCodComprador")),
                int_or_none(diversos.get("nCodVendedor")),
                int_or_none(diversos.get("nCodLancCR")),
                int_or_none(diversos.get("nCodLancCP")),
                parse_timestamp(info.get("dInc")),
                info.get("hInc"),
                info.get("uInc"),
                parse_timestamp(info.get("dAlt")),
                info.get("hAlt"),
                info.get("uAlt"),
                info.get("cImpAPI"),
                int_or_none(transferencia.get("nCodCCDestino")),
                json.dumps(distribuicao_list) if distribuicao_list else None,
                json.dumps(categorias_list) if categorias_list else None
            ))

            for cat in categorias_list:
                db_categorias_rows.append((
                    self.company_id,
                    ncodlanc,
                    cat.get("cCodCateg"),
                    cat.get("nPercCateg"),
                    cat.get("nValor")
                ))

            for dep in distribuicao_list:
                db_departamentos_rows.append((
                    self.company_id,
                    ncodlanc,
                    dep.get("cCodDep"),
                    dep.get("cDesDep"),
                    dep.get("nPerDep"),
                    dep.get("nValDep")
                ))

        return db_cc_rows, db_categorias_rows, db_departamentos_rows

    def clean_staging(self, cursor):
        cursor.execute("DELETE FROM staging.stg_fato_lancamentos_cc_categorias WHERE id_empresa = %s", (self.company_id,))
        cursor.execute("DELETE FROM staging.stg_fato_lancamentos_cc_departamentos WHERE id_empresa = %s", (self.company_id,))
        cursor.execute("DELETE FROM staging.stg_fato_lancamentos_cc WHERE id_empresa = %s", (self.company_id,))

    def save(self, cursor, raw_records: list) -> int:
        if not raw_records:
            return 0
        db_cc_rows, db_categorias_rows, db_departamentos_rows = self._build_rows(raw_records)
        if not db_cc_rows:
            return 0
        self._insert_pai(cursor, db_cc_rows)
        self._insert_filhas(cursor, db_categorias_rows, db_departamentos_rows)
        return len(db_cc_rows)

    def upsert(self, cursor, raw_records: list) -> int:
        """UPSERT incremental por janela de data. Idempotente por (id_empresa, ncodlanc)."""
        if not raw_records:
            return 0
        db_cc_rows, db_categorias_rows, db_departamentos_rows = self._build_rows(raw_records)
        if not db_cc_rows:
            return 0

        codigos = [row[1] for row in db_cc_rows]
        cursor.execute(
            "DELETE FROM staging.stg_fato_lancamentos_cc_categorias WHERE id_empresa = %s AND ncodlanc = ANY(%s)",
            (self.company_id, codigos)
        )
        cursor.execute(
            "DELETE FROM staging.stg_fato_lancamentos_cc_departamentos WHERE id_empresa = %s AND ncodlanc = ANY(%s)",
            (self.company_id, codigos)
        )

        query_upsert = """
            INSERT INTO staging.stg_fato_lancamentos_cc (
                id_empresa, ncodlanc, ncodagrup, ccodintlanc, ddtlanc, ncodcc,
                nvalorlanc, ccodcateg, cnumdoc, cobs, ctipo, ncodcliente, ncodprojeto,
                cnatureza, corigem, ddtconc, chrconc, cusconc, cidentlanc,
                ncodcomprador, ncodvendedor, ncodlanccr, ncodlanccp, dinc, hinc,
                uinc, dalt, halt, ualt, cimpapi, ncodccdestino, json_distribuicao,
                json_categorias
            ) VALUES %s
            ON CONFLICT (id_empresa, ncodlanc) DO UPDATE SET
                ncodagrup       = EXCLUDED.ncodagrup,
                ccodintlanc     = EXCLUDED.ccodintlanc,
                ddtlanc         = EXCLUDED.ddtlanc,
                ncodcc          = EXCLUDED.ncodcc,
                nvalorlanc      = EXCLUDED.nvalorlanc,
                ccodcateg       = EXCLUDED.ccodcateg,
                cnumdoc         = EXCLUDED.cnumdoc,
                cobs            = EXCLUDED.cobs,
                ctipo           = EXCLUDED.ctipo,
                ncodcliente     = EXCLUDED.ncodcliente,
                ncodprojeto     = EXCLUDED.ncodprojeto,
                cnatureza       = EXCLUDED.cnatureza,
                corigem         = EXCLUDED.corigem,
                ddtconc         = EXCLUDED.ddtconc,
                chrconc         = EXCLUDED.chrconc,
                cusconc         = EXCLUDED.cusconc,
                cidentlanc      = EXCLUDED.cidentlanc,
                ncodcomprador   = EXCLUDED.ncodcomprador,
                ncodvendedor    = EXCLUDED.ncodvendedor,
                ncodlanccr      = EXCLUDED.ncodlanccr,
                ncodlanccp      = EXCLUDED.ncodlanccp,
                dinc            = EXCLUDED.dinc,
                hinc            = EXCLUDED.hinc,
                uinc            = EXCLUDED.uinc,
                dalt            = EXCLUDED.dalt,
                halt            = EXCLUDED.halt,
                ualt            = EXCLUDED.ualt,
                cimpapi         = EXCLUDED.cimpapi,
                ncodccdestino   = EXCLUDED.ncodccdestino,
                json_distribuicao = EXCLUDED.json_distribuicao,
                json_categorias = EXCLUDED.json_categorias,
                dt_extracao     = NOW()
        """
        execute_values(cursor, query_upsert, db_cc_rows)
        self._insert_filhas(cursor, db_categorias_rows, db_departamentos_rows)
        return len(db_cc_rows)

    def _insert_pai(self, cursor, db_cc_rows):
        execute_values(cursor, """
            INSERT INTO staging.stg_fato_lancamentos_cc (
                id_empresa, ncodlanc, ncodagrup, ccodintlanc, ddtlanc, ncodcc,
                nvalorlanc, ccodcateg, cnumdoc, cobs, ctipo, ncodcliente, ncodprojeto,
                cnatureza, corigem, ddtconc, chrconc, cusconc, cidentlanc,
                ncodcomprador, ncodvendedor, ncodlanccr, ncodlanccp, dinc, hinc,
                uinc, dalt, halt, ualt, cimpapi, ncodccdestino, json_distribuicao,
                json_categorias
            ) VALUES %s
        """, db_cc_rows)

    def _insert_filhas(self, cursor, db_categorias_rows, db_departamentos_rows):
        if db_categorias_rows:
            execute_values(cursor, """
                INSERT INTO staging.stg_fato_lancamentos_cc_categorias (
                    id_empresa, ncodlanc, ccodcategoria, npercentual, nvalor
                ) VALUES %s
            """, db_categorias_rows)

        if db_departamentos_rows:
            execute_values(cursor, """
                INSERT INTO staging.stg_fato_lancamentos_cc_departamentos (
                    id_empresa, ncodlanc, ccoddep, cdesdep, nperdep, nvaldep
                ) VALUES %s
            """, db_departamentos_rows)
