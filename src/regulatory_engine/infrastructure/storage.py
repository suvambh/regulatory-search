from pathlib import Path, PurePosixPath

import boto3
from botocore.exceptions import ClientError

from regulatory_engine.settings import (
    AWS_REGION,
    REGULATORY_S3_BUCKET,
    REGULATORY_S3_PROCESSED_PREFIX,
    REGULATORY_S3_RAW_PREFIX,
)


def s3_enabled() -> bool:
    return bool(REGULATORY_S3_BUCKET)


def get_s3_client():
    return boto3.client(
        "s3",
        region_name=AWS_REGION,
    )


def s3_key_for_path(
    local_path: Path,
) -> str:
    """
    Convert an application-local path into
    its persistent S3 object key.

    corpus/... -> raw/...
    data/...   -> processed/...
    """

    path = Path(local_path)

    parts = path.parts

    if not parts:
        raise ValueError(
            "Empty local path"
        )

    if parts[0] == "corpus":

        relative = Path(
            *parts[1:]
        )

        return str(
            PurePosixPath(
                REGULATORY_S3_RAW_PREFIX
            )
            / PurePosixPath(
                relative.as_posix()
            )
        )

    if parts[0] == "data":

        relative = Path(
            *parts[1:]
        )

        return str(
            PurePosixPath(
                REGULATORY_S3_PROCESSED_PREFIX
            )
            / PurePosixPath(
                relative.as_posix()
            )
        )

    raise ValueError(
        "Only paths under corpus/ or data/ "
        f"can be mapped to S3: {local_path}"
    )


def object_exists(
    key: str,
) -> bool:

    if not s3_enabled():
        return False

    client = get_s3_client()

    try:

        client.head_object(
            Bucket=REGULATORY_S3_BUCKET,
            Key=key,
        )

        return True

    except ClientError as exc:

        error_code = (
            exc.response
            .get("Error", {})
            .get("Code")
        )

        if error_code in {
            "404",
            "NoSuchKey",
            "NotFound",
        }:
            return False

        raise


def download_file(
    key: str,
    local_path: Path,
) -> Path:

    if not s3_enabled():
        raise RuntimeError(
            "S3 storage is not configured"
        )

    local_path = Path(
        local_path
    )

    local_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    client = get_s3_client()

    print(
        f"Downloading "
        f"s3://{REGULATORY_S3_BUCKET}/{key}"
        f" -> {local_path}"
    )

    client.download_file(
        REGULATORY_S3_BUCKET,
        key,
        str(local_path),
    )

    return local_path


def upload_file(
    local_path: Path,
    key: str | None = None,
) -> str | None:

    if not s3_enabled():
        return None

    local_path = Path(
        local_path
    )

    if not local_path.exists():
        raise FileNotFoundError(
            local_path
        )

    if key is None:
        key = s3_key_for_path(
            local_path
        )

    client = get_s3_client()

    print(
        f"Uploading {local_path} -> "
        f"s3://{REGULATORY_S3_BUCKET}/{key}"
    )

    client.upload_file(
        str(local_path),
        REGULATORY_S3_BUCKET,
        key,
    )

    return key


def ensure_local_file(
    local_path: Path,
) -> Path:
    """
    Ensure that a required input exists locally.

    If already local, reuse it.

    Otherwise, if S3 is configured, download it.
    """

    local_path = Path(
        local_path
    )

    if local_path.exists():
        return local_path

    if not s3_enabled():
        raise FileNotFoundError(
            local_path
        )

    key = s3_key_for_path(
        local_path
    )

    if not object_exists(key):
        raise FileNotFoundError(
            f"Neither local file nor S3 object "
            f"exists for {local_path}. "
            f"Expected S3 key: {key}"
        )

    return download_file(
        key=key,
        local_path=local_path,
    )


def restore_cached_file(
    local_path: Path,
) -> bool:
    """
    Restore an already-processed artifact from S3.

    Returns True when the local file is ready
    to use, False when it must be generated.
    """

    local_path = Path(
        local_path
    )

    if local_path.exists():
        return True

    if not s3_enabled():
        return False

    key = s3_key_for_path(
        local_path
    )

    if not object_exists(key):
        return False

    download_file(
        key=key,
        local_path=local_path,
    )

    return True


def persist_file(
    local_path: Path,
) -> None:
    """
    Persist a generated artifact when S3
    storage is enabled.

    In local-only mode this is intentionally
    a no-op.
    """

    if not s3_enabled():
        return

    upload_file(
        local_path=local_path,
    )