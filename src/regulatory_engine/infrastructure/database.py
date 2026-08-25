import psycopg

from regulatory_engine.settings import DATABASE_URL


def connect_db():
    return psycopg.connect(
        DATABASE_URL
    )