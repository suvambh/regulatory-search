from pathlib import Path

from regulatory_engine.infrastructure.database import (
    connect_db,
)


MIGRATIONS_DIR = Path(
    "database/migrations"
)


def ensure_migration_table(
    cur,
):
    """
    Store which SQL migrations have already
    been applied to this database.
    """

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            filename TEXT PRIMARY KEY,
            applied_at TIMESTAMPTZ
                NOT NULL DEFAULT NOW()
        )
        """
    )


def migration_applied(
    cur,
    filename: str,
) -> bool:

    cur.execute(
        """
        SELECT 1
        FROM schema_migrations
        WHERE filename = %s
        """,
        (filename,),
    )

    return (
        cur.fetchone()
        is not None
    )


def run_migrations(
    migrations_dir: Path = MIGRATIONS_DIR,
):
    """
    Apply unapplied .sql migration files
    in filename order.
    """

    migrations_dir = Path(
        migrations_dir
    )

    if not migrations_dir.exists():
        raise FileNotFoundError(
            f"Migrations directory not found: "
            f"{migrations_dir}"
        )

    migration_files = sorted(
        migrations_dir.glob(
            "*.sql"
        )
    )

    if not migration_files:
        raise RuntimeError(
            f"No SQL migrations found in "
            f"{migrations_dir}"
        )

    with connect_db() as conn:

        with conn.cursor() as cur:

            ensure_migration_table(
                cur
            )

            conn.commit()

            for migration_path in (
                migration_files
            ):

                filename = (
                    migration_path.name
                )

                if migration_applied(
                    cur,
                    filename,
                ):
                    print(
                        f"Migration already applied: "
                        f"{filename}"
                    )
                    continue

                print(
                    f"Applying migration: "
                    f"{filename}"
                )

                sql = (
                    migration_path
                    .read_text(
                        encoding="utf-8"
                    )
                )

                cur.execute(
                    sql
                )

                cur.execute(
                    """
                    INSERT INTO schema_migrations (
                        filename
                    )
                    VALUES (%s)
                    """,
                    (
                        filename,
                    ),
                )

                conn.commit()

                print(
                    f"Migration applied: "
                    f"{filename}"
                )

    print(
        "Database migrations complete."
    )