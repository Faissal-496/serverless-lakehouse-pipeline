#!/bin/bash
set -euo pipefail

AWS_REGION="${aws_region}"
ENVIRONMENT="${environment}"
AIRFLOW_ECR_REPO="${airflow_ecr_repo}"
AIRFLOW_IMAGE_TAG="${airflow_image_tag}"
AIRFLOW_ROLE="${airflow_role}"
AIRFLOW_ENABLE_FLOWER="${airflow_enable_flower}"
GIT_REPO="${airflow_dags_repo}"
GIT_BRANCH="${airflow_dags_branch}"
S3_BUCKET="${s3_bucket_name}"

RDS_ENDPOINT_RAW="${rds_endpoint}"
RDS_DB_NAME="${rds_db_name}"
RDS_USERNAME="${rds_username}"
RDS_PASSWORD="${rds_password}"
RDS_FORCE_SSL="${rds_force_ssl}"

RABBITMQ_ENDPOINT_RAW="${rabbitmq_endpoint}"
RABBITMQ_USERNAME="${rabbitmq_username}"
RABBITMQ_PASSWORD="${rabbitmq_password}"

AIRFLOW_FERNET_KEY="${airflow_fernet_key}"
AIRFLOW_WEBSERVER_SECRET_KEY="${airflow_webserver_secret_key}"
ENABLE_SECRETS_MANAGER="${enable_secrets_manager}"
SECRETS_RDS_ARN="${secrets_rds_arn}"
SECRETS_MQ_ARN="${secrets_mq_arn}"
SECRETS_AIRFLOW_ARN="${secrets_airflow_arn}"

apt-get update -y
apt-get install -y docker.io docker-compose-plugin git curl
systemctl enable --now docker
usermod -aG docker ubuntu

mkdir -p /opt/airflow /opt/airflow/logs /opt/airflow/plugins /opt/airflow/dags /opt/airflow/work /opt/lakehouse

# Parse RDS endpoint (supports host:port or URLs)
RDS_ENDPOINT_CLEAN="$${RDS_ENDPOINT_RAW#postgresql://}"
RDS_ENDPOINT_CLEAN="$${RDS_ENDPOINT_CLEAN#postgres://}"
RDS_ENDPOINT_CLEAN="$${RDS_ENDPOINT_CLEAN#jdbc:postgresql://}"
RDS_HOST="$${RDS_ENDPOINT_CLEAN%%:*}"
RDS_PORT="$${RDS_ENDPOINT_CLEAN##*:}"
if [[ "$${RDS_HOST}" == "$${RDS_PORT}" ]]; then
  RDS_PORT="5432"
fi

# Parse RabbitMQ endpoint (supports amqps://host:port or host:port)
RABBITMQ_ENDPOINT_CLEAN="$${RABBITMQ_ENDPOINT_RAW#amqps://}"
RABBITMQ_ENDPOINT_CLEAN="$${RABBITMQ_ENDPOINT_CLEAN#amqp://}"
RABBITMQ_HOST="$${RABBITMQ_ENDPOINT_CLEAN%%:*}"
RABBITMQ_PORT="$${RABBITMQ_ENDPOINT_CLEAN##*:}"
if [[ "$${RABBITMQ_HOST}" == "$${RABBITMQ_PORT}" ]]; then
  RABBITMQ_PORT="5671"
fi

AWS_ACCOUNT_ID="$$(aws sts get-caller-identity --query Account --output text)"
ECR_REGISTRY="$${AWS_ACCOUNT_ID}.dkr.ecr.$${AWS_REGION}.amazonaws.com"
AIRFLOW_IMAGE="$${ECR_REGISTRY}/$${AIRFLOW_ECR_REPO}:$${AIRFLOW_IMAGE_TAG}"

aws ecr get-login-password --region "$${AWS_REGION}" | docker login --username AWS --password-stdin "$${ECR_REGISTRY}"
docker pull "$${AIRFLOW_IMAGE}"

# Optionally load secrets from AWS Secrets Manager (overrides vars)
if [[ "$${ENABLE_SECRETS_MANAGER}" == "true" ]]; then
  if [[ -n "$${SECRETS_RDS_ARN}" ]]; then
    export RDS_SECRET_JSON
    RDS_SECRET_JSON="$$(aws secretsmanager get-secret-value --secret-id "$${SECRETS_RDS_ARN}" --query SecretString --output text)"
    RDS_USERNAME="$$(python3 - <<'PY'\nimport json,os\nprint(json.loads(os.environ['RDS_SECRET_JSON']).get('username',''))\nPY)"
    RDS_PASSWORD="$$(python3 - <<'PY'\nimport json,os\nprint(json.loads(os.environ['RDS_SECRET_JSON']).get('password',''))\nPY)"
    RDS_HOST="$$(python3 - <<'PY'\nimport json,os\nprint(json.loads(os.environ['RDS_SECRET_JSON']).get('host',''))\nPY)"
  fi
  if [[ -n "$${SECRETS_MQ_ARN}" ]]; then
    export MQ_SECRET_JSON
    MQ_SECRET_JSON="$$(aws secretsmanager get-secret-value --secret-id "$${SECRETS_MQ_ARN}" --query SecretString --output text)"
    RABBITMQ_USERNAME="$$(python3 - <<'PY'\nimport json,os\nprint(json.loads(os.environ['MQ_SECRET_JSON']).get('username',''))\nPY)"
    RABBITMQ_PASSWORD="$$(python3 - <<'PY'\nimport json,os\nprint(json.loads(os.environ['MQ_SECRET_JSON']).get('password',''))\nPY)"
    RABBITMQ_ENDPOINT_RAW="$$(python3 - <<'PY'\nimport json,os\nprint(json.loads(os.environ['MQ_SECRET_JSON']).get('endpoint',''))\nPY)"
  fi
  if [[ -n "$${SECRETS_AIRFLOW_ARN}" ]]; then
    export AIRFLOW_SECRET_JSON
    AIRFLOW_SECRET_JSON="$$(aws secretsmanager get-secret-value --secret-id "$${SECRETS_AIRFLOW_ARN}" --query SecretString --output text)"
    AIRFLOW_FERNET_KEY="$$(python3 - <<'PY'\nimport json,os\nprint(json.loads(os.environ['AIRFLOW_SECRET_JSON']).get('fernet_key',''))\nPY)"
    AIRFLOW_WEBSERVER_SECRET_KEY="$$(python3 - <<'PY'\nimport json,os\nprint(json.loads(os.environ['AIRFLOW_SECRET_JSON']).get('webserver_secret',''))\nPY)"
  fi
fi

# Clone repo for docker compose file (GitSync is used for DAGs at runtime)
if [ ! -d /opt/lakehouse/.git ]; then
  git clone --depth 1 --branch "$${GIT_BRANCH}" "$${GIT_REPO}" /opt/lakehouse
else
  cd /opt/lakehouse
  git fetch --depth 1 origin "$${GIT_BRANCH}"
  git checkout "$${GIT_BRANCH}"
  git reset --hard "origin/$${GIT_BRANCH}"
fi

AIRFLOW_INIT="false"
if [[ "$${AIRFLOW_ROLE}" == "scheduler" ]]; then
  AIRFLOW_INIT="true"
fi

DB_SSL_MODE=""
if [[ "$${RDS_FORCE_SSL}" == "true" ]]; then
  DB_SSL_MODE="?sslmode=require"
fi

cat > /opt/airflow/.env <<EOF_ENV
AWS_REGION=$${AWS_REGION}
APP_ENV=$${ENVIRONMENT}
S3_BUCKET=$${S3_BUCKET}
AIRFLOW_IMAGE=$${AIRFLOW_IMAGE}
GIT_SYNC_REPO=$${GIT_REPO}
GIT_SYNC_BRANCH=$${GIT_BRANCH}
AIRFLOW_DB_CONN=postgresql+psycopg2://$${RDS_USERNAME}:$${RDS_PASSWORD}@$${RDS_HOST}:$${RDS_PORT}/$${RDS_DB_NAME}$${DB_SSL_MODE}
AIRFLOW_RESULT_BACKEND=db+postgresql://$${RDS_USERNAME}:$${RDS_PASSWORD}@$${RDS_HOST}:$${RDS_PORT}/$${RDS_DB_NAME}$${DB_SSL_MODE}
AIRFLOW_BROKER_URL=amqps://$${RABBITMQ_USERNAME}:$${RABBITMQ_PASSWORD}@$${RABBITMQ_HOST}:$${RABBITMQ_PORT}
AIRFLOW_FERNET_KEY=$${AIRFLOW_FERNET_KEY}
AIRFLOW_WEBSERVER_SECRET_KEY=$${AIRFLOW_WEBSERVER_SECRET_KEY}
AIRFLOW_INIT=$${AIRFLOW_INIT}
EOF_ENV

cd /opt/lakehouse
if [[ "$${AIRFLOW_ROLE}" == "scheduler" ]]; then
  docker compose --env-file /opt/airflow/.env -f docker/compose/docker-compose-aws.yml up -d git-sync airflow-webserver airflow-scheduler
  if [[ "$${AIRFLOW_ENABLE_FLOWER}" == "true" ]]; then
    docker compose --env-file /opt/airflow/.env -f docker/compose/docker-compose-aws.yml up -d airflow-flower
  fi
elif [[ "$${AIRFLOW_ROLE}" == "worker" ]]; then
  docker compose --env-file /opt/airflow/.env -f docker/compose/docker-compose-aws.yml up -d git-sync airflow-worker
else
  echo "Unknown AIRFLOW_ROLE: $${AIRFLOW_ROLE}"
  exit 1
fi
