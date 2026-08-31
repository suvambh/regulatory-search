import psycopg

from regulatory_engine.settings import (
    DATABASE_URL,
)


def connect_db(
    db_url: str | None = None,
):
    """
    Create a PostgreSQL connection.

    When db_url is omitted, use the application's
    configured DATABASE_URL.

    An explicit db_url remains useful for tests,
    ingestion tools, and local overrides.
    """

    return psycopg.connect(
        db_url or DATABASE_URL
    )