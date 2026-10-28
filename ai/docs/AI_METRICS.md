# AI 서버 지표 목록

AI 서버가 `GET /metrics`로 내보내는 Prometheus 지표와 어디서 재는지를 정리한다. 지표 설계 논의는 #410.

## 1. 수집 방식

- Prometheus가 `/metrics`를 가져가는(pull) 방식. `/metrics`는 외부 공개 경로(`/api/ai/`) 밖이라 nginx로 열지 않음
- registry는 서버(lifespan)마다 하나. 서버 종료 때 등록표에서 sink를 해제해 다시 띄워도 옛 registry에 안 쌓임
- 재는 코드는 지표를 모름. 두 가지 통로로 기록만 남기고 `app/observability/metrics.py`가 지표로 바꿈
  - 세션 이벤트: `SessionManager.subscribe` → `SessionMetrics`
  - 측정 기록: `measurement_sinks`(`app/observability/measurements.py`) → `MeasurementMetrics`. 에이전트 실행 기록은 `agent_sinks` → `AgentMetrics`
- 현황 값(세션 수·자리·콜백 대기 수)은 수집(scrape) 때마다 읽음 (`SessionSnapshotCollector`, `CallbackOutboxCollector`)
- sink 오류는 경고 로그만 남기고 기록을 남긴 쪽 동작에 영향 없음

## 2. 라벨 원칙

- 상품 ID·실행 ID·URL·검색어는 라벨에 넣지 않음. 실행마다 시계열이 늘고 키가 노출될 수 있음
- 운영·평가·테스트는 실행 종류 `run_type`(production·evaluation·test)으로 나눔
- 외부 API는 클라이언트 클래스가 아니라 서버(기관) 단위 `api`로 묶음

## 3. 지금 있는 지표

Counter는 수집 때 이름 끝에 `_total`이 붙음 (`ai_client_calls` → `ai_client_calls_total`).

### 3.1 세션·대기열

| 지표 | 종류 | 라벨 | 내용 |
|---|---|---|---|
| `ai_session_queue_wait_seconds` | Histogram | `run_type` | 접수부터 실행 시작까지 대기 시간 |
| `ai_session_run_seconds` | Histogram | `run_type`, `outcome` | 실행 시작부터 결말까지 |
| `ai_session_total_seconds` | Histogram | `run_type`, `outcome` | 접수부터 결말까지 |
| `ai_session_stage_seconds` | Histogram | `run_type`, `stage` | 단계 하나의 소요 시간 |
| `ai_session_finished` | Counter | `run_type`, `outcome` | 결말(completed·awaiting_input·failed)별 수 |
| `ai_session_failed` | Counter | `run_type`, `error_code`, `stage` | 실패 코드·실패 단계별 수. 실행 전 실패는 `stage="none"` |
| `ai_session_tool_progress` | Counter | `run_type`, `tool_name`, `status` | Tool 진행 알림 수 |
| `ai_sessions` | Gauge | `status` | 상태별 보관 중인 세션 수 |
| `ai_session_slots_used` | Gauge | `scope`(all·dev) | 차지한 자리 수 |
| `ai_session_slots_limit` | Gauge | `scope`(all·dev·running) | 자리 상한 |
| `ai_session_accepted` | Counter | `run_type` | 누적 접수 수 |
| `ai_session_rejected` | Counter | `reason` | 사유별 누적 거절 수 |

- 소요 시간 구간: 1·5·10·30·60·120·300·600초 (세션 최대 600초)
- 재는 곳: `app/sessions/` 상태 전이 이벤트

### 3.2 모델 호출 (에이전트)

| 지표 | 종류 | 라벨 | 내용 |
|---|---|---|---|
| `ai_agent_calls` | Counter | `component`, `model`, `outcome` | 호출 수. `outcome`은 ok 또는 실패 단계(call·parsing·finalize) |
| `ai_agent_tokens` | Counter | `component`, `model`, `kind` | 토큰 수. cached는 input에, reasoning은 output에 포함 |
| `ai_agent_cost_krw` | Counter | `component`, `model` | 예상 비용(원). 단가 모르는 모델은 빠짐 |
| `ai_agent_call_seconds` | Histogram | `component`, `model`, `outcome` | 호출 1건 시간 |

- 재는 곳: `BaseAgent` 호출 기록(`AgentRunMeta`)

### 3.3 외부 API

| 지표 | 종류 | 라벨 | 내용 |
|---|---|---|---|
| `ai_client_calls` | Counter | `api`, `result` | 서버·결과별 호출 수 |
| `ai_client_seconds` | Histogram | `api` | 호출 1건 시간 |

- `api`: `law`(법제처, 별표 파일 포함)·`data_go_kr`(공공데이터포털, 관세청 세관장확인·식약처)·`customs`(관세청 품목분류)·`safety_korea`·`radio`·`marketplace`(판매 사이트)·`backend`(BE 콜백)·`llm`(모델 게이트웨이)
- `result`

  | 값 | 뜻 |
  |---|---|
  | `ok` | 2xx·3xx |
  | `http_error` | 4xx·5xx (예외 없이 상태 코드를 돌려주는 BE 콜백 포함) |
  | `api_error` | HTTP 200인데 본문이 오류라 파싱 실패 |
  | `timeout` | 시간 초과 |
  | `connect_error` | 연결 실패 등 전송 오류 |
  | `other` | 그 밖 (차단 URL·리다이렉트 초과 등) |

- 구간: 0.1·0.25·0.5·1·2·5·10·15·30·45·60초 (클라이언트 제한 시간이 경계)
- 재는 곳
  - `RequestClient.fetch_raw`·`fetch_parsed`: 조회 1번당 1건. 서버는 클래스 변수 `API`로 지정, 빠뜨리면 테스트가 잡음
  - `LlmClient` 전송 계층: HTTP 요청 1번당 1건. 에이전트를 거치지 않는 임베딩도 잡힘. SDK 재시도는 시도마다 기록
    - 스트리밍 응답도 조각 수와 상관없이 1건. 시간은 본문을 다 받고 닫을 때까지이고, 받다 끊기면 timeout·connect_error

### 3.4 콜백

| 지표 | 종류 | 라벨 | 내용 |
|---|---|---|---|
| `ai_callback_sent` | Counter | `event_type`, `result` | 이벤트별 최종 결과(delivered·dropped) |
| `ai_callback_dropped` | Counter | `reason` | 버린 사유 |
| `ai_callback_retries` | Counter | `event_type` | 재시도 횟수 합 |
| `ai_callback_pending` | Gauge | (없음) | 보내기 시작하지 않은 이벤트 수. 보내는 중·재시도 대기 중은 빠짐 |

- `event_type`: product_progress·product_awaiting_input·product_result·product_failed
- `reason`: `retry_exhausted`(재시도 초과)·`not_retryable`(4xx 등)·`shutdown`(종료 중)·`error`(예상 못 한 오류)
- 버린 이벤트가 생기면 BE 화면에서 진단이 멈춘 것처럼 보임
- 재는 곳: `CallbackOutbox` (HTTP 단위 결과는 `ai_client_calls{api="backend"}`)

### 3.5 Tool

| 지표 | 종류 | 라벨 | 내용 |
|---|---|---|---|
| `ai_tool_runs` | Counter | `tool_name`, `status` | 실행 결과(success·partial·failed·skipped) |
| `ai_tool_run_seconds` | Histogram | `tool_name`, `status` | 실행 1건 시간. 건너뛴 실행은 빠짐 |
| `ai_tool_errors` | Counter | `tool_name`, `error_type` | 실패 원인 |
| `ai_tool_findings` | Counter | `tool_name`, `determination` | 판단 항목 분포 |

- `error_type`: 예외 원인 체인을 보고 나눔
  - `model`: 모델 SDK 오류, 또는 실행 정보가 있는 에이전트 예외(출력 파싱 실패 등)
  - `client`: 근거 조회 실패 (클라이언트·httpx 오류)
  - `other`: 그 밖. 예외 없이 FAILED를 돌려준 경우 포함
- 구간: 1·2·5·10·20·30·60·120·300초
- 재는 곳: `ToolExecutor._execute_one`. 재실행 때 이전 판단을 살려 PARTIAL로 바꾼 결과가 아니라 Tool이 실제로 낸 결과를 기록

### 3.6 추출

| 지표 | 종류 | 라벨 | 내용 |
|---|---|---|---|
| `ai_extraction_seller_region` | Counter | `site`, `trimmed` | 아는 쇼핑몰 글 블록별 판매자 구역 자르기 결과 |

- `site`: aliexpress·temu. `trimmed`: `"true"`·`"false"`
- 쇼핑몰 화면이 아닌 글(직접 붙여 넣은 설명 등)은 자를 대상이 아니라 세지 않음
- `trimmed="false"`가 늘면 쇼핑몰 화면 변경 의심
- 재는 곳: `ExtractionAgent._build_messages` (후처리에서 다시 자르는 건 세지 않음)

## 4. 추가 예정

| 지표 | 시점 | 비고 |
|---|---|---|
| `ai_http_requests`, `ai_http_request_seconds` | 엔드포인트 개편(#406) 머지 후 | 라벨 `route`는 라우트 템플릿 |
| `ai_build_info` | #406·#420 머지 후 | `version`, `model_profile` |
| `ai_cache_lookups`, `ai_law_refresh_runs`, `ai_law_refresh_last_success_timestamp` | DB 캐시(#420) 머지 후 | |
| `ai_result_status`, `ai_result_incomplete` | 진단서 변환(#408)·파이프라인 연결(#320) 후 | |
| `ai_pipeline_end`, `ai_verification_results`, `ai_pipeline_retry_rounds`, `ai_question_rounds`, `ai_questions_asked`, `ai_diagnosis_cost_krw` | 파이프라인 연결(#320) 후 | |
| `ai_tool_runs`에 `run_type` 추가 | 파이프라인 연결(#320) 후 | `ToolExecutor`가 실행 컨텍스트를 받게 되면. `ai_session_tool_progress`는 이때 합침 |

## 5. 알람 후보

- 콜백 버림 발생: `ai_callback_dropped`
- 기관별 실패율 급증: `ai_client_calls`
- 대기열 거절 발생: `ai_session_rejected`
- Tool 실패율 급증: `ai_tool_runs`
- 법령 점검 마지막 성공이 하루 넘게 지남: `ai_law_refresh_last_success_timestamp` (#420 후)
