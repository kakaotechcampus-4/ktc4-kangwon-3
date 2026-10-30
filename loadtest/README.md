# 부하 테스트 (k6)

BE(`backend/beforeselling`)에 부하를 줘서 병목을 찾고, 개선 전·후를 같은 조건에서 비교하기 위한 도구 모음이다.

- **BE 코드는 바꾸지 않는다.** 운영과 같은 이미지에 `AI_BASE_URL`만 Mock AI로 바꿔 띄운다.
- AI 서버는 Mock(`mock-ai/`)으로 대신한다. 접수(202) → 진행 콜백 → 결과/질문/실패 콜백을 실제 AI와 같은 순서로 보낸다.
  - 상품 1개 처리 시간은 기본 1~2분이다.
  - 큐는 없다. 들어오는 요청은 모두 받는다.
- 진단 1건은 상품마다 콜백을 약 15회 보내고, 콜백마다 `diagnoses` 행을 `FOR UPDATE`로 잠근다. FE는 3초마다 폴링한다.
  - 사용자 클릭보다 **콜백과 폴링이 주된 부하**이므로, Mock 없이 API만 두드리면 실제 부하가 재현되지 않는다.

## 구성

```
loadtest/
  compose.perf.yml        perf-app(운영 이미지) · perf-mock-ai · postgres/redis exporter
  .env.perf.example       perf 전용 환경 변수 (복사해서 .env.perf로)
  seed/init-perf-db.sql   운영 PG 안에 perf role·database 생성 (1회)
  seed/seed.sql           테스트 유저 1,000명
  mock-ai/                Mock AI 서버 (FastAPI)
  prometheus/targets.json 테스트 중에만 Prometheus에 넣는 수집 대상
  k6/lib/                 설정 · JWT 생성 · API 래퍼 · 사용자 흐름
  k6/config/profiles.js   load / stress / spike / soak 프로파일
  k6/scenarios/           smoke · prepare · api-* · journey
  results/                회차별 결과 (커밋하지 않음)
infra/monitoring/grafana/dashboards/loadtest.json   "beforeselling 부하 테스트" 대시보드
```

### 운영 EC2에서의 격리

EC2 한 대에 운영 서비스가 모두 있으므로 다음처럼 나눈다.

| 대상 | 방법 |
|---|---|
| BE | 테스트하는 동안 운영 BE(blue/green 중 활성 쪽)를 **내린다**. 메모리 여유를 확보하고, 운영 트래픽이 섞이지 않게 하기 위해서다. |
| PostgreSQL | 운영 컨테이너(`be-db`) 안의 **별도 database `beforeselling_perf`**를 쓴다. 전용 role `perf`는 운영 테이블 권한이 없다. |
| Redis | 운영 컨테이너(`be-redis`)의 **DB 15번**을 쓴다. AT는 k6가 직접 만들기 때문에 사용량이 거의 없다. 다만 `allkeys-lru`는 인스턴스 전체에 적용되므로 메모리를 감시한다. |
| secret | `JWT_SECRET`, `INTERNAL_API_TOKEN`, `TOKEN_ENCRYPTION_KEY`는 **perf 전용 값**을 쓴다. 운영과 공유하는 값은 `REDIS_PASSWORD` 하나다. |
| 트래픽 | 로컬 k6 → `EC2 공인 IP:18080`으로 직접 보낸다. 보안그룹은 **내 IP/32만**, 테스트하는 동안만 연다. Cloudflare·nginx를 거치지 않는다. |
| 추가 메모리 | 약 1.9GB (perf-app 1500m + mock 256m + exporters 128m) |

## 로컬에서 먼저 확인

EC2에 올리기 전에 같은 구성을 로컬 Docker에서 smoke로 확인한다. BE의 기존 compose가 `be_appnet`, `db`, `redis`를 만든다.

```bash
cd backend/beforeselling
docker compose up -d --wait db redis
docker compose build app                       # beforeselling-app:latest
cd ../../loadtest
cp .env.perf.example .env.perf                 # PERF_IMAGE_TAG=latest, REDIS_PASSWORD=BE .env 값, MOCK_DURATION_*=5/10
docker exec -i be-db psql -U <BE .env의 DB_USERNAME> -d postgres -v perf_password=<DB_PASSWORD> < seed/init-perf-db.sql
docker compose -f compose.perf.yml --env-file .env.perf up -d --build --wait
docker exec -i be-db psql -U perf -d beforeselling_perf < seed/seed.sql
k6 run -e BASE_URL=http://localhost:18080 -e JWT_SECRET=<perf JWT_SECRET> k6/scenarios/smoke.js
```

## 처음 한 번만 (EC2)

### 1. Prometheus 설정 반영

`infra/monitoring/prometheus/prometheus.yml`에 `loadtest` job(file_sd)과 Grafana 대시보드(`loadtest.json`)가 추가되어 있다.

- develop에 병합되면 모니터링 배포 워크플로가 서버에 반영한다.
- 평소에는 대상 파일이 없어서 아무것도 수집하지 않는다.

### 2. perf database·role 생성 (EC2)

```bash
cd ~/ktc4-kangwon-3/loadtest            # 저장소를 받아 둔 위치
cp .env.perf.example .env.perf && chmod 600 .env.perf
vi .env.perf                            # 값 채우기 (아래 표)
set -a; . ./.env.perf; set +a
APP_ENV=/home/ubuntu/app/.env           # 운영 BE env (운영 PG 사용자 이름 확인용)
docker exec -i be-db psql -U "$(grep ^DB_USERNAME= $APP_ENV | cut -d= -f2)" -d postgres \
  -v perf_password="$DB_PASSWORD" < seed/init-perf-db.sql
```

`.env.perf`에서 채울 값:

| 키 | 값 |
|---|---|
| `PERF_IMAGE_TAG` | `docker inspect -f '{{.Config.Image}}' be-server-<blue\|green>`의 태그 부분 |
| `DB_PASSWORD` | 새로 생성 (`openssl rand -base64 24`) |
| `REDIS_PASSWORD` | 운영 `.env`의 `REDIS_PASSWORD` |
| `JWT_SECRET`, `INTERNAL_API_TOKEN` | `openssl rand -base64 48`로 각각 새로 생성 |
| `TOKEN_ENCRYPTION_KEY` | `openssl rand -base64 32` |

### 3. 스키마·유저·조회용 데이터

```bash
# perf-app이 한 번 떠야 ddl-auto가 스키마를 만든다
docker compose -f compose.perf.yml --env-file .env.perf up -d --build --wait
docker exec -i be-db psql -U perf -d beforeselling_perf < seed/seed.sql
```

로컬 PC에서 다음을 실행한다.

```bash
k6 run -e BASE_URL=http://<EC2-IP>:18080 -e JWT_SECRET=<perf JWT_SECRET> k6/scenarios/prepare.js
```

이 데이터는 조회 기준선(`api-products-list`, `api-diagnoses-get`)에 쓴다. 생성이 끝난 뒤 Mock 처리 시간(최대 2분)이 지나야 진단이 완료된다.

## 매 회차 실행 절차

**시간대: 새벽.** 운영 API가 약 1~1.5시간 중단된다.

1. **사전 확인 (EC2)**
   - `df -h`
   - `free -m`
   - 운영 BE의 활성 색 확인: `cat /etc/nginx/be-upstream.conf`
2. **보안그룹**에 `내 IP/32 → TCP 18080` 규칙을 추가한다.
3. **운영 BE 중지**
   ```bash
   cd /home/ubuntu/app && COMPOSE_FILE=docker-compose.yml:docker-compose.prod.yml docker compose stop app-<color>
   ```
   중지한 뒤 `free -m`으로 여유가 3.5GB 안팎인지 확인한다.
4. **perf 스택 기동과 수집 대상 등록**
   ```bash
   cd ~/ktc4-kangwon-3/loadtest
   docker compose -f compose.perf.yml --env-file .env.perf up -d --build --wait
   MON_DIR=/home/ubuntu/app/monitoring
   mkdir -p $MON_DIR/prometheus/loadtest && cp prometheus/targets.json $MON_DIR/prometheus/loadtest/
   ```
   Grafana의 **beforeselling 부하 테스트** 대시보드에서 대상 `be-perf`에 값이 나오는지 확인한다.
5. **smoke** → **워밍업**(load 프로파일을 `CONCURRENT=10`으로 3분 실행하고 중간에 Ctrl+C) → **본 측정** (아래 시나리오)
6. **중단 조건**: 하나라도 해당하면 즉시 Ctrl+C 한다.
   - 호스트 메모리 > 90%
   - OOM 발생
   - 운영 AI/DB/Redis 컨테이너 재시작
   - Redis 메모리가 maxmemory(320MB)에 근접하거나 evicted가 0보다 큼
7. **기록**: 아래 [결과 기록 양식](#결과-기록-양식)을 채운다.
8. **정리**
   ```bash
   rm -f $MON_DIR/prometheus/loadtest/targets.json
   docker compose -f compose.perf.yml --env-file .env.perf down     # perf DB는 다음 회차를 위해 남긴다
   cd /home/ubuntu/app && COMPOSE_FILE=docker-compose.yml:docker-compose.prod.yml docker compose start app-<color>
   until [ "$(docker inspect -f '{{.State.Health.Status}}' be-server-<color>)" = healthy ]; do sleep 5; done
   curl -sfo /dev/null -w '%{http_code}\n' https://palgijeone.com/v3/api-docs   # 200이면 복구 완료
   ```
   보안그룹 규칙도 삭제한다.

> 운영 BE는 `docker compose start`로 되살린다(`up`이 아님). `up`은 IMAGE_TAG 없이 `:latest`로 재생성하기 때문이다(`deploy/blue-green.sh`의 rollback과 같은 이유).

## 시나리오

모든 명령은 로컬 PC의 `loadtest/` 디렉터리에서 실행한다. 공통 인자는 다음과 같다.

```bash
export BASE_URL=http://<EC2-IP>:18080 JWT_SECRET=<perf JWT_SECRET>
RUN=$(date +%m%d-%H%M)
K6="k6 run -e BASE_URL=$BASE_URL -e JWT_SECRET=$JWT_SECRET"
# 결과 저장: K6_WEB_DASHBOARD=true K6_WEB_DASHBOARD_EXPORT=results/$RUN-<name>.html $K6 --summary-export results/$RUN-<name>.json ...
```

| 단계 | 명령 | 목적 |
|---|---|---|
| smoke | `$K6 k6/scenarios/smoke.js` | 생성 → 콜백 → COMPLETED(질문이 있으면 답변 → 재진단 → COMPLETED)까지 끝나는지. 실패가 하나라도 있으면 실패로 처리한다. |
| 기준선: 목록 | `$K6 -e STEPS=10,25,50,100,200 k6/scenarios/api-products-list.js` | 페이지 + count 쿼리, 키워드 `LIKE '%kw%'`(30%)의 한계 |
| 기준선: 상세 | `$K6 -e STEPS=10,25,50,100,200 k6/scenarios/api-diagnoses-get.js` | 폴링 대상(요청당 약 10쿼리)의 한계 |
| 기준선: 생성 | `$K6 -e STEPS=1,2,5,10 k6/scenarios/api-diagnoses-create.js` | 생성 + @Async 접수 + 이어지는 콜백 부하 |
| load | `$K6 -e PROFILE=load -e CONCURRENT=50 k6/scenarios/journey.js` | 목표 동시 세션에서 SLO를 지키는지 (약 18분) |
| stress | `$K6 -e PROFILE=stress -e STRESS_STEPS=50,100,200,400 k6/scenarios/journey.js` | 처리량이 꺾이는 지점과 처음 포화되는 자원 (약 30분) |
| spike | `$K6 -e PROFILE=spike -e CONCURRENT=50 -e SPIKE_PEAK=200 k6/scenarios/journey.js` | 급증 후 큐·풀이 회복되는지 (약 17분) |
| soak | `$K6 -e PROFILE=soak -e CONCURRENT=50 -e SOAK_MINUTES=45 k6/scenarios/journey.js` | 메모리·커넥션 누수, async 큐 증가 (약 50분) |

- 단일 API 기준선은 한 단계에서 SLO가 깨지면 그 지점이 해당 API의 한계(knee)다. 그 이상은 Ctrl+C로 끊어도 된다.
- `journey.js`는 진단 세션과 둘러보기 세션(`BROWSE_RATIO`배, 기본 1)을 함께 넣는다.
- smoke는 `.env.perf`에서 `MOCK_DURATION_MIN_S=5`, `MOCK_DURATION_MAX_S=10`으로 줄여 빠르게 한 번 확인한다. 그다음 기본값(60/120)으로 되돌려 `up -d`하고 한 번 더 확인한다.

### 부하 목표 (가정)

근거 데이터가 없으므로 아래 가정에서 출발한다. 실제 지표가 생기면 바꾼다.

- **피크 동시 세션 = DAU × 평균 세션 시간(분) ÷ 활성 시간(720분) × 피크 계수(5~10)**
  - DAU 1,000, 세션 5분이면 평균 약 7명이고, 피크는 35~70명이다. 그래서 load 목표를 **50**으로 잡았다.
- k6에는 동시 세션을 도착률로 바꿔 넣는다(리틀의 법칙).
  - 세션 1개 ≈ 150초(AI 1~2분 + 폴링·생각 시간)
  - 50명 ÷ 150초 → 분당 20세션 (`profiles.js`의 `sessionsPerMinute`)
- 동시 세션이 50일 때의 정상 상태 서버 부하
  - 폴링 약 17 req/s
  - 콜백 약 17~20 req/s (상품 평균 1.7개 × 약 15회 ÷ 90초 × 50)
  - 진행 중인 상품 약 85개
- SLO 초안

| 항목 | 목표 |
|---|---|
| 조회 p95 | < 500ms |
| 생성 p95 | < 1s |
| 에러율 | < 1% |
| 콜백 | Mock의 `ok` 외 outcome = 0 |
| 질문 없는 진단의 E2E p95 | < 130s |

> **k6의 응답시간에는 로컬 PC ↔ EC2 왕복 지연이 섞인다.** 응답시간은 Grafana(서버 측 `http_server_requests`)를 기준으로 판단하고, k6 수치는 처리량·에러·E2E와 중단 안전장치로 쓴다. k6 summary에 `dropped_iterations`가 있거나 로컬 CPU가 포화되면 부하 생성기의 한계이므로 그 회차는 버린다.

## 무엇을 보고 어떻게 판단하나

대시보드는 **beforeselling 부하 테스트**(`$job` = `be-perf`)를 본다. 평균은 보지 않는다. 다음 순서로 본다.

1. **p95/p99 응답시간**
2. **처리량(req/s)**
3. **에러율**
4. **포화도**: Tomcat 스레드, Hikari pending, async 큐, CPU, GC, 힙, DB 락
5. **진단 E2E 시간**: 사용자가 체감하는 시간

| 보이는 패턴 | 의심할 곳 | 다음에 볼 것 |
|---|---|---|
| p95↑, Tomcat busy ≈ max, CPU 여유 | 스레드가 I/O를 기다림 | Hikari pending, 외부 호출 |
| Hikari pending > 0, acquire 시간↑ | 커넥션 풀(기본 10) 부족 또는 느린 쿼리·락 | usage 시간, PG 락, `pg_stat_activity` |
| 콜백 p95↑, PG 락↑, Mock 재시도↑ | 같은 진단의 콜백이 `diagnoses` 행 잠금에서 줄을 섬 | 상품 수가 많은 진단일수록 심한지 |
| `run_not_assigned` 재시도↑ | 202 뒤 `assignRuns` 저장이 늦음 | async executor 큐, Hikari |
| executor queued가 계속 증가 | @Async 풀(8스레드, 무제한 큐) 포화 | AI 접수 지연 × 유입률 |
| 힙이 max에 붙고 GC 일시정지↑ | 메모리(SerialGC, 1500m × 70%) | 할당이 많은 엔드포인트 |
| process CPU ≈ 100% | 연산·직렬화 | 프로파일링(async-profiler, Sentry 프로파일) |
| PG `returned` ≫ `fetched` | 풀스캔(예: 키워드 검색) | 실행 계획(`EXPLAIN ANALYZE`) |
| k6 `dropped_iterations` 또는 로컬 CPU↑ | 부하 생성기 한계 | 서버 문제가 아니다. 회차를 버린다 |

### 코드에서 미리 세운 가설

측정으로 확인할 것들이다.

- Hikari 기본 풀 10, Tomcat 기본 200 스레드
- `@EnableAsync`만 있고 executor 설정이 없음 → Boot 기본값(8스레드, 무제한 큐)을 AI 접수·S3 삭제·메일이 함께 씀
- 콜백마다 `diagnoses` 행을 `SELECT ... FOR UPDATE`로 잠금 (lock timeout 3s)
- 폴링마다 상세 조회 약 10쿼리 (`@BatchSize(100)`이라 N+1은 아님)
- 목록 키워드 검색 `lower(name) like '%kw%'` → 인덱스를 못 탐
- `SimpleClientHttpRequestFactory`: AI 호출에 커넥션 풀이 없음
- 운영은 Sentry 트레이싱·프로파일링 100% → 기준선에서는 끄고, 오버헤드는 별도 실험으로 비교한다(별도 Sentry 프로젝트 DSN 사용)

## 개선 → 재측정

1. 가설 하나만 고친 브랜치로 이미지를 만든다. 예: `beforeselling-app:perf-hikari20`
2. `.env.perf`의 `PERF_IMAGE_TAG`만 바꾼다.
3. 같은 프로파일·같은 시간대에서 **3회씩** 측정해 기준선과 비교한다. 설정 값만 바꾸는 실험(Hikari 크기 등)은 이미지를 새로 만들지 않고 `compose.perf.yml`의 `environment`에 추가해도 된다.

## 결과 기록 양식

`results/<MMDD-HHMM>-<시나리오>.md`(커밋하지 않음) 또는 팀 문서에 남긴다.

```markdown
## <날짜> <시나리오/프로파일> — <한 줄 결론>
- 이미지: beforeselling-app:<tag> (커밋 <sha>) / 바꾼 것: <없음 | 설정·코드 변경>
- 조건: CONCURRENT=<n> / STEPS=<…> / Mock <min>~<max>s, 질문 <ratio>, 실패 <ratio>
- k6: req/s <n>, 에러율 <n>%, dropped_iterations <n>, E2E p95 <n>s (summary: results/<file>.json, 리포트: results/<file>.html)
- 서버(Grafana, 같은 시간 범위): p95 <n>ms / p99 <n>ms, Tomcat busy 최대 <n>, Hikari pending 최대 <n>, executor queued 최대 <n>, 힙 최대 <n>MB, CPU 최대 <n>%
- 처음 포화된 자원: <…>
- 관찰 / 다음 가설: <…>
```

## 개념 정리

- **VU(Virtual User)**: k6에서 시나리오 함수를 반복 실행하는 동시 실행 단위다.
  - RPS ≈ VU ÷ (응답시간 + 생각 시간)이다. VU를 고정하면(closed model) 서버가 느려질 때 요청률도 같이 떨어져 병목이 가려진다.
  - 그래서 여기서는 **도착률(arrival-rate, open model)**을 정하고 VU는 k6가 필요한 만큼 쓰게 한다.
- **동시 사용자 수**: 같은 순간에 세션이 살아 있는 사용자 수다.
  - 리틀의 법칙(동시 수 = 도착률 × 체류 시간)으로 도착률과 서로 바꿀 수 있다.
  - 이 서비스는 진단을 기다리는 동안에도 폴링과 콜백이 계속 생기므로 체류 시간이 길고, 그만큼 동시 수가 크게 잡힌다.

## 프로젝트가 끝나면

```bash
docker exec -i be-db psql -U <운영 DB_USERNAME> -d postgres -c 'DROP DATABASE beforeselling_perf' -c 'DROP ROLE perf'
docker exec be-redis sh -c 'redis-cli -a "$REDIS_PASSWORD" -n 15 FLUSHDB'   # FLUSHALL 금지(운영 키까지 지움)
docker image rm perf-mock-ai:local
```
