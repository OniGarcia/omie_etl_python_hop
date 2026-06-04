from abc import ABC, abstractmethod
from omie_client import OmieClient

class BaseExtractor(ABC):
    def __init__(self, client: OmieClient, company_id: int):
        self.client = client
        self.company_id = company_id

    @abstractmethod
    def fetch(self, filtro: dict = None) -> list:
        """Coleta dados da API Omie. filtro=None → carga full; dict com chaves de data → incremental."""
        pass

    @abstractmethod
    def clean_staging(self, cursor):
        """DELETE completo dos dados desta empresa no staging (usado no full reload)."""
        pass

    @abstractmethod
    def save(self, cursor, raw_records: list) -> int:
        """INSERT em lote no staging. Retorna número de registros inseridos."""
        pass

    def upsert(self, cursor, raw_records: list) -> int:
        """UPSERT incremental no staging. Implementado apenas nos extractors de tabelas fato."""
        raise NotImplementedError(f"{self.__class__.__name__} não implementa upsert incremental.")
