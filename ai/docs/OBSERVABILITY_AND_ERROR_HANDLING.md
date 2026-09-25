# AI Observability 및 예외 처리 체계

## 문서 상태

- 상태: `Proposed`
- 목적: AI 파트의 observability와 예외 처리 기준을 합의한다.
- 적용 범위: Model 호출, Agent, Tool, 외부 API Client, Repository, Pipeline

## 1. 배경

현재 사용량 기록, 검증 Trace, Agent별 예외, Tool 실패 결과 등 필요한 기능이 일부 구현되어 있지만, 
각 기능이 서로 다른 시점에 개별적으로 추가되어 다음 문제가 반복되고 있습니다.

- Agent마다 토큰 사용량을 수집하는 방식이 다르다.
- 운영 실행과 평가 실행을 구분할 별도 필드가 존재하지 않는다.
- Pipeline에서 어느 상품의 어느 단계가 실패했는지 일관되게 추적할 장치가 존재하지 않는다.
- 외부 API Client마다 원본 예외를 전달하거나 `RuntimeError`로 변환하는 방식이 다르다.
- 로그 기록 실패를 어디까지 무시하고 어떻게 알릴지 기준이 없다.

이 문서는 특정 구현을 바로 확정하기보다, 이후 PR에서 같은 기준으로 구현하고 리뷰할 수 있도록 공통 용어와 책임 경계를 제안하기 위해 작성되었습니다.

## 2. 현재 구현에서 확인한 사항

### 2.1 사용량 기록

`app/usage.py`는 모델명, 토큰 수, 예상 비용, 지연 시간, 성공 여부 등을 JSONL로 기록합니다. 
Verification Agent는 `UsageMetadataCallbackHandler`를 사용하고, Extraction Agent는 `include_raw=True'옵션을 사용하여 사용량을 읽고 있습니다.

현재 기록에는 다음과 같은 공통 정보가 필요해 보입니다.

- 하나의 Pipeline 실행을 연결하는 `run_id`
- 진단서와 상품을 구분하는 `diagnosis_id`, `product_id`
- 운영·평가·테스트를 구분하는 `run_type`
- 최초 실행과 재실행을 구분하는 `retry_round`
- 프롬프트 변경 전후를 구분하는 `prompt_version`
- Pipeline 단계 또는 실제 실행 주체를 나타내는 `component`

또한 사용량 기록 실패를 모두 무시하므로 본 요청은 보호되지만, 관측 데이터가 유실됐다는 사실도 확인하기 어렵습니다.

### 2.2 실행 Trace

Verification Agent는 규칙 검사와 모델 검토 과정에서 `TraceEvent`를 생성합니다. 반면 Extraction, Selection, ToolExecutor, Aggregator, Pipeline Runner에는 동일한 Trace 계약이 적용되어 있지 않습니다.

Verification에서 기록되는 Trace는 해당 Agent 내부 판단 과정을 설명하는 데 유용할 수는 있지만, 전체 요청 관점에서는 다음 흐름도 연결되어야 한다고 봅니다.

```text
Pipeline 시작
→ Extraction
→ Selection
→ Tool 실행
→ Aggregation
→ Verification
→ 승인 / 사용자 입력 대기 / 수정 필요 / Tool 재실행
→ Pipeline 종료
```

따라서 개별 Agent가 전체 Trace를 관리하기보다 Pipeline이 전체 실행 흐름을 소유하고, 각 구성 요소가 공통된 형식의 이벤트를 제공하는 방향이 좋아보입니다.

### 2.3 예외 처리

현재 Agent 예외는 원인을 `raise ... from exc`로 보존하고 있으며, Verification은 실패 시 규칙 검사 결과를 `partial_result`로 보존합니다.

반면 다음 경계는 일관되지 않습니다.

- ToolExecutor는 Tool 실행 중 발생한 넓은 범위의 `Exception`을 `ToolResult.FAILED`로 변환합니다.
- 외부 API Client는 `httpx.HTTPStatusError`를 그대로 전달하거나 `RuntimeError`로 변환합니다.
- Pipeline Runner는 단계별 예외를 보강하지 않고 상위로 전달합니다.
- API 응답에 노출할 메시지와 내부 원인·Stack Trace의 경계가 정의되지 않았습니다.

특히 다음 두 실패는 구분해야 합니다.

1. 외부 API 타임아웃처럼 운영 중 발생 가능한 실패
2. 실행한 Tool과 반환된 `tool_name`이 다른 것처럼 코드 계약이 깨진 실패

두 경우를 모두 정상적인 Tool 실패 결과로 바꾸면 서비스는 계속될 수 있지만, 프로그래밍 오류가 숨겨질 수 있습니다.

### 2.4 평가 메타데이터

PR #143에서 평가 메타데이터를 다뤄주셨습니다.

평가 결과에는 모델, 프롬프트 경로·Hash, Git Commit, Dirty 상태, 실행 횟수 등이 기록되고 있습니다.
이는 운영 사용량과 목적이 다르므로 별도 기록으로 유지하는 것이 적절해 보입니다.

다만 평가 실행도 실제 모델 호출의 일부이므로 공통 `run_id` 또는 `eval_run_id`를 사용해 평가 결과와 사용량 기록을 연결할 수 있어야 할 것 같습니다.

## 3. 용어와 책임 구분

관측에 필요한 정보를 하나의 파일이나 객체에 모두 넣지 않고 목적에 따라 구분합니다.

| 구분 | 목적 | 주요 내용 |
| --- | --- | --- |
| 운영 로그 | 개발·운영 중 상태와 실패 원인 확인 | 단계, 로그 수준, 오류 코드, 지연 시간 |
| 사용량 지표 | 비용·토큰·모델 호출 성능 측정 | 입력·출력 토큰, 비용, 모델, 성공 여부 |
| 실행 Trace | 한 요청의 비즈니스 흐름 재구성 | 단계 시작·완료, 분기, 재실행, 사용자 입력 대기 |
| 평가 메타데이터 | 평가 결과의 재현과 비교 | Fixture 버전, Prompt 버전, Git Commit, 실행 횟수 |
| 예외 | 실패 전파와 복구 정책 결정 | 오류 유형, 재시도 가능 여부, 부분 결과, 원인 |

이 정보들은 역할은 다르지만 공통 실행 식별자를 통해 연결합니다.

## 4. 공통 실행 컨텍스트 제안

각 Agent가 개별적으로 식별자를 만들지 않고 Pipeline 진입 시 생성한 실행 컨텍스트를 하위 구성 요소에 전달합니다.

| 필드 | 의미 |
| --- | --- |
| `run_id` | 상품 하나에 대한 Pipeline 실행 식별자 |
| `diagnosis_id` | 여러 상품을 포함할 수 있는 진단서 식별자 |
| `product_id` | 대상 상품 식별자 |
| `run_type` | `production`, `evaluation`, `test` 구분 |
| `retry_round` | 최초 실행은 `0`, 재검증·재실행 시 증가하는 회차 |

구성 요소가 기록하는 이벤트에는 다음 정보를 추가합니다.

| 필드 | 의미 |
| --- | --- |
| `component_type` | `agent`, `tool`, `client`, `repository`, `pipeline` |
| `component_name` | `extraction`, `selection`, `radio_tool` 등 실제 실행 주체 |
| `stage` | Pipeline 내 실행 단계 |
| `status` | `started`, `completed`, `failed`, `skipped`, `awaiting_input` 등 |
| `timestamp` | 이벤트 발생 시각 |
| `latency_ms` | 해당 작업의 소요 시간 |

Tool 단위 실행은 기존 `execution_id`가 있다면 함께 기록합니다.

stage는 다음과 같이 별도 문자열이 아닌 enum으로 제한할 생각입니다.
```python
class PipelineStage(StrEnum):
    PIPELINE = "pipeline"
    EXTRACTION = "extraction"
    SELECTION = "selection"
    TOOL_EXECUTION = "tool_execution"
    AGGREGATION = "aggregation"
    VERIFICATION = "verification"
    FINALIZATION = "finalization"
```

### 식별자 생성 책임 제안

- BE가 제공한 진단서 식별자는 `diagnosis_id`로 사용합니다.
- 상품 식별자는 요청의 `product_id`를 사용합니다.
- `run_id`는 Pipeline이 상품별 실행을 시작할 때 생성합니다.
- 재실행은 같은 `run_id` 안에서 `retry_round`를 증가시키는 것을 기본으로 합니다.
- 사용자 응답 이후 완전히 새로운 요청으로 재개하는 경우 같은 `run_id`를 유지할지는 API 재개 계약과 함께 결정합니다.

## 5. 사용량 기록 기준 제안

### 5.1 수집 방식

수집 구현은 모델 호출 형태에 맞게 나눌 수 있습니다.

- 원본 응답을 받을 수 있는 Agent: `from_response(raw_response)`
- Callback 기반 Agent: `from_handler(callback_handler)`

두 방식은 최종적으로 동일한 `CallUsage` 형식으로 변환할 생각입니다.
```python
from_response(raw_response)

{
    "input_tokens": 100,
    "output_tokens": 20,
    "model": "gpt-4.1-mini",
}
```
```python
from_handler(callback_handler)
{
    "gpt-4.1-mini": {
        "input_tokens": 100,
        "output_tokens": 20,
    }
}
```
위처럼 다른 형식의 로그를 아래 `CallUsage`로 변환합니다.
```python
CallUsage(
    reported_model="gpt-4.1-mini",
    input_tokens=100,
    cached_tokens=0,
    output_tokens=20,
)
```
```
Raw Response ─── from_response() ─┐
                                  ├─→ CallUsage
Callback Handler ─ from_handler() ┘
```
### 5.2 기록 책임

- 사용량은 실제 모델을 호출한 Agent가 한 번만 기록합니다.
- Pipeline Runner나 평가 Runner는 같은 호출을 다시 기록하지 않습니다.
- Pipeline은 실행 컨텍스트를 전달하고 전체 집계가 필요할 때 기존 기록을 조회하거나 합산합니다.
- 평가와 운영은 Agent 이름을 바꾸지 않고 `run_type`으로 구분합니다.

예를 들어 `extraction-eval`이라는 Agent 이름을 만들기보다 다음과 같이 기록하는 것을 생각중입니다.

```
component_name = extraction
run_type = evaluation
```

### 5.3 모델 호출 1건을 저장하는 UsageRecord 필드

UsageRecord는 CallUsage 와 실행 정보, 그리고 호출 결과를 종합한 객체입니다.
필드는 아래와 같이 구성할 생각입니다.

- 공통 실행 컨텍스트
- `component_name`
- `configured_model`
- `reported_model`
- `input_tokens`
- `cached_input_tokens`
- `output_tokens`
- `total_tokens`
- `estimated_cost_krw`
- `latency_ms`
- `success`
- `error_code` 또는 `error_type`
- `prompt_version`


### 5.4 기록 실패 정책

사용량 기록 실패가 상품 진단 결과까지 실패시키지 않아야 합니다. 다만 현재처럼 완전히 무시하면 데이터 유실을 알 수 없으므로 별도의 Fallback 경고를 남깁니다.

Fallback 경고는 실패했을 때와 같은 저장 경로를 다시 사용하지 않아야 합니다. 
구체적으로 표준 오류 출력, 별도 운영 Logger 중 어느 방식을 사용할지는 배포 환경을 확인한 뒤 결정합니다.

JSONL은 로컬 개발과 초기 검증에는 적합하다고 생각합니다. JSONL을 사용했을 때 지난 번 리뷰에서 다뤘듯이 동일 프로세스 내 동시 실행 테스트에서는 기록이 분리됐지만, 다중 Process·다중 Instance 환경에서는 확인되지 않았기에 원자성과 내구성이 보장된다고 간주하지 않아야 합니다. 이 부분도 확인이 필요합니다.

배포 환경이 확정되면 JSONL을 유지할지, 표준 출력 기반 구조화 로그 또는 DB 저장 방식으로 변경할지 다시 결정하면 될 것 같습니다.

## 6. 예외 계약 제안

### 6.1 공통 예외가 제공해야 할 정보

AI 파트에서의 공통 예외는 최소한 다음 정보를 제공해야 한다고 생각합니다.

- `error_code`: 코드에서 안정적으로 분기할 수 있는 값
- `stage`: 실패한 Pipeline 단계
- `retryable`: 같은 입력으로 재시도할 수 있는지 여부
- `public_message`: 외부에 공개해도 되는 메시지
- `partial_result`: 실패 전까지 생성된 결과가 있을 때 보존하는 값
- 원본 예외: `raise ... from exc`를 사용해 내부 원인을 보존
```python
class AIServiceError(Exception):
    def __init__(
        self,
        *,
        error_code: str,
        stage: str | None = None,
        retryable: bool = False,
        public_message: str = "AI 처리 중 오류가 발생했습니다.",
        partial_result: object | None = None,
    ) -> None:
        super().__init__(public_message)
        self.error_code = error_code
        self.stage = stage
        self.retryable = retryable
        self.public_message = public_message
        self.partial_result = partial_result
```
error코드도 가능하면 문자열이 아닌 별도의 enum으로 관리하면 좋을 것 같습니다.
```python
class ErrorCode(StrEnum):
    MODEL_TIMEOUT = "model_timeout"
    MODEL_OUTPUT_INVALID = "model_output_invalid"
    EXTERNAL_API_UNAVAILABLE = "external_api_unavailable"
    TOOL_CONTRACT_VIOLATION = "tool_contract_violation"
```
모든 오류마다 클래스를 새로 만들면 너무 많아질 것 같고, 그렇다고 AIServiceError같은 공통 오류로 다 처리하면, 다시 구분하기 어려워질 것 같습니다. 
그래서 다음과 같은 상위 분류를 공통 코드나 하위 예외 타입으로 표현하면 좋을 것 같습니다.

- config 오류
- 입력 검증 오류
- 모델 호출 오류
- Structured Output 변환 오류
- 외부 API 오류
- Tool 실행 오류
- 내부 계약 위반
- Repository 오류
- Pipeline 실행 오류

### 6.2 실패 유형별 처리 원칙

| 실패 유형 | 처리 방향 | 재시도 |
| --- | --- | --- |
| 사용자 입력 형식 오류 | 요청 거절, 공개 가능한 원인 반환 | 하지 않음 |
| 모델 Timeout·Rate Limit | 모델 호출 오류로 변환하고 기록 | 오류 종류에 따라 제한적으로 수행 |
| Structured Output 변환 실패 | 변환 오류로 구분하고 원본 원인 보존 | 제한 횟수 내 검토 |
| 외부 API Timeout·5xx | 외부 API 오류로 변환 | 가능 |
| 외부 API 인증·권한·일반 4xx | 비재시도 오류로 구분 | 원칙적으로 하지 않음 |
| Tool의 예상 가능한 운영 실패 | `ToolResult.FAILED`로 보존하고 원인 기록 | 정책에 따라 수행 |
| Tool 반환값 계약 위반 | 내부 계약 오류로 즉시 드러냄 | 자동 재시도하지 않음 |
| DB 저장 실패 | Transaction Rollback 후 Repository 오류 | 원인에 따라 결정 |
| 관측 데이터 기록 실패 | 본 작업은 유지하고 Fallback 경고 | 저장 방식에 따라 결정 |
| Pipeline 단계 실패 | 단계·실행 컨텍스트·부분 결과를 포함해 상위 전달 | 원인에 따라 결정 |

### 6.3 ToolExecutor에서 오류 구분

예시로 ToolExecutor는 다음을 같은 `except Exception`에서 처리하지 않는 방향으로 수정할 계획입니다.

- Tool 내부의 예상 가능한 외부 연동 실패
- Tool이 잘못된 이름이나 상태를 반환한 계약 위반
- 코드 결함으로 발생한 예상하지 못한 예외

예상 가능한 Tool 실패는 결과 객체로 보존할 수 있지만, 
계약 위반은 조용히 실패 결과로 바꾸지 않고 테스트와 운영 로그에서 즉시 드러나게 설계할 생각입니다.

## 7. Pipeline Trace 기준 제안

Trace는 Debug 로그의 모음이 아니라 한 상품 진단이 어떤 상태를 거쳤는지 나타내기 위한 기록입니다.

Pipeline이 전체 Trace의 소유자가 되고, 각 구성 요소는 공통 형식의 이벤트를 추가합니다.

주요 이벤트 예시는 다음과 같습니다.

```
pipeline_started
stage_started
stage_completed
stage_failed
tool_execution_started
tool_execution_completed
tool_retry_requested
verification_completed
awaiting_user_input
pipeline_completed
pipeline_failed
```

각 이벤트는 공통 실행 컨텍스트와 구성 요소 정보를 포함합니다. 
자유 형식의 `detail`만 남기기보다 오류 코드, 요청 Tool, 상태 변경 등 검색할 값은 구조화된 필드로 기록합니다.

일단 Verification Agent의 기존 Trace는 제거 대상이 아닙니다.
Verification 내부 이벤트를 전체 Pipeline Trace에 연결하거나, 
Agent 내부 Trace로 유지하되 같은 `run_id`를 부여하는 두 방법을 비교하고 결정하겟습니다.

Trace에는 다음 내용을 기본적으로 저장하지 않습니다. 필요하다면 추가는 할 수 있지만 필수가 아닙니다.

- 전체 상품 원문
- 모델에 전달한 전체 Prompt와 응답
- 인증 정보와 API Key
- 모델의 비공개 추론 과정

약식으로 확인해봤을 때 trace가 너무 길어지면 파악이 힘들 것 같아서 정보를 최소화하는 방향을 택했습니다.
이외에도 더 최소화할 수 있는 방법이 있다면 채택할 생각이 있습니다.

필요한 근거는 식별자, Hash, 길이, 결과 요약처럼 최소 정보로만 기록합니다.

## 8. 운영 로그 기준 제안

### 로그 수준

- `DEBUG`: 로컬 진단에 필요한 세부 정보. 민감한 원문은 제외한다.
- `INFO`: Pipeline·Agent·Tool의 시작, 완료, 정상적인 상태 전환
- `WARNING`: 복구 가능한 실패, 재시도, 기능 저하, 데이터 기록 실패
- `ERROR`: 요청 또는 단계를 완료하지 못한 실패

### 로그에 포함할 정보

- 공통 실행 컨텍스트
- 구성 요소와 단계
- 이벤트와 상태
- 소요 시간
- 오류 코드와 재시도 가능 여부
- 재실행 회차

### 로그에 포함하지 않을 정보

- API Key, Authorization Header, Secret
- Key가 Query Parameter에 포함된 원본 URL
- 상품 상세페이지 전체 원문
- 모델 Prompt·응답 전문

내부 Stack Trace는 오류 분석을 위해 운영 로그에 기록할 수 있습니다.
다만 인증 정보나 상품 원문이 포함되지 않도록 마스킹해야 하며,
BE·FE에 반환하는 API 오류 응답에는 Stack Trace를 노출하지 않습니다.

운영 환경은 JSON 구조화 로그, 로컬 환경은 읽기 쉬운 Text 형식을 사용할 수 있게 설계합니다.

어떻게보면 trace와 역할이 겹칠수도 있지만, trace는 정해진 상태 변화만 남기고, 운영 로그는 분석에 필요한 설명을 더 남길 수 있기에 더 자유롭다고 생각하면 될 듯합니다.

## 9. 평가 기록과 사용량 기록의 관계

평가 메타데이터와 운영 사용량은 서로 다른 목적으로 저장합니다.

평가 메타데이터에는 다음 정보를 유지합니다.

- 평가 Suite·Fixture 버전
- 모델과 실행 횟수
- Prompt 경로와 Hash 또는 버전
- Git Commit과 Dirty 상태
- 평가 결과와 주요 지표

모델 호출 사용량은 공통 사용량 체계를 사용하되 `run_type=evaluation`으로 기록한다. 평가 결과와 사용량을 `run_id` 또는 `eval_run_id`로 연결하면 프롬프트별 품질·비용·지연 시간을 함께 비교할 수 있습니다.

`prompt_version`은 파일 경로만으로 표현하지 않으며, 파일 이동과 내용 변경을 구분할 수 있도록 내용 Hash를 기본으로 사용하고,
사람이 이해할 Semantic Version처럼 별도 버전을 추가할지는 별도로 결정합니다. 이 부분은 결국 사람이 관리하는 사항이기에 누락될 가능성을 배제할 수는 없다고 판단하여 과제로 남겻습니다.

## 10. 단계별 적용 순서

지금까지 정리한 사항은 모든 코드를 한 PR에서 변경하지 않고 다음 순서로 나누어서 작업합니다.
이 문서가 승인 됐을 때를 전제로 합니다.

1. 공통 실행 컨텍스트와 필드 명세 확정
2. 공통 예외 계약 및 오류 코드 정의
3. 사용량 Adapter와 공통 Record 형식 정리
4. Extraction·Selection·Verification의 사용량 기록 통일
5. 외부 API Client와 ToolExecutor의 예외 경계 정리
6. Pipeline 단계별 Trace 및 부분 결과 보존 구현
7. API 예외 응답 매핑 정의
8. 배포 환경의 구조화 로그와 저장 방식 확정
9. 동시 실행·재실행·부분 실패 통합 테스트 추가

각 단계는 기존 동작을 보존하는 테스트와 함께 별도 이슈·PR로 진행합니다.

## 11. 논의가 필요한 사항

문서에서 제안된 방식에 대한 모든 것들이 논의 대상입니다.

구체적인 사항들은 아래와 같이 정리해봤습니다.

- [ ] 사용자 답변 후 Pipeline을 재개할 때 기존 `run_id`를 유지할 것인가?
- [ ] Trace를 내부에서만 사용할지, BE·FE에도 일부 제공할지 결정.
- [ ] 운영 로그와 사용량 기록을 JSONL, 표준 출력, DB 중 어디에 저장할지 결정.
- [ ] 관측 데이터 저장 실패 시 사용할 Fallback 경로를 결정한다.
- [ ] Tool의 계약 위반을 즉시 실패시킬지, 실패 결과로 보존할지 확정한다.
- [ ] 재시도 정책을 Pipeline, Tool, Client 중 어느 계층이 소유할지 확정한다.
- [ ] `prompt_version`을 Hash만 사용할지 별도 버전을 함께 사용할지 결정한다.
- [ ] 사용자 입력과 모델 입출력 중 운영 환경에 저장할 수 있는 범위를 확정한다.
- [ ] API에 공개할 공통 오류 코드와 메시지 형식을 BE·FE와 합의한다.

## 12. 완료 기준

다음 조건을 만족하면 공통 체계가 적용된 것으로 봅니다.

- 한 상품의 Pipeline 실행을 `run_id`로 처음부터 끝까지 추적할 수 있다.
- 다상품 진단에서도 `diagnosis_id`와 `product_id`로 실행을 구분할 수 있다.
- 운영·평가·테스트 기록이 이름 규칙이 아닌 명시적인 필드로 구분된다.
- 한 번의 모델 호출이 중복 없이 한 번만 사용량으로 기록된다.
- 실패한 단계, 오류 유형, 재시도 가능 여부, 부분 결과를 확인할 수 있다.
- 예상 가능한 운영 실패와 내부 계약 위반을 구분할 수 있다.
- API 응답에는 안전한 메시지만 노출되고 내부 원인은 보존된다.
- 로그와 Trace에 인증 정보와 불필요한 원문이 남지 않는다.
- 동시 실행, 재실행, 부분 실패 상황을 자동화된 테스트로 검증한다.


---
이 문서는 안건이 완료되기 전까지 계속 수정될 예정이며, 완료되면 확정된 사항을 바탕으로 재구성합니다.