#!/usr/bin/env bash
# blue-green.sh 동작 테스트. docker/nginx/systemctl/curl/flock/pgrep/sleep을 stub으로 바꿔 서버 없이 실행한다.
#   bash deploy/test/blue-green.test.sh
set -uo pipefail

SCRIPT="$(cd "$(dirname "$0")/.." && pwd)/blue-green.sh"
FAILURES=0
CURRENT=""

# ---------- stub 환경 ----------

setup() {
  WORK=$(mktemp -d)
  STUB_BIN="$WORK/bin"
  STATE="$WORK/state"   # 컨테이너 이름 = 파일명, 내용 = 상태(running/exited)
  FLAGS="$WORK/flags"   # 실패를 흉내 낼 플래그 파일
  CALLS="$WORK/calls.log"
  mkdir -p "$STUB_BIN" "$STATE" "$FLAGS"
  : > "$CALLS"

  export UPSTREAM_FILE="$WORK/be-upstream.conf"
  export MEMINFO_FILE="$WORK/meminfo"
  export LOCK_FILE="$WORK/be-deploy.lock"
  export MIN_AVAILABLE_MB=1200
  export STATE FLAGS CALLS
  printf 'MemTotal:        3900000 kB\nMemAvailable:    2048000 kB\n' > "$MEMINFO_FILE"
  printf 'proxy_pass http://be_app;\n' > "$WORK/nginx-T.out"
  export NGINX_T_OUT="$WORK/nginx-T.out"

  cat > "$STUB_BIN/docker" <<'EOF'
#!/usr/bin/env bash
echo "docker $*" >> "$CALLS"
color_of() { for a in "$@"; do case $a in app-blue|app-green) echo "be-server-${a#app-}";; esac; done; }
if [ "$1" = inspect ]; then
  name="${!#}"
  # 실제 docker도 대상이 없으면 -f 출력으로 빈 줄을 찍고 exit 1 한다.
  [ -f "$STATE/$name" ] || { echo; exit 1; }
  case "$*" in
    *Health*) cat "$FLAGS/health-$name" 2>/dev/null || echo healthy ;;
    *) cat "$STATE/$name" ;;
  esac
  exit 0
fi
if [ "$1" = compose ]; then
  shift
  sub=$1
  name=$(color_of "$@")
  case $sub in
    up)
      [ -z "$name" ] && exit 0
      [ -f "$FLAGS/up-fail" ] && { echo running > "$STATE/$name"; exit 1; }
      echo running > "$STATE/$name" ;;
    start) echo running > "$STATE/$name" ;;
    stop) echo exited > "$STATE/$name" ;;
    rm) rm -f "$STATE/$name" ;;
    ps) echo db-id; echo redis-id ;;
  esac
  exit 0
fi
case $1 in
  stop) echo exited > "$STATE/${!#}" ;;
  rm) rm -f "$STATE/${!#}" ;;
esac
exit 0
EOF

  cat > "$STUB_BIN/nginx" <<'EOF'
#!/usr/bin/env bash
echo "nginx $*" >> "$CALLS"
case $1 in
  -T) [ -f "$FLAGS/nginx-dump-fail" ] && exit 1; cat "$NGINX_T_OUT" ;;
  -t) [ -f "$FLAGS/nginx-test-fail" ] && exit 1 ;;
esac
exit 0
EOF

  cat > "$STUB_BIN/systemctl" <<'EOF'
#!/usr/bin/env bash
echo "systemctl $*" >> "$CALLS"
[ -f "$FLAGS/reload-fail" ] && exit 1
exit 0
EOF

  cat > "$STUB_BIN/curl" <<'EOF'
#!/usr/bin/env bash
echo "curl $*" >> "$CALLS"
[ -f "$FLAGS/smoke-fail" ] && exit 22
exit 0
EOF

  cat > "$STUB_BIN/flock" <<'EOF'
#!/usr/bin/env bash
echo "flock $*" >> "$CALLS"
[ -f "$FLAGS/lock-busy" ] && exit 1
exit 0
EOF

  printf '#!/usr/bin/env bash\nexit 1\n' > "$STUB_BIN/pgrep"
  printf '#!/usr/bin/env bash\nexit 0\n' > "$STUB_BIN/sleep"
  chmod +x "$STUB_BIN"/*
}

teardown() {
  rm -rf "$WORK"
}

run_script() {
  PATH="$STUB_BIN:$PATH" bash "$SCRIPT" "$@" > "$WORK/out.log" 2>&1
  EXIT_CODE=$?
}

given_upstream() { printf 'upstream be_app {\n    server 127.0.0.1:%s;\n}\n' "$1" > "$UPSTREAM_FILE"; }
given_container() { echo "$2" > "$STATE/$1"; }
flag() { : > "$FLAGS/$1"; }

# ---------- 검증 헬퍼 ----------

fail() {
  echo "  FAIL: $*"
  echo "  --- 스크립트 출력 ---"; sed 's/^/  | /' "$WORK/out.log"
  echo "  --- 호출 기록 ---"; sed 's/^/  | /' "$CALLS"
  FAILURES=$((FAILURES + 1))
}

assert_exit() { [ "$EXIT_CODE" -eq "$1" ] || fail "종료 코드 기대=$1 실제=$EXIT_CODE"; }
assert_failed() { [ "$EXIT_CODE" -ne 0 ] || fail "실패해야 하는데 성공했다"; }
assert_upstream_port() { grep -q "127.0.0.1:$1;" "$UPSTREAM_FILE" || fail "upstream 포트 기대=$1 실제=$(cat "$UPSTREAM_FILE" 2>/dev/null)"; }
assert_state() {
  local actual
  actual=$(cat "$STATE/$1" 2>/dev/null || echo missing)
  [ "$actual" = "$2" ] || fail "$1 상태 기대=$2 실제=$actual"
}
assert_called() { grep -qF -- "$1" "$CALLS" || fail "호출 기대: $1"; }
assert_not_called() { ! grep -qF -- "$1" "$CALLS" || fail "호출되면 안 됨: $1"; }
assert_output() { grep -qF -- "$1" "$WORK/out.log" || fail "출력 기대: $1"; }

# ---------- deploy ----------

test_deploy_blue_active_then_switch_to_green_and_stop_blue() {
  given_upstream 8080; given_container be-server-blue running

  run_script deploy sha-new

  assert_exit 0
  assert_upstream_port 8082
  assert_state be-server-green running
  assert_state be-server-blue exited
  assert_called "docker compose up -d --no-deps --force-recreate --wait --wait-timeout 180 app-green"
  assert_called "curl -sf -o /dev/null --max-time 5 http://127.0.0.1:8082/v3/api-docs"
  assert_called "systemctl reload nginx"
}

test_deploy_green_active_then_switch_to_blue_and_stop_green() {
  given_upstream 8082; given_container be-server-green running; given_container be-server-blue exited

  run_script deploy sha-new

  assert_exit 0
  assert_upstream_port 8080
  assert_state be-server-blue running
  assert_state be-server-green exited
}

test_deploy_passes_image_tag_to_compose() {
  given_upstream 8080; given_container be-server-blue running
  # stub이 IMAGE_TAG를 기록하도록 감싼다
  mv "$STUB_BIN/docker" "$STUB_BIN/docker-real"
  cat > "$STUB_BIN/docker" <<'EOF'
#!/usr/bin/env bash
[ "$1" = compose ] && [ "$2" = up ] && echo "IMAGE_TAG=${IMAGE_TAG:-}" >> "$CALLS"
exec "$(dirname "$0")/docker-real" "$@"
EOF
  chmod +x "$STUB_BIN/docker"

  run_script deploy sha-new

  assert_exit 0
  assert_called "IMAGE_TAG=sha-new"
}

test_deploy_first_migration_stops_legacy_gracefully_without_removing() {
  given_upstream 8080; given_container be-server running

  run_script deploy sha-new

  assert_exit 0
  assert_upstream_port 8082
  assert_state be-server-green running
  assert_called "docker stop -t 70 be-server"
  assert_state be-server exited
}

test_deploy_to_blue_removes_leftover_legacy_first() {
  given_upstream 8082; given_container be-server-green running; given_container be-server exited

  run_script deploy sha-new

  assert_exit 0
  assert_called "docker rm -f be-server"
  assert_state be-server missing
  assert_upstream_port 8080
}

test_deploy_health_failure_keeps_active_and_removes_target() {
  given_upstream 8080; given_container be-server-blue running; flag up-fail

  run_script deploy sha-new

  assert_failed
  assert_upstream_port 8080
  assert_state be-server-blue running
  assert_state be-server-green missing
  assert_not_called "systemctl reload nginx"
  assert_called "docker compose logs --tail 100 app-green"
}

test_deploy_smoke_failure_keeps_active_and_removes_target() {
  given_upstream 8080; given_container be-server-blue running; flag smoke-fail

  run_script deploy sha-new

  assert_failed
  assert_upstream_port 8080
  assert_state be-server-blue running
  assert_state be-server-green missing
  assert_not_called "systemctl reload nginx"
  assert_called "curl -sf -o /dev/null --max-time 5 http://127.0.0.1:8082/v3/api-docs"
}

test_deploy_nginx_test_failure_restores_upstream() {
  given_upstream 8080; given_container be-server-blue running; flag nginx-test-fail

  run_script deploy sha-new

  assert_failed
  assert_upstream_port 8080
  assert_state be-server-blue running
  assert_state be-server-green missing
  assert_not_called "systemctl reload nginx"
  assert_called "nginx -t"
}

test_deploy_reload_failure_restores_upstream() {
  given_upstream 8080; given_container be-server-blue running; flag reload-fail

  run_script deploy sha-new

  assert_failed
  assert_upstream_port 8080
  assert_state be-server-blue running
  assert_state be-server-green missing
  assert_called "systemctl reload nginx"
}

test_deploy_aborts_when_target_already_running() {
  given_upstream 8080; given_container be-server-blue running; given_container be-server-green running

  run_script deploy sha-new

  assert_failed
  assert_output "상태 불일치"
  assert_upstream_port 8080
  assert_state be-server-green running
  assert_not_called "docker compose up"
}

test_deploy_aborts_when_memory_is_low() {
  given_upstream 8080; given_container be-server-blue running
  printf 'MemAvailable:     512000 kB\n' > "$MEMINFO_FILE"

  run_script deploy sha-new

  assert_failed
  assert_output "가용 메모리"
  assert_not_called "docker compose up"
}

test_deploy_aborts_when_nginx_does_not_use_upstream_yet() {
  given_upstream 8080; given_container be-server running
  printf 'proxy_pass http://127.0.0.1:8080;\n' > "$NGINX_T_OUT"

  run_script deploy sha-new

  assert_failed
  assert_output "infra-nginx"
  assert_not_called "docker compose"
}

test_deploy_aborts_when_upstream_file_missing() {
  given_container be-server running

  run_script deploy sha-new

  assert_failed
  assert_not_called "docker compose"
  assert_output "upstream 파일"
}

test_deploy_aborts_when_lock_is_held() {
  given_upstream 8080; given_container be-server-blue running; flag lock-busy

  run_script deploy sha-new

  assert_failed
  assert_not_called "docker compose"
  assert_output "다른 배포"
}

test_deploy_without_image_tag_fails() {
  given_upstream 8080; given_container be-server-blue running

  run_script deploy

  assert_failed
  assert_not_called "docker compose"
  assert_output "사용법"
}

# ---------- rollback ----------

test_rollback_starts_previous_color_and_removes_current() {
  given_upstream 8082; given_container be-server-green running; given_container be-server-blue exited

  run_script rollback

  assert_exit 0
  assert_upstream_port 8080
  assert_state be-server-blue running
  assert_state be-server-green missing
  assert_called "docker compose start app-blue"
  assert_not_called "docker compose up"
}

test_rollback_fails_when_no_previous_container() {
  given_upstream 8082; given_container be-server-green running

  run_script rollback

  assert_failed
  assert_output "롤백 대상"
  assert_upstream_port 8082
  assert_state be-server-green running
}

test_deploy_without_legacy_does_not_touch_it() {
  given_upstream 8082; given_container be-server-green running

  run_script deploy sha-new

  assert_exit 0
  assert_not_called "docker rm -f be-server"
  assert_not_called "docker stop -t 70 be-server"
}

test_rollback_unhealthy_previous_keeps_current() {
  given_upstream 8082; given_container be-server-green running; given_container be-server-blue exited
  echo unhealthy > "$FLAGS/health-be-server-blue"

  run_script rollback

  assert_failed
  assert_upstream_port 8082
  assert_state be-server-green running
  assert_state be-server-blue exited
  assert_called "docker compose start app-blue"
}

test_unknown_command_fails() {
  given_upstream 8080

  run_script whatever

  assert_failed
  assert_output "사용법"
}

# ---------- 실행 ----------

TESTS=$(declare -F | awk '{print $3}' | grep '^test_')
TOTAL=0
for t in $TESTS; do
  TOTAL=$((TOTAL + 1))
  CURRENT=$t
  before=$FAILURES
  setup
  "$t"
  teardown
  if [ "$FAILURES" -eq "$before" ]; then echo "ok   $CURRENT"; else echo "FAIL $CURRENT"; fi
done

echo
if [ "$FAILURES" -ne 0 ]; then
  echo "실패한 검증 $FAILURES 건 / 테스트 $TOTAL 개"
  exit 1
fi
echo "테스트 $TOTAL 개 모두 통과"
