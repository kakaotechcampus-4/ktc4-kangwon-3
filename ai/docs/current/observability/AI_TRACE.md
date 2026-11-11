# 진단 trace

진단 한 건이 단계마다 무엇을 받아 무엇을 출력하였는지 로컬 JSON 파일로 기록하는 도구이다. 에이전트·Tool·프롬프트를 수정할 때 동일한 입력으로 수정 전후를 비교하는 데 사용한다. 서버 로그는 [AI_LOGGING.md](AI_LOGGING.md)를 참고한다.

## 1. 서버 로그와 차이

| | 서버 로그 | trace |
|---|---|---|
| 기록 대상 | 서버 실행 전체 | 로컬 CLI로 실행한 진단 |
| 기록 내용 | 진단 흐름의 주요 지점별 한 줄 | 단계 결과·모델 호출 입출력 원문·Tool 내부 판단 근거 |
| 상품 원문·모델 응답 | 기록하지 않음 | 기록함 |
| 저장 위치 | `docker logs` | `logs/traces/` 아래 JSON (git 추적 제외) |

- 서버에는 기록기가 없으므로 trace 코드는 아무 동작도 하지 않는다. 기록은 `trace_run()`으로 감싼 블록 안에서만 이루어진다.
- 기록기는 문맥 변수로 조회하므로 단계·Tool 코드는 기록기를 인자로 전달받지 않는다.

## 2. 실행

`ai/` 폴더에서 실행한다. 서버·세션 관리자·BE 콜백을 거치지 않고 진단 함수만 실행한다.

- 모델·외부 API를 실제로 호출하므로 `.env`의 키가 필요하며 비용이 발생한다.
- `DATABASE_URL`이 없어도 실행된다. 이때 관세 Tool은 CLIP만 조회한다.
- 실행 종류(`run_type`)는 `evaluation`이다.
- 기록 중에는 Tool을 하나씩 순차 실행한다. 기록기가 열린 단계와 진행 중인 호출을 하나의 객체로 관리하기 때문이다. 그러므로 실행 시간은 서버와 다르다.

### 2.1 처음부터

```bash
venv/bin/python -m app.diagnosis.trace_cli logs/trace-inputs/kc-fan.json
```

입력 파일은 `/diagnose` 요청의 상품 하나와 동일한 형식이다. `productId`가 없으면 파일 이름을 사용한다.

```json
{
  "textBlocks": ["무선 선풍기 USB 충전식", "정격전압 5V"],
  "imageUrls": ["https://example.com/1.jpg"],
  "sourceUrl": "https://example.com/products/1"
}
```

- 저장 위치는 `logs/traces/<입력 파일 이름>/run-N.json`이며, 번호는 폴더의 마지막 번호 다음 번호이다. `--out`으로 폴더를 변경할 수 있다.
- 터미널에는 단계·Tool 진행, 결말, 질문을 출력하고 마지막 줄에 trace 파일 경로를 출력한다.

### 2.2 질문에 답해 재진단

```bash
venv/bin/python -m app.diagnosis.trace_cli logs/trace-inputs/kc-fan.json --answer r1_q1=네 --answer r1_q2=아니요
```

- 같은 폴더의 마지막 실행이 질문을 남기고 멈춘 실행이어야 한다. 그 파일의 최종 결과·질문·이전 답변으로 재진단 입력을 구성한다.
- 해당 회차의 질문에 모두 답해야 한다(서버와 동일한 규칙). 답변이 누락되거나 다른 키가 있으면 거절한다.

### 2.3 단계 다시 실행

```bash
# run-1의 추출 결과를 그대로 쓰고 선택부터 끝까지
venv/bin/python -m app.diagnosis.trace_cli --from logs/traces/kc-fan/run-1.json --stage selection
# 선택 단계 하나만 돌리고 멈춤
venv/bin/python -m app.diagnosis.trace_cli --from logs/traces/kc-fan/run-1.json --stage selection --only
```

- 실행 입력은 이전 trace의 추출 단계 `input`에서 읽으므로 입력 파일이 필요하지 않다.
- 시작 단계 이전의 단계는 이전 trace의 결과를 사용하며, 해당 단계에 `replayed: true`를 기록한다.
- 저장된 결과는 첫 회차(round 0)만 사용한다. Tool 재실행 회차는 앞 결과에 의하여 달라지므로 항상 실제로 실행한다.
- 결과는 이전 trace와 동일한 폴더에 다음 번호로 저장하고, `info.replay`에 원본 파일과 시작 단계를 기록한다.
- `--only`를 지정하면 시작 단계를 마친 뒤 멈추며, 결말은 `{"reason": "stopped", "stage": ...}`이다.
- 단계: `extraction` → `selection` → `tool_execution` → `aggregation` → `verification`
- 앞 단계 모델 출력이 실행마다 달라지는 흔들림을 고정하고 한 단계만 비교할 때 사용한다.

### 2.4 옵션 규칙

- 입력 파일과 `--from`은 둘 중 하나만 지정한다.
- `--from`에는 `--stage`가 필요하며 `--answer`는 사용할 수 없다.
- `--stage`·`--only`는 `--from`과 함께 사용한다.
- 옵션 오류, 입력 파일 오류, 다시 실행 오류는 종료 코드 2를 반환하고, 정상 종료는 0을 반환한다.

## 3. 파일 구조

실행 하나를 파일 하나로 저장한다.

```json
{
  "run": "run-1",
  "info": {"source": "logs/trace-inputs/kc-fan.json"},
  "steps": [
    {"id": "s1", "kind": "extraction", "input": {...}, "output": {...}, "calls": [...]},
    {"id": "s2", "kind": "selection", "output": {...}, "calls": [...]},
    {"id": "s3", "kind": "tool_execution", "round": 0, "output": {...}, "steps": [
      {"id": "s4", "kind": "tool", "tool": "electrical_safety", "selected": true, "result": {...}}
    ]},
    {"id": "s9", "kind": "aggregation", "round": 0, "output": {...}},
    {"id": "s10", "kind": "verification", "round": 0, "output": {...}, "calls": [...]}
  ],
  "finish": {"reason": "completed", "result": {...}},
  "prompts": {"3f2a9c1d0b7e": "시스템 프롬프트 원문"}
}
```

(값은 형식 설명을 위한 예시이다)

| 키 | 내용 |
|---|---|
| `info` | 실행 정보(입력 출처, 다시 실행 정보). 열린 단계 밖에서 기록한 값도 여기에 포함된다 |
| `steps` | 단계. 실행 순서대로 기록하며 단계 안에 하위 단계(`steps`)를 둔다 |
| `finish` | 결말 |
| `prompts` | 시스템 프롬프트 원문(지문 → 원문). 호출에는 지문만 기록한다 |

- ID는 실행 안에서 생성된 순서대로 부여한다(`s1`, `c1`, …). 동일한 입력이면 동일한 ID가 부여되므로 diff로 비교할 수 있다.
- 실행마다 새로 생성하는 ID(uuid)도 실행 내 번호로 바꾸어 저장한다. 판단 ID `f1`·`f2`…, Tool 실행 ID `e1`…, 진단서 ID `a1`, 검증 지적 ID `i1`…, 재질문 ID `q1`…이며, 검증 호출 본문 속 ID도 함께 바뀐다.
- 이미지는 링크만 기록한다. 링크가 없는 data URI(긴 이미지 조각)는 본문 대신 `data:image/jpeg;base64,…(생략)`으로 기록한다.

### 3.1 단계

| `kind` | 기록 내용 |
|---|---|
| `extraction` | `input`(실행 입력 전체: 원래 입력·이전 결과·답변), `output`(답변 반영 후 상품 정보), `seller_region`(판매자 영역 자르기), `postprocess`(후처리로 바뀐 값), `image_split`(이미지별 자르기 결과) |
| `selection` | `output`(Tool 6개 선택 결과) |
| `tool_execution` | `round`, `output`(선택 내역·Tool 결과), 하위 `tool` 단계 |
| `tool` | `tool`·`selected`·`reason`, `result`(상태·판단 요약·재질문·할 일). 근거 조회형 Tool은 아래 값도 기록한다 |
| `aggregation` | `round`, `output`(종합 초안) |
| `verification` | `round`, `output`(검증 결과). 모델 검토가 실패하여 규칙 검사 결과로 진행한 경우 `model_review_error`(실패 원인) |

- 다음 단계의 입력은 앞 단계의 `output`이므로 별도로 기록하지 않는다(추출 단계 `input`만 기록).
- 재실행 회차는 `round` 1, 2, …의 `tool_execution`·`aggregation`·`verification`이 이어서 기록된다.
- 선택되지 않은 Tool은 Tool 실행기가 실행하지 않으므로 `tool` 단계가 기록되지 않는다. 미선택 내역과 `skipped` 상태는 `tool_execution`의 `output`에 남는다.

근거 조회형 Tool(관세·전파·식품의약·전기·어린이)의 `tool` 단계:

| 키 | 내용 |
|---|---|
| `snippet_ids` | 모델에 제시한 원문 조각 ID |
| `facts` | 상품 조건 대조. `kept`(사용한 조건), `dropped`(제외한 조건) |
| `picks` | 후보 선택마다 `candidates`(후보 ID)와 `selections`(선택별 `outcome`) |
| `conflicted`·`assumptions`·`query` | 충돌한 조건, 가정, 조회 기록 |

`picks`의 `outcome`: `chosen`(채택) · `not_applicable`(해당 없음) · `not_in_candidates`(후보에 없는 ID) · `duplicate`(중복) · `no_confirmed_fact`(확인된 조건 없음) · `rule`(코드 규칙으로 제외) · `over_limit`(개수 상한 초과).

표시·광고 Tool의 `tool` 단계에는 `claims`를 기록한다. `kept`(유지한 주장), `dropped_quotes`(원문에 없어 제외한 인용), `kc_added`(코드로 추가한 KC 주장)로 구성된다.

`image_split`의 이미지별 `result`: `split`(조각으로 나눔, 조각 수) · `not_split`(짧은 이미지이거나 받기·읽기에 실패한 경우이며, 두 경우는 구분하지 않음) · `over_limit`(긴 이미지이나 상품당 조각 상한을 초과하여 원래 주소를 사용).

### 3.2 모델 호출

모델 호출은 호출 시점에 열린 단계의 `calls`에 원문 그대로 기록한다. 열린 단계가 없으면 `info.calls`에 기록한다.

| 키 | 내용 |
|---|---|
| `id`·`component` | 호출 ID(`c1`, …), 에이전트 이름 |
| `request` | 보낸 메시지(시스템 프롬프트는 지문만) 또는 판단 모델 요청 |
| `output` | 스키마로 검증한 출력. 해석에 실패하면 `null` |
| `raw` | 해석에 실패하였거나 잘린 응답 본문 |
| `error` | 호출 실패 원인 |
| `meta` | 모델·토큰·비용·시간 등 실행마다 달라지는 값 |

### 3.3 결말

| `reason` | 함께 기록되는 값 |
|---|---|
| `completed`·`revision_required`·`retry_limit_exceeded`·`no_progress` 등 종료 이유 | `result`(최종 결과) |
| `user_input_required` | `result`, `question_round`, `questions` |
| `failed` (단계 실패) | `stage`·`code`·`retryable`, `error`, `at` |
| `error` (그 밖의 예외) | `error`, `at` |
| `stopped` (`--only`) | `stage` |

실패 위치는 다음과 같이 기록한다.

- 예외가 처음 전파된 가장 안쪽 단계: `error`에 예외 이름·메시지·원인(`cause`)을 기록하고, 호출 실패이면 호출 ID(`call`)도 기록한다.
- 그 바깥 단계: 동일한 예외(또는 `raise ... from`으로 감싼 예외)이면 `{"type", "from": 처음 실패한 단계 ID}`만 기록한다.
- `finish.at`: 처음 실패한 단계의 ID·종류·경로(`path`)·호출 ID를 기록한다.

## 4. 비교

`meta`(시간·토큰·비용)는 실행마다 달라지므로 제외하고 비교한다.

```bash
diff <(jq -S 'del(.. | .meta?)' logs/traces/kc-fan/run-1.json) \
     <(jq -S 'del(.. | .meta?)' logs/traces/kc-fan/run-2.json)
```

단계 하나만 비교하는 경우:

```bash
jq '.steps[] | select(.kind == "selection") | .output' logs/traces/kc-fan/run-1.json
```

## 5. 주의

- trace 파일에는 상품 원문·모델 응답 원문이 포함되며, 예외 메시지 속 URL의 키도 가리지 않는다. 그러므로 `logs/` 밖으로 옮기거나 공유하지 않는다. 입력 파일도 `logs/trace-inputs/`처럼 git이 무시하는 위치에 둔다.
- 파일 쓰기에 실패하면 경고 로그만 기록하며, 진단 결과와 예외는 영향을 받지 않는다.
- 저장된 결과는 기록 당시의 스키마 형식이다. 스키마가 바뀐 뒤 이전 trace로 단계를 다시 실행하면 읽기 오류가 발생한다.
- 재진단과 단계 다시 실행은 이전 결과를 trace 파일에서 읽으므로 판단·진단서 ID 등이 이미 `f1`, `a1` 형식의 번호이다. 새 실행은 그 번호 다음부터 부여한다(이전 실행이 `f5`까지이면 새 판단은 `f6`부터).

### 5.1 개발자 참고

- 이미지 자르기 기록(`app/diagnosis/tracing.py`)은 `ImageSplitter`의 내부 메서드(`_tiles`)·값(`_max_tiles`)에 의존하며, 상한 판단을 동일한 순서로 다시 계산한다. `ImageSplitter`를 수정하면 함께 확인한다.
- 파이프라인 단계 기록은 단계 hook(`app/diagnosis/tracing.py`·`replay.py`)으로 연결한다. hook 순서는 `app/diagnosis/job.py`의 `_stage_hooks` 한 곳에서 정하며, 바깥부터 재실행 회차 로그 표시 → 진행 알림 → 다시 실행 멈춤 → trace → 다시 실행 건너뛰기 → LangSmith 순이다. 다시 실행 hook 2개는 단계 다시 실행에서만, LangSmith hook은 LangSmith를 켠 경우에만 포함된다. 순서를 바꾸면 `replayed` 표시와 멈춤 결말의 위치가 달라진다.

## 6. LangSmith

진단의 모델 호출을 웹 화면에서 확인한다. trace 파일과 별개이며 함께 사용할 수 있다.

| | trace 파일 | LangSmith |
|---|---|---|
| 확인 방법 | 파일 열기, `jq` | 웹 화면 |
| 두 실행 비교 | `diff` (동일 입력이면 동일 ID) | 없음 |
| 단계 다시 실행 | `--from`, `--stage` | 없음 |
| 공유 | 하지 않음 (5장) | 동일 계정의 화면 링크 |

### 6.1 켜기

`.env`에 설정한다. 키는 LangSmith 설정 화면에서 발급한다.

```bash
LANGSMITH_TRACING=true
LANGSMITH_API_KEY=<API 키>
LANGSMITH_PROJECT=<프로젝트 이름>   # 예: 로컬 ktc4-local, 서버 ktc4-prod
```

켠 상태에서 `trace_cli`나 서버로 진단을 실행하면 화면에 다음과 같이 기록된다.

```text
diagnosis:<상품 ID>
├ extraction
├ selection
├ tool_execution
│ └ tool:<Tool 이름>
├ aggregation
└ verification       (재실행은 verification #1처럼 회차가 붙음)
```

단계·Tool 이름은 hook으로 연결한다(`app/diagnosis/langsmith_trace.py`). 에이전트·Tool 코드는 수정하지 않는다. 단계 다시 실행에서 건너뛴 단계는 기록되지 않는다.

`diagnosis:<상품 ID>`의 Input에는 진단 입력이 기록된다.

| 항목 | 내용 |
|---|---|
| `product_id`·`source_url`·`text_blocks` | 받은 값 그대로 |
| `image_urls` | 주소는 그대로 기록한다. base64 이미지는 앞 40자와 전체 길이만 기록한다 (`data:image/png;base64,AAAA… (300,022자)`) |
| `resume` | 재진단 여부. 이전 결과 본문은 Output과 중복되므로 포함하지 않는다 |
| `answers` | 재진단 시 받은 답변(회차·질문 키·답) |

Output에는 진단 결과가, Metadata에는 실행 ID·실행 종류·진단 ID가 기록된다.

채팅 모델 호출은 LangChain이 자동으로 기록한다. 판단 모델(Jev·Luna `/decisions`) 호출은 LangChain을 거치지 않으므로 판단 클라이언트가 직접 기록한다(`app/clients/llm/decision/base.py`). 호출한 단계 아래에 `decision:<모델>`로 표시되며 판단 대상·질문·답·토큰이 포함된다. 진단 묶음 안에서 호출한 경우만 기록하므로 진단 밖에서 실행되는 입력 가드는 기록되지 않는다.

채팅 모델 응답이 출력 상한 초과·콘텐츠 필터로 잘리면 ChatOpenAI 실행에는 출력이 기록되지 않으므로, 에이전트 공통 호출이 별도로 기록한다(`app/agents/base/agent.py`). 호출한 단계 아래에 `잘린 응답:<에이전트 이름>`으로 표시되며 실패 종류와 잘린 원문·출력 토큰 수가 포함된다.

### 6.2 주의

- 프롬프트·상품 문구·모델 응답이 LangSmith로 전송된다.
- `.env`를 읽는 모든 실행에서 켜지며, 로컬 컨테이너도 다시 생성하면 켜진다. 켠 상태로 평가 러너를 실행하면 채팅 모델 호출이 진단 단위로 묶이지 않고 개별 전송되며, 판단 모델 호출은 기록되지 않는다. 이를 피하려면 명령 앞에 `LANGSMITH_TRACING=false`를 지정한다.
- 테스트에서는 항상 꺼진다(`tests/conftest.py`).
- 전송 서버에 장애가 발생하여도 진단 결과는 영향을 받지 않는다. 오류 로그가 기록되며 프로세스 종료가 지연될 수 있다.
- 모델·Tool 호출 이외의 코드 판정과 외부 조회는 화면에 별도로 표시되지 않는다.
- 화면의 비용은 LangSmith 단가 기준이다. 실제 비용은 모델 호출 사용량 기록(`logs/usage.jsonl`)으로 확인하며, 확인 방법은 [AI_LOGGING.md](AI_LOGGING.md) 5장을 참고한다.

---

변경 이력: [history/AI_TRACE.md](../../history/observability/AI_TRACE.md)
