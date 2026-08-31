from functools import lru_cache

import boto3

from regulatory_engine.settings import AWS_REGION


@lru_cache
def get_textract_client():
    return boto3.client(
        "textract",
        region_name=AWS_REGION,
    )