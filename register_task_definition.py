import json
import subprocess
import tempfile
import os


REGION = "eu-west-3"
REPOSITORY = "regulatory-engine"
IMAGE_TAG = "v1"
SECRET_NAME = "regulatory/database-url"

EXECUTION_ROLE = "regulatory-ecs-execution-role"
TASK_ROLE = "regulatory-ecs-task-role"

TASK_FAMILY = "regulatory-engine"
LOG_GROUP = "/ecs/regulatory-engine"


def aws(*args):
    return subprocess.check_output(
        ["aws", *args, "--region", REGION],
        text=True,
    ).strip()


# AWS account
account_id = aws(
    "sts",
    "get-caller-identity",
    "--query",
    "Account",
    "--output",
    "text",
)

# ECR image
ecr_uri = aws(
    "ecr",
    "describe-repositories",
    "--repository-names",
    REPOSITORY,
    "--query",
    "repositories[0].repositoryUri",
    "--output",
    "text",
)

image = f"{ecr_uri}:{IMAGE_TAG}"

# IAM roles
execution_role_arn = aws(
    "iam",
    "get-role",
    "--role-name",
    EXECUTION_ROLE,
    "--query",
    "Role.Arn",
    "--output",
    "text",
)

task_role_arn = aws(
    "iam",
    "get-role",
    "--role-name",
    TASK_ROLE,
    "--query",
    "Role.Arn",
    "--output",
    "text",
)

# DATABASE_URL secret
database_url_secret_arn = aws(
    "secretsmanager",
    "describe-secret",
    "--secret-id",
    SECRET_NAME,
    "--query",
    "ARN",
    "--output",
    "text",
)

task_definition = {
    "family": TASK_FAMILY,

    "networkMode": "awsvpc",

    "requiresCompatibilities": [
        "FARGATE"
    ],

    "cpu": "512",
    "memory": "1024",

    "runtimePlatform": {
        "cpuArchitecture": "X86_64",
        "operatingSystemFamily": "LINUX",
    },

    "executionRoleArn": execution_role_arn,
    "taskRoleArn": task_role_arn,

    "containerDefinitions": [
        {
            "name": "regulatory-web",

            "image": image,

            "essential": True,

            "portMappings": [
                {
                    "containerPort": 8501,
                    "protocol": "tcp",
                }
            ],

            "environment": [
                {
                    "name": "AWS_REGION",
                    "value": "eu-west-3",
                },
                {
                    "name": "EMBEDDING_MODEL",
                    "value": "cohere.embed-multilingual-v3",
                },
                {
                    "name": "CLASSIFICATION_MODEL",
                    "value": "eu.amazon.nova-pro-v1:0",
                },
            ],

            "secrets": [
                {
                    "name": "DATABASE_URL",
                    "valueFrom": database_url_secret_arn,
                }
            ],

            "logConfiguration": {
                "logDriver": "awslogs",
                "options": {
                    "awslogs-group": LOG_GROUP,
                    "awslogs-region": REGION,
                    "awslogs-stream-prefix": "web",
                },
            },
        }
    ],
}


fd, path = tempfile.mkstemp(suffix=".json")

try:
    with os.fdopen(fd, "w") as f:
        json.dump(task_definition, f, indent=2)

    result = subprocess.check_output(
        [
            "aws",
            "ecs",
            "register-task-definition",
            "--region",
            REGION,
            "--cli-input-json",
            f"file://{path}",
            "--query",
            "taskDefinition.{Family:family,Revision:revision,Arn:taskDefinitionArn}",
            "--output",
            "json",
        ],
        text=True,
    )

    print(result)

finally:
    if os.path.exists(path):
        os.remove(path)
