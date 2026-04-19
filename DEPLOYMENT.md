# Deployment Guide

## Architecture

```
Developer → Git Push → Jenkins CI → Manual Deploy → EC2 (Docker Compose)
                ↓
        Lint + Test + Validate
```

## CI/CD Flow

### 1. Development
- Work on feature branch or `migration_prod`
- Push commits to trigger CI

### 2. CI Pipeline (Jenkins - Automatic)
Jenkins runs on every push to `dev`, `migration_prod`, `main`:

| Stage | Description |
|-------|-------------|
| Setup | Install Python deps |
| Quality Gates | Autoflake + Black + Flake8 (parallel) |
| DAG Validation | Syntax check all Airflow DAGs |
| Unit Tests | pytest on tests/ |
| Package Build | Build lakehouse wheel |

### 3. Deployment (Manual)
SSH to EC2 and run the deploy script:

```bash
ssh -i ~/.ssh/lakehouse_assurance_prod ubuntu@15.237.250.134

# Full deployment
sudo /opt/serverless-lakehouse-pipeline/deploy.sh all deploy

# Rebuild specific service
sudo /opt/serverless-lakehouse-pipeline/deploy.sh jenkins rebuild

# Check status
sudo /opt/serverless-lakehouse-pipeline/deploy.sh all status

# View logs
sudo /opt/serverless-lakehouse-pipeline/deploy.sh airflow-webserver logs
```

## Services

| Service | Internal Port | External Port | URL |
|---------|--------------|---------------|-----|
| Airflow Webserver | 8080 | ALB:443 | https://airflow.octaa.tech |
| Jenkins | 8080 | ALB:443/9080 | https://jenkins.octaa.tech |
| Spark Master | 8080/7077 | 9090/7077 | http://<ec2-ip>:9090 |
| Spark Worker 1 | 8081 | 9091 | - |
| Spark Worker 2 | 8081 | 9092 | - |

## DAG Sync
- Git-sync sidecar pulls DAGs from `orchestration/airflow/dags/` every 60s
- No manual DAG deployment needed — just push to the repo

## Rollback
```bash
# On EC2
cd /opt/serverless-lakehouse-pipeline
sudo git log --oneline -5          # Find target commit
sudo git reset --hard <commit>     # Rollback code
sudo docker compose --env-file .env.docker up -d --force-recreate  # Restart
```
