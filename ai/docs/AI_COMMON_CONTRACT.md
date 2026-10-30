# AI 공통 실행·관측·예외 계약

## 0. 적용 기준

- 상태: `Review Ready`
- 적용 범위: Agent, 모델 호출, Tool, Client, Repository, Pipeline, 평가 실행
- 근거: [#171](https://github.com/kakaotechcampus-4/ktc4-kangwon-3/pull/171), [#231](https://github.com/kakaotechcampus-4/ktc4-kangwon-3/issues/231)
- 이 문서의 Python 코드는 **마이그레이션 목표 인터페이스**다. 이미 구현된 절은 코드를 지우고 구현 위치와 문서와 달라진 점만 남긴다. 코드를 문서에 복사해 두지 않는다(코드가 기준).
- 팀 리뷰 후 승인된 버전을 구현 기준으로 사용한다. 새로 구체화한 스키마의 타입·필수 여부도 이 문서 리뷰 대상이다.

### 구현 현황 (2026-10-26, develop 기준)

| 절 | 상태 | 구현 위치 |
| --- | --- | --- |
| §2 실행 컨텍스트 | 구현됨 (세션 계층까지만 전달) | `app/domain/context.py` |
| §3 프롬프트 로더 | 구현됨 | `app/prompts/__init__.py` |
| §4.2 BaseAgent | 구현됨 (#364) | `app/agents/base/`, Tool 안 모델 호출은 `app/tools/base/steps.py` |
| §4.3 context 인자 | 미구현. 공개 메서드는 `run(input)` | — |
| §5 UsageRecord·Sink | 미구현. 평탄한 JSONL `record()` 유지 + 지표 sink 등록표(#379) | `app/usage.py`, `app/observability/` |
| §6.1 예외·응답 코드 | 구현됨 (#382) | `app/domain/errors.py` |
| §6.2 Client·Tool 오류 경계 | 일부. ToolExecutor 구분·Client 예외 변환은 미구현 | — |
| §6.3 API 경계 | 구현됨 | `app/routers/exception_handlers.py` |
| §7.1 ExecutionEvent | 미구현. 세션 이벤트가 상품 단위 진행을 대신함 | `app/sessions/events.py` |
| §7.1.2 콜백 이벤트 | 구현됨 (#310·#317) | `app/schemas/callback.py`, `app/callbacks/` |
| §7.1.3 공개 진단서 | 구현됨 (#405). 서버 조립 교체는 #320 | `app/schemas/callback.py`, `app/results/` |
| §7.1.4 진단 접수·재진단 요청 | 구현됨 (#402) | `app/schemas/request.py`, `app/routers/diagnose.py` |

- 파이프라인 연결(#320) 전까지 `/diagnose`는 501로 거절한다. BE 연동은 케이스 더미(`/dummy`), 샌드박스는 고정 더미로 실행한다(`main.py`).
- 기존 [제안 문서](OBSERVABILITY_AND_ERROR_HANDLING.md)는 논의 이력으로 보존한다. 구현 시 이 문서와 제안 문서를 섞어 적용하지 않는다.
- 내부 Python 필드명은 snake_case를 사용한다. BE API DTO의 alias 규칙은 별도 API 계약을 따른다.

### 마이그레이션 단계

| 단계 | 변경 범위 | 유지할 동작 |
| --- | --- | --- |
| M1 | BaseAgent, AgentError, 원본 응답 수집, 공용 프롬프트 로더, 콘솔 사용량 로그 통합 | 기존 공개 호출·인자, 판단 로직, 기존 예외, 재시도 횟수 |
| M2 | ExecutionContext, UsageRecord, run_type 전달 | 판단 결과, 기존 로그 집계 호환 |
| M3 | 합의된 응답 코드의 AIServiceError 적용, Client·Tool 오류 경계 | 원본 원인, 부분 결과, 공개 메시지 보호 |
| M4 | Pipeline Trace, 운영 저장소·로그 설정 | 업무적 재실행과 기술적 재시도의 구분 |

**M1에서 미사용 `context=None` 인자를 추가하지 않는다.** 아래 컨텍스트 인터페이스는 M2부터 적용한다. M1에 M2~M4의 정책 변경을 섞지 않는다.

### 계약 합의 시점과 코드 이관 시점

**BE와의 응답 코드·HTTP 상태·공개 메시지·API 오류 매핑 합의는 M3까지 기다리지 않는다.** #171의 적용 순서대로 공통 컨텍스트 정의 다음에 예외·API 오류 계약을 합의하고, 사용량 Adapter·Record의 세부 계약을 확정한다. BE 연동에 필요한 오류 계약 논의는 M1과 병행할 수 있다.

M1~M4는 AI 코드의 이관 단위이며, 계약을 합의하는 순서가 아니다. M3는 먼저 합의한 오류 계약을 내부 예외·Client·Tool에 적용하는 단계다. 계약이 필요한 API 구현은 사용량 이관 완료를 기다리지 않고 별도 PR에서 먼저 적용할 수 있다.

## 1. 전체 연결 구조와 소유권

```text
요청 / 평가 진입점
  └─ ExecutionContext 생성
       └─ 상품별 Pipeline
            ├─ Agent / Tool / Client / Repository에 전달
            ├─ 모델 호출 → CallUsage → UsageRecord
            ├─ 상태 전환 → TraceEvent
            ├─ 실행·실패 분석 → 운영 로그
            └─ 실패 → AIServiceError → API 경계에서 안전한 응답
```

| 대상 | 소유자 | 규칙 |
| --- | --- | --- |
| 상품별 run_id | 상품 Pipeline 실행 진입점 | 실행 시작에 한 번 생성 |
| diagnosis_id, product_id | 요청 제공자 | 전달받은 값을 유지. LLM이 생성하지 않음 |
| 단독 평가 run_id | 평가 실행 진입점 | 각 실행에 생성하고 Agent에 전달 |
| retry_round | Pipeline | 최초 0. 업무적 재실행 때만 증가 |
| 모델 사용량 기록 | 실제 모델 호출 구성 요소 | 논리적 호출당 한 번 기록 |
| 전체 사용량 집계 | Pipeline / 평가 집계 계층 | 기존 기록을 합산. 같은 호출을 다시 기록하지 않음 |
| 전체 Trace | Pipeline | 하위 이벤트를 같은 실행으로 연결 |
| 운영 로그 | 각 구성 요소 | 자신의 상태·오류만 기록 |
| 외부 오류 응답 | API 경계 | 내부 원인·원문을 노출하지 않음 |

## 2. 공통 실행 컨텍스트 — M2

### 2.1 스키마 — 구현됨

위치: `app/domain/context.py` (`RunType`, `PipelineStage`, `ExecutionContext.start()`·`next_round()`). 필드·불변 조건은 아래 표와 같다.

- 컨텍스트는 지금 **세션 계층에만** 있다(`DiagnosisSession.context`). Pipeline·Agent·Tool에는 넘기지 않는다(§4.3 미구현).
- `next_round()`를 부르는 곳은 아직 없다. 파이프라인은 지역 변수로 재실행 회차를 센다(`pipeline/runner.py`).

### 2.2 필드와 불변 조건

| 필드 | 필수 여부 | 값 / 생성 규칙 |
| --- | --- | --- |
| run_id | 필수 | 진입점이 생성. 하위 구성 요소에서 재생성 금지 |
| product_id | 필수 | 상품 요청 ID. 평가에서는 Fixture의 상품 ID |
| diagnosis_id | 선택 | 운영 진단서 요청은 BE ID 전달. 단독 평가·테스트는 null 허용 |
| run_type | 필수 | production / evaluation / test |
| retry_round | 기본 0 | 0 이상의 정수. bool 금지 |

- BE 진단서 요청에서 diagnosis_id가 필요한지는 API 요청 DTO에서 검증한다. 공통 컨텍스트는 단독 평가도 지원하므로 null을 허용한다.
- 재실행은 새로운 컨텍스트 스냅샷을 만들되 run_id·diagnosis_id·product_id·run_type은 유지한다.
- 동시 실행 사이에 변경 가능한 컨텍스트를 공유하지 않는다.
- SDK·Client의 내부 재시도는 retry_round를 변경하지 않는다.
- 사용자 답변 이후 재개(재진단)하면 **run_id를 새로 발급**한다(`ExecutionContext.start()`, #310). diagnosis_id·product_id·run_type은 유지한다. 콜백의 `sequence`도 실행마다 1부터 다시 센다.
- `next_round()`는 회차 값만 생성한다. 실행 가능 횟수는 Pipeline 정책이 검증한다.

### 기존 RetryRequest·ToolResult와 회차 일치

- 회차의 기준은 Pipeline이 생성한 `ExecutionContext.retry_round`다. 독립적인 카운터를 추가하지 않는다.
- 재실행을 시작할 때 `RetryRequest.retry_round`에 해당 컨텍스트의 값을 넣고, 이번 실행으로 생성한 `ToolResult.retry_round`도 같은 값으로 기록한다.
- `RetryRequest.latest_tool_results`는 재실행 전의 결과 스냅샷이므로 그 안의 회차는 이전 값일 수 있다. 기존의 요청 회차 검증을 유지한다(#203이 반영된 `feature/ai/agent-pipeline` 기준).
- 이번에 실행하지 않은 Tool 결과와 `tool_result_history`의 과거 회차는 변경하지 않는다. 모든 최신 결과를 현재 회차로 덮어쓰지 않는다.
- ToolExecutor 경계에서 요청 회차와 컨텍스트가 일치하는지 검사한다. SDK 내부 retry는 어느 필드의 업무 회차도 올리지 않는다.

### 2.3 생성 위치

- 진단 접수: 세션 관리자가 상품마다 `ExecutionContext.start(run_type=PRODUCTION)`로 만든다.
- 재진단: 답변 검사 후 새 컨텍스트를 만든다(`sessions/manager/manager.py`의 `resume`).
- 개발용 진단·평가: 각 진입점이 만든다.

## 3. 프롬프트 로더 — M1

### 3.1 접근 인터페이스 — 구현됨

위치: `app/prompts/__init__.py` (`PromptName`, `PromptSnapshot`, `get_prompt`, `clear_prompt_cache`, `load_prompt`). 처음 제안과 다른 점:

- `PromptName`: 3개 → 15개. Tool의 facts·review(`customs/facts` 등 10개), `advertising`, `image_triage` 추가
- 파일 위치: `agents/<name>/prompt.md`를 먼저 찾고, `prompts/<name>.md`와 두 곳에 다 있으면 오류
- 캐시: `lru_cache(maxsize=None)`
- 공용 헬퍼 `normalize_newlines`·`fingerprint` 추가. `load_prompt`는 등록 안 된 이름이면 ValueError

### 3.2 계약

- Agent와 평가 러너는 같은 PromptSnapshot을 사용한다.
- 모델에 전달하는 text와 기록하는 sha256은 같은 스냅샷에서 가져온다.
- 파일 경로만 버전으로 사용하지 않는다.
- SHA-256 전체 문자열을 기록하고 화면 표시만 짧게 줄일 수 있다.
- 기존 평가의 LF 정규화·지문과 호환되는지 테스트한다.
- 평가 러너가 Agent의 `PROMPT_PATH` / `_PROMPT_PATH`를 import하지 않도록 이관한다. (미완료: `eval/runner.py`·`selection_runner.py`·`collect_runner.py`가 아직 import함. 값은 로더에서 가져온 경로라 지문은 같음)
- 캐시 갱신 시점은 미결정이다. 운영 중 자동 갱신은 이번 인터페이스로 보장하지 않는다. 개발·평가에서 초기화할 수 있는 명시적 함수만 제공한다.
- 기존 `prompt_fingerprint(path)`의 임의 파일 평가 기능이 필요하면 유지하되, 해시 계산 규칙은 같은 함수를 공유한다.

## 4. Agent 인터페이스와 실행 경계 — M1 / M2

### 4.1 Base가 담당할 일

| BaseAgent | 각 Agent |
| --- | --- |
| 공용 프롬프트 접근 | 어떤 프롬프트·출력 스키마를 쓸지 |
| 구조화 모델 호출 | 입력 메시지 구성 |
| raw 응답 파싱 확인 | 상품 규칙 추출·병합 |
| 사용량 수집·기록 | Tool 선택 판단 |
| 수집한 사용량으로 콘솔 토큰 로그 출력 | 출력 옵션과 로깅 설정 |
| 호출·파싱 예외 변환 | 검증 규칙·범위 검사·결과 병합 |
| 공통 기록 실패 경고 | 기존 검증 내부 Trace |

### 4.2 BaseAgent — 구현됨 (#364)

위치: `app/agents/base/` 패키지 (`agent`·`errors`·`meta`·`parsing`·`protocols`·`usage_log`). 처음 제안과 다른 점:

- `BaseAgent[InputT, OutputT, ResultT]`(ABC). 공개 메서드는 `run(input)`·`run_with_meta(input)` 두 개
- 하위 클래스 구현: `_build_messages`·`_subject_id` (필요하면 `_finalize`·`_skip`)
- ClassVar 추가: `task_name`·`output_label`·`structured_output_options`·`creates_default_model`·`model_profile`
- `AgentError(AIError, RuntimeError)`에 `meta: AgentRunMeta` 추가. `ModelFailurePhase`에 `FINALIZE` 추가
- 실행 정보 `AgentRunMeta`·`AgentResult` 신설 (`base/meta.py`)
- Tool 안의 모델 호출도 BaseAgent를 상속: `ToolStep` + `ToolStepInput(payload, subject_id)` (`app/tools/base/steps.py`)
- 콘솔 토큰 로그는 `base/usage_log.py`의 `log_token_usage`
- 모델 생성: `build_agent_model(name)`·`build_tool_model(name)` (`app/clients/llm`, #311·#401). 프로필은 `config/profiles.py`

기존 Agent별 예외(`ExtractionFailedError` 등)는 각 Agent 모듈에 남기고 부모만 `AgentError`로 바꿨다.

- 기존 예외 import 경로·메시지·cause·partial_result를 유지한다.
- 모델 생성은 `build_agent_model()`·`build_tool_model()`의 공통 설정 경로를 사용한다. 모델 stub 주입을 유지한다.
- 검증의 규칙 전용 실행에서는 모델을 자동 생성하지 않는다. 다른 Agent와 생성 시점을 맞추려고 이 동작을 변경하지 않는다.
- `include_raw=True`를 세 Agent에 적용한다. `strict`는 Agent별 기존 설정을 유지한다.
- 생성자의 `configured_model` / `usage_agent` 등 기존 인자를 임의로 삭제하지 않는다.
- M1에서 세 Agent가 과도기 `usage_agent`를 공통 생성자에 전달할 수 있도록 한다. 기존에 인자가 없던 VerificationAgent에도 선택적 키워드 인자로 추가하며 기본 기록 이름은 `verification`을 유지한다.
- M1의 `usage_agent`는 기존 기록 이름을 선택하는 용도이며 아직 `run_type`이 적용되었다는 의미가 아니다.
- 기술적 재시도를 M1에서 신설하지 않는다.

#### 검증의 부분 결과·Trace 보존 경계

Base는 `partial_result`를 전달받아 예외에 보존한다. 부분 결과를 생성하거나 검증 Trace를 직접 관리하지 않는다. Agent별 `_failure_message()`로 기존 메시지를 유지한다.

VerificationAgent는 규칙 검사 결과를 `_invoke()`에 전달하고, 발생한 **동일한 VerificationError**를 잡아 기존 Trace를 추가한 뒤 `raise`로 다시 전달한다. 새 VerificationError로 감싸지 않으므로 원본 예외가 `__cause__`에 그대로 남는다.

아래는 VerificationAgent 안에 둘 내부 호출 경계 예시다. 규칙 검사·범위 검사·병합을 대체하지 않는다.

```python
def _review_with_trace(
    self,
    messages,
    *,
    subject_id,
    rules,
    trace,
):
    try:
        return self._invoke(
            messages,
            subject_id=subject_id,
            partial_result=rules,
        )
    except VerificationError as exc:
        cause = exc.__cause__
        self._append_trace(
            trace,
            action="model_review_failed",
            status="failed",
            detail=f"_Review 생성 실패: {type(cause).__name__}",
        )
        raise
```

- 기존 호출 실패는 `CALL`, 응답의 `parsing_error` 또는 `parsed` 누락은 `PARSING`으로 구분한다.
- `parsing_error`가 예외이면 그 객체를 cause로 사용한다. 원인 예외 없이 `parsed`가 누락되면 `MissingParsedOutput` 예외를 만들어 cause로 연결하고, 사용량 로그의 `error_type`도 기존 값인 `MissingParsedOutput`을 유지한다.
- `MissingParsedOutput`을 새 cause로 연결하더라도 Agent별 기존 오류 메시지는 유지한다. 메시지를 cause 문자열로 자동 조립하지 않고, `_failure_message()`에서 기존의 parsed 누락 문구를 반환한다.
- 모델 호출·파싱 실패와 범위 검사·병합 실패의 메시지·Trace action을 섞지 않는다. 후자는 기존 VerificationAgent 경계에 유지한다.
- 모델 미설정은 `_invoke()` 진입 전 기존 검증 분기에서 처리한다. 규칙 전용 실행에 모델을 생성하는 방식으로 해결하지 않는다.
- 내부 예외 문구는 M1 호환 대상이지만 외부 응답·공통 로그에 그대로 노출하지 않는다. M3에서는 안전한 응답 코드 메시지로 이관한다.

#### 콘솔 토큰 로그 통합

- #231 논의 ⑦의 추출 담당 의견에 따라 기존 `_log_token_usage()`를 Base의 공통 출력으로 통합하여 유지한다.
- 이미 수집한 사용량으로 출력하며 모델 응답을 다시 수집하거나 `record()`를 다시 호출하지 않는다.
- 로컬 실행 스크립트의 로그 확인 기능을 유지한다. 출력 여부는 Logger 레벨·Handler 설정으로 제어한다.
- Prompt·응답 전문은 출력하지 않는다. 콘솔 출력 실패가 판정 결과나 원래 모델 예외를 바꾸지 않게 한다.

### 4.3 context 전달 — 미구현

- 공개 메서드는 `run(input)` 하나로 통일됐다(#364). 처음 제안한 `extract/select/verify(..., *, context)`는 쓰지 않는다.
- 컨텍스트를 Agent까지 넘길 때는 메서드 인자 대신 입력 스키마 또는 `run`의 키워드 인자로 넘기는 방향으로 다시 정한다. Pipeline Protocol·구현·CLI·평가 Runner·stub을 같은 PR에서 갱신한다.
- 규칙만 실행하는 `verify_rules()`는 모델 사용량을 기록하지 않는다.
- 검증의 범위 검사·결과 병합을 Base로 옮기지 않는다.

### 4.4 모델 호출 순서

```text
시작 시각과 call_id 확보
→ include_raw=True 모델 invoke
→ raw에서 CallUsage 수집
→ parsing_error / parsed 검사
→ 성공 또는 실패 UsageRecord 한 번 기록
→ 파싱 결과 반환 / Agent별 예외 발생
```

| 결과 | 사용량 | 기록 success | Agent 동작 |
| --- | --- | --- | --- |
| 정상 parsed | raw에서 수집 | true | parsed 반환 |
| parsing_error 있음 | raw에서 확보되면 보존 | false | 원인 연결 후 예외 |
| parsed 없음 | raw에서 확보되면 보존 | false | 출력 변환 실패 |
| invoke 예외 | 확보 불가능하면 null | false | 원본 원인 연결 후 예외 |

- 사용량 미확보는 0토큰이 아니다.
- 검증의 범위 검사는 모델 응답 후 별도 처리다. 모델 호출 성공과 검증 전체 성공을 같은 지표로 취급하지 않는다.
- 범위 검사 실패는 운영 로그·Trace에 기록하고, 같은 모델 호출의 UsageRecord를 추가하지 않는다.
- 검증 실패 시 규칙 검사 결과를 VerificationError.partial_result에 보존하는 책임은 VerificationAgent에 남긴다.
- 구현(#364): 지금은 UsageRecord 대신 `usage.record()`로 한 번 기록한다. 성공 기록은 `_finalize`까지 끝난 뒤 남기며, `_finalize` 실패는 `failure_phase=finalize`. 길이 초과·콘텐츠 필터는 `from_completion`으로 사용량을 살려 PARSING 실패로 기록한다.

## 5. 사용량 스키마 — M2

예정 위치: `app/observability/usage.py`
기존 `app/usage.py`는 이관 중 호환 진입점으로 사용할 수 있다.

> **현재 상태 (미구현)**: UsageRecord·UsageSink·record_usage는 없다. 지금은 아래처럼 동작한다.
> - `app/usage.py`의 `record(agent, usage, *, configured_model, reasoning_effort, subject_id, ok, elapsed_ms, error_type, failure_phase)`가 평탄한 JSONL 한 줄을 쓴다. 쓰기 실패는 그대로 무시(`pass`).
> - `CallUsage`는 dataclass. `cached_tokens`(모르면 0), `reasoning_tokens`·`cache_write_tokens` 추가. 수집 함수는 `from_response`·`from_handler`·`from_completion`.
> - 에이전트 실행 결과는 sink 등록표(`app/observability/agent_sinks.py`, #379)로 나간다. 사용량 JSONL과 Prometheus 지표(`ai_agent_*`, `observability/metrics.py`)가 그 sink다. sink 오류는 WARNING만 남기고 판정을 바꾸지 않는다.
> - 아래 5.1~5.3은 M2 목표로 남긴다.

### 5.1 정규화된 사용량

```python
from pydantic import BaseModel, ConfigDict, Field, computed_field, model_validator


class CallUsage(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    reported_model: str | None = None
    input_tokens: int = Field(ge=0, strict=True)
    cached_input_tokens: int | None = Field(default=None, ge=0, strict=True)
    output_tokens: int = Field(ge=0, strict=True)

    @model_validator(mode="after")
    def validate_cached_tokens(self) -> "CallUsage":
        if (
            self.cached_input_tokens is not None
            and self.cached_input_tokens > self.input_tokens
        ):
            raise ValueError("cached_input_tokens는 input_tokens를 초과할 수 없습니다.")
        return self

    @computed_field
    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens


def from_response(raw_response: object) -> CallUsage | None: ...


def from_handler(callback_handler: object) -> CallUsage | None: ...


def estimate_krw(
    usage: CallUsage,
    configured_model: str | None,
) -> float | None: ...
```

- cached_input_tokens는 input_tokens에 포함된다. total_tokens에 중복 합산하지 않는다.
- 사용량 전체가 불명확하면 CallUsage는 null, 캐시만 불명확하면 cached_input_tokens는 null이다.
- 단가 또는 필요한 사용량이 불명확하면 estimated_cost_krw는 null이다. 0으로 예산을 판단하지 않는다.
- 비정상 메타데이터는 수집 실패로 경고한다. 관측 변환 실패로 상품 판정을 실패시키지 않는다.
- Callback adapter는 호환을 위해 유지할 수 있지만 세 Agent의 표준 수집 경로는 raw다.
- 캐시 값을 0으로 보완하는 기존 구현에서 null로 이관하므로 집계·비용 계산·테스트를 함께 수정한다.

### 5.2 호출 단위 저장 형식

```python
from datetime import timezone

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator


class UsageRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    call_id: str = Field(min_length=1)
    context: ExecutionContext
    component_name: str = Field(min_length=1)
    stage: PipelineStage
    timestamp: AwareDatetime
    latency_ms: int = Field(ge=0, strict=True)
    configured_model: str | None = None
    usage: CallUsage | None = None
    estimated_cost_krw: float | None = Field(default=None, ge=0)
    success: bool
    error_code: str | None = None
    error_type: str | None = None
    prompt_version: str = Field(min_length=1)

    @field_validator("timestamp")
    @classmethod
    def normalize_timestamp(cls, value: AwareDatetime) -> AwareDatetime:
        return value.astimezone(timezone.utc)
```

| 필드 | 계약 |
| --- | --- |
| call_id | 논리적 모델 호출 식별자. 시작 시 생성하고 성공·실패에 같은 ID 사용 |
| context | 실행 컨텍스트 스냅샷 |
| component_name / stage | 실제 호출 주체와 Pipeline 단계 |
| timestamp | UTC timezone-aware. 저장 시 ISO 8601 |
| latency_ms | monotonic clock으로 측정. 논리적 호출의 SDK 내부 retry 대기 포함 |
| usage | 사용량 불명확하면 null. total_tokens는 computed_field로 직렬화 |
| success | invoke·구조화 출력 파싱 완료 여부. 규제 판단 승인 여부가 아님 |
| error_code / error_type | 공통 코드 도입 전에는 타입, 이후에는 코드와 타입. 원본 예외 메시지는 저장하지 않음 |
| prompt_version | 실제 사용한 PromptSnapshot.sha256 |

저장 JSON은 위 중첩 구조를 표준으로 사용한다. `model_dump(mode="json")`으로 직렬화하며 usage의 `total_tokens`도 포함한다. 기존 평탄한 JSONL은 읽기 호환으로 처리하고 과거 행을 덮어쓰지 않는다.

### 5.3 저장 인터페이스와 실패

```python
from typing import Protocol


class UsageSink(Protocol):
    def write(self, record: UsageRecord) -> None: ...


def record_usage(record: UsageRecord, *, sink: UsageSink) -> None:
    # sink 실패를 여기서 처리하고 별도 운영 logger에 WARNING을 남긴다.
    # 원래 Agent의 성공·실패를 변경하지 않는다.
    raise NotImplementedError
```

- Sink 구현은 JSONL / stdout / DB 중 별도 결정한다. 위 시그니처가 DB 동기 쓰기를 강제하지는 않는다.
- 같은 call_id를 Agent와 Pipeline이 중복 발급·저장하지 않는다.
- call_id만으로 저장소의 exactly-once가 보장되지 않는다. 쓰기 retry·중복 전달은 Sink 설계에서 처리한다.
- Fallback logger는 실패한 Sink에 쓰지 않는다. Handler 출력 경로를 설정한다.
- SDK 내부의 실제 요청별 식별·과금 수집은 별도 설계한다.

## 6. 예외 스키마 — M3

위치: `app/domain/errors.py` — 구현됨 (#382)

### 6.1 응답 코드와 공통 예외 — 구현됨

- 공통 뿌리 `AIError(Exception)`. 이를 상속: `AIServiceError`, `AgentError`, `ClientError`(`clients/errors.py`), `ConfigError`(`config/errors.py`), 세션 예외(`sessions/errors.py`) 등
- `AgentError`는 `AIServiceError`의 하위가 아니라 **형제**다(처음 제안과 다름). 둘 다 `RuntimeError`도 상속해 기존 catch 호환을 유지한다.
- `AIServiceError(response_code, stage, retryable, partial_result, data)` — `data`가 추가됨(예: 409의 `conflictProductIds`)
- `AIResponseCode`는 BE와 합의해 확정했다:

| 코드 | HTTP | 쓰는 곳 |
| --- | --- | --- |
| `AI_INVALID_REQUEST` | 422 | 요청 형식 오류, 이번 회차 질문에 다 답하지 않음 |
| `AI_UNKNOWN_QUESTION_KEY` | 400 | 묻지 않은 질문의 답변 |
| `AI_UNAUTHORIZED` | 401 | 내부 토큰 없음·불일치 |
| `AI_NOT_FOUND` / `AI_SESSION_NOT_FOUND` | 404 | 경로 없음 / 세션 없음 |
| `AI_METHOD_NOT_ALLOWED` | 405 | |
| `AI_SESSION_CONFLICT` | 409 | 실행 중인(접수·실행) 상품 포함. 답변 대기 상품은 해당 없음 |
| `AI_RESUME_CONFLICT` | 409 | 기다리는 질문과 다른 답변·중복 답변 |
| `AI_QUEUE_FULL` | 429 | 진단 대기열 초과 |
| `AI_INTERNAL_ERROR` | 500 | 처리 못 한 예외 |
| `AI_NOT_IMPLEMENTED` | 501 | |
| `AI_PIPELINE_ERROR` | 500 | 실패 콜백: 진단 중 처리 못 한 예외 (retryable=false) |
| `AI_TIMEOUT` | 500 | 실패 콜백: 진단 시간 초과 (retryable=true) |

정확한 목록·문구는 `AIResponseCode`가 기준이다.

- `raise ... from exc`로 내부 cause를 보존한다. 공개 message에 원본 exc를 넣지 않는다.
- retryable은 재시도 가능성이며 즉시 재시도하라는 명령이 아니다.
- partial_result는 내부 부분 결과다. FinalAssessment나 ApiResponse.data로 무조건 변환하지 않는다.
- 모델 검증이 미완료된 규칙 검사 결과를 승인으로 반환하지 않는다.

### 6.2 실패별 처리 책임

| 실패 | 변환·처리 경계 | 자동 retry |
| --- | --- | --- |
| 설정·입력 오류 | 설정 로딩 / API 입력 경계 | 없음 |
| 모델 Timeout·Rate Limit | SDK 또는 공통 모델 Client 한 곳 | 제한적 |
| 출력 parse 실패 | Agent 또는 모델 adapter 한 곳 | 상한 합의 후 |
| 외부 API Timeout·5xx | 외부 API Client | 제한적 |
| 인증·권한·일반 4xx | Client | 원칙적으로 없음 |
| 예상 가능한 Tool 운영 실패 | Tool / ToolExecutor 결과 변환 경계 | 하위 retry와 중복하지 않음 |
| Tool 반환 계약 위반·코드 결함 | ToolExecutor / Pipeline | 없음. 일반 FAILED에 숨기지 않음 |
| DB 실패 | transaction 소유자 | rollback 후 원인에 따라 판단 |
| 사용량 저장 실패 | record_usage | 판정 중단하지 않음 |
| Verification 추가 Tool 요구 | Pipeline | 업무적 재실행. retry_round 증가 |
| 사용자 입력 요구 | Pipeline | 자동 retry 없이 종료 |

SDK → Agent → Tool → Pipeline에서 같은 오류를 각각 retry하지 않는다. SDK / Client 설정과 Pipeline 재실행 상한을 구분해 관리한다.

> **미구현**: ToolExecutor는 아직 계약 위반·코드 결함까지 `except Exception` 하나로 FAILED 처리한다. 외부 API Client도 아직 `httpx.HTTPStatusError`·`RuntimeError`를 그대로 던진다(ClientError로 감싸지 않음).

### 6.3 API 경계 — 구현됨 (`app/routers/exception_handlers.py`)

| 내부 | 외부 |
| --- | --- |
| response_code.code | ApiResponse.code |
| response_code.message | ApiResponse.message |
| response_code.http_status | HTTP 응답 status |
| cause / stack trace | 비공개 |
| partial_result | API 계약으로 정의한 안전한 DTO만 |
| retryable | 공개 여부를 BE와 별도 합의 |

`ApiResponse{code, message, details, data}`를 유지한다. `details`에는 요청 필드 오류만 넣고 내부 stack trace를 넣지 않는다.

## 7. Trace·운영 로그 — M4

### 7.1 목표 이벤트 스키마

예정 위치: `app/observability/trace.py` — **미구현**

> 지금은 상품 단위 진행을 세션 이벤트(`app/sessions/events.py`: Started·StageChanged·ToolProgressed·AwaitingInput·Completed·Failed·Resumed)와 상태 전이표(`app/sessions/transitions.py`)가 맡고, 콜백(§7.1.2)으로 BE에 나간다. 구성 요소 단위 ExecutionEvent는 아래 목표로 남긴다.

```python
from datetime import timezone
from enum import StrEnum

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator

from ..schemas.schemas import ExecutionEndReason


class ComponentType(StrEnum):
    AGENT = "agent"
    TOOL = "tool"
    CLIENT = "client"
    REPOSITORY = "repository"
    PIPELINE = "pipeline"


class EventStatus(StrEnum):
    STARTED = "started"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    AWAITING_INPUT = "awaiting_input"


class ExecutionEvent(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    context: ExecutionContext
    component_type: ComponentType
    component_name: str = Field(min_length=1)
    stage: PipelineStage
    event: str = Field(min_length=1)
    status: EventStatus
    timestamp: AwareDatetime
    latency_ms: int | None = Field(default=None, ge=0, strict=True)
    execution_id: str | None = None
    call_id: str | None = None
    error_code: str | None = None
    retryable: bool | None = None
    termination_reason: ExecutionEndReason | None = None

    @field_validator("timestamp")
    @classmethod
    def normalize_timestamp(cls, value: AwareDatetime) -> AwareDatetime:
        return value.astimezone(timezone.utc)
```

- ExecutionEvent는 전체 Pipeline용이다. 기존 Verification 내부 TraceEvent와 같은 타입으로 취급하지 않는다.
- ExecutionEvent는 내부 관측용이며 BE에 직접 직렬화해서 전달하지 않는다. 외부 전달은 §7.1.2의 별도 API DTO로 변환한다.
- 시작 이벤트는 latency_ms=null, 완료·실패 이벤트는 측정값을 넣는다.
- status는 작업의 완료 상태다. VerificationStatus·OverallStatus와 다른 개념이다.
- event 이름과 BE/FE 공개 범위는 Trace 구현 전에 확정한다. termination_reason은 ExecutionEndReason을 사용하며 별도 문자열 목록을 만들지 않는다.
- 실패·미완료 상태에 따른 정상적인 loop 종료와 미처리 예외에 따른 pipeline_failed를 구분한다.
- 종료 사유·대상 Tool·검증 상태를 자유문으로만 기록하지 않는다.
- 검증 내부 Trace 연결과 외부 공개 범위는 M1 범위 밖이다.

### 7.1.1 응답·종료 이벤트의 공통 종료 사유

정의 위치는 `app/schemas/schemas.py`의 `ExecutionEndReason`이다. 아래 표는 #240의 계약을 명시하며, Enum을 Trace 모듈에 중복 정의하지 않는다.

| Enum | JSON 값 | FinalAssessment.verification_status |
| --- | --- | --- |
| `COMPLETED` | `completed` | `verified` 또는 `verified_with_warnings` |
| `USER_INPUT_REQUIRED` | `user_input_required` | `incomplete` |
| `REVISION_REQUIRED` | `revision_required` | `incomplete` |
| `RETRY_LIMIT_EXCEEDED` | `retry_limit_exceeded` | `incomplete` |
| `NO_PROGRESS` | `no_progress` | `incomplete` |
| `COST_LIMIT_EXCEEDED` | `cost_limit_exceeded` | `incomplete` |
| `QUESTION_LIMIT_EXCEEDED` | `question_limit_exceeded` | `incomplete` |

- `FinalAssessment.termination_reason`은 필수이며, 해당 실행의 Pipeline 종료 이벤트에는 응답과 같은 Enum 값을 기록한다. 응답과 Trace의 종료 사유는 Runner가 결정한 동일한 값에서 생성한다.
- `ExecutionEvent.termination_reason`은 선택 필드다. 시작·진행·개별 구성 요소 완료 이벤트에는 Pipeline 종료 사유가 없을 수 있으므로 `None`을 허용한다. `EventStatus.COMPLETED`만으로 `ExecutionEndReason.COMPLETED`를 자동 지정하지 않는다.
- `COMPLETED`는 검증 흐름 완료이지 상품의 규제상 적합이나 기관 인증을 뜻하지 않는다.
- `USER_INPUT_REQUIRED`는 이번 실행이 종료됐다는 뜻이며 진단 전체의 완료가 아니다. 사용자 답변 이후 저장 상태를 사용한 재개는 별도 API 계약으로 정의한다.
- 현재 처리되지 않은 예외는 `FinalAssessment`를 생성하지 않는다. 이때 `pipeline_failed` 이벤트는 `status=FAILED`와 오류 코드·실패 단계를 기록하며, 일곱 종료 사유 중 하나로 강제 변환하지 않는다. 예외의 `partial_result`도 자동으로 최종 응답이 되지 않는다.
- `QUESTION_LIMIT_EXCEEDED`: 질문 회차(최대 2회, #310)를 다 쓰고도 질문이 남으면 질문 대신 미완료 결과로 끝낸다(`sessions/manager/runner.py`).
- 세션에서 처리 못 한 예외는 실패 콜백 `AI_PIPELINE_ERROR`(retryable=false), 시간 초과(600초)는 `AI_TIMEOUT`(retryable=true)으로 끝낸다.
- 비용 제한은 Enum 값이 정의됐다고 구현된 것이 아니다. 실제 예산 계산·확인·중단 정책은 별도 작업이다. 신규 종료 사유가 필요하면 공통 Enum과 응답·Trace 소비 계약을 함께 갱신한다.

### 7.1.2 BE 전달용 상품 실행 이벤트(콜백) — 구현됨

위치: `app/schemas/callback.py`(DTO), `app/callbacks/`(이벤트 변환·발신함), `app/clients/backend/callback.py`(전송, #401).
전달 방식: AI → BE `POST /internal/v1/ai/products/{productId}`, 헤더 `X-Internal-Token` (#305·#332). 응답 분류·재시도는 발신함이 맡는다.

| 내부 기록 | BE 전달 |
| --- | --- |
| 세션 이벤트 | 상품 실행의 공개 단계·상태 변화만 선별 |
| 전체 ExecutionContext | diagnosis_id / product_id / run_id만 전달 |
| call_id, 내부 execution_id, component_name, run_type | 비공개 |
| 원본 예외, stack trace, 원문 응답·query | 비공개 |

별도 `ApiModel`(`app/schemas/base.py`, camelCase alias)을 쓴다. 내부 StrictModel·LLM 스키마에 API alias를 적용하지 않는다.

| 이벤트 (`eventType`) | 필드 | 비고 |
| --- | --- | --- |
| 공통 | `eventId`, `diagnosisId`, `productId`, `runId`, `sequence` | eventId는 BE 중복 수신 키. runId는 재진단마다 새로 발급, sequence는 실행마다 1부터 |
| `product_progress` | `stage`, `stageStatus`(started·completed·skipped), `toolName` | toolName은 Tool 실행 단계에서만. BE는 저장하지 않고 표시만 |
| `product_awaiting_input` | `questionRound`(1~2), `questions[]` | 실행의 마지막. 질문 키·순서 중복 금지 |
| `product_result` | `assessment` (§7.1.3) | 실행의 마지막. 진단서를 콜백에 바로 담음 |
| `product_failed` | `stage`, `error{code(≤50자), message, retryable}` | 실행의 마지막 |

질문 `PublicQuestionDto`: `questionKey`(≤50자), `questionOrder`(1부터), `questionText`, `helpText`.

- 질문은 최대 2회차. 2회차에는 1회차에 없던 새 키만 묻는다. 재진단 요청은 이번 회차 질문에 **모두** 답해야 한다(아니면 422).
- `toolName`·카드의 분야 이름은 BE `ToolName` 값: `CUSTOMS`, `CHILDREN`, `ELECTRICAL`, `RADIO`, `FOOD_DRUG`, `LABEL_AD`.
- 처음 제안과 달라진 점: 이벤트별 `status`·`retryRound`·`assessmentId`·`terminationReason`·`verificationStatus` 삭제, `runId` 추가, 질문 형식이 키·순서 기반으로 바뀜, 결과 콜백이 진단서를 직접 담음.

### 7.1.3 BE·FE 전달용 공개 진단서 — 형식 구현됨

위치: `app/schemas/callback.py`의 `PublicAssessmentDto`. 내부 FinalAssessment와 LLM 스키마는 바꾸지 않고 변환기(`AssessmentPresenter`)가 만든다.

| 필드 | 의미 |
| --- | --- |
| `status` | `completed` / `incomplete`. 입력 대기는 질문 콜백으로 따로 나감 |
| `resultStatus` | 결과 상태. `PURCHASING_AGENT_ALLOWED`(구매대행 가능) / `DIRECT_IMPORT_CERTIFICATION_REQUIRED`(사입 인증 필요) / `RECHECK_REQUIRED`(재확인 필요) |
| `summary` | AI가 만드는 공개 요약 |
| `toolReviews[]` | 분야 카드: `toolName`, `status`(COMPLETED·SKIPPED·INCOMPLETE), `message`, `findings[]` |
| `requiredActions[]` | 상품 전체의 할 일 목록. 카드에 나눠 담지 않음 |
| `notices[]` | 미완료 사유·정보 부족·참고 안내 |

판단 `PublicFindingDto`: `subject`(≤255), `determination`, `riskLevel`, `summary`, `rationale`, `legalSources[]`.
근거 `PublicLegalSourceDto`: `sourceName`·`lawName`·`article`(≤255), `quotedText`, `sourceUrl`, `effectiveDate`(≤50). 길이는 BE 수신 DTO·DB 칸과 같고(#331), 넘으면 AI가 잘라서 보낸다.

- 미완료(`incomplete`)는 `notices`가 반드시 있고 `resultStatus`는 `RECHECK_REQUIRED`만 쓴다.
- 같은 분야 카드를 두 번 보내지 않는다. 문자열 칸은 공백만 있으면 안 된다(BE `@NotBlank`).
- 카드 상태: COMPLETED = 해당 분야를 검토함(규제 비대상·안전·인증을 뜻하지 않음), SKIPPED = 이 상품에 해당하지 않아 검토하지 않음, INCOMPLETE = 근거 조회 실패 등으로 검토를 마치지 못함.
- `resultStatus`는 AI가 정해진 규칙으로 정한다(#310, #405). 구현: `app/results/status.py`. 위에서부터 먼저 맞는 것을 쓴다.

| 순서 | 조건 | `resultStatus` |
| --- | --- | --- |
| 1 | 진단 미완료 | `RECHECK_REQUIRED` |
| 2 | 판단 대상 tool에 `REQUIRED`·`POSSIBLY_REQUIRED` 판단이 있음 | `DIRECT_IMPORT_CERTIFICATION_REQUIRED` |
| 3 | 지원 분야 밖 규제 대상 신호: 추출의 `chemical_product`·`weapon_like`·`plant_material` 중 하나라도 `true` (tool 선택과 상관없이) | `RECHECK_REQUIRED` |
| 4 | 판단 대상 tool이 하나도 없음 | `PURCHASING_AGENT_ALLOWED` |
| 5 | 판단 대상 tool 실행 실패(`FAILED`·`PARTIAL`), 또는 정보 부족(`INSUFFICIENT_INFORMATION`이거나 위험도 `UNKNOWN`) | `RECHECK_REQUIRED` |
| 6 | 그 밖 | `PURCHASING_AGENT_ALLOWED` |

  - 표시·광고(`LABEL_AD`)는 판매 방식과 무관한 문구 의무라 결과 상태 계산에서 뺀다. 카드·할 일로 보여 주고, 구매대행 가능인데 표시·광고 판단이 있으면 요약에 "표시·광고 문구는 확인이 필요합니다"를 덧붙인다.
  - 지원 분야 밖 신호가 있으면 결과 상태와 상관없이 `notices`에 확인하지 않는 법령을 안내한다 (화학제품안전법, 총포·도검·화약류법, 식물방역법).
  - 구매대행 가능이면 `notices`에 확인한 분야와 확인하지 않은 범위(생활용품 안전관리, 가스·소방용품 등)를 안내한다.
  - 변환기 `app/results/presenter.py`(`ResultPresenter`)가 6개 분야 카드를 항상 같은 순서로 보내고, 할 일은 분야 순서로 중복 없이 모은다. 서버 조립의 더미 변환기 교체는 #320.
- 공개 가능한 판단·안내를 결정하는 책임은 AI에 있다. BE·FE가 원본 검증 이슈로 판단의 유효성을 재검사하지 않는다.

### 7.1.4 진단 접수·재진단 요청 (BE → AI) — 구현됨

위치: `app/schemas/request.py`, `app/routers/diagnose.py`. 경로 앞부분은 `/api/ai/v1/diagnose`.

| 경로 | 요청 | 응답 |
| --- | --- | --- |
| `POST /content` | `diagnosisId`, `products[]`(1~10개, productId 중복 불가): `productId`, `textBlocks[]`, `imageUrls[]`, `sourceUrl` | 202. 결과는 상품별 콜백 |
| `POST /resume` | `diagnosisId`, `productId`, `runId`(질문으로 끝난 실행), `questionRound`(1~2), `answers[]`: `questionKey`, `answerText`(≤500자) | 202. 새 runId로 다시 실행 |

- **상품 입력 조건(#310 합의)**: 텍스트(`textBlocks`)·이미지(`imageUrls`)·URL(`sourceUrl`) 중 **하나 이상** 있으면 접수한다.
  - URL만 있는 상품의 처리(지원 판매 사이트 수집 #337, 미지원 사이트의 실패 코드)는 파이프라인 연결(#320) 때 정한다.
- 이미지는 URL로 받는다(#389·#403). base64 data URI도 호환으로 받는다.
- 원래 입력·추출 결과·이전 질문과 답변은 AI 세션이 보관한다. BE는 재진단 때 ID와 이번 회차 답변만 보낸다.
- **답변 대기 상품의 재접수(#451)**: 답변 대기 상품이 `/content`로 다시 오면 기다리던 세션을 버리고 새 runId로 1회차부터 실행한다.
  - BE가 실패 처리한 상품을 다시 진단할 때 24시간 보관이 끝날 때까지 409로 막히지 않게 하기 위함이다.
  - 버린 실행의 runId로 온 `/resume`은 `AI_RESUME_CONFLICT`(409)로 거절한다.
  - 접수·실행 중인 상품은 지금처럼 `AI_SESSION_CONFLICT`(409)로 요청 전체를 거절한다.

### 7.2 운영 로그 규칙

| 레벨 | 용도 |
| --- | --- |
| DEBUG | 로컬 상세 진단. 민감한 원문 제외 |
| INFO | 정상 시작·완료·상태 전환 |
| WARNING | 복구 가능한 실패, retry, 기능 저하, 관측 저장 실패 |
| ERROR | 요청·단계를 완료하지 못한 실패 |

공통 컨텍스트와 component / stage를 로그에 연결한다. 운영 JSON과 로컬 text에서 의미를 바꾸지 않는다.

**기록 금지:** API Key, Authorization, Secret, 인증 query 포함 URL, 상품 원문 전체, Prompt·모델 응답 전문. 내부 stack trace는 마스킹해 저장할 수 있지만 외부 응답에 반환하지 않는다.

## 8. 마이그레이션 대응표

| 현재 | 이관 대상 | 단계 | 함께 수정할 대상 | 상태 (10/26) |
| --- | --- | --- | --- | --- |
| Agent별 모델 invoke·parse 처리 | BaseAgent._invoke | M1 | 세 Agent, stub, patch 대상 | 완료 (#364) |
| 기존 Agent 예외의 RuntimeError 상속 | AgentError 상속 | M1 | 생성자 호환, cause, partial_result 테스트 | 완료 (AIError도 상속, #382) |
| 검증 Callback 수집 | include_raw=True + from_response | M1 | parsing_error 검사, 검증 stub, 실패 기록 | 완료 |
| 개별 PROMPT_PATH / lru_cache | get_prompt / PromptSnapshot | M1 | 평가 Runner, health, 캐시 테스트 | 완료 |
| eval.runner의 Agent PROMPT_PATH import | 공용 로더 snapshot.path | M1 | prompt_fingerprint, 평가 metadata | 남음 |
| 검증 from_env의 load_settings 경로 | 공통 모델 생성 경로 | M1 | 설정 cache 테스트. 규칙 전용 생성 유지 | 완료 (`build_agent_model`) |
| Agent별 콘솔 `_log_token_usage()` | Base 공통 출력 유지 | M1 | 로컬 실행 스크립트·Logger 설정·중복 기록 검사 | 완료 (`base/usage_log.py`) |
| Verification 고정 기록 이름 `verification` | 선택적 usage_agent, 기본값 verification | M1 | 생성자·평가 실행·기본 이름 호환 테스트 | 완료 |
| record(agent, usage, ...) | record_usage(UsageRecord, sink=...) | M2 | 전체 Agent, 평가, 집계, 기록 테스트 | 남음 (sink 등록표만 추가, #379) |
| record의 agent | component_name | M2 | 과거 로그 읽기 호환 | 남음 |
| usage_agent="extraction-eval" | component_name="extraction", run_type=evaluation | M2 | 평가 Runner·과거 집계 호환 | 남음 |
| record의 subject_id | context.product_id | M2 | CLI·Pipeline·평가 호출부 | 남음 |
| record의 ok / elapsed_ms | success / latency_ms | M2 | 사용량 adapter·테스트 | 남음 |
| CallUsage.cached_tokens | cached_input_tokens | M2 | estimate_krw, from_response, from_handler, summary | 남음 |
| RetryRequest·ToolResult의 retry_round | ExecutionContext 기준으로 이번 실행 회차 일치 | M2 | Runner·ToolExecutor·기존 회차 검증·과거 이력 보존 | 남음 (컨텍스트는 세션까지만) |
| context 인자 없음 | context 전달 (§4.3) | M2 | Protocol, Runner, CLI, 평가, stub | 남음 |
| 개별 예외 | response_code + stage + retryable | M3 | 오류 목록, API handler, ToolExecutor | API·세션 완료. ToolExecutor·Client 남음 |
| 검증 에이전트 Trace | Pipeline 이벤트 + 내부 Trace 연결 | M4 | Runner, Agent 이벤트, 종료 사유 | 남음 (상품 단위는 세션 이벤트·콜백) |
| 저장 예외 pass | 독립 logger WARNING | 기록 공통화 시 | Handler 설정, Sink 실패 테스트 | 일부 (sink 오류만 WARNING) |

**선행 상태 주의:** #231은 #224 반영 후를 전제한다. 반면 조회 당시 develop의 SelectionAgent에는 사용량 record 처리가 없다. M1은 선행 변경을 반영한 코드를 기준으로 작업해 기록 유실·중복 추가를 방지한다.

### 8.1 과거 로그 읽기 호환

- 과거 agent / subject_id / 평탄한 토큰 필드와 새 UsageRecord를 모두 집계할 수 있게 한다.
- 과거 extraction-eval 행은 알려진 이름에 한해 extraction / evaluation으로 대응시킨다.
- 과거 로그에 없는 run_id·diagnosis_id·prompt_version을 임의로 보완하지 않는다.
- 불명확한 과거 run_type은 집계에서 unknown으로 구분한다. 실행 컨텍스트의 RunType에 unknown을 추가한다는 뜻은 아니다.
- 과거 로그의 null 사용량을 0비용으로 완전 측정한 것처럼 취급하지 않는다. 미측정 건수도 구분한다.

## 9. 이관 PR 확인 항목

| 단계 | 필수 테스트 |
| --- | --- |
| M1 | 세 Agent 성공, invoke 실패, parse 실패, parsed 누락, 모델 stub 주입 |
| M1 | 검증 규칙 전용은 모델 생성·호출 없음. 실패 시 규칙 partial_result 유지 |
| M1 | Agent별 실패 메시지 유지, 원본 cause 직접 연결, 검증 실패 Trace 한 번 추가 |
| M1 | 원인 없는 parsed 누락은 MissingParsedOutput cause·error_type을 사용하며, Agent별 기존 누락 메시지 유지 |
| M1 | 검증 usage_agent 기본값·별도 이름 지원, 콘솔 출력과 사용량 저장 중복 없음 |
| M1 | 범위 검사·병합 실패의 기존 예외 유지. 모델 사용량 중복 기록 없음 |
| M1 | Prompt 본문·지문 일치, CRLF/LF 호환, 캐시 초기화, 평가 임의 path 호환 |
| M2 | 같은 상품 동시 실행 run_id 분리, 0→1→2 retry_round, 부모 context 불변 |
| M2 | 요청·컨텍스트·이번 실행 결과 회차 일치, 미실행 결과·과거 history 회차 보존 |
| M2 / M4 | naive timestamp 거부, timezone-aware 입력의 UTC 정규화 |
| M2 | 사용량 누락·캐시 불명확·단가 불명확, null과 0 구분, 과거 로그 집계 호환 |
| M2 | Sink 실패 시 판정 유지·WARNING. 원래 실패 원인을 저장 실패로 덮어쓰지 않음 |
| M3 | 코드·HTTP·공개 문구 매핑, cause 유지, 원문·stack trace 비공개 |
| M3 | 기존 Agent별 예외·AgentError·RuntimeError catch 호환 및 생성 호출부 이관 |
| M3 | Tool 운영 실패·계약 위반 구분, 같은 원인 retry 중복 없음 |
| M4 | 최초·재실행·입력 대기·상한 종료·예외 종료 Trace, 개별 execution_id 연결 |

파일 이동으로 patch 대상을 변경할 수 있다. 기대 동작을 약화해 테스트를 통과시키지 않는다. 실제 모델 테스트는 보조 확인이며 계약 테스트는 stub / Fake로 재현한다.

## 10. 이 계약에서 결정하지 않는 사항

| 항목 | 별도 확정할 내용 |
| --- | --- |
| 비용 상한 중단 | 상품 / 진단서 단위 상한, 호출 전 추정, 병렬 예약, 실제 중단·결과 반환 정책. 종료 사유 값은 COST_LIMIT_EXCEEDED로 정의됨 |
| 동일 결과 조기 중단 | 비교 대상, 의미적 동일성, 실패 원인별 복구 가능성 |
| 재개 API | ~~답변 후 run_id~~ 새로 발급으로 결정(§2.2, §7.1.4). 세션 영속화(재시작에도 유지)는 남음 |
| AIResponseCode 목록 | ~~채번·HTTP 상태·공개 문구~~ 확정(§6.1). 새 코드(URL 미지원 등)는 추가 시 갱신 |
| Trace 목록 | 구성 요소 단위 이벤트 이름. BE 공개 범위는 콜백(§7.1.2)으로 결정됨 |
| 운영 저장소 | JSONL / stdout / DB, 수집·보관, 다중 process 원자성 |
| Prompt 캐시 갱신 | 재시작 반영 / 명시적 갱신 / 평가 시 처리 |
| SDK retry 측정 | 실제 요청별 usage·비용 수집 범위 |

미결정 사항을 기존 성공·승인 상태로 대체하지 않는다. 구현 필요 시 별도 PR에서 계약을 확장한다.
