"""Local, transactional storage. Immutable revisions prevent accidental overwrites."""
from contextlib import contextmanager
from pathlib import Path
import sqlite3
from backend.core.config import settings


@contextmanager
def database():
    path = Path(settings.HISTORY_DB_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path, timeout=10)
    connection.row_factory = sqlite3.Row
    try:
        connection.execute('''CREATE TABLE IF NOT EXISTS revisions (
            audit_id TEXT NOT NULL, revision INTEGER NOT NULL, title TEXT NOT NULL,
            note TEXT NOT NULL, created_at TEXT NOT NULL, report TEXT NOT NULL,
            PRIMARY KEY (audit_id, revision))''')
        connection.execute('''CREATE TABLE IF NOT EXISTS evaluation_examples (
            example_id TEXT PRIMARY KEY, payload TEXT NOT NULL)''')
        yield connection
        connection.commit()
    except BaseException:
        connection.rollback()
        raise
    finally:
        connection.close()
