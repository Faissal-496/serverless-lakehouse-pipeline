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

EMR_APPLICATION_ID="${emr_application_id}"
EMR_EXECUTION_ROLE_ARN="${emr_execution_role_arn}"
LAKEHOUSE_WHL_S3="${lakehouse_whl_s3}"
SPARK_CONF_S3="${spark_conf_s3}"
AWS_ACCOUNT_ID="${account_id}"

# Disable sshd DNS reverse lookup to prevent SSH banner exchange timeout on private instances
if ! grep -q '^UseDNS no' /etc/ssh/sshd_config; then
  echo 'UseDNS no' >> /etc/ssh/sshd_config
  systemctl restart sshd || true
fi

apt-get update -y
apt-get install -y ca-certificates curl gnupg git python3-pip

# Install Docker via official method (docker.io may not be available)
install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
chmod a+r /etc/apt/keyrings/docker.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" > /etc/apt/sources.list.d/docker.list
apt-get update -y
apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
systemctl enable --now docker
usermod -aG docker ubuntu

# Add user to docker group (wait a bit for service to be ready)
sleep 2

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

AWS_ACCOUNT_ID="$${AWS_ACCOUNT_ID}"
ECR_REGISTRY="$${AWS_ACCOUNT_ID}.dkr.ecr.$${AWS_REGION}.amazonaws.com"
AIRFLOW_IMAGE="$${ECR_REGISTRY}/$${AIRFLOW_ECR_REPO}:$${AIRFLOW_IMAGE_TAG}"

# Install awscli v2
if ! command -v aws &>/dev/null; then
  curl -fsSL "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o /tmp/awscliv2.zip
  apt-get install -y unzip
  unzip -q /tmp/awscliv2.zip -d /tmp
  /tmp/aws/install
  rm -rf /tmp/awscliv2.zip /tmp/aws
fi

aws ecr get-login-password --region "$${AWS_REGION}" | docker login --username AWS --password-stdin "$${ECR_REGISTRY}"
docker pull "$${AIRFLOW_IMAGE}"

# Optionally load secrets from AWS Secrets Manager (overrides vars)
if [[ "$${ENABLE_SECRETS_MANAGER}" == "true" ]]; then
  if [[ -n "$${SECRETS_RDS_ARN}" ]]; then
    RDS_SECRET_JSON="$(aws secretsmanager get-secret-value --secret-id "$${SECRETS_RDS_ARN}" --query SecretString --output text)"
    RDS_USERNAME="$(echo "$${RDS_SECRET_JSON}" | python3 -c "import sys,json; print(json.load(sys.stdin).get('username',''))")"
    RDS_PASSWORD="$(echo "$${RDS_SECRET_JSON}" | python3 -c "import sys,json; print(json.load(sys.stdin).get('password',''))")"
    RDS_HOST="$(echo "$${RDS_SECRET_JSON}" | python3 -c "import sys,json; print(json.load(sys.stdin).get('host',''))")"
  fi
  if [[ -n "$${SECRETS_MQ_ARN}" ]]; then
    MQ_SECRET_JSON="$(aws secretsmanager get-secret-value --secret-id "$${SECRETS_MQ_ARN}" --query SecretString --output text)"
    RABBITMQ_USERNAME="$(echo "$${MQ_SECRET_JSON}" | python3 -c "import sys,json; print(json.load(sys.stdin).get('username',''))")"
    RABBITMQ_PASSWORD="$(echo "$${MQ_SECRET_JSON}" | python3 -c "import sys,json; print(json.load(sys.stdin).get('password',''))")"
    RABBITMQ_ENDPOINT_RAW="$(echo "$${MQ_SECRET_JSON}" | python3 -c "import sys,json; print(json.load(sys.stdin).get('endpoint',''))")"
  fi
  if [[ -n "$${SECRETS_AIRFLOW_ARN}" ]]; then
    AIRFLOW_SECRET_JSON="$(aws secretsmanager get-secret-value --secret-id "$${SECRETS_AIRFLOW_ARN}" --query SecretString --output text)"
    AIRFLOW_FERNET_KEY="$(echo "$${AIRFLOW_SECRET_JSON}" | python3 -c "import sys,json; print(json.load(sys.stdin).get('fernet_key',''))")"
    AIRFLOW_WEBSERVER_SECRET_KEY="$(echo "$${AIRFLOW_SECRET_JSON}" | python3 -c "import sys,json; print(json.load(sys.stdin).get('webserver_secret',''))")"
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
EMR_APPLICATION_ID=$${EMR_APPLICATION_ID}
EMR_EXECUTION_ROLE_ARN=$${EMR_EXECUTION_ROLE_ARN}
LAKEHOUSE_WHL_S3=$${LAKEHOUSE_WHL_S3}
SPARK_CONF_S3=$${SPARK_CONF_S3}
EOF_ENV

cd /opt/lakehouse

# Inject AIRFLOW_INIT into compose environment (not available inside container otherwise)
sed -i '/SPARK_CONF_S3:/a\    AIRFLOW_INIT: $${AIRFLOW_INIT:-false}' docker/compose/docker-compose-aws.yml
# Add Celery broker SSL setting for Amazon MQ (amqps://)
sed -i '/AIRFLOW__CELERY__RESULT_BACKEND:/a\    AIRFLOW__CELERY__BROKER_USE_SSL: "true"' docker/compose/docker-compose-aws.yml

if [[ "$${AIRFLOW_ROLE}" == "scheduler" ]]; then
  # Run database migration before starting services (fresh DB needs tables)
  docker compose --env-file /opt/airflow/.env -f docker/compose/docker-compose-aws.yml run --rm --no-deps airflow-webserver airflow db migrate
  docker compose --env-file /opt/airflow/.env -f docker/compose/docker-compose-aws.yml run --rm --no-deps airflow-webserver \
    airflow users create --username admin --password admin \
    --firstname Airflow --lastname Admin --role Admin \
    --email admin@octaa.tech || true
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
