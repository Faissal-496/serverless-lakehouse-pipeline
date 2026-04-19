#!/bin/bash
# =============================================================================
# Lakehouse Platform - Deployment Script
# =============================================================================
# Usage: ./deploy.sh [component] [action]
#
# Components: all | jenkins | airflow | spark | git-sync
# Actions:    deploy | restart | rebuild | status | logs
#
# Examples:
#   ./deploy.sh all deploy       # Full deployment (pull + rebuild + restart)
#   ./deploy.sh jenkins rebuild  # Rebuild only Jenkins
#   ./deploy.sh all status       # Show status of all services
# =============================================================================

set -euo pipefail

REPO_DIR="/opt/serverless-lakehouse-pipeline"
ENV_FILE="${REPO_DIR}/.env.docker"
COMPOSE="docker compose --env-file ${ENV_FILE}"

cd "${REPO_DIR}"

COMPONENT="${1:-all}"
ACTION="${2:-deploy}"

log() { echo "[$(date '+%H:%M:%S')] $*"; }

pull_latest() {
    log "Pulling latest code..."
    git fetch --all
    git reset --hard origin/migration_prod
    log "Now at $(git log --oneline -1)"
}

rebuild() {
    local svc="$1"
    if [ "$svc" = "all" ]; then
        log "Rebuilding all images..."
        $COMPOSE build --no-cache
    else
        log "Rebuilding ${svc}..."
        $COMPOSE build --no-cache "$svc"
    fi
}

restart() {
    local svc="$1"
    if [ "$svc" = "all" ]; then
        log "Restarting all services..."
        $COMPOSE up -d --force-recreate
    else
        log "Restarting ${svc}..."
        $COMPOSE up -d --force-recreate "$svc"
    fi
}

status() {
    log "Service Status:"
    $COMPOSE ps --format "table {{.Name}}\t{{.Status}}\t{{.Ports}}" 2>/dev/null || $COMPOSE ps
}

show_logs() {
    local svc="$1"
    if [ "$svc" = "all" ]; then
        $COMPOSE logs --tail=20
    else
        $COMPOSE logs --tail=20 "$svc"
    fi
}

case "$ACTION" in
    deploy)
        pull_latest
        rebuild "$COMPONENT"
        restart "$COMPONENT"
        log "Waiting 30s for services to stabilize..."
        sleep 30
        status
        log "Deployment complete."
        ;;
    restart)
        restart "$COMPONENT"
        sleep 10
        status
        ;;
    rebuild)
        pull_latest
        rebuild "$COMPONENT"
        restart "$COMPONENT"
        sleep 10
        status
        ;;
    status)
        status
        ;;
    logs)
        show_logs "$COMPONENT"
        ;;
    *)
        echo "Unknown action: $ACTION"
        echo "Valid actions: deploy | restart | rebuild | status | logs"
        exit 1
        ;;
esac
