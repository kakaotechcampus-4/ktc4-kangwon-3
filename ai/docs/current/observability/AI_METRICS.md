# AI 서버 지표 목록

AI 서버가 `GET /metrics`로 내보내는 Prometheus 지표와 측정 위치를 정리한다.

## 1. 수집 방식

- Prometheus가 `/metrics`를 가져가는(pull) 방식이다. `/metrics`는 외부 공개 경로(`/api/ai/`) 밖에 있으므로 nginx로 공개하지 않는다.
- registry는 서버(lifespan)마다 하나이다. 서버 종료 시 등록표에서 sink를 해제하므로, 서버를 다시 기동하여도 이전 registry에 값이 누적되지 않는다.
- 측정하는 코드는 지표를 알지 못한다. 두 가지 통로로 기록만 남기고 `app/observability/metrics.py`가 이를 지표로 변환한다.
  - 세션 이벤트: `SessionManager.subscribe` → `SessionMetrics`
  - 측정 기록: `measurement_sinks`(`app/observability/measurements.py`) → `MeasurementMetrics`. 에이전트 실행 기록은 `agent_sinks` → `AgentMetrics`
- 현황 값(세션 수·자리·콜백 대기 수)은 수집(scrape)할 때마다 읽는다(`SessionSnapshotCollector`, `CallbackOutboxCollector`).
- sink 오류는 오류 로그(ERROR)만 기록하며, 기록을 남긴 쪽의 동작에는 영향을 주지 않는다.
- Counter·Histogram의 `_created`(최초 생성 시각) 시계열은 내보내지 않는다(`startup/lifespan.py`의 `disable_created_metrics()`).
- 값이 정해진 라벨 조합(세션 결말·단계, Tool 진행 알림, 콜백 결과·버린 사유·재시도, Tool 상태·실패 원인·판단 항목, 판매자 구역 자르기, 외부 API 결과, 캐시 조회, 정기 작업 결과, 법령 변경)은 처음부터 0으로 생성해 둔다. 처음 기록될 때 시계열이 생기면 `increase()`·`rate()`가 첫 기록을 세지 못하기 때문이다. 모델 이름·라우트·오류 코드처럼 값이 정해지지 않은 라벨은 미리 생성할 수 없으므로 대시보드 식으로 보완한다(4장).
- 서버에서는 모니터링 스택(`infra/monitoring`)의 Prometheus가 `be-ai-net`으로 `ai-server:8000/metrics`를 15초마다 수집한다(job `ai-app`).

## 2. 라벨 원칙

- 상품 ID·실행 ID·URL·검색어는 라벨에 포함하지 않는다. 실행마다 시계열이 늘어나고 키가 노출될 수 있기 때문이다.
- 운영·평가·테스트·BE 연동 더미는 실행 종류 `run_type`(production·evaluation·test·dummy)으로 구분한다. 개발용 샌드박스 진단은 `test`로 기록된다.
- 외부 API는 클라이언트 클래스가 아니라 서버(기관) 단위 `api`로 묶는다.

## 3. 지표 목록

Counter는 수집 시 이름 끝에 `_total`이 덧붙는다(`ai_client_calls` → `ai_client_calls_total`).

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
| `ai_sessions` | Gauge | `status` | 상태(accepted·running·awaiting_input·completed·failed)별 보관 중인 세션 수 |
| `ai_session_slots_used` | Gauge | `scope`(all·dev) | 차지한 자리 수 |
| `ai_session_slots_limit` | Gauge | `scope`(all·dev·running) | 자리 상한 |
| `ai_session_accepted` | Counter | `run_type` | 누적 접수 수 |
| `ai_session_rejected` | Counter | `reason` | 사유(`queue_full`: 대기열 가득 참·`conflict`: 실행 중 상품 충돌)별 누적 거절 수 |
| `ai_session_awaiting_replaced` | Counter | (없음) | 새 접수로 폐기한 답변 대기 세션 누적 수 |

- 소요 시간 구간: 1·5·10·30·60·120·300·600초(세션 최대 600초)
- `ai_session_failed`의 `stage`는 AI 내부 단계 이름을 그대로 기록하며, 내부 전용 단계 `pipeline`도 그대로 기록된다. 실패 콜백은 공개 단계만 전송하므로 이 경우 콜백의 단계는 null이다.
- 측정 위치: `app/sessions/` 상태 전이 이벤트

### 3.2 모델 호출 (에이전트)

| 지표 | 종류 | 라벨 | 내용 |
|---|---|---|---|
| `ai_agent_calls` | Counter | `component`, `model`, `outcome` | 호출 수. `outcome`은 `ok`, 실패 단계(`call`·`parsing`·`finalize`), 실패 단계를 알 수 없는 실패 `failed` 중 하나 |
| `ai_agent_tokens` | Counter | `component`, `model`, `kind` | 토큰 수. `kind`는 `input`·`cached`·`output`·`reasoning`이며, `cached`는 `input`에, `reasoning`은 `output`에 포함된다 |
| `ai_agent_cost_krw` | Counter | `component`, `model` | 예상 비용(원). 단가를 알 수 없는 모델은 제외 |
| `ai_agent_call_seconds` | Histogram | `component`, `model`, `outcome` | 호출 1건 소요 시간 |

- `component`는 기록 이름(`usage_name`)이 있으면 그 값, 없으면 에이전트 이름이다. 평가 호출은 `extraction-eval`처럼 운영과 다른 기록 이름을 사용한다.
- 소요 시간 구간: 0.5·1·2·5·10·20·30·60·120초
- 측정 위치: `BaseAgent` 호출 기록(`AgentRunMeta`)

### 3.3 외부 API

| 지표 | 종류 | 라벨 | 내용 |
|---|---|---|---|
| `ai_client_calls` | Counter | `api`, `result` | 서버·결과별 호출 수 |
| `ai_client_seconds` | Histogram | `api` | 호출 1건 소요 시간 |

- `api`: `law`(법제처, 별표 파일 포함)·`data_go_kr`(공공데이터포털, 관세청 세관장확인·식약처)·`customs_clip`(관세청 품목분류 사례 CLIP)·`safety_korea`·`radio`·`marketplace`(판매 사이트)·`backend`(BE 콜백)·`llm`(모델 게이트웨이)
- `result`

  | 값 | 의미 |
  |---|---|
  | `ok` | 2xx·3xx |
  | `http_error` | 4xx·5xx (예외 없이 상태 코드를 반환하는 BE 콜백 포함) |
  | `api_error` | HTTP 200이지만 본문이 오류여서 파싱에 실패 |
  | `timeout` | 시간 초과 |
  | `connect_error` | 연결 실패 등 전송 오류 |
  | `other` | 그 밖의 오류 (차단 URL·리다이렉트 초과 등) |

- 소요 시간 구간: 0.1·0.25·0.5·1·2·5·10·15·30·45·60초(클라이언트 제한 시간이 구간 경계)
- 측정 위치
  - `RequestClient.fetch_raw`·`fetch_parsed`: 조회 1회당 1건이다. 서버는 클래스 변수 `API`로 지정하며, 지정하지 않으면 테스트에서 검출된다.
  - `LlmClient` 전송 계층: HTTP 요청 1회당 1건이다. 에이전트를 거치지 않는 임베딩도 포함되며, SDK 재시도는 시도마다 기록된다.
    - 스트리밍 응답도 조각 수와 관계없이 1건이다. 시간은 본문을 모두 받고 연결을 닫을 때까지이며, 수신 중 끊기면 `timeout`·`connect_error`로 기록된다.
  - 판단 API(`/decisions`)는 SDK를 거치지 않으므로 `RequestClient`와 동일하게 조회 1회당 1건이다(`api="llm"`). 일시 오류 재시도는 한 조회 안에서 처리되므로 별도로 기록하지 않으며, 소요 시간에 재시도 대기가 포함된다.

### 3.4 콜백

| 지표 | 종류 | 라벨 | 내용 |
|---|---|---|---|
| `ai_callback_sent` | Counter | `event_type`, `result` | 이벤트별 최종 결과(delivered·dropped) |
| `ai_callback_dropped` | Counter | `reason` | 폐기 사유 |
| `ai_callback_retries` | Counter | `event_type` | 재시도 횟수 합 |
| `ai_callback_pending` | Gauge | (없음) | 전송을 시작하지 않은 이벤트 수. 전송 중·재시도 대기 중인 이벤트는 제외 |

- `event_type`: product_progress·product_awaiting_input·product_result·product_failed·law_changes(법령 변경 묶음)
- `reason`: `retry_exhausted`(재시도 초과)·`not_retryable`(4xx 등)·`shutdown`(종료 중)·`error`(예상하지 못한 오류)
- 폐기된 이벤트가 생기면 BE 화면에서 진단이 멈춘 것처럼 보인다.
  - `law_changes`는 다르다. 개정 알림이 전달되지 않고 다음 점검에서도 다시 검출되지 않으므로, 오류 로그의 값으로 재전송해야 한다([DB_CACHE.md](../storage/DB_CACHE.md)).
- 측정 위치: `CallbackOutbox`, 법령 변경은 `LawChangeNotifier` (HTTP 단위 결과는 `ai_client_calls{api="backend"}`)
- BE 도착 대조: `delivered`는 BE가 2xx로 응답한 이벤트 수이므로 BE의 `http_server_requests_seconds_count{uri=~"/internal/.*", status=~"2.."}`와 일치해야 한다. 대시보드 "콜백 도착" 패널에서 확인한다.
  - BE 배포 시 이전 BE가 마지막 수집 이후 받은 콜백은 BE 지표에 남지 않으므로 AI 쪽 값이 더 클 수 있다. 그 밖의 차이는 불일치 신호이다.

### 3.5 Tool

| 지표 | 종류 | 라벨 | 내용 |
|---|---|---|---|
| `ai_tool_runs` | Counter | `tool_name`, `status` | 실행 결과(success·partial·failed·skipped) |
| `ai_tool_run_seconds` | Histogram | `tool_name`, `status` | 실행 1건 소요 시간. 건너뛴 실행은 제외 |
| `ai_tool_errors` | Counter | `tool_name`, `error_type` | 실패 원인 |
| `ai_tool_findings` | Counter | `tool_name`, `determination` | 판단 항목 분포 |

- `error_type`은 예외 원인 체인을 확인하여 분류한다.
  - `model`: 모델 SDK 오류, 또는 실행 정보가 있는 에이전트 예외(출력 파싱 실패 등)
  - `client`: 근거 조회 실패(클라이언트·httpx 오류)
  - `other`: 그 밖의 오류. 예외 없이 FAILED를 반환한 경우 포함
- 소요 시간 구간: 1·2·5·10·20·30·60·120·300초
- 측정 위치: `ToolExecutor._execute_one`. 재실행 시 이전 판단을 유지하여 PARTIAL로 바꾼 결과가 아니라 Tool이 실제로 반환한 결과를 기록한다.

### 3.6 추출

| 지표 | 종류 | 라벨 | 내용 |
|---|---|---|---|
| `ai_extraction_seller_region` | Counter | `site`, `trimmed` | 지원하는 쇼핑몰의 글 블록별 판매자 구역 자르기 결과 |

- `site`: aliexpress·temu. `trimmed`: `"true"`·`"false"`
- 쇼핑몰 화면이 아닌 글(직접 입력한 설명 등)은 자르기 대상이 아니므로 세지 않는다.
- `trimmed="false"`가 증가하면 쇼핑몰 화면 변경을 의심한다.
- 측정 위치: `ExtractionAgent._build_messages` (후처리에서 다시 자르는 경우는 세지 않음)

### 3.7 캐시·DB

| 지표 | 종류 | 라벨 | 내용 |
|---|---|---|---|
| `ai_cache_lookups` | Counter | `cache`, `result` | Tool이 DB 캐시를 먼저 조회한 횟수 |
| `ai_law_refresh_runs` | Counter | `result` | 법령 점검 결과(ok·partial·failed) |
| `ai_law_refresh_last_success_timestamp` | Gauge | (없음) | 법령 점검이 실패 문서 없이 끝난 마지막 시각(Unix 초). 0이면 기동 이후 아직 없음 |
| `ai_law_changes` | Counter | `kind`, `tool` | 법령 점검에서 찾은 근거 문서 변경 수 |
| `ai_clip_ingest_runs` | Counter | `result` | CLIP 주간 적재 결과(ok·partial·failed·skipped) |
| `ai_clip_ingest_last_success_timestamp` | Gauge | (없음) | CLIP 주간 적재가 실패 사례 없이 끝난 마지막 시각(Unix 초). 0이면 기동 이후 아직 없음 |
| `ai_clip_ingest_cases` | Counter | `outcome` | 주간 적재에서 새로 저장(saved)·삭제(removed)·상세 조회 실패(failed)한 결정사례 수 |

- `cache`: 응답 캐시 `law.eflaw_search`·`law.text`·`admrul.search`·`admrul.text`·`customs.gw`, 결정사례 DB `customs.cases`
- `result`

  | 값 | 응답 캐시 | 결정사례 DB |
  |---|---|---|
  | `hit` | 만료 전 DB 값을 사용 | 가까운 사례를 찾아 CLIP을 호출하지 않음 |
  | `miss` | 값이 없거나 만료되어 외부 API로 받음 (실패는 세지 않으며 `ai_client_calls`에서 확인) | 가까운 사례가 없어 CLIP으로 조회 |
  | `stale` | 외부 API 실패·저장 조건 불일치로 만료된 DB 값을 사용 | (없음) |
  | `skipped` | DB 장애로 건너뛰고 외부 API로 받음 | DB·임베딩 실패로 CLIP으로 조회 |

- 법령 점검(스케줄러)이 본문을 확보하는 조회는 세지 않는다(`build_law_fetchers(measure=False)`).
- DB 없이 기동한 서버(DATABASE_URL 없음)는 세지 않는다.
- 측정 위치: `CachedFetcherBase.fetch_parsed`, `DatabaseFirstCaseSearch._near`
- 법령 점검은 문서 하나라도 실패하면 `partial`, 전부 실패하면 `failed`이다. 실패한 문서는 이전 법령 그대로 남으므로 `ok`일 때만 성공 시각을 갱신한다.
  - 측정 위치: `refresh_laws`. 정기 점검만 세며 기동 시에는 실행하지 않는다(실행 시각은 [DB_CACHE.md](../storage/DB_CACHE.md) 참고). CLI `law-refresh`는 별도 프로세스이므로 세지 않는다.
- 법령 변경 `kind`: `announced`(새 판 발표)·`applied`(근거로 선택하는 판이 바뀜)·`skipped`(시행일이 되었으나 이후 판이 있어 사용하지 않음, 사람의 확인 필요). `tool`은 그 문서를 근거로 사용하는 Tool이다.
  - 시행일 정기 점검을 놓치면 그날의 `applied`·`skipped`는 다음 날 점검에서도 검출되지 않는다. 그날 CLI `law-refresh`를 실행하면 변경 로그에 기록된다(별도 프로세스이므로 지표에는 반영되지 않음).
- CLIP 주간 적재는 상세 조회가 하나라도 실패하면 `partial`, 저장한 사례 없이 실패만 있으면 `failed`이며, 목록 수집·임베딩·저장 오류도 `failed`이다. hs_cases가 비어 있어(초기 적재 전) 건너뛰면 `skipped`이다.
  - 측정 위치: `run_scheduled_clip_ingest`. 정기 적재만 세며 기동 직후에는 실행하지 않는다(실행 시각은 [DB_CACHE.md](../storage/DB_CACHE.md) 참고). 직접 실행하는 `cli clip-ingest`는 세지 않는다.

### 3.8 HTTP 요청

| 지표 | 종류 | 라벨 | 내용 |
|---|---|---|---|
| `ai_http_requests` | Counter | `route`, `method`, `status` | 받은 요청 수. 409·422·429 비율 등 |
| `ai_http_request_seconds` | Histogram | `route`, `method` | 요청 1건 처리 시간(응답 헤더까지) |

- `route`: 라우트 템플릿(`/api/ai/v1/sandbox/diagnose/{product_id}`). 일치하는 라우트가 없는 요청은 `unmatched`
- 처리 중 예외로 끝난 요청은 `status="500"`으로 기록한다.
- Prometheus 수집 요청(`/metrics`)은 세지 않으며, 헬스 체크는 센다.
- 소요 시간 구간: 0.01·0.025·0.05·0.1·0.25·0.5·1·2.5·5·10초(진단은 세션에서 실행되고 접수는 즉시 응답)
- 측정 위치: `record_http_requests` 미들웨어(`app/observability/http_requests.py`)

## 4. 대시보드

Grafana 대시보드는 "AI 서버 개요"(`infra/monitoring/grafana/dashboards/ai-overview.json`)이다. 모델 호출·Tool·외부 API·콜백·캐시 지표에는 `run_type`이 없으므로 실행 종류 선택은 세션 지표에만 적용된다.

횟수·합계 패널은 `increase()` 대신 수집 한 번마다 증가한 양을 합산한다.

- 수집 한 번의 증가 `d` (`p` = `process_start_time_seconds`):
  ```
  (c - c offset 15s) >= 0 unless on(job, instance) p != p offset 15s
  or (c - last_over_time(c[5m] offset 15s)) >= 0 unless on(job, instance) (p offset 15s or p != last_over_time(p[5m] offset 15s))
  or c + 0
  ```
- 시계열: `sum by (...) (sum_over_time((d)[$__interval:15s]))`
- stat: 동일한 식에 `[$__range:15s]`, instant 쿼리를 사용한다. 비율은 이 합계끼리 나눈다.
- `increase()`를 사용하지 않는 이유: 구간 끝까지 외삽하므로 1회가 1.33처럼 나타나고, 1분 창이 겹쳐 한 번의 증가가 여러 칸에 표시되며, 처음 생긴 시계열의 첫 기록을 세지 못한다.
- 1줄: 평상시. 직전 수집과의 차이이며, 그 사이 재시작하였으면 건너뛴다.
- 2줄: 직전 수집이 실패하여 값이 비었을 때. 5분 이내 마지막 값과의 차이이다. 직전 수집은 성공하였으나 시계열만 없었던 경우(이 프로세스에서 새로 생성됨)나 마지막 수집 뒤 재시작한 경우는 건너뛴다.
- 3줄: 그 밖의 경우(처음 생긴 시계열, 재시작, 값 감소)는 현재 값을 그대로 센다. `+ 0`은 이름이 있는 시계열과 없는 시계열이 함께 나타날 때 발생하는 오류를 방지한다.
- `p`는 AI(`observability/metrics.py` `app_metrics()`의 `ProcessCollector`)와 BE(Spring 기본)가 내보낸다. 없으면 재시작을 감지하지 못한다(값이 감소한 재시작만 3줄로 센다).
- `15s`는 `ai-app`·`be-app` 수집 간격이다. 수집 간격을 바꾸면 식의 `15s`도 함께 바꾼다.

다음 경우에는 실제 값과 차이가 생긴다.

- 마지막 수집과 서버 종료 사이의 기록, 종료 시 재시도 중이던 콜백은 지표에 남지 않는다.
- 재시작 없이 수집이 5분 넘게 끊기면 그 시점의 누적값 전체를 센다.
- 재시작 뒤 시계열이 처음 생긴 수집의 바로 앞 수집이 실패하였고 이전 프로세스의 같은 시계열이 5분 이내에 있었으면, 이전 값만큼 적게 센다.

## 5. 알람 후보

- 콜백 폐기 발생: `ai_callback_dropped`
- 기관별 실패율 급증: `ai_client_calls`
- 대기열 거절 발생: `ai_session_rejected`
- Tool 실패율 급증: `ai_tool_runs`
- 법령 점검 마지막 성공 후 하루 초과: `time() - (ai_law_refresh_last_success_timestamp > 0) > 86400` (재기동 뒤 첫 점검 전에는 0)
- 법령 점검 실패: `increase(ai_law_refresh_runs_total{result=~"failed|partial"}[1d]) > 0` (재기동 뒤 점검이 계속 실패하면 성공 시각이 0에 머물러 위 식으로 검출되지 않음)
- 사람이 확인할 법령 변경: `increase(ai_law_changes_total{kind="skipped"}[1d]) > 0`
- CLIP 주간 적재 실패: `increase(ai_clip_ingest_runs_total{result=~"failed|partial"}[1d]) > 0` (기동 직후에는 실행하지 않으므로 성공 시각 기준 알람은 재기동 뒤 오탐이 발생함)
- CLIP 주간 적재 중단(스케줄러가 실행되지 않아 실패도 기록되지 않는 경우): `ai_clip_ingest_last_success_timestamp > 0 and time() - ai_clip_ingest_last_success_timestamp > 8 * 86400` (성공 시각 0은 재기동 직후이므로 제외)

---

변경 이력: [history/AI_METRICS.md](../../history/observability/AI_METRICS.md)
