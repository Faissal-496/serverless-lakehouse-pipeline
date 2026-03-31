#!/bin/bash
# ==============================================================================
# Lakehouse Platform Deployment Script
# Deploy Airflow HA + Spark Standalone with proper architecture
# ==============================================================================

set -e

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
COMPOSE_FILE="$PROJECT_ROOT/docker-compose-lakehouse.yml"
ENV_FILE="$PROJECT_ROOT/.env.lakehouse"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[✓]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[!]${NC} $1"; }
log_error() { echo -e "${RED}[✗]${NC} $1"; }

# ==============================================================================
# Main Deployment Functions
# ==============================================================================

init() {
    log_info "Initializing Lakehouse platform..."
    
    # Create .env if not exists
    if [ ! -f "$ENV_FILE" ]; then
        log_info "Creating .env file..."
        cat > "$ENV_FILE" << 'ENVEOF'
# AWS Configuration
AWS_ACCESS_KEY_ID=minimal
AWS_SECRET_ACCESS_KEY=minimal
AWS_DEFAULT_REGION=eu-west-3

# S3 Configuration
S3_BUCKET=lakehouse-assurance-moto-dev
GLUE_DB_NAME=lakehouse_assurance_dev

# Environment
APP_ENV=dev
ENVEOF
        log_success ".env created"
    fi
    
    log_success "Initialization complete"
}

deploy() {
    log_info "Deploying Lakehouse platform..."
    log_info "Using docker-compose file: $COMPOSE_FILE"
    
    # Verify compose file exists
    if [ ! -f "$COMPOSE_FILE" ]; then
        log_error "Compose file not found: $COMPOSE_FILE"
        exit 1
    fi
    
    # Pull images
    log_info "Pulling Docker images..."
    docker-compose -f "$COMPOSE_FILE" pull
    
    # Deploy stack
    log_info "Starting services..."
    docker-compose -f "$COMPOSE_FILE" up -d
    
    log_success "Deployment complete"
    log_info "Waiting for services to stabilize (30s)..."
    sleep 30
    
    # Health checks
    log_info "Performing health checks..."
    check_status
}

check_status() {
    log_info "Service Status:"
    echo ""
    
    # PostgreSQL
    if docker exec lakehouse-postgres pg_isready -U airflow &>/dev/null; then
        log_success "PostgreSQL"
    else
        log_error "PostgreSQL"
    fi
    
    # Redis
    if docker exec lakehouse-redis redis-cli ping &>/dev/null; then
        log_success "Redis"
    else
        log_error "Redis"
    fi
    
    # Spark Master
    if docker exec lakehouse-spark-master curl -s http://localhost:8080 &>/dev/null; then
        log_success "Spark Master (Web UI: http://localhost:8084)"
    else
        log_error "Spark Master"
    fi
    
    # Spark Workers
    WORKERS=$(docker ps | grep -c "spark-worker" || echo "0")
    if [ "$WORKERS" -eq 2 ]; then
        log_success "Spark Workers (x2)"
    else
        log_warn "Spark Workers (found $WORKERS, expected 2)"
    fi
    
    # Airflow Webserver
    if docker exec lakehouse-airflow-webserver curl -s http://localhost:8080/health &>/dev/null; then
        log_success "Airflow Webserver (http://localhost:8080)"
    else
        log_error "Airflow Webserver"
    fi
    
    # Airflow Scheduler
    if docker ps | grep -q "lakehouse-airflow-scheduler"; then
        log_success "Airflow Scheduler"
    else
        log_error "Airflow Scheduler"
    fi
    
    # Airflow Workers
    WORKERS=$(docker ps | grep -c "lakehouse-airflow-worker" || echo "0")
    if [ "$WORKERS" -eq 2 ]; then
        log_success "Airflow Celery Workers (x2)"
    else
        log_warn "Airflow Celery Workers (found $WORKERS, expected 2)"
    fi
    
    echo ""
}

stop() {
    log_info "Stopping Lakehouse platform..."
    docker-compose -f "$COMPOSE_FILE" down
    log_success "Stopped"
}

logs() {
    log_info "Tailing logs (Ctrl+C to exit)..."
    docker-compose -f "$COMPOSE_FILE" logs -f "$@"
}

status() {
    log_info "Lakehouse Platform Status"
    docker-compose -f "$COMPOSE_FILE" ps
}

test_connection() {
    log_info "Testing Spark cluster connectivity..."
    
    # From Airflow worker perspective
    docker exec lakehouse-airflow-worker-1 bash -c "
        echo 'Testing connectivity from Airflow Worker...'
        nc -zv spark-master 7077 && echo '✓ Spark RPC port' || echo '✗ Spark RPC port'
        nc -zv spark-master 8084 && echo '✓ Spark Web UI' || echo '✗ Spark Web UI'
    "
    
    log_success "Connectivity test complete"
}

test_dag() {
    log_info "Testing main ETL DAG..."
    
    docker exec lakehouse-airflow-webserver airflow dags test lakehouse_etl_main 2024-01-01
    
    log_success "DAG test complete"
}

# ==============================================================================
# CLI
# ==============================================================================

COMMAND=${1:-help}

case "$COMMAND" in
    init)
        init
        ;;
    deploy)
        init
        deploy
        ;;
    stop)
        stop
        ;;
    restart)
        stop
        sleep 2
        deploy
        ;;
    status)
        status
        ;;
    logs)
        shift
        logs "$@"
        ;;
    test)
        test_connection
        test_dag
        ;;
    help)
        cat << 'HELPEOF'
Lakehouse Platform Deployment Tool

Usage: ./deploy-lakehouse.sh <command>

Commands:
  init              Initialize environment (.env file)
  deploy            Deploy full stack (init + start services)
  stop              Stop all services
  restart           Restart all services
  status            Show service status
  logs [SERVICE]    Tail service logs (default: all)
  test              Run connectivity + DAG tests
  help              Show this help message

Examples:
  ./deploy-lakehouse.sh deploy
  ./deploy-lakehouse.sh logs spark-master
  ./deploy-lakehouse.sh logs airflow-scheduler
  ./deploy-lakehouse.sh test

Web UIs:
  Airflow:      http://localhost:8080 (admin/airflow)
  Spark Master: http://localhost:8084

HELPEOF
        ;;
    *)
        log_error "Unknown command: $COMMAND"
        exit 1
        ;;
esac
