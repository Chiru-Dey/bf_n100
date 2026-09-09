import pytest

from src.etl.loader import connect_db, init_schema
from src.settings import get_settings


@pytest.fixture
def db_conn(monkeypatch, tmp_path):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "test.db"))
    get_settings.cache_clear()
    conn = connect_db()
    init_schema(conn)
    yield conn
    conn.close()
    get_settings.cache_clear()
