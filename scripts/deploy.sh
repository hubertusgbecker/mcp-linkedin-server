#!/usr/bin/env bash
# scripts/deploy.sh — Deploy MCP LinkedIn Server to the remote Docker host
#
# Usage:
#   ./scripts/deploy.sh              # Pull image, update repo, restart container
#   ./scripts/deploy.sh --sync-profile  # Also sync browser profile from local Mac
#   ./scripts/deploy.sh --logs         # Show container logs after deploy
#   ./scripts/deploy.sh --status       # Just show remote status, don't deploy
#
# Prerequisites:
#   - SSH access: root@synology
#   - Docker installed on remote
#   - Browser profile created locally: uvx mcp-linkedin-server --get-session

set -euo pipefail

REMOTE="root@synology"
REMOTE_DIR="/docker/mcp-linkedin-server"
DOCKER_BIN="/var/packages/ContainerManager/target/usr/bin"
LOCAL_PROFILE="$HOME/.linkedin-mcp"
REMOTE_PROFILE="/root/.linkedin-mcp"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log()  { echo -e "${BLUE}==>${NC} $*"; }
ok()   { echo -e "${GREEN}  ✓${NC} $*"; }
warn() { echo -e "${YELLOW}  !${NC} $*"; }
err()  { echo -e "${RED}  ✗${NC} $*" >&2; }

remote() {
    ssh "$REMOTE" "export PATH=\$PATH:$DOCKER_BIN; $*"
}

cmd_status() {
    log "Remote status"
    echo ""
    remote "cd $REMOTE_DIR && git log --oneline -1"
    echo ""
    remote "docker compose -f $REMOTE_DIR/docker-compose.yml ps 2>/dev/null || echo 'No containers running'"
    echo ""
    remote "docker images --format 'table {{.Repository}}\t{{.Tag}}\t{{.Size}}' | grep -E 'REPOSITORY|linkedin' || echo 'No images found'"
}

cmd_sync_profile() {
    log "Syncing browser profile to remote..."
    if [[ ! -d "$LOCAL_PROFILE/profile" ]]; then
        err "No local profile at $LOCAL_PROFILE/profile/"
        err "Create one first: uvx mcp-linkedin-server --get-session"
        exit 1
    fi
    scp -O -r "$LOCAL_PROFILE/" "$REMOTE:$REMOTE_PROFILE/"
    ok "Profile synced ($(du -sh "$LOCAL_PROFILE" | cut -f1))"
}

cmd_deploy() {
    log "Deploying MCP LinkedIn Server"
    echo ""

    # 1. Update repo on remote
    log "Pulling latest from GitHub..."
    remote "cd $REMOTE_DIR && git fetch origin && git reset --hard origin/main"
    ok "Repo updated"

    # 2. Pull or build the image
    IMAGE_TAG=$(remote "grep 'image:' $REMOTE_DIR/docker-compose.yml | awk '{print \$2}'")
    log "Image: $IMAGE_TAG"
    if remote "docker pull $IMAGE_TAG 2>/dev/null"; then
        ok "Image pulled from registry"
    else
        warn "Image not in registry — building from source..."
        remote "docker compose -f $REMOTE_DIR/docker-compose.yml build"
        ok "Image built locally"
    fi

    # 3. Recreate container
    log "Restarting container..."
    remote "docker compose -f $REMOTE_DIR/docker-compose.yml down 2>/dev/null || true"
    remote "docker compose -f $REMOTE_DIR/docker-compose.yml up -d"
    ok "Container started"

    # 4. Prune old images
    remote "docker image prune -f >/dev/null 2>&1 || true"

    echo ""
    log "Deploy complete"
    cmd_status
}

cmd_logs() {
    remote "docker compose -f $REMOTE_DIR/docker-compose.yml logs --tail=50 -f"
}

# --- Main ---
SYNC_PROFILE=false
SHOW_LOGS=false
STATUS_ONLY=false

for arg in "$@"; do
    case "$arg" in
        --sync-profile) SYNC_PROFILE=true ;;
        --logs)         SHOW_LOGS=true ;;
        --status)       STATUS_ONLY=true ;;
        -h|--help)
            echo "Usage: $0 [--sync-profile] [--logs] [--status]"
            echo ""
            echo "  --sync-profile  Copy local browser profile to remote before deploy"
            echo "  --logs          Follow container logs after deploy"
            echo "  --status        Show remote status only (no deploy)"
            exit 0
            ;;
        *) err "Unknown argument: $arg"; exit 1 ;;
    esac
done

if $STATUS_ONLY; then
    cmd_status
    exit 0
fi

if $SYNC_PROFILE; then
    cmd_sync_profile
    echo ""
fi

cmd_deploy

if $SHOW_LOGS; then
    echo ""
    cmd_logs
fi
