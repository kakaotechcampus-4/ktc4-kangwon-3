# AI 서버 로그

AI 서버가 남기는 앱 로그의 설정·형식·레벨 기준과 서버에서 보는 방법, 로그·오류를 Sentry로 보내는 방식을 정리한다. 로그 논의는 #497, 지표는 [AI_METRICS.md](AI_METRICS.md), 로컬 진단 trace는 [AI_TRACE.md](AI_TRACE.md).

## 1. 설정

- 서버는 uvicorn만 실행해 따로 설정하지 않으면 WARNING 이상만 나옴. lifespan 시작 때 `configure_logging()`(`app/observability/logs.py`)이 `app` 로거에 핸들러·레벨을 붙임
- 레벨은 환경변수 `LOG_LEVEL` (DEBUG·INFO·WARNING·ERROR, 비우면 INFO). 그 밖의 값은 기동 실패
- `app` 로거만 설정. uvicorn 로거는 uvicorn 설정 그대로, 외부 라이브러리(httpx 등)는 WARNING 이상만 (요청 주소에 API 키가 들어가는 로그 방지)
- 출력은 표준 에러 → 서버에서는 `docker logs`로 봄
- uvicorn이 붙인 핸들러(기동·접근 로그)도 같은 형식으로 맞춤. 상태 코드 뒤 설명(`OK` 등)과 색은 빠짐
- 헬스체크(`/api/ai/v1/health`)·지표 수집(`/metrics`)의 성공 응답은 접근 로그에서 뺌. 15초마다 불려 진단 로그를 덮음. 실패 응답은 남음
- 컨테이너 로그는 10MB씩 5개까지만 보관 (`docker-compose.yml`의 `x-logging`)

## 2. 형식

```
2026-11-02 21:03:12,345 INFO app.sessions.manager.runner: 진단 시작 (대기 0.0초, 답변 0개) diagnosis_id=d-1 product_id=p-1 run_id=... run_type=production stage=extraction
```

`시각 레벨 로거: 메시지` 뒤에 실행 정보가 ` key=value`로 붙음.

### 2.1 실행 정보

진단 실행 중 남긴 줄에만 붙음. 실행 밖(기동·법령 점검·CLIP 적재 등)의 줄에는 없음.

| 필드 | 내용 | 붙는 때 |
|---|---|---|
| `diagnosis_id` | 진단서 ID | 진단서로 들어온 실행 (단독 실행이면 없음) |
| `product_id` | 상품 ID | 실행 내내 |
| `run_id` | 실행 ID | 실행 내내 |
| `run_type` | production·evaluation·test | 실행 내내 |
| `stage` | 지금 단계 (extraction·selection·tool_execution 등) | 첫 단계 알림부터 |
| `retry_round` | Tool 재실행 회차 | 검증이 Tool을 다시 부른 뒤부터 |

- 문맥 변수(`ContextVar`)라 로그를 남기는 쪽 코드는 실행 정보를 모름. 메시지에 상품·실행 ID를 다시 넣지 않음
- 새 스레드로는 자동으로 안 넘어감 → 스레드를 띄우는 쪽에서 `contextvars.copy_context().run`으로 넘김 (관세 결정사례 검색어 스레드)
- 콜백 전송 스레드는 실행 컨텍스트가 없어 이벤트의 진단서·상품·실행 ID를 `log_fields()`로 붙임

## 3. 레벨 기준

| 레벨 | 기준 | 예 |
|---|---|---|
| ERROR | 예상하지 못한 예외(코드 오류 가능성). traceback까지 | Tool 코드 오류, sink·구독자 처리 실패, 진단 실행 실패 |
| WARNING | 예상한 실패(`AIError`: 외부 API·모델·Tool 오류). 원인 예외를 한 줄로, traceback 없이 | 진단 단계 실패, Tool 실행 실패, 모델 호출 실패, 콜백 재시도·버림, 접수 거절 |
| INFO | 진단 흐름의 주요 지점. 상품 하나에 수십 줄 이내 | 접수, 시작, 모델 호출, 요약 |
| DEBUG | 문제 볼 때만 | 토큰 사용량 상세(캐시 쓰기·적중률), 게이트웨이 원본 usage |

- 예외 메시지 속 URL의 키(`serviceKey`·`OC`)는 `mask_sensitive_params()`로 가림
- 상품 원문·모델 응답 원문·진단서 본문은 남기지 않음

## 4. 진단 하나에 남는 주요 줄

| 메시지 | 레벨 | 남기는 곳 |
|---|---|---|
| `진단 접수 (글 N개 N자, 이미지 N장, URL 있음/없음)` | INFO | `sessions/manager/manager.py` |
| `재진단 접수 (질문 회차 N, 답변 N개)` | INFO | `sessions/manager/manager.py` |
| `진단 접수 거절: 대기열 가득 참` / `진행 중인 상품 ...` | WARNING | `sessions/manager/manager.py` |
| `재진단 접수 거절: {이유} (질문 회차 n, 답변 n개)` | WARNING | `sessions/manager/manager.py` |
| `서버 종료: 실행 중 진단 n개를 최대 N초 기다림` / `n개 끝남, n개 남음 (N초)` | INFO | `sessions/manager/manager.py` |
| `서버 종료로 진단을 버림: 실행 중 n개(...), 대기 중 n개(...), 답변 대기 n개 (...)` (0개인 항목은 빠짐, DB 보관 안 할 때) | WARNING | `sessions/manager/manager.py` |
| `서버 종료로 진단을 멈춤, DB에 보관: 실행 중 n개(...) 재시작 때 시간 초과 실패, 대기 중 n개(...) 재시작 때 다시 실행, 답변 대기 n개 재시작 때 복원` (0개인 항목은 빠짐) | WARNING | `sessions/manager/manager.py` |
| `재시작 전 대기 세션 복원, 다시 실행 (답변 n개)` / `재시작 전 답변 대기 세션 복원 (질문 회차 n)` | INFO | `sessions/manager/manager.py` |
| `재시작 전 실행 중이던 진단을 시간 초과 실패로 끝냄 (정상 종료 처리 없이 끊김)` | WARNING | `sessions/manager/manager.py` |
| `재시작 전 대기 세션이 최대 시간을 넘겨 실행하지 않고 시간 초과 실패로 끝냄` | WARNING | `sessions/manager/manager.py` |
| `진단 세션 복원: 대기 n개, 답변 대기 n개, 끊긴 실행 n개, 되살리지 않음 n개` | INFO | `sessions/manager/manager.py` |
| `보관된 진단 세션을 읽지 못해 지움 (product_id=...)` | WARNING | `db/session_archive.py` |
| `진단 시작 (대기 N초, 답변 N개)` | INFO | `sessions/manager/runner.py` |
| `입력 확인 통과 (글 점수, 이미지 점수)` | INFO | `diagnosis/guard.py` |
| `입력 확인 차단` / `입력 확인 의심: 형식, 점수, 못 본 이미지, 실패 호출, 발췌` | WARNING | `diagnosis/guard.py` |
| `입력 확인 실패, 확인 없이 진단` | WARNING | `diagnosis/guard.py` |
| `모델 호출 {이름} (모델, 시간, 토큰, 비용)` | INFO | `agents/base/usage_log.py` |
| `모델 호출 실패 {이름} (...)` | WARNING | `agents/base/usage_log.py` |
| `Tool 실행 실패 {Tool}: {원인} ← {감싼 원인}…` | WARNING·ERROR | `diagnosis/run_log.py` |
| `결정사례 검색어 실패 '{검색어}': {원인}` | WARNING | `tools/customs/search.py` |
| `진단 단계 실패 (stage, code, retryable): {원인}` | WARNING | `diagnosis/job.py` |
| `질문 회차 초과로 미완료 처리` | INFO | `sessions/manager/runner.py` |
| `진단 요약: ...` | INFO | `sessions/manager/runner.py` |
| `콜백 재시도 예정` / `콜백 이벤트를 보내지 못함` | WARNING | `callbacks/outbox.py` |

### 4.1 진단 요약

실행이 끝날 때 상품마다 한 줄. 느린 단계·비싼 상품·자주 실패하는 Tool을 고르는 용도.

```
진단 요약: 완료 action_required, 검증 verified, 종료 completed | 총 84.2초 | 단계(초) extraction 12.3 selection 5.1 tool_execution 40.2 aggregation 3.0 verification 20.1 finalization 0.0 | Tool(초) electrical_safety success 18.2, customs success 25.0 | Tool 실행 1회 | 모델 호출 9회(실패 0) 토큰 입력 52310 출력 4120 | 비용 41.3원
```

(숫자는 예시)

- 결말: `완료 {종합 상태}, 검증 {검증 상태}, 종료 {종료 이유}` / `답변 대기, 질문 N개` / `실패 {코드}, 재시도 가능·불가`
- 단계 시간: Tool 재실행 회차의 같은 단계는 더함. `Tool 실행 N회`가 2 이상이면 검증이 Tool을 다시 부른 것
- Tool: 실행 순서대로, 건너뜀은 뺌. 재실행이 있으면 회차별로 묶음 (`[1] radio_compliance success 1.2, ... [2] labeling_advertising_detection success 1.7`)
- 모델 호출·토큰·비용: 이 실행의 에이전트 호출 합. 단가를 모르는 모델은 비용에서 빠짐
- 모으는 곳: `app/observability/run_summary.py` (측정 기록·에이전트 실행 기록 sink로 받음)

## 5. 서버에서 보기

```bash
# 최근 로그 따라가기
docker logs -f --tail 200 ai-server

# 상품 하나의 흐름
docker logs ai-server 2>&1 | grep "product_id=p-123"

# 상품별 요약만
docker logs ai-server 2>&1 | grep "진단 요약"

# 경고·오류만
docker logs ai-server 2>&1 | grep -E " (WARNING|ERROR) "
```

- 레벨을 바꾸려면 서버 `.env`의 `LOG_LEVEL`을 고치고 컨테이너를 다시 띄움
- 배포·`docker stop` 때 실행 중이던 진단은 끝날 때까지 기다림 (drain). 끝난 결과는 평소처럼 콜백으로 나감
  - 기다리는 시간: 580초(`SESSION_DRAIN_SECONDS`)와 실행 중인 세션이 모두 최대 시간(600초)을 넘기는 시각 중 이른 쪽. 넘긴 세션은 시간 초과 실패 콜백
  - 이후 남은 콜백을 15초까지 보내고 종료. 컨테이너 종료 대기(`stop_grace_period`)는 600초
  - 대기 중 세션은 취소됨. 멈춘 상품은 `서버 종료로 진단을 멈춤`(DB 보관) 또는 `서버 종료로 진단을 버림` 줄로 확인
  - 기다리는 동안 새 요청은 받지 않음. BE는 받지 못한 요청을 대기로 돌렸다가 다시 보냄
- 대기·실행 중·답변 대기 세션은 DB에도 보관해 재시작 때 되살림. 상태별 처리는 `AI_SESSION_ARCHIVE.md`
- 모델 호출 사용량 기록(`logs/usage.jsonl`)은 named volume `ai-logs`에 남아 배포 뒤에도 유지. 보기: `docker exec ai-server python -m app.usage`
  - 10MB를 넘으면 `usage.jsonl.1`부터 한 칸씩 밀고 새 파일로 시작, 5개까지만 보관 (`docker logs` 상한과 같음)
  - `python -m app.usage`는 지금 파일(`usage.jsonl`)만 집계

## 6. 새 로그를 넣을 때

- 실행 중 코드면 메시지에 상품·실행 ID를 넣지 않음 (실행 정보로 붙음)
- 실행 밖에서도 불리는 코드(발신함 종료, 시간 초과 처리, 접수)는 ID를 메시지에 넣음
- 스레드를 새로 띄우면 `copy_context().run`으로 실행 정보를 넘김
- 레벨은 3장 기준. 예외를 잡아 실패 결과로 바꾸는 곳은 원인을 남김 (안 남기면 원인이 어디에도 안 보임)
- ERROR는 Sentry 이벤트가 됨 (7장). 예상한 실패를 ERROR로 남기면 Sentry 알림이 쌓임

## 7. Sentry 로그·오류 전송

진단은 세션 스레드에서 돌고 실패를 잡아 로그로 남겨서, 요청 예외만 보내면 대부분 안 잡힘. 그래서 3장 레벨 기준을 그대로 씀. 설정은 `app/observability/sentry.py`.

### 7.1 켜기

- 환경변수 `SENTRY_DSN`(Sentry 프로젝트 주소, `https://`로 시작)이 있으면 켜짐, 비우면 꺼짐. 켜면 `SENTRY_ENVIRONMENT`(운영·개발 구분 이름) 필수. 아니면 기동 실패
- lifespan 시작 때 `configure_logging()` 바로 다음에 켬. 기동 로그에 `Sentry 켜짐 (environment=..., 로그 INFO)` 또는 `Sentry 꺼짐 (SENTRY_DSN 없음)`
- 비워 두면 꺼진 채로 기동 → 서버 `.env`에 두 값이 없어도 배포는 막히지 않음. 켤 때 서버 `.env`에 두 값을 넣고 컨테이너를 다시 띄움
- 로컬·테스트는 비워 둠
- `SENTRY_LOG_LEVEL`: Logs로 보낼 최소 레벨. `INFO`(기본)·`WARNING`·`ERROR`·`OFF`. `OFF`면 로그 전송을 끄고 오류 이벤트만 보냄. 모르는 값이면 기동 실패
  - 할당량(로그 5GB)이 차 가면 서버 `.env`만 바꿔 `WARNING` → `OFF` 순으로 줄이고 컨테이너를 다시 띄움

### 7.2 보내는 것

| 대상 | Sentry에서 |
|---|---|
| ERROR 로그 (traceback 포함) | 이벤트 |
| 요청 처리 중 잡지 않은 예외 (500) | 이벤트 |
| 예외 처리기가 응답으로 바꾼 4xx | 안 감 |
| INFO 이상 로그 | 로그 (Logs 화면, `SENTRY_LOG_LEVEL` 이상만). 이벤트 앞의 흐름 기록(breadcrumb)에도 남음 |
| DEBUG 로그 | 안 감 |

- 진단 실행 중 이벤트·로그에는 2.1 실행 정보를 붙임 (이벤트는 태그, 로그는 속성) → Sentry에서 진단서·상품·실행·단계별로 걸러 봄. 실행 밖에는 없음
  - 상품 하나의 흐름: Logs 화면에서 `product_id:<상품 ID>`로 검색 (5장 `grep`과 같은 용도)
- 로그는 `docker logs`와 같은 내용 (3장 기준이라 상품 원문·모델 응답 원문·진단서 본문 없음). 외부 라이브러리는 WARNING 이상만
- 성능 트레이스는 쓰지 않음

### 7.3 안 보내는 것

| 대상 | 방법 |
|---|---|
| 요청 본문 (상품 원문) | `max_request_body_size="never"`. 기본값은 개인정보 설정과 상관없이 본문을 보냄 |
| IP·쿠키 | `send_default_pii=False` |
| 오류 위치별 지역 변수 | `include_local_variables=False`. 요청 헤더·상품 원문·키가 든 URL이 그대로 실림 |
| 내부 인증 헤더 (`X-Internal-Token`·`X-Dev-Api-Key`) | 보내기 직전 뺌. `Authorization`·`Cookie`는 SDK가 가림 |
| URL의 키 (`serviceKey`·`OC`) | 예외 메시지, 로그 문구·인자·`extra`(이벤트·로그 둘 다), 흐름 기록(외부 호출의 `url`·`http.query` 포함)에서 `***`로 가림 |

- 예외 메시지 속 상품 원문은 가리지 않음 (검증 오류 메시지에 입력값이 들어가는 경우 등). 메시지를 지우면 원인을 못 봄
- 오류 위치 주변 소스 줄은 감 (코드라 비밀값 없음)
