import time
import httpx
import logging
import truststore
truststore.inject_into_ssl()

logger = logging.getLogger("OmieClient")

class OmieAPIError(Exception):
    """Exceção levantada para erros retornados pela API do Omie (faultcode/faultstring)."""
    def __init__(self, faultcode, faultstring):
        self.faultcode = faultcode
        self.faultstring = faultstring
        super().__init__(f"Erro Omie [{faultcode}]: {faultstring}")

class OmieClient:
    def __init__(self, app_key: str, app_secret: str, base_url: str = "https://app.omie.com.br/api/v1/"):
        self.app_key = app_key
        self.app_secret = app_secret
        self.base_url = base_url.rstrip("/") + "/"
        self.client = httpx.Client(timeout=60.0)

    def _post(self, endpoint: str, call_name: str, params: dict, max_retries: int = 5) -> dict:
        """Realiza uma requisição POST para a API Omie com tratamento de retries e rate limits."""
        url = f"{self.base_url}{endpoint.lstrip('/')}/"
        payload = {
            "call": call_name,
            "app_key": self.app_key,
            "app_secret": self.app_secret,
            "param": [params]
        }

        retry_delay = 2.0
        for attempt in range(1, max_retries + 1):
            try:
                # Pequeno delay preventivo (throttling de 200ms) para evitar hitting rate limit
                time.sleep(0.200)

                response = self.client.post(url, json=payload)
                
                # Se for erro de rate limit (429) ou erro temporário de servidor (503/502)
                if response.status_code in (429, 502, 503):
                    logger.warning(
                        f"Retorno HTTP {response.status_code} na chamada {call_name}. "
                        f"Tentativa {attempt}/{max_retries}. Aguardando {retry_delay}s..."
                    )
                    time.sleep(retry_delay)
                    retry_delay *= 2  # Backoff exponencial
                    continue

                response.raise_for_status()
                data = response.json()

                # Verifica se há falha retornada no corpo JSON (Omie costuma retornar 200 OK para falhas)
                if "faultstring" in data:
                    faultcode = data.get("faultcode", "UNKNOWN")
                    faultstring = data.get("faultstring", "")
                    
                    # Trata limite de requisições por segundo se vier como falha de negócio
                    if "limite de requisições" in faultstring.lower() or "bloqueio temporario" in faultstring.lower():
                        logger.warning(
                            f"Rate limit atingido via JSON no endpoint {endpoint} ({call_name}). "
                            f"Tentativa {attempt}/{max_retries}. Aguardando {retry_delay}s..."
                        )
                        time.sleep(retry_delay)
                        retry_delay *= 2
                        continue
                    
                    raise OmieAPIError(faultcode, faultstring)

                return data

            except (httpx.RequestError, httpx.HTTPStatusError) as e:
                if attempt == max_retries:
                    logger.error(f"Erro de rede persistente na chamada {call_name} para {url}: {e}")
                    raise
                logger.warning(
                    f"Erro de conexão na chamada {call_name} (Tentativa {attempt}/{max_retries}): {e}. "
                    f"Aguardando {retry_delay}s..."
                )
                time.sleep(retry_delay)
                retry_delay *= 2

        raise Exception(f"Falha na requisição {call_name} após {max_retries} tentativas.")

    def fetch_paginated(self, endpoint: str, call_name: str, list_key: str, registros_por_pagina: int = 50, extra_params: dict = None, size_param_name: str = "registros_por_pagina", page_param_name: str = "pagina") -> list:
        """Itera por todas as páginas da API e consolida os dados em uma lista única."""
        all_records = []
        page = 1

        # Parâmetros extras padrões
        if extra_params is None:
            extra_params = {"apenas_importado_api": "N"}

        while True:
            params = {
                page_param_name: page,
                size_param_name: registros_por_pagina
            }
            params.update(extra_params)

            logger.info(f"Baixando {call_name} - Página {page}...")

            try:
                result = self._post(endpoint, call_name, params)
            except OmieAPIError as e:
                # Se for erro indicando que a página não existe ou não há mais registros, encerra loop
                # Omie costuma retornar faultcode '3' ou '100' quando não há mais registros na página
                if e.faultcode in ("3", "100") or "não encontrada" in e.faultstring.lower() or "não encontrado" in e.faultstring.lower():
                    logger.info(f"Fim da paginação de {call_name} na página {page} (Nenhum registro extra encontrado).")
                    break
                raise e

            # Obtém a lista de registros
            records = result.get(list_key)

            # Se for dicionário com sub-registros, extrai valores
            if isinstance(records, dict):
                records = list(records.values())

            # Se vier vazio ou None, chegamos ao final
            if not records:
                logger.info(f"Nenhum registro retornado em {call_name} - Página {page}. Finalizando paginação.")
                break

            all_records.extend(records)

            # Verifica total de páginas — suporta tanto "total_de_paginas" quanto "nTotPaginas"
            total_paginas = result.get("total_de_paginas") or result.get("nTotPaginas")
            if total_paginas and page >= int(total_paginas):
                logger.info(f"Atingido o total de páginas ({total_paginas}) de {call_name}. Finalizando paginação.")
                break

            page += 1

        return all_records
