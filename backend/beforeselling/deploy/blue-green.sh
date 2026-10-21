#!/usr/bin/env bash
# BE Blue-Green 배포/롤백. SSM(root)으로 compose 파일과 .env가 있는 release 디렉터리에서 실행한다.
#   blue-green.sh deploy <IMAGE_TAG>
#   blue-green.sh rollback
# 흐름과 불변식은 deploy/README.md 참고.
set -euo pipefail

UPSTREAM_FILE=${UPSTREAM_FILE:-/etc/nginx/be-upstream.conf}
MEMINFO_FILE=${MEMINFO_FILE:-/proc/meminfo}
LOCK_FILE=${LOCK_FILE:-/var/lock/be-deploy.lock}
MIN_AVAILABLE_MB=${MIN_AVAILABLE_MB:-1200}
HEALTH_TIMEOUT_SECONDS=${HEALTH_TIMEOUT_SECONDS:-180}
DRAIN_MAX_SECONDS=${DRAIN_MAX_SECONDS:-30}
SMOKE_ATTEMPTS=${SMOKE_ATTEMPTS:-10}
# compose의 stop_grace_period(70s)와 맞춘다. legacy 컨테이너는 그 설정이 없어서 직접 넘긴다.
LEGACY_STOP_TIMEOUT=70
LEGACY_CONTAINER=be-server

# 이게 없으면 stop/start/logs가 app-blue/app-green을 찾지 못한다.
export COMPOSE_FILE=docker-compose.yml:docker-compose.prod.yml

log() { echo "[blue-green] $*"; }
die() { echo "[blue-green] 실패: $*" >&2; exit 1; }
usage() { die "사용법: $0 deploy <IMAGE_TAG> | rollback"; }

port_of() { if [ "$1" = blue ]; then echo 8080; else echo 8082; fi; }
other_color() { if [ "$1" = blue ]; then echo green; else echo blue; fi; }
container_of() { echo "be-server-$1"; }

# running / exited / ... / missing
container_state() {
  inspect_container '{{.State.Status}}' "$1"
}

# docker inspect -f 는 대상이 없으면 빈 줄을 찍고 실패한다 → 그대로 쓰면 "\nmissing"이 돼 비교가 어긋난다.
inspect_container() {
  local value
  value=$(docker inspect --type container -f "$1" "$2" 2>/dev/null) || value=""
  echo "${value:-missing}"
}

acquire_lock() {
  # SSM 폴링이 타임아웃돼 job이 끝나도 서버의 스크립트는 계속 돈다 → GitHub concurrency만으로는 겹침을 못 막는다.
  # 호출한 쪽(SSM 명령)이 이미 같은 락을 잡았다면 다시 잡지 않는다(새로 열면 자기 자신과 교착된다).
  [ "${BE_DEPLOY_LOCK_HELD:-}" = 1 ] && return 0
  exec 9>"$LOCK_FILE"
  flock -w 600 9 || die "다른 배포/롤백이 진행 중입니다 ($LOCK_FILE)"
}

require_nginx_uses_upstream() {
  local conf
  # 파이프로 grep -q에 넘기면 pipefail 아래에서 nginx가 SIGPIPE로 죽어 오탐할 수 있어 변수에 담는다.
  conf=$(nginx -T 2>/dev/null) || die "nginx -T 실패 - upstream 파일($UPSTREAM_FILE)이 없거나 설정이 깨졌습니다. infra-nginx 워크플로를 먼저 반영하세요"
  case $conf in
    *"http://be_app"*) ;;
    *) die "nginx 설정이 아직 be_app upstream을 쓰지 않습니다 - infra-nginx 워크플로를 먼저 반영하세요" ;;
  esac
}

active_color() {
  [ -f "$UPSTREAM_FILE" ] || die "upstream 파일이 없습니다: $UPSTREAM_FILE"
  local content
  content=$(cat "$UPSTREAM_FILE")
  case $content in
    *"127.0.0.1:8080;"*) echo blue ;;
    *"127.0.0.1:8082;"*) echo green ;;
    *) die "upstream 파일을 해석할 수 없습니다: $UPSTREAM_FILE" ;;
  esac
}

require_memory() {
  local available_kb available_mb
  available_kb=$(awk '/^MemAvailable:/ {print $2}' "$MEMINFO_FILE")
  available_mb=$((available_kb / 1024))
  [ "$available_mb" -ge "$MIN_AVAILABLE_MB" ] \
    || die "가용 메모리 ${available_mb}MB < 필요 ${MIN_AVAILABLE_MB}MB - 새 컨테이너를 띄우지 않았습니다"
  log "가용 메모리 ${available_mb}MB"
}

smoke() {
  local port=$1
  for _ in $(seq 1 "$SMOKE_ATTEMPTS"); do
    curl -sf -o /dev/null --max-time 5 "http://127.0.0.1:$port/v3/api-docs" && return 0
    sleep 3
  done
  return 1
}

wait_healthy() {
  local container=$1 status
  for _ in $(seq 1 $((HEALTH_TIMEOUT_SECONDS / 3))); do
    status=$(inspect_container '{{.State.Health.Status}}' "$container")
    [ "$status" = healthy ] && return 0
    sleep 3
  done
  return 1
}

# upstream 파일을 바꾸고 nginx를 graceful reload 한다. 실패하면 파일을 원래대로 돌려놓는다.
switch_to() {
  local port previous tmp
  port=$(port_of "$1")
  previous=$(cat "$UPSTREAM_FILE")
  tmp=$(mktemp "$UPSTREAM_FILE.XXXXXX")
  printf 'upstream be_app {\n    server 127.0.0.1:%s;\n}\n' "$port" > "$tmp"
  chmod 644 "$tmp"
  mv "$tmp" "$UPSTREAM_FILE"

  if nginx -t && systemctl reload nginx; then
    log "nginx → 127.0.0.1:$port 전환"
    return 0
  fi
  printf '%s\n' "$previous" > "$UPSTREAM_FILE"
  return 1
}

# reload 후 옛 worker가 처리 중인 요청을 다 마칠 때까지 기다린다.
# Grafana websocket이 옛 worker를 오래 붙잡을 수 있어서 상한을 둔다.
drain() {
  sleep 2
  for _ in $(seq 1 "$DRAIN_MAX_SECONDS"); do
    pgrep -f 'nginx: worker process is shutting down' > /dev/null || return 0
    sleep 1
  done
  log "드레인 대기 ${DRAIN_MAX_SECONDS}s 초과 - 남은 연결은 옛 worker가 계속 처리합니다"
}

deploy() {
  local tag=$1 active target before_ids after_ids
  require_nginx_uses_upstream
  active=$(active_color)
  target=$(other_color "$active")
  [ "$(container_state "$(container_of "$target")")" != running ] \
    || die "상태 불일치: 비활성이어야 할 $target 이 실행 중입니다. nginx($UPSTREAM_FILE)와 컨테이너 상태를 확인하세요"
  require_memory
  log "활성 $active → 대상 $target (IMAGE_TAG=$tag)"

  before_ids=$(docker compose ps -q db redis)
  docker compose up -d --wait db redis
  after_ids=$(docker compose ps -q db redis)
  [ "$before_ids" = "$after_ids" ] || log "경고: db/redis 설정 변경으로 재생성됐습니다 (이 구간은 무중단이 아닙니다)"

  # 최초 이관 때 graceful stop만 해 둔 legacy가 8080을 쥐고 있으면 blue가 뜰 수 없다.
  if [ "$target" = blue ] && [ "$(container_state "$LEGACY_CONTAINER")" != missing ]; then
    docker rm -f "$LEGACY_CONTAINER"
  fi

  # 실패한 대상은 stop이 아니라 rm 한다 → "남아 있는 비활성 컨테이너 = 직전 정상 버전"이 유지돼 rollback이 안전하다.
  if ! IMAGE_TAG="$tag" docker compose up -d --no-deps --force-recreate --wait --wait-timeout "$HEALTH_TIMEOUT_SECONDS" "app-$target"; then
    docker compose logs --tail 100 "app-$target" || true
    docker compose rm -sf "app-$target"
    die "$target 기동/헬스체크 실패 - $active 가 계속 서비스합니다"
  fi
  if ! smoke "$(port_of "$target")"; then
    docker compose rm -sf "app-$target"
    die "$target 스모크 테스트 실패 - $active 가 계속 서비스합니다"
  fi
  if ! switch_to "$target"; then
    docker compose rm -sf "app-$target"
    die "nginx 전환 실패 - upstream을 되돌렸고 $active 가 계속 서비스합니다"
  fi
  drain

  # 옛 색은 지우지 않고 멈춰 두어 rollback 대상으로 남긴다.
  if [ "$(container_state "$(container_of "$active")")" = running ]; then
    docker compose stop "app-$active"
  fi
  if [ "$(container_state "$LEGACY_CONTAINER")" = running ]; then
    docker stop -t "$LEGACY_STOP_TIMEOUT" "$LEGACY_CONTAINER"
  fi
  log "완료: $target 서비스 중, $active 정지(롤백 대상)"
}

rollback() {
  local active target
  require_nginx_uses_upstream
  active=$(active_color)
  target=$(other_color "$active")
  case $(container_state "$(container_of "$target")") in
    missing) die "롤백 대상($target) 컨테이너가 없습니다" ;;
    running) die "상태 불일치: 비활성이어야 할 $target 이 실행 중입니다" ;;
  esac
  require_memory
  log "롤백: $active → $target"

  # up은 쓰지 않는다. IMAGE_TAG 없이 up 하면 :latest(=최신 빌드)로 재생성돼 버린다.
  docker compose start "app-$target"
  if ! wait_healthy "$(container_of "$target")" || ! smoke "$(port_of "$target")"; then
    docker compose stop "app-$target"
    die "$target 이 정상 기동하지 않았습니다 - $active 가 계속 서비스합니다"
  fi
  if ! switch_to "$target"; then
    docker compose stop "app-$target"
    die "nginx 전환 실패 - upstream을 되돌렸고 $active 가 계속 서비스합니다"
  fi
  drain

  # 롤백한 버전은 문제가 있던 버전이므로 지운다. 남겨 두면 다음 rollback이 그쪽으로 되돌아간다.
  docker compose rm -sf "app-$active"
  log "완료: $target 서비스 중, $active 제거"
}

main() {
  case ${1:-} in
    deploy) [ -n "${2:-}" ] || usage; acquire_lock; deploy "$2" ;;
    rollback) acquire_lock; rollback ;;
    *) usage ;;
  esac
}

main "$@"
