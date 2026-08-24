#!/usr/bin/env bash
# Local dev environment for the AI Observability Platform (README.md
# "Quick start" Path A) — no AWS account, no Kubernetes cluster.
#
# Brings up:
#   - mcp-server/.venv + ai-engine/.venv (installed, not "running" — they're
#     libraries/a stdio-driven tool server, not standalone daemons)
#   - the MCP server itself, HTTP transport, http://localhost:8080/mcp
#   - local-dev/docker-compose.yml: Prometheus, Grafana, node-exporter,
#     and a synthetic-metrics mock-exporter (see local-dev/README notes
#     in docker-compose.yml for what is/isn't real data)
#
# Usage:
#   scripts/run-local.sh up       # idempotent — safe to re-run
#   scripts/run-local.sh down
#   scripts/run-local.sh status
#   scripts/run-local.sh restart
#
# Env vars:
#   SKIP_AI_ENGINE=1   don't bother setting up ai-engine/.venv (it's not
#                       needed to run anything — only its own tests/notebook)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
MCP_DIR="$REPO_ROOT/mcp-server"
PID_FILE="$MCP_DIR/.mcp-server.pid"
LOG_FILE="$MCP_DIR/.mcp-server.log"

log()  { printf '==> %s\n' "$*"; }
warn() { printf 'WARNING: %s\n' "$*" >&2; }
die()  { printf 'ERROR: %s\n' "$*" >&2; exit 1; }

# --- helpers -----------------------------------------------------------

find_python() {
  # Project needs 3.11+; plain `python3` is often older on macOS.
  for candidate in python3.13 python3.12 python3.11; do
    if command -v "$candidate" >/dev/null 2>&1; then
      command -v "$candidate"
      return 0
    fi
  done
  if command -v python3 >/dev/null 2>&1 \
      && python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)' 2>/dev/null; then
    command -v python3
    return 0
  fi
  return 1
}

ensure_docker() {
  command -v docker >/dev/null 2>&1 || die "docker not found — install Docker Desktop first."
  if docker info >/dev/null 2>&1; then
    return 0
  fi
  log "Docker daemon isn't running."
  if [[ "$(uname -s)" == "Darwin" ]] && [[ -d "/Applications/Docker.app" ]]; then
    log "Launching Docker Desktop and waiting for it to be ready..."
    open -a Docker
    for _ in $(seq 1 60); do
      docker info >/dev/null 2>&1 && { log "Docker is up."; return 0; }
      sleep 2
    done
  fi
  die "Docker daemon still not reachable — start it manually and re-run."
}

ensure_venv() {
  local dir="$1" name="$2" python_bin
  if [[ -x "$dir/.venv/bin/python" ]]; then
    log "$name: .venv already exists, skipping install (delete $dir/.venv to force a rebuild)."
    return 0
  fi
  python_bin="$(find_python)" || die "$name needs Python 3.11+ — none found (tried python3.11/3.12/3.13, and python3). Install one, e.g. \`brew install python@3.13\`."
  log "$name: creating .venv with $python_bin ..."
  (cd "$dir" && "$python_bin" -m venv .venv && .venv/bin/pip install -q --upgrade pip \
    && .venv/bin/pip install -q -r requirements.txt pytest)
  log "$name: installed."
}

ensure_env_file() {
  if [[ ! -f "$MCP_DIR/.env" ]]; then
    log "mcp-server/.env missing — creating from .env.example."
    cp "$MCP_DIR/.env.example" "$MCP_DIR/.env"
  fi
  # This script runs the server standalone (no MCP client attached to
  # stdin/stdout), so it needs HTTP transport, not the file's stdio default.
  if grep -q '^TRANSPORT=stdio' "$MCP_DIR/.env" 2>/dev/null; then
    log "mcp-server/.env: switching TRANSPORT to streamable-http (this script runs it standalone, not via an MCP client)."
    # Portable in-place edit (macOS/BSD sed needs a backup-suffix arg; GNU sed doesn't).
    if sed --version >/dev/null 2>&1; then
      sed -i 's/^TRANSPORT=stdio/TRANSPORT=streamable-http/' "$MCP_DIR/.env"
    else
      sed -i '' 's/^TRANSPORT=stdio/TRANSPORT=streamable-http/' "$MCP_DIR/.env"
    fi
  fi
}

mcp_server_running() {
  # Started by this script (pidfile), OR something else already answers
  # on 8080 (e.g. started manually) — either way, don't try to bind the
  # port again.
  { [[ -f "$PID_FILE" ]] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; } \
    || [[ "$(curl -s -o /dev/null -w '%{http_code}' http://localhost:8080/mcp/ 2>/dev/null)" == "307" ]]
}

wait_for() {
  local url="$1" name="$2" ok_codes="$3" tries=30 code
  for _ in $(seq 1 "$tries"); do
    code="$(curl -s -o /dev/null -w '%{http_code}' "$url" 2>/dev/null || true)"
    if [[ ",$ok_codes," == *",$code,"* ]]; then
      log "$name is up ($url -> $code)."
      return 0
    fi
    sleep 1
  done
  warn "$name didn't respond as expected within ${tries}s ($url -> ${code:-no response}). It may still be starting — check with '$0 status'."
}

print_urls() {
  cat <<EOF

--------------------------------------------------------------------
 Service         URL
--------------------------------------------------------------------
 MCP Server      http://localhost:8080/mcp
 Grafana         http://localhost:3000        (login: admin / admin*)
 Prometheus      http://localhost:9090
 node-exporter   http://localhost:9100/metrics
 mock-exporter   http://localhost:9101/metrics
--------------------------------------------------------------------
 * unless changed via the Grafana UI — local-dev/docker-compose.yml
   only sets the initial password.

 Dashboards live under the "AI Observability Platform" folder in
 Grafana. Two panels there (Top Error Logs, Similar Historical
 Incidents) use a Loki datasource this local stack doesn't run.
--------------------------------------------------------------------
EOF
}

# --- commands ------------------------------------------------------------

cmd_up() {
  ensure_docker
  ensure_venv "$MCP_DIR" "mcp-server"
  if [[ "${SKIP_AI_ENGINE:-0}" != "1" ]]; then
    ensure_venv "$REPO_ROOT/ai-engine" "ai-engine"
  fi
  ensure_env_file

  log "Starting local-dev Compose stack (Prometheus, Grafana, node-exporter, mock-exporter)..."
  (cd "$REPO_ROOT/local-dev" && docker compose up -d --build)

  if mcp_server_running; then
    if [[ -f "$PID_FILE" ]]; then
      log "MCP server already running (pid $(cat "$PID_FILE"))."
    else
      log "Something's already answering on :8080/mcp/ (not started by this script) — leaving it alone."
    fi
  else
    log "Starting MCP server (HTTP transport, background, log at ${LOG_FILE#$REPO_ROOT/})..."
    (cd "$MCP_DIR" && nohup .venv/bin/python server.py >"$LOG_FILE" 2>&1 & echo $! >"$PID_FILE")
  fi

  wait_for "http://localhost:9090/-/ready" "Prometheus" "200"
  wait_for "http://localhost:3000/api/health" "Grafana" "200"
  wait_for "http://localhost:8080/mcp/" "MCP server" "307"

  print_urls
}

cmd_down() {
  if [[ -f "$PID_FILE" ]]; then
    log "Stopping MCP server (pid $(cat "$PID_FILE"))..."
    kill "$(cat "$PID_FILE")" 2>/dev/null || true
    sleep 1
  fi
  rm -f "$PID_FILE"

  # Belt-and-suspenders: on macOS, a Homebrew "framework" python3 launcher
  # forks into a distinct child PID for the actual interpreter, so $!
  # (captured at start-up) can point at a process that's already gone
  # while the real server is still listening. Fall back to whatever's
  # actually bound to :8080, however it got there.
  if mcp_server_running; then
    if command -v lsof >/dev/null 2>&1; then
      log "Something's still answering on :8080/mcp/ — stopping whatever's bound to that port..."
      lsof -ti :8080 | xargs -r kill 2>/dev/null || true
      sleep 1
      mcp_server_running && warn "Still answering on :8080/mcp/ after kill — stop it manually (lsof -i :8080)."
    else
      warn "Something's still answering on :8080/mcp/ and 'lsof' isn't available to find/stop it — stop it manually."
    fi
  fi

  log "Stopping local-dev Compose stack..."
  (cd "$REPO_ROOT/local-dev" && docker compose down)
}

cmd_status() {
  echo "-- Docker containers --"
  docker ps --filter "name=ai-obs-" --format 'table {{.Names}}\t{{.Status}}' 2>/dev/null || echo "(docker not reachable)"
  echo
  echo "-- MCP server --"
  if [[ -f "$PID_FILE" ]] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
    echo "running, pid $(cat "$PID_FILE")"
  elif mcp_server_running; then
    echo "something is answering on :8080/mcp/, but not started by this script"
  else
    echo "not running"
  fi
}

case "${1:-up}" in
  up)      cmd_up ;;
  down)    cmd_down ;;
  restart) cmd_down; cmd_up ;;
  status)  cmd_status ;;
  *) die "Usage: $0 {up|down|restart|status}" ;;
esac
