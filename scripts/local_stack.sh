#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG_DIR="$ROOT_DIR/tmp/local-stack/logs"
PID_DIR="$ROOT_DIR/tmp/local-stack/pids"
mkdir -p "$LOG_DIR" "$PID_DIR"

all_services=(api worker scheduler web)

usage() {
  cat <<'EOF'
Usage:
  ./scripts/local_stack.sh start [api|worker|scheduler|web ...]
  ./scripts/local_stack.sh stop [api|worker|scheduler|web ...]
  ./scripts/local_stack.sh status

If no service list is provided, all services are used.
EOF
}

resolve_services() {
  if [[ "$#" -eq 0 ]]; then
    printf '%s\n' "${all_services[@]}"
    return 0
  fi

  for service in "$@"; do
    case "$service" in
      api|worker|scheduler|web)
        printf '%s\n' "$service"
        ;;
      *)
        echo "Unknown service: $service" >&2
        exit 1
        ;;
    esac
  done
}

service_command() {
  case "$1" in
    api)
      printf '%s\n' "uvicorn app.main:app --host 0.0.0.0 --port 3106"
      ;;
    worker)
      printf '%s\n' "celery -A jobs.celery_app worker --loglevel=info"
      ;;
    scheduler)
      printf '%s\n' "python -m jobs.scheduler"
      ;;
    web)
      printf '%s\n' "pnpm --dir web dev --host 0.0.0.0 --port 5206"
      ;;
  esac
}

service_pattern() {
  case "$1" in
    api)
      printf '%s\n' "uvicorn app.main:app --host 0.0.0.0 --port 3106"
      ;;
    worker)
      printf '%s\n' "celery -A jobs.celery_app worker --loglevel=info"
      ;;
    scheduler)
      printf '%s\n' "python -m jobs.scheduler"
      ;;
    web)
      printf '%s\n' "vite.*--host 0.0.0.0 --port 5206"
      ;;
  esac
}

service_url() {
  case "$1" in
    api)
      printf '%s\n' "http://localhost:3106/health"
      ;;
    web)
      printf '%s\n' "http://localhost:5206/"
      ;;
    *)
      printf '%s\n' "-"
      ;;
  esac
}

pid_file() {
  printf '%s\n' "$PID_DIR/$1.pid"
}

log_file() {
  printf '%s\n' "$LOG_DIR/$1.log"
}

find_existing_pid() {
  local pattern

  pattern="$(service_pattern "$1")"
  ps -ax -o pid=,command= | awk -v pattern="$pattern" '
    $0 ~ pattern && $0 !~ /awk -v pattern/ {
      print $1
      exit
    }
  '
}

start_service() {
  local service="$1"
  local pidfile
  local logfile
  local command
  local pid

  pidfile="$(pid_file "$service")"
  logfile="$(log_file "$service")"
  command="$(service_command "$service")"

  if [[ -f "$pidfile" ]]; then
    pid="$(cat "$pidfile")"
    if kill -0 "$pid" 2>/dev/null; then
      echo "$service already running (pid $pid)"
      return 0
    fi
    rm -f "$pidfile"
  fi

  pid="$(find_existing_pid "$service")"
  if [[ -n "$pid" ]]; then
    echo "$pid" >"$pidfile"
    echo "$service already running (pid $pid)"
    return 0
  fi

  : >"$logfile"
  (
    cd "$ROOT_DIR"
    nohup bash -lc "$command" >>"$logfile" 2>&1 &
    echo $! >"$pidfile"
  )

  sleep 1
  pid="$(cat "$pidfile")"
  if kill -0 "$pid" 2>/dev/null; then
    echo "started $service (pid $pid) -> $(service_url "$service")"
    return 0
  fi

  echo "failed to start $service; recent log output:" >&2
  tail -n 40 "$logfile" >&2 || true
  exit 1
}

stop_service() {
  local service="$1"
  local pidfile
  local pid

  pidfile="$(pid_file "$service")"
  if [[ ! -f "$pidfile" ]]; then
    pid="$(find_existing_pid "$service")"
    if [[ -n "$pid" ]]; then
      kill "$pid"
      echo "stopped $service (pid $pid)"
      return 0
    fi
    echo "$service not running"
    return 0
  fi

  pid="$(cat "$pidfile")"
  if kill -0 "$pid" 2>/dev/null; then
    kill "$pid"
    echo "stopped $service (pid $pid)"
  else
    echo "$service pid file was stale ($pid)"
  fi
  rm -f "$pidfile"
}

status_service() {
  local service="$1"
  local pidfile
  local logfile
  local pid

  pidfile="$(pid_file "$service")"
  logfile="$(log_file "$service")"
  if [[ -f "$pidfile" ]]; then
    pid="$(cat "$pidfile")"
    if kill -0 "$pid" 2>/dev/null; then
      echo "$service: running (pid $pid) log=$(basename "$logfile") url=$(service_url "$service")"
      return 0
    fi
    echo "$service: stale pid file ($pid)"
    return 0
  fi

  pid="$(find_existing_pid "$service")"
  if [[ -n "$pid" ]]; then
    echo "$service: running (pid $pid) log=$(basename "$logfile") url=$(service_url "$service")"
    return 0
  fi

  echo "$service: stopped"
}

main() {
  local action="${1:-status}"
  shift || true

  case "$action" in
    start)
      while IFS= read -r service; do
        start_service "$service"
      done < <(resolve_services "$@")
      ;;
    stop)
      while IFS= read -r service; do
        stop_service "$service"
      done < <(resolve_services "$@")
      ;;
    status)
      while IFS= read -r service; do
        status_service "$service"
      done < <(printf '%s\n' "${all_services[@]}")
      ;;
    *)
      usage
      exit 1
      ;;
  esac
}

main "$@"
