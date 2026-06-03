"""
Suíte de testes unitários para o ETL Python do Omie.

Cobre:
  - OmieClient: retry, rate limit, paginação, erros de API
  - LancamentosCCExtractor: filtro de null, mapeamento de campos, tabelas filhas
  - ContasPagarExtractor: filtro de null, parse_date, parse_bool
  - Orchestrator: dry-run, fluxo ACID (sucesso e erro)
"""

import sys
import os
import pytest
from unittest.mock import MagicMock, patch, call
from datetime import datetime, date

# Resolve imports de dentro de python_etl sem precisar instalar como pacote
sys.path.insert(0, os.path.dirname(__file__))

# ---------------------------------------------------------------------------
# parse_timestamp (lancamentos_cc)
# ---------------------------------------------------------------------------

class TestParseTimestamp:
    def setup_method(self):
        from extractors.lancamentos_cc import parse_timestamp
        self.parse = parse_timestamp

    def test_none_retorna_none(self):
        assert self.parse(None) is None

    def test_string_vazia_retorna_none(self):
        assert self.parse("") is None

    def test_formato_ddmmyyyy_hhmmss(self):
        resultado = self.parse("15/03/2024 10:30:00")
        assert resultado == datetime(2024, 3, 15, 10, 30, 0)

    def test_formato_ddmmyyyy(self):
        resultado = self.parse("01/01/2023")
        assert resultado == datetime(2023, 1, 1, 0, 0, 0)

    def test_formato_iso_com_hora(self):
        resultado = self.parse("2024-06-02 08:00:00")
        assert resultado == datetime(2024, 6, 2, 8, 0, 0)

    def test_formato_iso_sem_hora(self):
        resultado = self.parse("2024-06-02")
        assert resultado == datetime(2024, 6, 2, 0, 0, 0)

    def test_formato_desconhecido_retorna_string(self):
        raw = "32/13/9999"
        assert self.parse(raw) == raw


# ---------------------------------------------------------------------------
# parse_date e parse_bool (contas_pagar)
# ---------------------------------------------------------------------------

class TestParseDateContasPagar:
    def setup_method(self):
        from extractors.contas_pagar import parse_date
        self.parse = parse_date

    def test_none_retorna_none(self):
        assert self.parse(None) is None

    def test_formato_ddmmyyyy(self):
        assert self.parse("20/05/2025") == date(2025, 5, 20)

    def test_formato_iso(self):
        assert self.parse("2025-05-20") == date(2025, 5, 20)

    def test_formato_iso_com_hora(self):
        assert self.parse("2025-05-20 00:00:00") == date(2025, 5, 20)

    def test_formato_invalido_retorna_string(self):
        assert self.parse("nao-e-data") == "nao-e-data"


class TestParseBool:
    def setup_method(self):
        from extractors.contas_pagar import parse_bool
        self.parse = parse_bool

    def test_none_retorna_none(self):
        assert self.parse(None) is None

    def test_s_maiusculo(self):
        assert self.parse("S") is True

    def test_n_maiusculo(self):
        assert self.parse("N") is False

    def test_sim(self):
        assert self.parse("sim") is True

    def test_nao_com_cedilha(self):
        assert self.parse("não") is False

    def test_bool_true(self):
        assert self.parse(True) is True

    def test_bool_false(self):
        assert self.parse(False) is False


# ---------------------------------------------------------------------------
# OmieClient — _post
# ---------------------------------------------------------------------------

class TestOmieClientPost:
    def _make_client(self, mock_http_class):
        from omie_client import OmieClient
        mock_http_instance = MagicMock()
        mock_http_class.return_value = mock_http_instance
        client = OmieClient("key123", "secret456")
        return client, mock_http_instance

    @patch("omie_client.time.sleep")
    @patch("omie_client.httpx.Client")
    def test_sucesso_retorna_dados(self, mock_httpx, mock_sleep):
        client, mock_http = self._make_client(mock_httpx)
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = {"lista": [1, 2, 3]}
        mock_http.post.return_value = resp

        resultado = client._post("financas/categorias", "ListarCategorias", {})

        assert resultado == {"lista": [1, 2, 3]}
        mock_sleep.assert_called_once_with(0.200)

    @patch("omie_client.time.sleep")
    @patch("omie_client.httpx.Client")
    def test_429_faz_retry_e_retorna_sucesso(self, mock_httpx, mock_sleep):
        from omie_client import OmieClient
        client, mock_http = self._make_client(mock_httpx)

        resp_429 = MagicMock()
        resp_429.status_code = 429

        resp_ok = MagicMock()
        resp_ok.status_code = 200
        resp_ok.json.return_value = {"ok": True}

        mock_http.post.side_effect = [resp_429, resp_ok]

        resultado = client._post("ep", "Call", {})
        assert resultado == {"ok": True}
        assert mock_http.post.call_count == 2

    @patch("omie_client.time.sleep")
    @patch("omie_client.httpx.Client")
    def test_faultstring_rate_limit_faz_retry(self, mock_httpx, mock_sleep):
        client, mock_http = self._make_client(mock_httpx)

        resp_limit = MagicMock()
        resp_limit.status_code = 200
        resp_limit.json.return_value = {
            "faultcode": "999",
            "faultstring": "Bloqueio temporario de requisições"
        }

        resp_ok = MagicMock()
        resp_ok.status_code = 200
        resp_ok.json.return_value = {"data": []}

        mock_http.post.side_effect = [resp_limit, resp_ok]

        resultado = client._post("ep", "Call", {})
        assert resultado == {"data": []}

    @patch("omie_client.time.sleep")
    @patch("omie_client.httpx.Client")
    def test_faultstring_negocio_levanta_omieapierror(self, mock_httpx, mock_sleep):
        from omie_client import OmieAPIError
        client, mock_http = self._make_client(mock_httpx)

        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = {"faultcode": "42", "faultstring": "Empresa inválida"}
        mock_http.post.return_value = resp

        with pytest.raises(OmieAPIError) as exc:
            client._post("ep", "Call", {})

        assert exc.value.faultcode == "42"
        assert "Empresa inválida" in str(exc.value)

    @patch("omie_client.time.sleep")
    @patch("omie_client.httpx.Client")
    def test_max_retries_esgotados_levanta_excecao(self, mock_httpx, mock_sleep):
        import httpx
        client, mock_http = self._make_client(mock_httpx)
        mock_http.post.side_effect = httpx.RequestError("timeout")

        with pytest.raises(httpx.RequestError):
            client._post("ep", "Call", {}, max_retries=3)

        assert mock_http.post.call_count == 3


# ---------------------------------------------------------------------------
# OmieClient — fetch_paginated
# ---------------------------------------------------------------------------

class TestOmieClientFetchPaginated:
    def _make_client(self, mock_http_class):
        from omie_client import OmieClient
        mock_http_instance = MagicMock()
        mock_http_class.return_value = mock_http_instance
        client = OmieClient("k", "s")
        return client

    @patch("omie_client.time.sleep")
    @patch("omie_client.httpx.Client")
    def test_para_quando_total_de_paginas_atingido(self, mock_httpx, mock_sleep):
        client = self._make_client(mock_httpx)

        pagina1 = {"itens": [{"id": 1}, {"id": 2}], "total_de_paginas": 2}
        pagina2 = {"itens": [{"id": 3}], "total_de_paginas": 2}

        def fake_post(endpoint, call_name, params, max_retries=5):
            if params["pagina"] == 1:
                return pagina1
            return pagina2

        client._post = MagicMock(side_effect=fake_post)

        result = client.fetch_paginated("ep", "Call", "itens")
        assert len(result) == 3
        assert client._post.call_count == 2

    @patch("omie_client.time.sleep")
    @patch("omie_client.httpx.Client")
    def test_para_quando_lista_vazia(self, mock_httpx, mock_sleep):
        client = self._make_client(mock_httpx)

        def fake_post(endpoint, call_name, params, max_retries=5):
            if params["pagina"] == 1:
                return {"itens": [{"id": 1}]}
            return {"itens": []}  # segunda página vazia

        client._post = MagicMock(side_effect=fake_post)

        result = client.fetch_paginated("ep", "Call", "itens")
        assert len(result) == 1

    @patch("omie_client.time.sleep")
    @patch("omie_client.httpx.Client")
    def test_faultcode_3_encerra_paginacao(self, mock_httpx, mock_sleep):
        from omie_client import OmieAPIError
        client = self._make_client(mock_httpx)

        def fake_post(endpoint, call_name, params, max_retries=5):
            if params["pagina"] == 1:
                return {"itens": [{"id": 1}]}
            raise OmieAPIError("3", "Página não encontrada")

        client._post = MagicMock(side_effect=fake_post)

        result = client.fetch_paginated("ep", "Call", "itens")
        assert len(result) == 1

    @patch("omie_client.time.sleep")
    @patch("omie_client.httpx.Client")
    def test_faultcode_negocio_propaga_excecao(self, mock_httpx, mock_sleep):
        from omie_client import OmieAPIError
        client = self._make_client(mock_httpx)

        client._post = MagicMock(side_effect=OmieAPIError("500", "Erro interno"))

        with pytest.raises(OmieAPIError):
            client.fetch_paginated("ep", "Call", "itens")


# ---------------------------------------------------------------------------
# LancamentosCCExtractor — clean_staging e save
# ---------------------------------------------------------------------------

class TestLancamentosCCExtractor:
    def _make_extractor(self):
        from omie_client import OmieClient
        from extractors.lancamentos_cc import LancamentosCCExtractor
        client = MagicMock(spec=OmieClient)
        return LancamentosCCExtractor(client, company_id=1)

    def test_clean_staging_executa_tres_deletes_na_ordem(self):
        extractor = self._make_extractor()
        cursor = MagicMock()
        extractor.clean_staging(cursor)

        calls = cursor.execute.call_args_list
        assert len(calls) == 3
        assert "stg_fato_lancamentos_cc_categorias" in calls[0][0][0]
        assert "stg_fato_lancamentos_cc_departamentos" in calls[1][0][0]
        assert "stg_fato_lancamentos_cc" in calls[2][0][0]
        # todos passam o company_id correto
        for c in calls:
            assert c[0][1] == (1,)

    @patch("extractors.lancamentos_cc.execute_values")
    def test_save_lista_vazia_retorna_zero(self, mock_ev):
        extractor = self._make_extractor()
        cursor = MagicMock()
        result = extractor.save(cursor, [])
        assert result == 0
        mock_ev.assert_not_called()

    @patch("extractors.lancamentos_cc.execute_values")
    def test_save_filtra_registros_sem_ncodlanc(self, mock_ev):
        extractor = self._make_extractor()
        cursor = MagicMock()
        records = [
            {"nCodLanc": None, "cabecalho": {}, "detalhes": {}, "diversos": {}, "info": {}, "transferencia": {}},
            {"cabecalho": {}, "detalhes": {}, "diversos": {}, "info": {}, "transferencia": {}},  # sem chave
        ]
        result = extractor.save(cursor, records)
        assert result == 0
        mock_ev.assert_not_called()

    @patch("extractors.lancamentos_cc.execute_values")
    def test_save_registro_valido_chama_insert(self, mock_ev):
        extractor = self._make_extractor()
        cursor = MagicMock()
        records = [{
            "nCodLanc": 12345,
            "nCodAgrup": None,
            "cCodIntLanc": "INT-001",
            "cabecalho": {"dDtLanc": "01/06/2026 10:00:00", "nCodCC": 99, "nValorLanc": 1500.0},
            "detalhes": {"cCodCateg": "1.01", "cNumDoc": "DOC1", "cObs": "", "cTipo": "D", "nCodCliente": 7, "nCodProjeto": None, "aCodCateg": []},
            "diversos": {"cNatureza": "D", "cOrigem": "API", "dDtConc": None, "cHrConc": None, "cUsConc": None, "cIdentLanc": None, "nCodComprador": None, "nCodVendedor": None, "nCodLancCR": None, "nCodLancCP": None},
            "info": {"dInc": "01/06/2026", "hInc": "10:00", "uInc": "admin", "dAlt": None, "hAlt": None, "uAlt": None, "cImpAPI": "N"},
            "transferencia": {"nCodCCDestino": None},
            "departamentos": []
        }]

        result = extractor.save(cursor, records)
        assert result == 1
        # deve ter sido chamado ao menos 1 vez (para a tabela pai)
        assert mock_ev.call_count >= 1

    @patch("extractors.lancamentos_cc.execute_values")
    def test_save_com_categorias_e_departamentos(self, mock_ev):
        extractor = self._make_extractor()
        cursor = MagicMock()
        records = [{
            "nCodLanc": 99,
            "cabecalho": {}, "diversos": {}, "info": {}, "transferencia": {},
            "detalhes": {
                "aCodCateg": [
                    {"cCodCateg": "1.01", "nPercCateg": 60.0, "nValor": 900.0},
                    {"cCodCateg": "2.01", "nPercCateg": 40.0, "nValor": 600.0},
                ]
            },
            "departamentos": [
                {"cCodDep": "DEP1", "cDesDep": "Vendas", "nPerDep": 100.0, "nValDep": 1500.0}
            ]
        }]

        extractor.save(cursor, records)
        # Deve chamar execute_values 3 vezes: pai, categorias, departamentos
        assert mock_ev.call_count == 3

    @patch("extractors.lancamentos_cc.execute_values")
    def test_save_sem_categorias_nao_chama_insert_categorias(self, mock_ev):
        extractor = self._make_extractor()
        cursor = MagicMock()
        records = [{
            "nCodLanc": 88,
            "cabecalho": {}, "diversos": {}, "info": {}, "transferencia": {},
            "detalhes": {"aCodCateg": []},
            "departamentos": []
        }]

        extractor.save(cursor, records)
        # Apenas a tabela pai
        assert mock_ev.call_count == 1


# ---------------------------------------------------------------------------
# ContasPagarExtractor — save
# ---------------------------------------------------------------------------

class TestContasPagarExtractor:
    def _make_extractor(self):
        from omie_client import OmieClient
        from extractors.contas_pagar import ContasPagarExtractor
        client = MagicMock(spec=OmieClient)
        return ContasPagarExtractor(client, company_id=3)

    @patch("extractors.contas_pagar.execute_values")
    def test_filtra_sem_codigo_lancamento(self, mock_ev):
        extractor = self._make_extractor()
        cursor = MagicMock()
        records = [{"codigo_lancamento_omie": None, "info": {}}]
        result = extractor.save(cursor, records)
        assert result == 0
        mock_ev.assert_not_called()

    @patch("extractors.contas_pagar.execute_values")
    def test_registro_valido_retorna_count(self, mock_ev):
        extractor = self._make_extractor()
        cursor = MagicMock()
        records = [
            {"codigo_lancamento_omie": 1001, "info": {}, "categorias": [], "distribuicao": []},
            {"codigo_lancamento_omie": 1002, "info": {}, "categorias": [], "distribuicao": []},
        ]
        result = extractor.save(cursor, records)
        assert result == 2

    @patch("extractors.contas_pagar.execute_values")
    def test_categorias_e_distribuicao_geram_inserts_filhos(self, mock_ev):
        extractor = self._make_extractor()
        cursor = MagicMock()
        records = [{
            "codigo_lancamento_omie": 2000,
            "info": {},
            "categorias": [{"codigo_categoria": "CAT1", "percentual": 100.0, "valor": 500.0}],
            "distribuicao": [{"ccoddep": "DEP1", "cdesdep": "Geral", "nperdep": 100.0, "nvaldep": 500.0}]
        }]
        extractor.save(cursor, records)
        assert mock_ev.call_count == 3


# ---------------------------------------------------------------------------
# Orchestrator — executar_etl_empresa
# ---------------------------------------------------------------------------

class TestOrchestrator:
    def _make_cursor_mock(self, log_id=42):
        cursor = MagicMock()
        cursor.__enter__ = MagicMock(return_value=cursor)
        cursor.__exit__ = MagicMock(return_value=False)
        cursor.fetchone.return_value = (log_id,)
        return cursor

    def _make_conn_mock(self, cursor):
        conn = MagicMock()
        conn.cursor.return_value = cursor
        return conn

    @patch("orchestrator.get_db_transaction")
    @patch("orchestrator.OmieClient")
    def test_dry_run_nao_altera_staging(self, mock_omie_class, mock_tx):
        from orchestrator import executar_etl_empresa
        cursor = self._make_cursor_mock()
        conn = self._make_conn_mock(cursor)

        mock_client = MagicMock()
        mock_omie_class.return_value = mock_client

        extractor_mock = MagicMock()
        extractor_mock.fetch.return_value = [{"id": 1}]

        with patch("orchestrator.EXTRACTOR_MAPPING", {"dummy": MagicMock(return_value=extractor_mock)}):
            executar_etl_empresa(conn, 1, "Empresa Test", "k", "s", dry_run=True)

        # Em dry_run, clean_staging e save NÃO devem ser chamados
        extractor_mock.clean_staging.assert_not_called()
        extractor_mock.save.assert_not_called()
        # get_db_transaction NÃO deve ser chamado
        mock_tx.assert_not_called()

    @patch("orchestrator.get_db_transaction")
    @patch("orchestrator.OmieClient")
    def test_sucesso_commita_e_registra_fim(self, mock_omie_class, mock_tx):
        from contextlib import contextmanager
        from orchestrator import executar_etl_empresa

        cursor = self._make_cursor_mock()
        conn = self._make_conn_mock(cursor)

        mock_client = MagicMock()
        mock_omie_class.return_value = mock_client

        extractor_mock = MagicMock()
        extractor_mock.fetch.return_value = [{"id": 1}]
        extractor_mock.save.return_value = 10

        @contextmanager
        def fake_tx(c):
            yield c

        mock_tx.side_effect = fake_tx

        with patch("orchestrator.EXTRACTOR_MAPPING", {"dummy": MagicMock(return_value=extractor_mock)}):
            executar_etl_empresa(conn, 1, "Empresa Test", "k", "s", dry_run=False)

        extractor_mock.clean_staging.assert_called_once()
        extractor_mock.save.assert_called_once()
        # commit deve ter sido chamado (início do lote + fim do lote)
        assert conn.commit.call_count >= 2

    @patch("orchestrator.get_db_transaction")
    @patch("orchestrator.OmieClient")
    def test_erro_no_fetch_registra_erro_e_propaga(self, mock_omie_class, mock_tx):
        from orchestrator import executar_etl_empresa

        cursor = self._make_cursor_mock()
        conn = self._make_conn_mock(cursor)

        mock_client = MagicMock()
        mock_omie_class.return_value = mock_client

        extractor_mock = MagicMock()
        extractor_mock.fetch.side_effect = Exception("API indisponível")

        with patch("orchestrator.EXTRACTOR_MAPPING", {"dummy": MagicMock(return_value=extractor_mock)}):
            with pytest.raises(Exception, match="API indisponível"):
                executar_etl_empresa(conn, 1, "Empresa Test", "k", "s", dry_run=False)

        # staging NÃO deve ter sido tocado
        extractor_mock.clean_staging.assert_not_called()
        extractor_mock.save.assert_not_called()
