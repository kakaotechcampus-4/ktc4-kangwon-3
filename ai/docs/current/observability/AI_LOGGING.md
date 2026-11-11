# AI 서버 로그

AI 서버가 기록하는 앱 로그의 설정·형식·레벨 기준과 서버에서 확인하는 방법, 로그·오류를 Sentry로 전송하는 방식을 정리한다. 지표는 [AI_METRICS.md](AI_METRICS.md), 로컬 진단 trace는 [AI_TRACE.md](AI_TRACE.md)를 참고한다.

## 1. 설정

- 서버는 uvicorn만 실행하므로 별도로 설정하지 않으면 WARNING 이상만 출력된다. lifespan 시작 시 `configure_logging()`(`app/observability/logs.py`)이 `app` 로거에 핸들러와 레벨을 설정한다.
- 레벨은 환경변수 `LOG_LEVEL`(DEBUG·INFO·WARNING·ERROR, 비우면 INFO)로 지정한다. 그 밖의 값이면 기동에 실패한다.
- `app` 로거만 설정한다. uvicorn 로거는 uvicorn 설정을 그대로 사용하고, 외부 라이브러리(httpx 등)는 WARNING 이상만 출력한다(요청 주소에 API 키가 포함된 로그 방지).
- 출력은 표준 에러이며, 서버에서는 `docker logs`로 확인한다.
- uvicorn이 설정한 핸들러(기동·접근 로그)도 동일한 형식으로 일치시킨다. 상태 코드 뒤 설명(`OK` 등)과 색상은 제외된다.
- 헬스체크(`/api/ai/v1/health`)·지표 수집(`/metrics`)의 성공 응답은 접근 로그에서 제외한다. 15초마다 호출되어 진단 로그를 가리기 때문이다. 실패 응답은 기록된다.
- 컨테이너 로그는 10MB 파일을 5개까지 보관한다(`docker-compose.yml`의 `x-logging`).

## 2. 형식

```
2026-01-01 21:03:12,345 INFO app.sessions.manager.runner: 진단 시작 (대기 0.0초, 답변 0개) diagnosis_id=d-1 product_id=p-1 run_id=... run_type=production
```

`시각 레벨 로거: 메시지` 뒤에 실행 정보가 ` key=value` 형식으로 덧붙는다.

### 2.1 실행 정보

진단 실행 중 기록한 줄에만 덧붙는다. 실행 밖(기동·법령 점검·CLIP 적재 등)에서 기록한 줄에는 없다.

| 필드 | 내용 | 기록 시점 |
|---|---|---|
| `diagnosis_id` | 진단서 ID | 진단서로 접수된 실행 (단독 실행이면 없음) |
| `product_id` | 상품 ID | 실행 전체 |
| `run_id` | 실행 ID | 실행 전체 |
| `run_type` | production·evaluation·test·dummy | 실행 전체 |
| `stage` | 현재 단계 (extraction·selection·tool_execution 등) | 첫 단계 알림부터 |
| `retry_round` | Tool 재실행 회차 | 검증이 Tool을 다시 호출한 뒤부터 |

- 문맥 변수(`ContextVar`)이므로 로그를 기록하는 코드는 실행 정보를 알 필요가 없다. 메시지에 상품·실행 ID를 다시 포함하지 않는다.
- 새 스레드로는 자동으로 전달되지 않으므로, 스레드를 생성하는 쪽에서 `contextvars.copy_context().run`으로 전달한다(Tool 병렬 실행, 입력 가드 이미지 병렬 판단, 관세 결정사례 검색어 스레드).
- 콜백 전송 스레드는 실행 컨텍스트가 없으므로 이벤트의 진단서·상품·실행 ID를 `log_fields()`로 덧붙인다.

## 3. 레벨 기준

| 레벨 | 기준 | 예 |
|---|---|---|
| ERROR | 예상하지 못한 예외(코드 오류 가능성). traceback 포함 | Tool 코드 오류, sink·구독자 처리 실패, 진단 실행 실패 |
| WARNING | 예상한 실패(`AIError`: 외부 API·모델·Tool 오류). 원인 예외를 traceback 없이 한 줄로 기록 | 진단 단계 실패, Tool 실행 실패, 모델 호출 실패, 콜백 폐기, 접수 거절 |
| INFO | 진단 흐름의 주요 지점. 상품 하나당 수십 줄 이내 | 접수, 시작, 모델 호출, 요약 |
| DEBUG | 문제 분석 시에만 사용 | 토큰 사용량 상세(캐시 쓰기·적중률), 게이트웨이 원본 usage, 콜백 중간 재시도 |

- 예외 메시지 속 키는 `mask_sensitive_params()`로 가린다. `serviceKey=`는 URL 쿼리가 아니어도 가리고, `OC=`는 쿼리일 때만 가린다(문장 속 `OC=`는 과전류 표기와 겹치기 때문).
- 상품 원문·모델 응답 원문·진단서 본문은 기록하지 않는다.

## 4. 주요 로그 줄

### 4.1 진단 하나에 기록되는 줄

| 메시지 | 레벨 | 기록 위치 |
|---|---|---|
| `진단 접수 (글 N개 N자, 이미지 N장, URL 있음/없음)` | INFO | `sessions/manager/manager.py` |
| `재진단 접수 (질문 회차 N, 답변 N개)` | INFO | `sessions/manager/manager.py` |
| `진단 접수 거절: 대기열 가득 참` / `진행 중인 상품 ...` | WARNING | `sessions/manager/manager.py` |
| `재진단 접수 거절: {이유} (질문 회차 n, 답변 n개)` | WARNING | `sessions/manager/manager.py` |
| `서버 종료: 실행 중 진단 n개를 최대 N초 기다림` / `n개 끝남, n개 남음 (N초)` | INFO | `sessions/manager/manager.py` |
| `서버 종료로 진단을 버림: 실행 중 n개(...), 대기 중 n개(...), 답변 대기 n개 (...)` (0개인 항목은 제외, DB에 보관하지 않는 경우) | WARNING | `sessions/manager/manager.py` |
| `서버 종료로 진단을 멈춤, DB에 보관: 실행 중 n개(...) 재시작 때 시간 초과 실패, 대기 중 n개(...) 재시작 때 다시 실행, 답변 대기 n개 재시작 때 복원` (0개인 항목은 제외) | WARNING | `sessions/manager/manager.py` |
| `재시작 전 대기 세션 복원, 다시 실행 (답변 n개)` / `재시작 전 답변 대기 세션 복원 (질문 회차 n)` | INFO | `sessions/manager/manager.py` |
| `재시작 전 실행 중이던 진단을 시간 초과 실패로 끝냄 (정상 종료 처리 없이 끊김)` | WARNING | `sessions/manager/manager.py` |
| `재시작 전 대기 세션이 최대 시간을 넘겨 실행하지 않고 시간 초과 실패로 끝냄` | WARNING | `sessions/manager/manager.py` |
| `진단 세션 복원: 대기 n개, 답변 대기 n개, 끊긴 실행 n개, 되살리지 않음 n개` | INFO | `sessions/manager/manager.py` |
| `보관된 진단 세션을 읽지 못해 지움 (product_id=...)` | WARNING | `db/session_archive.py` |
| `진단 시작 (대기 N초, 답변 N개)` | INFO | `sessions/manager/runner.py` |
| `입력 확인 통과 (글 점수, 이미지 점수)` | INFO | `diagnosis/guard.py` |
| `입력 확인 차단` / `입력 확인 의심: 형식, 점수, 못 본 이미지, 실패 호출, 발췌` | WARNING | `diagnosis/guard.py` |
| `입력 확인 판단 실패, 이 부분은 넘김: {원인}` (글·이미지 일부의 판단 실패) | WARNING | `agents/input_guard/agent.py` |
| `입력 확인 실패, 확인 없이 진단` | WARNING | `diagnosis/guard.py` |
| `모델 호출 {이름} (모델, 시간, 토큰, 비용)` | INFO | `agents/base/usage_log.py` |
| `모델 호출 실패 {이름} (...)` | WARNING | `agents/base/usage_log.py` |
| `Tool 실행 실패 {Tool}: {원인} ← {감싼 원인}…` | WARNING·ERROR | `diagnosis/run_log.py` |
| `결정사례 검색어 실패 '{검색어}': {원인}` | WARNING | `tools/customs/search.py` |
| `검증 모델 검토 실패, 규칙 검사 결과로 진행 (status=...): {원인}` | WARNING | `diagnosis/stages.py` |
| `진단 단계 실패 (stage, code, retryable): {원인}` | WARNING | `diagnosis/job.py` |
| `질문 회차 초과로 미완료 처리` | INFO | `sessions/manager/runner.py` |
| `진단 요약: ...` | INFO | `sessions/manager/runner.py` |
| `콜백 재시도 예정 n/5` | DEBUG | `callbacks/outbox.py` |
| `콜백 이벤트를 보내지 못함: {사유} (재시도 N회, ...)` | WARNING | `callbacks/outbox.py` |

### 4.2 진단 요약

실행이 끝날 때 상품마다 한 줄을 기록한다. 느린 단계, 비용이 큰 상품, 자주 실패하는 Tool을 찾는 데 사용한다.

```
진단 요약: 완료 action_required, 검증 verified, 종료 completed | 총 84.2초 | 단계(초) extraction 12.3 selection 5.1 tool_execution 40.2 aggregation 3.0 verification 20.1 finalization 0.0 | Tool(초) electrical_safety success 18.2, customs_requirements success 25.0 | Tool 실행 1회 | 모델 호출 9회(실패 0) 토큰 입력 52310 출력 4120 | 비용 41.3원
```

(숫자는 예시)

- 결말: `완료 {종합 상태}, 검증 {검증 상태}, 종료 {종료 이유}` / `답변 대기, 질문 N개` / `실패 {코드}, 재시도 가능·불가`
- 단계 시간: Tool 재실행 회차의 동일 단계는 합산한다. `Tool 실행 N회`가 2 이상이면 검증이 Tool을 다시 호출한 것이다.
- Tool: 실행 순서대로 기록하며 건너뛴 Tool은 제외한다. 재실행이 있으면 회차별로 묶는다(`[1] radio_compliance success 1.2, ... [2] labeling_advertising_detection success 1.7`).
- 모델 호출·토큰·비용: 이 실행의 에이전트 호출 합계이다. 단가를 알 수 없는 모델은 비용에서 제외된다.
- 집계 위치: `app/observability/run_summary.py` (측정 기록·에이전트 실행 기록 sink로 수신)

### 4.3 정기 작업·캐시 DB 줄

진단 실행 밖에서 기록되므로 실행 정보가 덧붙지 않는다.

| 메시지 | 레벨 | 기록 위치 |
|---|---|---|
| `법령 점검 완료 — 문서 N개, 버전 N개, 변경 N건, 실패 ...` | INFO | `db/law_cache.py` |
| `법령 점검 실패 — {문서}: {원인}` | WARNING | `db/law_cache.py` |
| `법령 변경 전달 실패` / `법령 점검 실행 실패` | ERROR | `db/law_cache.py` |
| `CLIP 주간 적재 — 새로 저장 N건, 삭제 N건, 실패 N건` | INFO | `db/clip_ingest.py` |
| `CLIP 주간 적재 건너뜀 — hs_cases가 비어 있음 ...` | WARNING | `db/clip_ingest.py` |
| `CLIP 주간 적재 실패` | ERROR | `db/clip_ingest.py` |
| `{조회} {저장소} {동작} 실패 — N초 동안 DB 건너뜀: {원인}` | WARNING | `db/fetchers.py` |
| `{조회} 조회 실패 — 만료된 캐시로 대신함 (만료 ...)` | WARNING | `db/fetchers.py` |
| `결정사례 DB 조회 실패 — CLIP으로 찾음: {원인}` | WARNING | `tools/customs/search.py` |

## 5. 서버에서 확인

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

- 레벨을 바꾸려면 서버 `.env`의 `LOG_LEVEL`을 수정하고 컨테이너를 다시 기동한다.
- 배포·`docker stop` 시 실행 중인 진단의 처리(drain)와 재시작 시 세션 복원은 [AI_SESSION_ARCHIVE.md](../storage/AI_SESSION_ARCHIVE.md)를 참고한다. 종료 시 멈춘 상품은 `서버 종료로 진단을 멈춤`(DB 보관) 또는 `서버 종료로 진단을 버림` 줄로 확인한다.
- 모델 호출 사용량 기록(`logs/usage.jsonl`)은 named volume `ai-logs`에 저장되므로 배포 후에도 유지된다. 확인: `docker exec ai-server python -m app.observability.usage`
  - 10MB를 넘으면 기존 파일을 `usage.jsonl.1`부터 한 칸씩 밀고 새 파일로 시작한다. 이전 파일은 `usage.jsonl.1`-`usage.jsonl.5`의 5개까지 보관한다.
  - `python -m app.observability.usage`는 현재 파일(`usage.jsonl`)만 집계한다.

## 6. 새 로그를 추가할 때

- 실행 중에 호출되는 코드이면 메시지에 상품·실행 ID를 포함하지 않는다(실행 정보로 덧붙음).
- 실행 밖에서도 호출되는 코드(발신함 종료, 시간 초과 처리, 접수)는 ID를 메시지에 포함한다.
- 스레드를 새로 생성하면 `copy_context().run`으로 실행 정보를 전달한다.
- 레벨은 3장 기준을 적용한다. 예외를 잡아 실패 결과로 바꾸는 곳은 원인을 기록한다(기록하지 않으면 원인을 어디에서도 확인할 수 없음).
- ERROR는 Sentry 이벤트가 된다(7장). 예상한 실패를 ERROR로 기록하면 Sentry 알림이 누적된다.

## 7. Sentry 로그·오류 전송

진단은 세션 스레드에서 실행되고 실패를 잡아 로그로 기록하므로, 요청 예외만 전송하면 대부분 검출되지 않는다. 그러므로 3장 레벨 기준을 그대로 적용한다. 설정은 `app/observability/sentry.py`에 있다.

### 7.1 켜기

- 환경변수 `SENTRY_DSN`(Sentry 프로젝트 주소, `https://`로 시작)이 있으면 켜지고, 비우면 꺼진다. 켜는 경우 `SENTRY_ENVIRONMENT`(운영·개발 구분 이름)가 필수이며, 없으면 기동에 실패한다.
- lifespan 시작 시 `configure_logging()` 바로 다음에 켠다. 기동 로그에 `Sentry 켜짐 (environment=..., 로그 INFO)` 또는 `Sentry 꺼짐 (SENTRY_DSN 없음)`이 기록된다.
- 비워 두면 꺼진 상태로 기동하므로, 서버 `.env`에 두 값이 없어도 배포는 중단되지 않는다. 켤 때는 서버 `.env`에 두 값을 입력하고 컨테이너를 다시 기동한다.
- 로컬·테스트에서는 비워 둔다.
- `SENTRY_LOG_LEVEL`: Logs로 전송할 최소 레벨이다. `INFO`(기본)·`WARNING`·`ERROR`·`OFF` 중 하나이며, `OFF`이면 로그 전송을 끄고 오류 이벤트만 전송한다. 그 밖의 값이면 기동에 실패한다.
  - 할당량(로그 5GB)이 소진되어 가면 서버 `.env`만 수정하여 `WARNING` → `OFF` 순으로 줄이고 컨테이너를 다시 기동한다.

### 7.2 전송하는 것

| 대상 | Sentry에서 |
|---|---|
| ERROR 로그 (traceback 포함) | 이벤트 |
| 요청 처리 중 잡지 않은 예외 (500) | 이벤트 |
| 예외 처리기가 응답으로 바꾼 4xx | 전송하지 않음 |
| INFO 이상 로그 | 로그 (Logs 화면, `SENTRY_LOG_LEVEL` 이상만). 이벤트 앞의 흐름 기록(breadcrumb)에도 포함 |
| DEBUG 로그 | 전송하지 않음 |

- 진단 실행 중 이벤트·로그에는 2.1의 실행 정보를 덧붙이므로(이벤트는 태그, 로그는 속성) Sentry에서 진단서·상품·실행·단계별로 필터링할 수 있다. 실행 밖에서 기록된 항목에는 없다.
  - 상품 하나의 흐름: Logs 화면에서 `product_id:<상품 ID>`로 검색한다(5장 `grep`과 동일한 용도).
- 로그는 `docker logs`와 동일한 내용이다(3장 기준이므로 상품 원문·모델 응답 원문·진단서 본문 없음). 외부 라이브러리는 WARNING 이상만 전송한다.
- 성능 트레이스는 사용하지 않으며, 외부 요청에 추적 헤더를 덧붙이지 않는다(`trace_propagation_targets=[]`).

### 7.3 전송하지 않는 것

| 대상 | 방법 |
|---|---|
| 요청 본문 (상품 원문) | `max_request_body_size="never"`. 기본값은 개인정보 설정과 관계없이 본문을 전송함 |
| IP·쿠키 | `send_default_pii=False` |
| 오류 위치별 지역 변수 | `include_local_variables=False`. 켜면 요청 헤더·상품 원문·키가 포함된 URL이 그대로 전송됨 |
| 내부 인증 헤더 (`X-Internal-Token`·`X-Dev-Api-Key`) | 전송 직전 제거. `Authorization`·`Cookie`는 SDK가 가림 |
| 키 (`serviceKey=`는 URL 쿼리 밖 포함, `OC=`는 쿼리만) | 예외 메시지, 로그 문구·인자·`extra`(이벤트·로그 모두), 흐름 기록(외부 호출의 `url`·`http.query` 포함)에서 `***`로 가림 |

- 예외 메시지 속 상품 원문은 가리지 않는다(검증 오류 메시지에 입력값이 포함되는 경우 등). 메시지를 지우면 원인을 확인할 수 없기 때문이다.
- 오류 위치 주변 소스 줄은 전송한다(코드이므로 비밀값 없음).

---

변경 이력: [history/AI_LOGGING.md](../../history/observability/AI_LOGGING.md)
