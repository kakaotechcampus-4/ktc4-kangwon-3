# AI 서버 지표 목록

AI 서버가 `GET /metrics`로 내보내는 Prometheus 지표와 어디서 재는지를 정리한다. 지표 설계 논의는 #410.

## 1. 수집 방식

- Prometheus가 `/metrics`를 가져가는(pull) 방식. `/metrics`는 외부 공개 경로(`/api/ai/`) 밖이라 nginx로 열지 않음
- registry는 서버(lifespan)마다 하나. 서버 종료 때 등록표에서 sink를 해제해 다시 띄워도 옛 registry에 안 쌓임
- 재는 코드는 지표를 모름. 두 가지 통로로 기록만 남기고 `app/observability/metrics.py`가 지표로 바꿈
  - 세션 이벤트: `SessionManager.subscribe` → `SessionMetrics`
  - 측정 기록: `measurement_sinks`(`app/observability/measurements.py`) → `MeasurementMetrics`. 에이전트 실행 기록은 `agent_sinks` → `AgentMetrics`
- 현황 값(세션 수·자리·콜백 대기 수)은 수집(scrape) 때마다 읽음 (`SessionSnapshotCollector`, `CallbackOutboxCollector`)
- sink 오류는 오류 로그(ERROR)만 남기고 기록을 남긴 쪽 동작에 영향 없음
- Counter·Histogram의 `_created`(처음 만든 시각) 시계열은 내보내지 않음 (`startup/lifespan.py`의 `disable_created_metrics()`)
- 값이 정해진 라벨 조합(세션 결말·단계, Tool 진행 알림, 콜백 결과·버린 사유·재시도, Tool 상태·실패 원인·판단 항목, 판매자 구역 자르기, 외부 API 결과, 캐시 조회, 정기 작업 결과, 법령 변경)은 처음부터 0으로 만들어 둠. 처음 기록될 때 생기면 `increase()`·`rate()`가 첫 기록을 못 셈. 모델 이름·라우트·오류 코드처럼 값이 정해지지 않은 라벨은 미리 못 만듦 → 대시보드 식으로 셈 (아래)
- 서버에서는 모니터링 스택(`infra/monitoring`)의 Prometheus가 `be-ai-net`으로 `ai-server:8000/metrics`를 15초마다 수집 (job `ai-app`)
- Grafana 대시보드는 "AI 서버 개요" (`infra/monitoring/grafana/dashboards/ai-overview.json`). 모델 호출·Tool·외부 API·콜백·캐시 지표엔 `run_type`이 없어 실행 종류 선택이 세션 지표에만 먹음
- 대시보드 횟수·합계 패널은 `increase()` 대신 수집 한 번마다 늘어난 만큼을 더함 (#609)
  - 수집 한 번의 증가 `d` (`p` = `process_start_time_seconds`):
    ```
    (c - c offset 15s) >= 0 unless on(job, instance) p != p offset 15s
    or (c - last_over_time(c[5m] offset 15s)) >= 0 unless on(job, instance) (p offset 15s or p != last_over_time(p[5m] offset 15s))
    or c + 0
    ```
  - 시계열: `sum by (...) (sum_over_time((d)[$__interval:15s]))`
  - stat: 같은 식에 `[$__range:15s]`, instant 쿼리. 비율은 이 합끼리 나눔
  - `increase()`를 안 쓰는 이유: 구간 끝까지 늘려 잡아 1번이 1.33처럼 나옴, 1분 창이 겹쳐 한 번이 여러 칸에 찍힘, 처음 생긴 시계열의 첫 기록을 못 셈
  - 1줄: 평소. 직전 수집과의 차이. 그 사이 재시작했으면 건너뜀
  - 2줄: 직전 수집이 실패해 비었을 때. 5분 안 마지막 값과의 차이. 직전 수집은 됐는데 시계열만 없었으면(이 프로세스에서 새로 생김) 또는 마지막 수집 뒤 재시작했으면 건너뜀
  - 3줄: 그 밖(처음 생긴 시계열, 재시작, 값이 줄어듦)은 지금 값을 그대로 셈. `+ 0`: 이름 있는·없는 시계열이 섞여 나는 오류 방지
  - `p`는 AI(`observability/metrics.py` `app_metrics()`의 `ProcessCollector`)와 BE(Spring 기본)가 내보냄. 없으면 재시작을 못 알아봄 (값이 줄어든 재시작만 3줄로 셈)
  - `15s`는 `ai-app`·`be-app` 수집 간격. 수집 간격을 바꾸면 식의 `15s`도 같이 바꿈
  - 한계: 마지막 수집과 서버 종료 사이의 기록, 종료 때 재시도 중이던 콜백은 지표에 안 남음
  - 한계: 재시작 없이 수집이 5분 넘게 끊기면 그때 누적값 전체를 셈
  - 한계: 재시작 뒤 시계열이 처음 생긴 수집 바로 앞 수집이 실패했고 옛 프로세스의 같은 시계열이 5분 안에 있었으면, 옛 값만큼 덜 셈
  - 식이 길어 나중에 Prometheus 기록 규칙(recording rule)으로 줄이는 방안 있음

## 2. 라벨 원칙

- 상품 ID·실행 ID·URL·검색어는 라벨에 넣지 않음. 실행마다 시계열이 늘고 키가 노출될 수 있음
- 운영·평가·테스트·BE 연동 더미는 실행 종류 `run_type`(production·evaluation·test·dummy)으로 나눔
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
| `ai_session_awaiting_replaced` | Counter | (없음) | 새 접수로 버린 답변 대기 세션 누적 수 (#451) |

- 소요 시간 구간: 1·5·10·30·60·120·300·600초 (세션 최대 600초)
- `ai_session_failed`의 `stage`: AI 내부 단계 그대로. 내부 전용 단계 `pipeline`도 그대로 남음 (실패 콜백은 공개 단계만 보내 이때 null)
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

- `api`: `law`(법제처, 별표 파일 포함)·`data_go_kr`(공공데이터포털, 관세청 세관장확인·식약처)·`customs_clip`(관세청 품목분류 사례 CLIP)·`safety_korea`·`radio`·`marketplace`(판매 사이트)·`backend`(BE 콜백)·`llm`(모델 게이트웨이)
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
  - 판단 API(`/decisions`)는 SDK를 거치지 않아 `RequestClient`와 같이 조회 1번당 1건 (`api="llm"`). 일시 오류 재시도는 한 조회 안에서 끝나 따로 기록하지 않고, 시간에 재시도 대기가 포함됨

### 3.4 콜백

| 지표 | 종류 | 라벨 | 내용 |
|---|---|---|---|
| `ai_callback_sent` | Counter | `event_type`, `result` | 이벤트별 최종 결과(delivered·dropped) |
| `ai_callback_dropped` | Counter | `reason` | 버린 사유 |
| `ai_callback_retries` | Counter | `event_type` | 재시도 횟수 합 |
| `ai_callback_pending` | Gauge | (없음) | 보내기 시작하지 않은 이벤트 수. 보내는 중·재시도 대기 중은 빠짐 |

- `event_type`: product_progress·product_awaiting_input·product_result·product_failed·law_changes(법령 변경 묶음)
- `reason`: `retry_exhausted`(재시도 초과)·`not_retryable`(4xx 등)·`shutdown`(종료 중)·`error`(예상 못 한 오류)
- 버린 이벤트가 생기면 BE 화면에서 진단이 멈춘 것처럼 보임
  - `law_changes`는 다름: 개정 알림이 안 가고 다음 점검에서도 다시 안 잡힘. 오류 로그의 값으로 재전송 필요 ([DB_CACHE.md](DB_CACHE.md))
- 재는 곳: `CallbackOutbox`, 법령 변경은 `LawChangeNotifier` (HTTP 단위 결과는 `ai_client_calls{api="backend"}`)
- BE 도착 맞춰 보기: `delivered`는 BE가 2xx로 응답한 이벤트 수라 BE `http_server_requests_seconds_count{uri=~"/internal/.*", status=~"2.."}`와 같아야 함. 대시보드 "콜백 도착" 패널
  - BE 배포 때 옛 BE가 마지막 수집 뒤 받은 콜백은 지표에 안 남음 → AI 쪽이 많을 수 있음. 그 밖의 차이는 어긋남 신호

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
- 지금 서버 앱은 `ToolExecutor`를 만들지 않음(평가 실행에서만 사용). 파이프라인 연결(#320) 전까지 서버 `/metrics`에서는 0
- 재는 곳: `ToolExecutor._execute_one`. 재실행 때 이전 판단을 살려 PARTIAL로 바꾼 결과가 아니라 Tool이 실제로 낸 결과를 기록

### 3.6 추출

| 지표 | 종류 | 라벨 | 내용 |
|---|---|---|---|
| `ai_extraction_seller_region` | Counter | `site`, `trimmed` | 아는 쇼핑몰 글 블록별 판매자 구역 자르기 결과 |

- `site`: aliexpress·temu. `trimmed`: `"true"`·`"false"`
- 쇼핑몰 화면이 아닌 글(직접 붙여 넣은 설명 등)은 자를 대상이 아니라 세지 않음
- `trimmed="false"`가 늘면 쇼핑몰 화면 변경 의심
- Tool과 같은 이유로 파이프라인 연결(#320) 전까지 서버 `/metrics`에서는 0 (`ExtractionAgent`는 평가 실행에서만 사용)
- 재는 곳: `ExtractionAgent._build_messages` (후처리에서 다시 자르는 건 세지 않음)

### 3.7 캐시·DB

| 지표 | 종류 | 라벨 | 내용 |
|---|---|---|---|
| `ai_cache_lookups` | Counter | `cache`, `result` | Tool이 DB 캐시를 먼저 본 조회 수 |
| `ai_law_refresh_runs` | Counter | `result` | 법령 점검 결과(ok·partial·failed) |
| `ai_law_refresh_last_success_timestamp` | Gauge | (없음) | 법령 점검이 실패 문서 없이 끝난 마지막 시각(Unix 초). 0이면 기동 뒤 아직 없음 |
| `ai_law_changes` | Counter | `kind`, `tool` | 법령 점검에서 찾은 근거 문서 변경 수 |
| `ai_clip_ingest_runs` | Counter | `result` | CLIP 주간 적재 결과(ok·partial·failed·skipped) |
| `ai_clip_ingest_last_success_timestamp` | Gauge | (없음) | CLIP 주간 적재가 실패 사례 없이 끝난 마지막 시각(Unix 초). 0이면 기동 뒤 아직 없음 |
| `ai_clip_ingest_cases` | Counter | `outcome` | 주간 적재에서 새로 저장(saved)·삭제(removed)·상세 실패(failed)한 결정사례 수 |

- `cache`: 응답 캐시 `law.eflaw_search`·`law.text`·`admrul.search`·`admrul.text`·`customs.gw`, 결정사례 DB `customs.cases`
- `result`

  | 값 | 응답 캐시 | 결정사례 DB |
  |---|---|---|
  | `hit` | 만료 전 DB 값을 씀 | 가까운 사례를 찾아 CLIP을 안 부름 |
  | `miss` | 없거나 만료돼 외부 API로 받음 (실패는 안 셈, `ai_client_calls`에서 봄) | 가까운 사례가 없어 CLIP으로 찾음 |
  | `stale` | 외부 API 실패·저장 조건 불일치로 만료된 DB 값을 씀 | (없음) |
  | `skipped` | DB 장애로 건너뛰고 외부 API로 받음 | DB·임베딩 실패로 CLIP으로 찾음 |

- 법령 점검(스케줄러)이 본문을 확보하는 조회는 세지 않음 (`build_law_fetchers(measure=False)`)
- DB 없이 뜬 서버(DATABASE_URL 없음)는 세지 않음
- 재는 곳: `CachedFetcherBase.fetch_parsed`, `DatabaseFirstCaseSearch._near`
- 법령 점검: 문서 하나라도 실패하면 `partial`, 전부 실패하면 `failed`. 실패한 문서는 법령이 낡은 채 남아 `ok`만 성공 시각을 바꿈
  - 재는 곳: `refresh_laws` (매일 00:05 KST, 기동 때는 안 돎). CLI `law-refresh`는 별도 프로세스라 안 세짐
- 법령 변경 `kind`: `announced`(새 판 발표)·`applied`(근거로 고르는 판이 바뀜)·`skipped`(시행일이 됐지만 나중 판이 있어 안 씀, 사람이 확인할 것). `tool`은 그 문서를 근거로 쓰는 Tool
  - 시행일 00:05 점검을 놓치면 그날의 `applied`·`skipped`는 다음 날 점검에서도 안 나옴. 그날 CLI `law-refresh`를 돌리면 변경 로그에 남음 (별도 프로세스라 지표로는 안 세짐)
- CLIP 주간 적재: 상세 하나라도 실패하면 `partial`, 저장한 사례 없이 실패만 있으면 `failed`, 목록 수집·임베딩·저장 오류도 `failed`. hs_cases가 비어(초기 적재 전) 건너뛰면 `skipped`
  - 재는 곳: `run_scheduled_clip_ingest` (매주 일요일 03:00 KST, 기동 직후엔 돌지 않음). 직접 돌리는 `cli clip-ingest`는 세지 않음

### 3.8 HTTP 요청

| 지표 | 종류 | 라벨 | 내용 |
|---|---|---|---|
| `ai_http_requests` | Counter | `route`, `method`, `status` | 받은 요청 수. 409·422·429 비율 등 |
| `ai_http_request_seconds` | Histogram | `route`, `method` | 요청 1건 처리 시간(응답 헤더까지) |

- `route`: 라우트 템플릿(`/api/ai/v1/sandbox/diagnose/{product_id}`). 맞는 라우트가 없는 요청은 `unmatched`
- 처리 중 예외로 끝난 요청은 `status="500"`
- Prometheus 수집 요청(`/metrics`)은 세지 않음. 헬스 체크는 셈
- 구간: 0.01·0.025·0.05·0.1·0.25·0.5·1·2.5·5·10초 (진단은 세션에서 돌고 접수는 바로 응답)
- 재는 곳: `record_http_requests` 미들웨어 (`app/observability/http_requests.py`)

## 4. 추가 예정

| 지표 | 시점 | 비고 |
|---|---|---|
| `ai_build_info` | 버전 규칙 결정 후 | `version`, `model_profile`. 지금 배포는 서버에서 소스로 빌드해 앱 안에 버전 정보가 없음 |
| `ai_result_status`, `ai_result_incomplete` | 진단서 변환(#408)·파이프라인 연결(#320) 후 | `reason` 라벨(#408 `DecisionReason`)로 재확인 필요가 미완료·Tool 실패·정보 부족·지원 분야 밖 중 어디서 오는지 구분 |
| `ai_pipeline_end`, `ai_verification_results`, `ai_pipeline_retry_rounds`, `ai_question_rounds`, `ai_questions_asked`, `ai_diagnosis_cost_krw` | 파이프라인 연결(#320) 후 | |
| `ai_tool_runs`에 `run_type` 추가 | 파이프라인 연결(#320) 후 | `ToolExecutor`가 실행 컨텍스트를 받게 되면. `ai_session_tool_progress`는 이때 합침 |

## 5. 알람 후보

- 콜백 버림 발생: `ai_callback_dropped`
- 기관별 실패율 급증: `ai_client_calls`
- 대기열 거절 발생: `ai_session_rejected`
- Tool 실패율 급증: `ai_tool_runs`
- 법령 점검 마지막 성공이 하루 넘게 지남: `time() - (ai_law_refresh_last_success_timestamp > 0) > 86400` (재기동 뒤 첫 점검 전엔 0)
- 법령 점검이 실패로 끝남: `increase(ai_law_refresh_runs_total{result=~"failed|partial"}[1d]) > 0` (재기동 뒤 점검이 계속 실패하면 성공 시각이 0에 머물러 위 식으로 안 잡힘)
- 사람이 확인할 법령 변경: `increase(ai_law_changes_total{kind="skipped"}[1d]) > 0`
- CLIP 주간 적재가 실패로 끝남: `increase(ai_clip_ingest_runs_total{result=~"failed|partial"}[1d]) > 0` (기동 직후엔 돌지 않아 성공 시각 기준 알람은 재기동 뒤 오탐)
- CLIP 주간 적재가 멈춤 (스케줄러가 돌지 않아 실패도 안 남는 경우): `ai_clip_ingest_last_success_timestamp > 0 and time() - ai_clip_ingest_last_success_timestamp > 8 * 86400` (성공 시각 0은 재기동 직후라 제외)
