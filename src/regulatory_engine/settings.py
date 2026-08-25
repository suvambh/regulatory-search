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

EMBEDDING_MODEL = os.getenv(
    "EMBEDDING_MODEL",
    "cohere.embed-multilingual-v3",
)

CLASSIFICATION_MODEL = os.getenv(
    "CLASSIFICATION_MODEL",
    "eu.amazon.nova-pro-v1:0",
)