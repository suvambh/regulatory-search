import json

import boto3


bedrock = boto3.client(
    "bedrock-runtime",
    region_name="eu-west-3",
)

response = bedrock.invoke_model(
    modelId="cohere.embed-multilingual-v3",
    body=json.dumps(
        {
            "texts": [
                "Machines automatiques de traitement de l'information"
            ],
            "input_type": "search_document",
        }
    ),
)

result = json.loads(response["body"].read())

embedding = result["embeddings"][0]

print("Vector dimensions:", len(embedding))
print("First 5 values:", embedding[:5])