import json
import subprocess
import tempfile
import os


REGION = "eu-west-3"
CLUSTER = "regulatory-cluster"
TASK_DEFINITION = "regulatory-engine"
CONTAINER_NAME = "regulatory-web"


def aws(*args):
    return subprocess.check_output(
        ["aws", *args, "--region", REGION],
        text=True,
    ).strip()


# Find our VPC
vpc_id = aws(
    "ec2",
    "describe-vpcs",
    "--filters",
    "Name=tag:Name,Values=regulatory-vpc",
    "--query",
    "Vpcs[0].VpcId",
    "--output",
    "text",
)

# Pick one public subnet
public_subnet = aws(
    "ec2",
    "describe-subnets",
    "--filters",
    f"Name=vpc-id,Values={vpc_id}",
    "Name=tag:Name,Values=regulatory-public-a",
    "--query",
    "Subnets[0].SubnetId",
    "--output",
    "text",
)

# Find ECS security group
ecs_sg = aws(
    "ec2",
    "describe-security-groups",
    "--filters",
    f"Name=vpc-id,Values={vpc_id}",
    "Name=group-name,Values=regulatory-ecs-sg",
    "--query",
    "SecurityGroups[0].GroupId",
    "--output",
    "text",
)


# Override Streamlit with a short DB test.
test_code = """
import os
import psycopg

print("Connecting to Aurora...")

with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
    with conn.cursor() as cur:

        print("Enabling pgvector...")

        cur.execute(
            "CREATE EXTENSION IF NOT EXISTS vector"
        )

        cur.execute(
            "SELECT extversion "
            "FROM pg_extension "
            "WHERE extname = 'vector'"
        )

        version = cur.fetchone()

        if not version:
            raise RuntimeError(
                "pgvector extension was not created"
            )

        print(f"pgvector version: {version[0]}")

    conn.commit()

print("DATABASE INITIALIZATION SUCCESSFUL")
"""


request = {
    "cluster": CLUSTER,
    "taskDefinition": TASK_DEFINITION,
    "launchType": "FARGATE",

    "networkConfiguration": {
        "awsvpcConfiguration": {
            "subnets": [public_subnet],
            "securityGroups": [ecs_sg],
            "assignPublicIp": "ENABLED",
        }
    },

    "overrides": {
        "containerOverrides": [
            {
                "name": CONTAINER_NAME,
                "command": [
                    "python",
                    "-c",
                    test_code,
                ],
            }
        ]
    },
}


fd, path = tempfile.mkstemp(suffix=".json")

try:
    with os.fdopen(fd, "w") as f:
        json.dump(request, f)

    task_arn = subprocess.check_output(
        [
            "aws",
            "ecs",
            "run-task",
            "--region",
            REGION,
            "--cli-input-json",
            f"file://{path}",
            "--query",
            "tasks[0].taskArn",
            "--output",
            "text",
        ],
        text=True,
    ).strip()

    print("Started test task:")
    print(task_arn)

finally:
    if os.path.exists(path):
        os.remove(path)
