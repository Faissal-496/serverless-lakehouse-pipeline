#!/bin/bash
set -euo pipefail

AWS_REGION="${aws_region}"
REPO_URL="${repo_url}"
REPO_BRANCH="${repo_branch}"
HOST_REPO_PATH="${host_repo_path}"

SECRETS_RDS_ARN="${secrets_rds_arn}"
SECRETS_AIRFLOW_ARN="${secrets_airflow_arn}"
SECRETS_JENKINS_ARN="${secrets_jenkins_arn}"

S3_BUCKET_NAME="${s3_bucket_name}"
AIRFLOW_DOMAIN="${airflow_domain}"
JENKINS_DOMAIN="${jenkins_domain}"
RDS_FORCE_SSL="${rds_force_ssl}"

log() {
  echo "[$(date -Is)] $*"
}

log "Installing base packages..."
export DEBIAN_FRONTEND=noninteractive
apt-get update -y
apt-get install -y --no-install-recommends \
  ca-certificates \
  curl \
  git \
  gnupg \
  jq \
  lsb-release \
  postgresql-client \
  awscli

log "Installing Docker Engine + Compose plugin..."
install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
chmod a+r /etc/apt/keyrings/docker.gpg
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo $VERSION_CODENAME) stable" \
  > /etc/apt/sources.list.d/docker.list
apt-get update -y
apt-get install -y --no-install-recommends docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
systemctl enable --now docker
usermod -aG docker ubuntu || true

log "Cloning repo..."
mkdir -p "$HOST_REPO_PATH"
if [ ! -d "$HOST_REPO_PATH/.git" ]; then
  git clone "$REPO_URL" "$HOST_REPO_PATH"
fi

cd "$HOST_REPO_PATH"
git fetch --all --prune
git checkout "$REPO_BRANCH"

log "Fetching secrets from AWS Secrets Manager..."
if [ -z "$SECRETS_RDS_ARN" ] || [ -z "$SECRETS_AIRFLOW_ARN" ] || [ -z "$SECRETS_JENKINS_ARN" ]; then
  log "ERROR: Secrets ARNs are empty. enable_secrets_manager must be true and Terraform must create secrets."
  exit 1
fi

RDS_SECRET_JSON="$(aws secretsmanager get-secret-value --region "$AWS_REGION" --secret-id "$SECRETS_RDS_ARN" --query SecretString --output text)"
AIRFLOW_SECRET_JSON="$(aws secretsmanager get-secret-value --region "$AWS_REGION" --secret-id "$SECRETS_AIRFLOW_ARN" --query SecretString --output text)"
JENKINS_SECRET_JSON="$(aws secretsmanager get-secret-value --region "$AWS_REGION" --secret-id "$SECRETS_JENKINS_ARN" --query SecretString --output text)"

RDS_USERNAME="$(echo "$RDS_SECRET_JSON" | jq -r '.username')"
RDS_PASSWORD="$(echo "$RDS_SECRET_JSON" | jq -r '.password')"
RDS_HOST="$(echo "$RDS_SECRET_JSON" | jq -r '.host')"
RDS_PORT="$(echo "$RDS_SECRET_JSON" | jq -r '.port')"
RDS_DBNAME="$(echo "$RDS_SECRET_JSON" | jq -r '.dbname')"

AIRFLOW_FERNET_KEY="$(echo "$AIRFLOW_SECRET_JSON" | jq -r '.fernet_key')"
AIRFLOW_WEBSERVER_SECRET_KEY="$(echo "$AIRFLOW_SECRET_JSON" | jq -r '.webserver_secret')"
AIRFLOW_ADMIN_USER="$(echo "$AIRFLOW_SECRET_JSON" | jq -r '.admin_user')"
AIRFLOW_ADMIN_PASSWORD="$(echo "$AIRFLOW_SECRET_JSON" | jq -r '.admin_password')"
AIRFLOW_ADMIN_EMAIL="$(echo "$AIRFLOW_SECRET_JSON" | jq -r '.admin_email')"
AIRFLOW_BASE_URL="$(echo "$AIRFLOW_SECRET_JSON" | jq -r '.base_url')"

JENKINS_ADMIN_USER="$(echo "$JENKINS_SECRET_JSON" | jq -r '.admin_user')"
JENKINS_ADMIN_PASSWORD="$(echo "$JENKINS_SECRET_JSON" | jq -r '.admin_password')"
JENKINS_PUBLIC_URL="$(echo "$JENKINS_SECRET_JSON" | jq -r '.public_url')"

SSL_QUERY=""
if [ "$RDS_FORCE_SSL" = "true" ]; then
  SSL_QUERY="?sslmode=require"
fi

AIRFLOW_DB_CONN="postgresql+psycopg2://$RDS_USERNAME:$RDS_PASSWORD@$RDS_HOST:$RDS_PORT/$RDS_DBNAME$SSL_QUERY"

log "Waiting for RDS to accept connections..."
export PGPASSWORD="$RDS_PASSWORD"
for i in $(seq 1 60); do
  if pg_isready -h "$RDS_HOST" -p "$RDS_PORT" -U "$RDS_USERNAME" -d "$RDS_DBNAME" > /dev/null 2>&1; then
    log "RDS is ready."
    break
  fi
  log "RDS not ready yet (attempt $i/60). Sleeping 10s..."
  sleep 10
done

log "Writing .env.docker..."
cat > .env.docker <<EOF
AIRFLOW_DB_CONN=$AIRFLOW_DB_CONN
AIRFLOW_FERNET_KEY=$AIRFLOW_FERNET_KEY
AIRFLOW_WEBSERVER_SECRET_KEY=$AIRFLOW_WEBSERVER_SECRET_KEY
AIRFLOW_ADMIN_USER=$AIRFLOW_ADMIN_USER
AIRFLOW_ADMIN_PASSWORD=$AIRFLOW_ADMIN_PASSWORD
AIRFLOW_ADMIN_EMAIL=$AIRFLOW_ADMIN_EMAIL
AIRFLOW_BASE_URL=$AIRFLOW_BASE_URL

AWS_DEFAULT_REGION=$AWS_REGION
S3_BUCKET=$S3_BUCKET_NAME

JENKINS_ADMIN_USER=$JENKINS_ADMIN_USER
JENKINS_ADMIN_PASSWORD=$JENKINS_ADMIN_PASSWORD
JENKINS_PUBLIC_URL=$JENKINS_PUBLIC_URL
HOST_REPO_PATH=$HOST_REPO_PATH
EOF
chmod 600 .env.docker

log "Starting Docker Compose stack..."
docker compose --env-file .env.docker up -d --build

log "Creating systemd unit for restart on reboot..."
cat > /etc/systemd/system/lakehouse-compose.service <<EOF
[Unit]
Description=Lakehouse Docker Compose Stack
After=docker.service
Requires=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=$HOST_REPO_PATH
ExecStart=/usr/bin/docker compose --env-file .env.docker up -d
ExecStop=/usr/bin/docker compose --env-file .env.docker down
TimeoutStartSec=0

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable lakehouse-compose.service

log "Bootstrap complete."
