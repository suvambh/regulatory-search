import json
import os
import subprocess
import tempfile
import urllib.parse

REGION = "eu-west-3"
CLUSTER_ID = "regulatory-db"
SECRET_NAME = "regulatory/database-url"
DATABASE_NAME = "regulatory"


def aws(*args):
    return subprocess.check_output(
        ["aws", *args, "--region", REGION],
        text=True,
    ).strip()


endpoint = aws(
    "rds",
    "describe-db-clusters",
    "--db-cluster-identifier",
    CLUSTER_ID,
    "--query",
    "DBClusters[0].Endpoint",
    "--output",
    "text",
)

rds_secret_arn = aws(
    "rds",
    "describe-db-clusters",
    "--db-cluster-identifier",
    CLUSTER_ID,
    "--query",
    "DBClusters[0].MasterUserSecret.SecretArn",
    "--output",
    "text",
)

secret_json = aws(
    "secretsmanager",
    "get-secret-value",
    "--secret-id",
    rds_secret_arn,
    "--query",
    "SecretString",
    "--output",
    "text",
)

credentials = json.loads(secret_json)

username = urllib.parse.quote(credentials["username"], safe="")
password = urllib.parse.quote(credentials["password"], safe="")

database_url = (
    f"postgresql://{username}:{password}"
    f"@{endpoint}:5432/{DATABASE_NAME}"
)

fd, temp_path = tempfile.mkstemp()

try:
    with os.fdopen(fd, "w") as temp_file:
        temp_file.write(database_url)

    subprocess.run(
        [
            "aws",
            "secretsmanager",
            "create-secret",
            "--region",
            REGION,
            "--name",
            SECRET_NAME,
            "--description",
            "DATABASE_URL for regulatory engine ECS application",
            "--secret-string",
            f"file://{temp_path}",
            "--tags",
            "Key=Project,Value=regulatory-engine",
        ],
        check=True,
    )

    print(f"Created Secrets Manager secret: {SECRET_NAME}")

finally:
    if os.path.exists(temp_path):
        os.remove(temp_path)
