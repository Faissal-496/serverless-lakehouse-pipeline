#!/bin/bash

# ============================================================================
# Local HA Environment Startup Script
# Usage: ./start-local-ha.sh [up|down|logs|status]
# ============================================================================

set -e

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
COMPOSE_FILE="$PROJECT_ROOT/docker-compose-local-ha.yml"
ENV_FILE="$PROJECT_ROOT/.env.local-ha"
COMPOSE_CMD=""  # Will be set by check_docker()

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Command
COMMAND=${1:-help}

# ============================================================================
# Functions
# ============================================================================

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

check_docker() {
    if ! command -v docker &> /dev/null; then
        log_error "Docker is not installed"
        exit 1
    fi
    
    # Check for docker compose (built-in, preferred)
    if docker compose version &> /dev/null; then
        COMPOSE_CMD="docker compose"
        log_success "Docker Compose (built-in) found"
    # Fallback to docker-compose plugin
    elif command -v docker-compose &> /dev/null; then
        COMPOSE_CMD="docker-compose"
        log_success "Docker Compose (plugin) found"
    else
        log_error "Docker Compose is not installed"
        exit 1
    fi
}

check_images() {
    log_info "Checking required Docker images..."
    
    local missing_images=0
    
    if ! docker images | grep -q "airflow-runtime.*local"; then
        log_error "Missing: airflow-runtime:local"
        missing_images=1
    else
        log_success "Found: airflow-runtime:local"
    fi
    
    if ! docker images | grep -q "spark-runtime.*local"; then
        log_error "Missing: spark-runtime:local"
        missing_images=1
    else
        log_success "Found: spark-runtime:local"
    fi
    
    if [ $missing_images -eq 1 ]; then
        log_warn "Building missing images..."
        docker build -f "$PROJECT_ROOT/docker/airflow/Dockerfile" -t airflow-runtime:local "$PROJECT_ROOT" || true
        docker build -f "$PROJECT_ROOT/docker/spark/Dockerfile" -t spark-runtime:local "$PROJECT_ROOT" || true
    fi
}

start_services() {
    log_info "Starting Local HA environment..."
    log_info "Git Branch: dev"
    log_info "Compose File: $COMPOSE_FILE"
    log_info "Env File: $ENV_FILE"
    
    cd "$PROJECT_ROOT"
    
    if [ ! -f "$ENV_FILE" ]; then
        log_error ".env.local-ha not found!"
        exit 1
    fi
    
    eval "$COMPOSE_CMD -f $COMPOSE_FILE --env-file $ENV_FILE up -d"
    
    log_success "Services started!"
    
    echo ""
    log_info "Waiting for services to initialize (30 seconds)..."
    sleep 30
    
    show_status
}

stop_services() {
    log_info "Stopping Local HA environment..."
    
    cd "$PROJECT_ROOT"
    eval "$COMPOSE_CMD -f $COMPOSE_FILE down"
    
    log_success "Services stopped!"
}

restart_services() {
    log_info "Restarting Local HA environment..."
    stop_services
    sleep 5
    start_services
}

show_status() {
    echo ""
    log_info "Service Status:"
    echo ""
    
    cd "$PROJECT_ROOT"
    eval "$COMPOSE_CMD -f $COMPOSE_FILE ps --no-trunc"
    
    echo ""
    log_info "Access URLs:"
    echo ""
    echo "  🌐 Airflow Web UI:      ${BLUE}http://localhost:8080${NC}"
    echo "  🔥 Jenkins Controller 1: ${BLUE}http://localhost:8081${NC}"
    echo "  🔥 Jenkins Controller 2: ${BLUE}http://localhost:8082${NC}"
    echo "  ⚡ Spark Master:        ${BLUE}http://localhost:4040${NC}"
    echo "  📊 Spark History:       ${BLUE}http://localhost:18080${NC}"
    echo ""
}

show_logs() {
    log_info "Streaming logs (Ctrl+C to stop)..."
    echo ""
    
    cd "$PROJECT_ROOT"
    eval "$COMPOSE_CMD -f $COMPOSE_FILE logs -f $@"
}

show_help() {
    cat <<EOF
${BLUE}Local HA Environment Control${NC}

Usage: $0 [command] [options]

Commands:
  up                Start all services
  down              Stop all services
  restart           Restart all services
  status            Show service status and URLs
  logs              Stream logs (add service name for specific service)
  shell <service>   Open shell in a service container
  build             Build local Docker images
  clean             Remove all containers and volumes
  help              Show this help message

Examples:
  $0 up                           # Start all services
  $0 logs airflow-webserver       # View webserver logs
  $0 shell airflow-webserver      # SSH into webserver
  $0 logs                         # View all logs

Service Names:
  - airflow-webserver
  - airflow-scheduler-1
  - airflow-scheduler-2
  - airflow-worker-1
  - airflow-worker-2
  - jenkins-controller-1
  - jenkins-controller-2
  - jenkins-agent-1
  - jenkins-agent-2
  - spark-master
  - git-sync

EOF
}

shell_service() {
    local service=$1
    if [ -z "$service" ]; then
        log_error "Service name required"
        exit 1
    fi
    
    log_info "Opening shell in $service..."
    cd "$PROJECT_ROOT"
    eval "$COMPOSE_CMD -f $COMPOSE_FILE exec $service /bin/bash"
}

build_images() {
    log_info "Building local Docker images..."
    
    log_info "Building airflow-runtime:local..."
    docker build -f "$PROJECT_ROOT/docker/airflow/Dockerfile" -t airflow-runtime:local "$PROJECT_ROOT"
    
    log_info "Building spark-runtime:local..."
    docker build -f "$PROJECT_ROOT/docker/spark/Dockerfile" -t spark-runtime:local "$PROJECT_ROOT"
    
    log_success "Images built!"
}

clean_environment() {
    log_warn "This will remove all containers and volumes!"
    read -p "Are you sure? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        log_info "Cleaning up..."
        cd "$PROJECT_ROOT"
        eval "$COMPOSE_CMD -f $COMPOSE_FILE down -v"
        log_success "Cleaned!"
    else
        log_warn "Cancelled"
    fi
}

# ============================================================================
# Main
# ============================================================================

case "$COMMAND" in
    up)
        check_docker
        check_images
        start_services
        ;;
    down)
        stop_services
        ;;
    restart)
        restart_services
        ;;
    status)
        show_status
        ;;
    logs)
        shift
        show_logs "$@"
        ;;
    shell)
        shell_service "$2"
        ;;
    build)
        check_docker
        build_images
        ;;
    clean)
        clean_environment
        ;;
    help)
        show_help
        ;;
    *)
        log_error "Unknown command: $COMMAND"
        echo ""
        show_help
        exit 1
        ;;
esac
