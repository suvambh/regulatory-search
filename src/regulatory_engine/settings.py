import os


DATABASE_URL = os.getenv(
    "DATABASE_URL",
    (
        "postgresql://regulatory_app:"
        "local_dev_password@localhost:5433/regulatory"
    ),
)


AWS_REGION = os.getenv(
    "AWS_REGION",
    "eu-west-3",
)

REGULATORY_S3_BUCKET = os.getenv(
    "REGULATORY_S3_BUCKET",
)

REGULATORY_S3_RAW_PREFIX = os.getenv(
    "REGULATORY_S3_RAW_PREFIX",
    "raw",
)

REGULATORY_S3_PROCESSED_PREFIX = os.getenv(
    "REGULATORY_S3_PROCESSED_PREFIX",
    "processed",
)

EMBEDDING_MODEL = os.getenv(
    "EMBEDDING_MODEL",
    "cohere.embed-multilingual-v3",
)


CLASSIFICATION_MODEL = os.getenv(
    "CLASSIFICATION_MODEL",
    "eu.amazon.nova-pro-v1:0",
)