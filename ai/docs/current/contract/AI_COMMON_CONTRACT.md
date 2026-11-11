# AI 공통 계약

AI 서버의 실행 컨텍스트, 프롬프트·가드레일, 에이전트 공통 동작, 오류, BE와의 요청·콜백·공개 진단서 형식을 정의한다. 코드가 기준이며, 이 문서는 현재 계약만 기술한다.

## 1. 범위

| 주제 | 이 문서 | 세부 문서 |
|---|---|---|
| 실행 컨텍스트, 프롬프트·가드레일, 에이전트 공통 | 2-4장 | |
| 사용량·실행 기록 | 5장 (요약) | [AI_METRICS.md](../observability/AI_METRICS.md), [AI_LOGGING.md](../observability/AI_LOGGING.md) |
| 오류와 응답 코드 | 6장 | |
| BE → AI 요청, AI → BE 콜백, 공개 진단서 | 7-9장 | |
| 종료 사유 | 10장 | |
| 운영 로그 레벨·기록 금지 항목 | | [AI_LOGGING.md](../observability/AI_LOGGING.md) |
| 세션 보관·재시작 복원 | | [AI_SESSION_ARCHIVE.md](../storage/AI_SESSION_ARCHIVE.md) |
| 법령 변경 전송 | | [DB_CACHE.md](../storage/DB_CACHE.md) |
| 로컬 진단 기록 | | [AI_TRACE.md](../observability/AI_TRACE.md) |
| 규제 Tool 공용 동작 | | [TOOL_COMMON.md](../tools/TOOL_COMMON.md) |

내부 Python 필드명은 snake_case를 사용한다. BE와 주고받는 DTO는 `ApiModel`(`app/schemas/base.py`)의 camelCase alias를 사용하며, 내부 `StrictModel`·모델 출력 스키마에는 alias를 적용하지 않는다.

## 2. 실행 컨텍스트

위치: `app/domain/context.py` (`ExecutionContext`, `RunType`, `PipelineStage`)

| 필드 | 필수 여부 | 규칙 |
|---|---|---|
| `run_id` | 필수 | 진입점이 생성. 하위 구성 요소에서 재생성하지 않음 |
| `product_id` | 필수 | 상품 요청 ID. 평가에서는 고정 입력의 상품 ID |
| `run_type` | 필수 | `production`, `evaluation`, `test`, `dummy` |
| `diagnosis_id` | 선택 | 운영 진단은 BE의 진단서 ID. 단독 평가·테스트는 `None` |
| `retry_round` | 기본 0 | 0 이상의 정수 |

- 컨텍스트는 변경할 수 없는 값이다(`frozen`). `ExecutionContext.start()`가 새 `run_id`와 회차 0으로 생성한다.
- 재진단은 `run_id`를 새로 발급하고 `diagnosis_id`·`product_id`·`run_type`은 유지한다. 콜백의 `sequence`도 실행마다 1부터 다시 센다.

### 2.1 생성 위치

| 실행 | 생성 위치 | `run_type` |
|---|---|---|
| 진단 접수 (`/diagnose/content`) | 세션 관리자 (`sessions/manager/manager.py`) | `production` |
| 재진단 (`/diagnose/resume`) | 세션 관리자 `resume` | `production` |
| 샌드박스 (`/sandbox/diagnose`) | 세션 관리자 `submit_dev` | `test` |
| 더미 (`/dummy/diagnose/*`) | 세션 관리자 | `dummy` |
| 진단 기록 실행 | `diagnosis/trace_cli.py` | `evaluation` |

### 2.2 전달 범위

컨텍스트는 세션, 진단 함수(`DiagnosisJob`), 입력 가드, 로그 문맥(`observability/logs.py`의 `run_log_context`)까지 전달한다. 파이프라인(`CompliancePipeline.run`)과 에이전트·Tool에는 전달하지 않으며, Tool 재실행 회차는 파이프라인이 별도로 센다.

`run_type`별로 실행하는 진단 함수가 다르다. `production`·`test`는 입력 가드를 거치는 실제 파이프라인을, `dummy`는 BE 연동 확인용 케이스 더미를 실행한다(`startup/lifespan.py`).

## 3. 프롬프트·가드레일

### 3.1 프롬프트 로더

위치: `app/prompts/__init__.py` (`PromptName`, `PromptSnapshot`, `get_prompt`, `load_prompt`, `clear_prompt_cache`, `normalize_newlines`, `fingerprint`)

- 프롬프트는 `PromptName`으로 등록한 이름으로만 읽는다. `load_prompt`에 등록되지 않은 이름을 입력하면 `ValueError`가 발생한다.
- 파일은 `agents/<이름>/prompt.md`를 먼저 찾고, 없으면 `prompts/<이름>.md`를 찾는다. 두 곳에 모두 있으면 오류다.
- 한 번 읽은 프롬프트는 프로세스 수명 동안 캐시한다. 캐시를 비우는 함수(`clear_prompt_cache`)는 개발·평가용이다.
- 모델에 전달하는 본문과 기록하는 지문(SHA-256)은 같은 스냅샷에서 가져온다. 줄바꿈은 LF로 정규화한 뒤 지문을 계산한다.
- 평가 기록의 `prompt_sha256`은 에이전트가 모델에 보내는 시스템 프롬프트(`Agent.system_prompt()`, 가드레일 포함) 기준이다. 선택 정답표의 지문 기준은 [SELECTION_EVAL.md](../eval/SELECTION_EVAL.md)에서 설명한다.

### 3.2 가드레일

입력 가드를 통과한 입력 속 지시문을 에이전트가 수행하지 않도록 하는 2차 방어다. 위치: `app/agents/base/guardrail.py`

- 가드레일을 사용하는 에이전트는 클래스에 `uses_guardrail = True`를 지정한다. 현재 추출, 선택, 표시·광고 검토 3곳이다. 규제 Tool 5개의 `ToolStep`에는 적용하지 않는다.
- 시스템 프롬프트는 프롬프트 본문, 공통 가드레일, 에이전트별 가드레일을 빈 줄로 연결한 것이다. 지문도 연결한 본문 기준이다.

| 문서 | 위치 |
|---|---|
| 공통 | `app/agents/base/guardrail.md` |
| 에이전트별 (에이전트 패키지) | `app/agents/<이름>/guardrail.md` |
| 에이전트별 (Tool 안 단계) | `app/tools/<Tool>/<단계>.guardrail.md` |
| 에이전트별 (Tool에 프롬프트 하나) | `app/tools/<Tool>/guardrail.md` |

- 가드레일을 지정하였는데 공통·에이전트별 문서 중 하나라도 없으면 에이전트 생성(서버 기동) 시 `FileNotFoundError`가 발생한다.
- 가드레일을 지정하지 않았는데 에이전트별 문서가 있으면 생성 시 WARNING을 기록하고 적용하지 않는다.
- 판단 모델만 사용하는 에이전트(판단 선택, 입력 가드)는 시스템 프롬프트가 없으므로 해당하지 않는다.

## 4. 에이전트 공통

### 4.1 BaseAgent

위치: `app/agents/base/` (`agent`, `errors`, `meta`, `parsing`, `protocols`, `usage_log`)

| BaseAgent | 각 에이전트 |
|---|---|
| 프롬프트·가드레일 적용 | 사용할 프롬프트·출력 스키마 (`prompt_name`, `output_schema`) |
| 구조화 모델 호출, 원본 응답(`include_raw`)에서 사용량 수집 | 입력 메시지 구성 (`_build_messages`) |
| 파싱 확인, 실패 단계 구분, 예외 변환 | 사용량 기록 대상 ID (`_subject_id`) |
| 사용량·실행 기록을 sink로 전달 | 결과 후처리 (`_finalize`), 호출 생략 (`_skip`) |
| 판단 모델(`/decisions`) 호출 | 실패 문구 (`_failure_message`) |

- 공개 메서드는 `run(input)`과 `run_with_meta(input)`이다. 후자는 결과와 실행 정보(`AgentRunMeta`)를 함께 반환한다.
- 모델 없이 시스템 프롬프트를 구하는 클래스 메서드 `system_prompt()`가 있다.
- 에이전트별 예외는 `AgentError`를 상속하며, 실행 정보(`meta`)를 보존한다.

### 4.2 실패 단계

| 단계 (`ModelFailurePhase`) | 경우 |
|---|---|
| `CALL` | 모델 호출 예외. 응답을 받지 못함 |
| `PARSING` | 응답의 파싱 오류, 파싱 결과 누락, 출력 길이 초과, 콘텐츠 필터 |
| `FINALIZE` | 에이전트의 결과 후처리(`_finalize`) 실패 |

- 사용량은 호출당 한 번 기록한다. 성공 기록은 후처리까지 끝난 뒤 남긴다.
- 실패한 호출도 원본 응답에서 사용량을 확보할 수 있으면 보존한다. 사용량을 확보하지 못한 것은 0토큰과 구분한다.
- 원인 예외는 `raise ... from`으로 연결하며, 공개 문구에 원인 예외의 내용을 포함하지 않는다.

### 4.3 Tool 안의 모델 호출

규제 Tool 5개의 모델 호출은 `ToolStep`(`app/tools/base/steps.py`)이 BaseAgent를 상속하여 수행한다. 입력은 `ToolStepInput(payload, subject_id)`이다. 표시·광고 Tool은 자체 `AdvertisingReviewer`를 사용한다. 각 Tool의 사용량 이름은 해당 Tool 문서에 기술한다.

### 4.4 판단 모델 호출

BaseAgent는 구조화 출력 모델 외에 판단 모델(`/decisions`) 호출 경로(`_call_decision`)를 가진다. `AGENT_DECISION_PROFILES`에 등록된 에이전트(판단 선택, 입력 가드)만 사용한다.

### 4.5 모델 생성과 프로필

- 모델은 `build_agent_model(name)`·`build_tool_model(name)`(`app/clients/llm`)로 생성한다. 테스트에서는 모델을 직접 주입할 수 있다.
- 프로필은 `app/config/profiles.py`의 `AGENT_PROFILES`, `TOOL_PROFILES`, `AGENT_DECISION_PROFILES`에서 정한다. 환경변수 `MODEL_PROFILE_OVERRIDES`로는 `AGENT_PROFILES`(`agent.<이름>`)와 `TOOL_PROFILES`(`tool.<이름>`)만 바꿀 수 있으며, 그 밖의 대상을 넣으면 `ConfigError`로 기동에 실패한다. `AGENT_DECISION_PROFILES`는 코드에서만 바꾼다.
- 검증 에이전트는 모델을 자동 생성하지 않는다(`creates_default_model = False`). 규칙 검사만 하는 `verify_rules()`는 모델을 호출하지 않는다.
- 채팅 모델 호출의 제한 시간은 45초, SDK 재시도는 1회다(`app/clients/llm/client.py`).

## 5. 사용량·실행 기록

- 에이전트 실행이 끝나면 실행 정보가 sink 등록표(`app/observability/agent_sinks.py`)로 전달된다. 기본 sink는 사용량 JSONL 기록, 호출 로그 한 줄, 실행 요약, 지표(서버에서만)다.
- sink 오류는 ERROR로 기록하고 판정 결과를 바꾸지 않는다.
- 사용량 JSONL은 `app/observability/usage.py`의 `record()`가 한 줄씩 기록하며, 쓰기 실패는 무시한다. 파일이 상한(10MB)을 넘으면 `.1`부터 한 칸씩 밀고 새 파일로 시작한다.
- 사용량 값(`CallUsage`)은 원본 응답(`from_response`), 콜백 핸들러(`from_handler`), 완료 응답(`from_completion`), 판단 모델 응답(`from_decision`)에서 수집한다.

세부 필드와 지표는 [AI_METRICS.md](../observability/AI_METRICS.md), 로그는 [AI_LOGGING.md](../observability/AI_LOGGING.md)에서 설명한다.

## 6. 오류

### 6.1 예외 계층

위치: `app/domain/errors.py`

- 공통 뿌리는 `AIError`다. `AIServiceError`, `AgentError`, `ClientError`(`clients/errors.py`), `ConfigError`(`config/errors.py`), 세션 예외(`sessions/errors.py`) 등이 상속한다.
- `AgentError`와 `AIServiceError`는 형제 관계이며, 둘 다 `RuntimeError`도 상속한다.
- `AIServiceError(response_code, stage, retryable, partial_result, data)`. `retryable`은 재시도 가능 여부이며 즉시 재시도하라는 뜻이 아니다. `partial_result`는 내부 부분 결과이며 공개 응답으로 자동 변환하지 않는다. `data`는 공개 가능한 추가 정보다(예: 409의 `conflictProductIds`).

### 6.2 응답 코드

정확한 목록·문구는 `AIResponseCode`가 기준이다.

| 코드 | HTTP | 사용처 |
|---|---|---|
| `AI_INVALID_REQUEST` | 422 | 요청 형식 오류, 이번 회차 질문에 모두 답하지 않음 |
| `AI_UNKNOWN_QUESTION_KEY` | 400 | 질문하지 않은 키의 답변. `data.questionKeys`에 해당 키 |
| `AI_UNAUTHORIZED` | 401 | 내부 토큰·개발용 키 없음 또는 불일치 |
| `AI_NOT_FOUND` / `AI_SESSION_NOT_FOUND` | 404 | 경로 없음 / 세션 없음 |
| `AI_METHOD_NOT_ALLOWED` | 405 | |
| `AI_SESSION_CONFLICT` | 409 | 접수·실행 중인 상품 포함. `data.conflictProductIds` |
| `AI_RESUME_CONFLICT` | 409 | 기다리는 질문이 아닌 답변, 중복 답변, 버린 실행의 답변 |
| `AI_QUEUE_FULL` | 429 | 진단 대기열 초과 |
| `AI_INTERNAL_ERROR` | 500 | 처리하지 못한 예외 |
| `AI_NOT_IMPLEMENTED` | 501 | |
| `AI_PIPELINE_ERROR` | 500 | 실패 콜백 (6.4) |
| `AI_TIMEOUT` | 500 | 실패 콜백 (6.4) |
| `AI_UNSUPPORTED_SITE` | 500 | 실패 콜백 (6.4) |
| `AI_SOURCE_FETCH_FAILED` | 500 | 실패 콜백 (6.4) |
| `AI_EMPTY_SOURCE` | 500 | 실패 콜백 (6.4) |

### 6.3 API 경계

위치: `app/routers/exception_handlers.py`

| 내부 | 외부 |
|---|---|
| `response_code.code`, `message`, `http_status` | `ApiResponse.code`, `message`, HTTP 상태 |
| 원인 예외, stack trace | 비공개 |
| `partial_result` | 비공개 |
| `data` | `ApiResponse.data` |

응답은 `ApiResponse{code, message, details, data}` 형식이다. `details`에는 요청 필드 오류만 포함한다.

### 6.4 실패 콜백

진단 중 실패는 `product_failed` 콜백(8장)으로 전달한다.

| 상황 | 코드 | `retryable` | `reviewFlag` |
|---|---|---|---|
| 추출 모델·이미지 분류가 429·5xx·연결 실패로 응답을 받지 못하였거나 출력이 길이 한도에 도달 | `AI_PIPELINE_ERROR` | true | |
| 검증 모델 검토에 실패하고 규칙 검사 결과도 없음 | `AI_PIPELINE_ERROR` | true | |
| 입력 가드 차단 | `AI_PIPELINE_ERROR` | false | `r1` |
| 공개 진단서 변환 실패 | `AI_PIPELINE_ERROR` | false | |
| 그 밖에 처리하지 못한 예외 | `AI_PIPELINE_ERROR` | false | |
| 진단 시간 초과(600초), 재시작으로 끊긴 실행 | `AI_TIMEOUT` | true | |
| 수집할 수 없는 판매 사이트 URL | `AI_UNSUPPORTED_SITE` | false | |
| 상품 페이지 수집 실패 | `AI_SOURCE_FETCH_FAILED` | true | |
| 수집하였으나 글·이미지가 없음 | `AI_EMPTY_SOURCE` | false | |

- 검증 모델 검토에 실패하였으나 규칙 검사 결과가 있으면 실패하지 않고 규칙 결과로 진행하며, 통과는 `REVISION_REQUIRED`로 낮춘다(`app/diagnosis/stages.py`).
- 입력 가드는 차단 판정이면 추출 단계 알림을 보낸 뒤 5-10초 후 실패한다. 의심 판정은 경고 로그만 기록하고, 가드 자체가 실패하면 통과시킨다(`app/diagnosis/guard.py`).
- `reviewFlag`는 BE 전용 검토 표시이며 FE로 전달하지 않는다.

### 6.5 재시도 책임

- 같은 오류를 SDK, 에이전트, Tool, 파이프라인에서 각각 재시도하지 않는다. 모델 호출 재시도는 클라이언트 계층에서만 한다. 채팅 모델은 SDK 설정(4.5), 판단 모델은 판단 클라이언트(`app/clients/llm/decision/base.py`)가 연결 실패와 429·502·503 응답에 한하여 재시도한다.
- 검증이 추가 Tool 실행을 요구하면 파이프라인이 Tool을 재실행한다. 이는 기술적 재시도가 아니라 업무적 재실행이다.
- Tool 실행기(`app/pipeline/tool_executor.py`)는 Tool에서 발생한 예외를 해당 Tool 결과의 `FAILED`로 기록한다.
- 공공 API 클라이언트(법제처, 공공데이터포털)는 HTTP 오류를 `httpx.HTTPStatusError`로 발생시킨다. 인증 키는 메시지에서 마스킹한다.

## 7. BE → AI 요청

위치: `app/schemas/request.py`, `app/routers/diagnose.py`. 경로 앞부분은 `/api/ai/v1/diagnose`이며, 내부 토큰(`X-Internal-Token`)이 필요하다.

| 경로 | 요청 | 응답 |
|---|---|---|
| `POST /content` | `diagnosisId`, `products[]`(1-10개, `productId` 중복 불가): `productId`, `textBlocks[]`, `imageUrls[]`, `sourceUrl` | 202. 결과는 상품별 콜백 |
| `POST /resume` | `diagnosisId`, `productId`, `runId`(질문으로 끝난 실행), `questionRound`(1-2), `answers[]`: `questionKey`(50자 이하), `answerText`(500자 이하) | 202. 새 `runId`로 다시 실행 |

### 7.1 상품 입력

- 텍스트(`textBlocks`), 이미지(`imageUrls`), URL(`sourceUrl`) 중 하나 이상 있으면 접수한다.
- 텍스트 없이 URL이 있으면 이미지가 함께 와도 판매 사이트에서 수집한 뒤 추출한다(`app/pipeline/extraction_step.py`). 함께 온 이미지를 추출에 포함할지는 사이트 설정(`uploaded_images`, `app/pipeline/url_source.py`)으로 정한다.
- 수집에 실패하면 함께 온 이미지가 있어도 진단을 계속하지 않는다. 자동 재시도는 없고 실패 콜백의 `retryable`로 재시도 가능 여부만 알린다(6.4).
- 이미지는 URL로 받으며, base64 data URI도 받는다.

### 7.2 재진단

- 원래 입력, 추출 결과, 이전 질문과 답변은 AI 세션이 보관한다. BE는 재진단 때 ID와 이번 회차 답변만 보낸다.
- 재진단 요청은 이번 회차 질문에 모두 답해야 한다. 일부만 답하면 422, 질문하지 않은 키가 있으면 400이다.
- 재진단은 이전 추출 결과에 답변을 "[사용자 답변] 질문 → 답변" 줄로 상품 글 끝에 추가하여 선택 단계부터 다시 실행한다(`app/diagnosis/answers.py`).
- 답변 대기 세션은 질문을 보낸 시각부터 24시간 보관한다.

### 7.3 재접수

- 답변 대기 상품이 `/content`로 다시 접수되면 기다리던 세션을 버리고 새 `runId`로 1회차부터 실행한다. 버린 실행의 `runId`로 온 `/resume`은 `AI_RESUME_CONFLICT`로 거절한다.
- 접수·실행 중인 상품이 포함되면 요청 전체를 `AI_SESSION_CONFLICT`로 거절한다.

### 7.4 입력 가드

운영 진단(`/content`, `/resume`)은 파이프라인 실행 전에 입력 가드(판단 모델)를 거친다. 처리는 6.4를 참조한다.

### 7.5 개발용 경로

| 경로 | 인증 | 내용 |
|---|---|---|
| `/sandbox/diagnose` (POST), `/sandbox/diagnose/{productId}` (GET) | 개발용 키 | 실제 파이프라인으로 진단하고 결과는 상태 조회로 확인. 콜백 없음. 상품 수·동시 실행 상한 `MAX_DEV_INFLIGHT_SESSIONS`(기본 3) |
| `/dummy/diagnose/content`, `/dummy/diagnose/resume` | 내부 토큰 | BE 연동 확인용 케이스 더미. 운영과 같은 상한·콜백 사용 |

## 8. AI → BE 콜백

위치: `app/schemas/callback.py`(DTO), `app/callbacks/`(이벤트 변환·발신함), `app/clients/backend/callback.py`(전송)

- 전달: `POST /internal/v1/ai/products/{productId}`, 헤더 `X-Internal-Token`. 응답 분류와 재전송은 발신함이 담당한다.
- 법령 변경 전송(`/internal/v1/ai/law-changes`)은 상품 콜백과 별개이며 [DB_CACHE.md](../storage/DB_CACHE.md)에서 설명한다.
- 콜백에는 `diagnosisId`, `productId`, `runId`만 전달한다. 실행 종류, 원인 예외, stack trace, 모델 원문 응답, 조회 기록은 전달하지 않는다.

| 이벤트 (`eventType`) | 필드 | 비고 |
|---|---|---|
| 공통 | `eventId`, `diagnosisId`, `productId`, `runId`, `sequence` | `eventId`는 BE 중복 수신 키. `sequence`는 실행마다 1부터 |
| `product_progress` | `stage`, `stageStatus`(started·completed·skipped), `toolName` | `toolName`은 Tool 실행 단계에서만. 선택된 Tool은 동시에 실행되므로 Tool 간 순서는 보장하지 않음(같은 Tool은 started → completed). BE는 저장하지 않고 표시만 |
| `product_awaiting_input` | `questionRound`(1-2), `questions[]` | 실행의 마지막 이벤트 |
| `product_result` | `assessment` (9장) | 실행의 마지막 이벤트 |
| `product_failed` | `stage`, `error{code(50자 이하), message, retryable, reviewFlag}` | 실행의 마지막 이벤트 (6.4) |

- `toolName`과 카드의 분야 이름은 BE `ToolName` 값(`CUSTOMS`, `CHILDREN`, `ELECTRICAL`, `RADIO`, `FOOD_DRUG`, `LABEL_AD`)이다.
- 재실행 회차에는 Tool 실행·집계·검증 단계 알림을 다시 보낸다. Tool 진행은 다시 실행하는 Tool만 started·completed를 다시 보내고, skipped는 다시 보내지 않는다(`app/diagnosis/progress.py`).

### 8.1 질문

질문 `PublicQuestionDto`: `questionKey`(50자 이하), `questionOrder`(1부터), `questionText`, `helpText`

- 질문 키는 `r{회차}_q{순서}` 형식이다(예: `r1_q1`). 같은 문장은 한 번만 질문하며, 꼭 필요한 질문을 앞에 둔다(`app/diagnosis/questions.py`).
- 질문은 최대 2회차다. 2회차에는 1회차에 없던 새 키만 질문한다. 질문 회차를 모두 사용하고도 질문이 남으면 미완료 결과로 종료한다(10장).
- 검증 모델이 생성한 질문은 검증이 제시한 이유를, Tool의 부족한 정보로 만든 질문은 질문 카탈로그(`app/tools/common/questions.py`)의 답변 방법·예시를 `helpText`로 보낸다.
- Tool의 부족한 정보는 진단 함수가 질문으로 옮긴다(`app/diagnosis/job.py`). 이전 회차에 질문한 문장은 제외하고, 여러 Tool이 같은 문장을 질문하면 하나로 합친다.
- 검증 모델이 생성한 질문 중 Tool이 이번 회차에 질문하는 조건이나 판매자가 이전 회차에 답변한 조건을 다시 묻는 질문은 검증 에이전트가 제외한다(`VerificationAgent._drop_covered_questions`). 같은 정보를 표현만 바꾸어 두 번 질문하지 않기 위함이다.
  - 검증 모델은 질문마다 그 질문이 묻는 상품 조건(`topic`)을 함께 출력한다. 값은 질문 카탈로그의 조건 필드 중 하나이며, 어디에도 해당하지 않으면 `other`다.
  - 코드는 Tool의 부족한 정보 문장과 상품 정보에 추가된 답변 줄의 질문 문장에서 조건 필드를 찾아(`field_for`, `answered_questions`) `topic`과 대조한다. 답변이 "모르겠어요"여도 제외한다. `other`인 질문은 제외하지 않는다.
  - 이름이 달라도 질문 내용이 같은 조건은 한 묶음으로 본다(`SAME_QUESTION_GROUPS`). 현재 묶음은 전원 방식(`power_source`)과 전지 전용 여부(`battery_only`) 하나다.

## 9. 공개 진단서

위치: `app/schemas/callback.py`의 `PublicAssessmentDto`. 내부 `FinalAssessment`를 변환기(`app/results/presenter.py`의 `ResultPresenter`)가 변환한다. 콜백과 샌드박스 상태 조회가 같은 변환기를 사용한다.

| 필드 | 의미 |
|---|---|
| `status` | `completed` / `incomplete`. 입력 대기는 질문 콜백으로 별도 전달 |
| `resultStatus` | `PURCHASING_AGENT_ALLOWED`(구매대행 가능), `DIRECT_IMPORT_CERTIFICATION_REQUIRED`(사입 인증 필요), `RECHECK_REQUIRED`(재확인 필요) |
| `summary` | 공개 요약 |
| `toolReviews[]` | 분야 카드: `toolName`, `status`, `message`, `findings[]` |
| `requiredActions[]` | 상품 전체의 할 일. 분야 순서로 모으고 중복 제거 |
| `notices[]` | 미완료 사유, 정보 부족, 참고 안내 |

- 판단 `PublicFindingDto`: `subject`(255자 이하), `determination`, `riskLevel`, `summary`, `rationale`, `legalSources[]`
- 근거 `PublicLegalSourceDto`: `sourceName`·`lawName`·`article`(255자 이하), `quotedText`, `sourceUrl`, `effectiveDate`(50자 이하). 길이는 BE 수신 DTO·DB 칸과 같으며, 초과하면 AI가 잘라서 보낸다.
- 미완료는 `notices`가 반드시 있고 `resultStatus`는 `RECHECK_REQUIRED`만 사용한다.
- 문자열 칸은 공백만으로 채우지 않는다(BE `@NotBlank`).
- 판단의 공개 여부는 AI가 결정한다. BE·FE는 내부 검증 이슈로 판단의 유효성을 재검사하지 않는다.

### 9.1 분야 카드

6개 분야 카드를 항상 같은 순서로 하나씩 보낸다.

| 카드 상태 | 조건 |
|---|---|
| `COMPLETED` | Tool 실행 결과가 `SUCCESS`. 규제 비대상·안전·인증을 뜻하지 않음 |
| `SKIPPED` | 선택되지 않은 분야 |
| `INCOMPLETE` | 선택되었으나 실행 결과가 `SUCCESS`·`SKIPPED`가 아니거나 실행 기록이 없음 |

카드에 포함하는 판단 내용과 길이 처리는 [TOOL_COMMON.md](../tools/TOOL_COMMON.md) 8장에서 설명한다.

### 9.2 결과 상태

`app/results/status.py`가 정해진 규칙으로 결정한다. 위에서부터 먼저 해당하는 것을 사용한다.

| 순서 | 조건 | `resultStatus` |
|---|---|---|
| 1 | 진단 미완료 | `RECHECK_REQUIRED` |
| 2 | 판단 대상 Tool에 `REQUIRED`·`POSSIBLY_REQUIRED` 판단이 있음 | `DIRECT_IMPORT_CERTIFICATION_REQUIRED` |
| 3 | 지원 분야 밖 신호: 추출의 `chemical_product`·`weapon_like`·`plant_material` 중 하나라도 `true` | `RECHECK_REQUIRED` |
| 4 | 판단 대상 Tool이 없음 | `PURCHASING_AGENT_ALLOWED` |
| 5 | 판단 대상 Tool의 실행 결과가 `SUCCESS`가 아님, 또는 정보 부족(`INSUFFICIENT_INFORMATION`이거나 위험도 `UNKNOWN`) | `RECHECK_REQUIRED` |
| 6 | 그 밖의 경우 | `PURCHASING_AGENT_ALLOWED` |

- 표시·광고(`LABEL_AD`)는 결과 상태 계산에서 제외한다. 결과 상태가 구매대행 가능이고 표시·광고에 `REQUIRED`·`POSSIBLY_REQUIRED` 판단이 있으면 요약 끝에 "다만 표시·광고 문구는 확인이 필요합니다."를 덧붙인다([ADVERTISING_TOOL.md](../tools/ADVERTISING_TOOL.md)).

### 9.3 안내

`notices`는 다음 순서로 구성하고 중복을 제거한다.

1. 미완료이면 종료 사유별 미완료 안내
2. 지원 분야 밖 신호별로 확인하지 않는 법령 안내(화학제품안전법, 총포·도검·화약류법, 식물방역법)
3. 구매대행 가능이면 확인한 분야와 확인하지 않은 범위(생활용품 안전관리, 가스·소방용품 등)
4. 질문으로 전달하지 않고 남은 부족 정보
5. 면책 문구 "법령 근거에 따른 참고 정보이며 법률 자문이나 확정 판단이 아닙니다."

### 9.4 결과 검토로 확정하지 못한 경우

종료 사유가 `REVISION_REQUIRED`(결과 검토에서 고쳐야 할 부분이 남아 확정하지 못함)이면, 검증의 `critical` 지적이 가리킨 판단을 분야별로 모아 재확인할 위치를 알린다.

| 항목 | 내용 |
|---|---|
| `summary` | "<분야> 분야에 재확인이 필요한 항목이 있습니다. 아래 해당 카드를 확인해 주세요." 분야는 카드 순서대로 한 번씩 기재 |
| 분야 카드 `message` | "이 카드의 ‘<판단 제목>’ 항목은 이번 진단에서 결론을 내리지 못했습니다. 아래 판단 근거가 판매할 상품에도 적용되는지 확인해 주세요." 판단 제목은 카드의 `subject`와 같음 |

- 검증 지적 원문은 모델이 작성한 글이므로 내보내지 않고, 이미 카드에 공개하는 판단 제목만 사용한다.
- 인증 후보 판단 자체가 지적받은 경우가 있으므로, 판단만으로 정한 결론 문장은 요약에 사용하지 않는다.
- `warning` 지적, 진단 결과에 없는 판단 ID는 제외한다. 연결할 판단이 없으면 기존 요약과 카드 문구를 그대로 사용한다.
- 카드 상태가 `INCOMPLETE`이면 기존 미완료 문구를 유지한다.
- `resultStatus`와 `notices`의 종료 사유 안내는 바뀌지 않는다.

## 10. 종료 사유

정의 위치: `app/schemas/schemas.py`의 `ExecutionEndReason`

| 값 | `verification_status` | 세션 결말 |
|---|---|---|
| `completed` | `verified` 또는 `verified_with_warnings` | 결과 콜백 (`completed`) |
| `user_input_required` | `incomplete` | 질문 콜백. 질문 회차가 남지 않았으면 `question_limit_exceeded`로 종료 |
| `revision_required` | `incomplete` | 결과 콜백 (`incomplete`) |
| `retry_limit_exceeded` | `incomplete` | 결과 콜백 (`incomplete`) |
| `no_progress` | `incomplete` | 결과 콜백 (`incomplete`) |
| `cost_limit_exceeded` | `incomplete` | 값만 정의. 비용 계산·중단은 구현되지 않음 |
| `question_limit_exceeded` | `incomplete` | 결과 콜백 (`incomplete`) |

- `completed`는 검증 흐름의 완료이며 상품의 규제상 적합이나 인증을 뜻하지 않는다.
- `user_input_required`는 이번 실행의 종료이며 진단 전체의 완료가 아니다.
- 처리하지 못한 예외는 `FinalAssessment`를 생성하지 않고 실패 콜백으로 종료한다(6.4). 예외의 부분 결과는 최종 결과가 되지 않는다.
- 서버 재시작 시 세션 처리는 [AI_SESSION_ARCHIVE.md](../storage/AI_SESSION_ARCHIVE.md)에서 설명한다.

## 11. 결정하지 않은 사항

| 항목 | 별도로 정할 내용 |
|---|---|
| 비용 상한 중단 | 상품·진단서 단위 상한, 호출 전 추정, 병렬 예약, 중단·결과 반환 정책 |
| 동일 결과 조기 중단 | 비교 대상, 의미적 동일성, 실패 원인별 복구 가능성 |
| 구성 요소 단위 실행 기록 | 이벤트 이름과 공개 범위 |
| 운영 저장소 | 사용량·실행 기록의 수집·보관 위치, 다중 프로세스 원자성 |
| 프롬프트 캐시 갱신 | 재시작 반영·명시적 갱신·평가 시 처리 |
| SDK 재시도 측정 | 실제 요청별 사용량·비용 수집 범위 |

미결정 사항을 기존 성공·승인 상태로 대체하지 않는다.

---

변경 이력: [history/AI_COMMON_CONTRACT.md](../../history/contract/AI_COMMON_CONTRACT.md)
