import psycopg2
from contextlib import contextmanager
from config import Config

@contextmanager
def get_db_connection():
    """Context manager para gerenciar a abertura e fechamento de conexões com o PostgreSQL."""
    conn = psycopg2.connect(Config.get_db_dsn())
    try:
        yield conn
    finally:
        conn.close()

@contextmanager
def get_db_transaction(conn):
    """Context manager para garantir transações atômicas (Commit / Rollback).
    
    Uso:
        with get_db_connection() as conn:
            with get_db_transaction(conn):
                # Executa queries
                # Caso ocorra exceção, executa ROLLBACK
                # Caso saia do bloco com sucesso, executa COMMIT
    """
    try:
        yield conn
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise e
