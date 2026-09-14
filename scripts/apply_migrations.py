"""Apply pending versioned SQL migrations to the configured PostgreSQL database."""

import sys
from pathlib import Path

import psycopg

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from backtest_hpg.config import get_database_url


def main() -> None:
    """Apply each migration filename once, in lexical version order."""

    dsn = get_database_url()
    with psycopg.connect(dsn, autocommit=True) as connection:
        has_registry = connection.execute("SELECT to_regclass('schema_migrations')").fetchone()[0] is not None
        applied = set()
        if has_registry:
            applied = {row[0] for row in connection.execute("SELECT version FROM schema_migrations")}
        for path in sorted((PROJECT_ROOT / "migrations").glob("*.sql")):
            if path.name not in applied:
                connection.execute(path.read_text(encoding="utf-8"))
                print(f"Applied {path.name}")


if __name__ == "__main__":
    main()
