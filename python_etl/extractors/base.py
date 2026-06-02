from abc import ABC, abstractmethod
from omie_client import OmieClient

class BaseExtractor(ABC):
    def __init__(self, client: OmieClient, company_id: int):
        self.client = client
        self.company_id = company_id

    @abstractmethod
    def fetch(self) -> list:
        """Coleta os dados do Omie API e retorna como lista de registros brutos em memória."""
        pass

    @abstractmethod
    def clean_staging(self, cursor):
        """Executa a query de DELETE para limpar os dados antigos desta empresa no staging."""
        pass

    @abstractmethod
    def save(self, cursor, raw_records: list) -> int:
        """Mapeia os dados brutos e faz a inserção em lote (Bulk Insert) no banco de dados.
        Retorna o número de registros inseridos.
        """
        pass
