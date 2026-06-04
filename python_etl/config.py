import os
from dotenv import load_dotenv

# Carrega o .env se existir
load_dotenv()

class Config:
    # Banco de Dados
    DB_HOST = os.getenv("DB_HOST", "db.jcposydvpilkvszbjxlo.supabase.co")
    DB_PORT = int(os.getenv("DB_PORT", "5432"))
    DB_NAME = os.getenv("DB_NAME", "postgres")
    DB_USER = os.getenv("DB_USER", "postgres")
    DB_PASSWORD = os.getenv("DB_PASSWORD", "au7B3wYEeT8bxgPy")

    # Configurações do Script
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
    CONCURRENCY_LIMIT = int(os.getenv("CONCURRENCY_LIMIT", "3"))

    # Configurações de carga incremental (CDC)
    # Overlap de dias ao montar o filtro incremental de CP/CR (compensa alterações tardias no Omie)
    INCREMENTAL_OVERLAP_DAYS = int(os.getenv("INCREMENTAL_OVERLAP_DAYS", "7"))
    # Janela de dias para extração de lançamentos CC no modo incremental
    CC_WINDOW_DAYS = int(os.getenv("CC_WINDOW_DAYS", "90"))

    @classmethod
    def get_db_dsn(cls) -> str:
        """Retorna a string de conexão (DSN) para o PostgreSQL."""
        return f"host={cls.DB_HOST} port={cls.DB_PORT} dbname={cls.DB_NAME} user={cls.DB_USER} password={cls.DB_PASSWORD}"
