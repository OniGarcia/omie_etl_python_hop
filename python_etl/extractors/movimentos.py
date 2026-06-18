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

def parse_date(dt_str):
    if not dt_str:
        return None
    for fmt in ('%d/%m/%Y %H:%M:%S', '%d/%m/%Y', '%Y-%m-%d %H:%M:%S', '%Y-%m-%d'):
        try:
            return datetime.strptime(dt_str, fmt).date()
        except ValueError:
            continue
    return None

class MovimentosExtractor(BaseExtractor):
    """Extrai os Movimentos Financeiros (financas/mf -> ListarMovimentos).

    Fonte da DATA REAL DE BAIXA (dDtPagamento) por título — correta inclusive em
    baixas agrupadas, onde o lançamento de conta corrente referencia só um dos
    títulos quitados. Full reload a cada execução (volume pequeno)."""

    def fetch(self, filtro: dict = None) -> list:
        return self.client.fetch_paginated(
            endpoint="financas/mf",
            call_name="ListarMovimentos",
            list_key="movimentos",
            registros_por_pagina=500,
            extra_params={},
            size_param_name="nRegPorPagina",
            page_param_name="nPagina"
        )

    def _build_rows(self, raw_records):
        rows = []
        for record in raw_records:
            det = record.get("detalhes", {}) or {}
            resumo = record.get("resumo", {}) or {}
            ncodtitulo = int_or_none(det.get("nCodTitulo"))
            if not ncodtitulo:
                continue
            rows.append((
                self.company_id,
                ncodtitulo,
                int_or_none(det.get("nCodTitRepet")),
                det.get("cCodCateg"),
                det.get("cGrupo"),
                det.get("cNatureza"),
                det.get("cStatus"),
                det.get("cTipo"),
                det.get("cOrigem"),
                parse_date(det.get("dDtEmissao")),
                parse_date(det.get("dDtVenc")),
                parse_date(det.get("dDtPrevisao")),
                parse_date(det.get("dDtPagamento")),
                parse_date(det.get("dDtRegistro")),
                int_or_none(det.get("nCodCC")),
                int_or_none(det.get("nCodCliente")),
                det.get("cCPFCNPJCliente"),
                det.get("nValorTitulo"),
                resumo.get("nValPago"),
                resumo.get("nValAberto"),
                resumo.get("nValLiquido"),
                resumo.get("cLiquidado"),
            ))
        return rows

    def clean_staging(self, cursor):
        cursor.execute("DELETE FROM staging.stg_fato_movimentos WHERE id_empresa = %s", (self.company_id,))

    def save(self, cursor, raw_records: list) -> int:
        if not raw_records:
            return 0
        rows = self._build_rows(raw_records)
        if not rows:
            return 0
        execute_values(cursor, """
            INSERT INTO staging.stg_fato_movimentos (
                id_empresa, ncodtitulo, ncodtitrepet, ccodcateg, cgrupo, cnatureza,
                cstatus, ctipo, corigem, ddtemissao, ddtvenc, ddtprevisao, ddtpagamento,
                ddtregistro, ncodcc, ncodcliente, ccpfcnpjcliente, nvalortitulo,
                nvalpago, nvalaberto, nvalliquido, cliquidado
            ) VALUES %s
        """, rows)
        return len(rows)
