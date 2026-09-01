from regulatory_engine.infrastructure.database import (
    connect_db,
)


def _row_to_dict(
    row,
):
    if row is None:
        return None

    return {
        "document_code":
            row[0],

        "document_name":
            row[1],

        "provision_id":
            row[2],

        "provision_type":
            row[3],

        "provision_code":
            row[4],

        "title":
            row[5],

        "text":
            row[6],

        "device_class":
            row[7],

        "source_section":
            row[8],

        "source_page":
            row[9],

        "source_excerpt":
            row[10],
    }


def get_medical_provision(
    provision_id: str,
    document_code: str | None = None,
):
    """
    Retrieve one exact medical regulatory provision.
    """

    with connect_db() as conn:
        with conn.cursor() as cur:

            if document_code is None:

                cur.execute(
                    """
                    SELECT
                        document_code,
                        document_name,
                        provision_id,
                        provision_type,
                        provision_code,
                        title,
                        text,
                        device_class,
                        source_section,
                        source_page,
                        source_excerpt
                    FROM medical_provisions
                    WHERE provision_id = %s
                    LIMIT 1
                    """,
                    (
                        provision_id,
                    ),
                )

            else:

                cur.execute(
                    """
                    SELECT
                        document_code,
                        document_name,
                        provision_id,
                        provision_type,
                        provision_code,
                        title,
                        text,
                        device_class,
                        source_section,
                        source_page,
                        source_excerpt
                    FROM medical_provisions
                    WHERE provision_id = %s
                      AND document_code = %s
                    LIMIT 1
                    """,
                    (
                        provision_id,
                        document_code,
                    ),
                )

            row = cur.fetchone()

    return _row_to_dict(
        row
    )


def find_medical_provisions(
    *,
    document_code: str,
    provision_type: str | None = None,
) -> list[dict]:
    """
    Retrieve regulatory provisions structurally.

    No semantic search is used here.
    """

    with connect_db() as conn:
        with conn.cursor() as cur:

            if provision_type is None:

                cur.execute(
                    """
                    SELECT
                        document_code,
                        document_name,
                        provision_id,
                        provision_type,
                        provision_code,
                        title,
                        text,
                        device_class,
                        source_section,
                        source_page,
                        source_excerpt
                    FROM medical_provisions
                    WHERE document_code = %s
                    ORDER BY
                        source_page,
                        id
                    """,
                    (
                        document_code,
                    ),
                )

            else:

                cur.execute(
                    """
                    SELECT
                        document_code,
                        document_name,
                        provision_id,
                        provision_type,
                        provision_code,
                        title,
                        text,
                        device_class,
                        source_section,
                        source_page,
                        source_excerpt
                    FROM medical_provisions
                    WHERE document_code = %s
                      AND provision_type = %s
                    ORDER BY
                        source_page,
                        id
                    """,
                    (
                        document_code,
                        provision_type,
                    ),
                )

            rows = cur.fetchall()

    return [
        _row_to_dict(
            row
        )
        for row
        in rows
    ]


def get_medical_provisions(
    provision_ids: list[str],
    *,
    document_code: str,
) -> list[dict]:
    """
    Retrieve an explicit bounded set of provisions.
    """

    if not provision_ids:
        return []

    with connect_db() as conn:
        with conn.cursor() as cur:

            cur.execute(
                """
                SELECT
                    document_code,
                    document_name,
                    provision_id,
                    provision_type,
                    provision_code,
                    title,
                    text,
                    device_class,
                    source_section,
                    source_page,
                    source_excerpt
                FROM medical_provisions
                WHERE document_code = %s
                  AND provision_id = ANY(%s)
                ORDER BY
                    source_page,
                    id
                """,
                (
                    document_code,
                    provision_ids,
                ),
            )

            rows = cur.fetchall()

    return [
        _row_to_dict(
            row
        )
        for row
        in rows
    ]