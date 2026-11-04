# 진단 trace

진단 한 건이 단계마다 무엇을 받아 무엇을 냈는지 로컬 JSON 파일로 남기는 도구. 에이전트·Tool·프롬프트를 고칠 때 같은 입력으로 고치기 전후를 비교하는 용도. 서버 로그는 [AI_LOGGING.md](AI_LOGGING.md).

## 1. 서버 로그와 차이

| | 서버 로그 | trace |
|---|---|---|
| 켜지는 곳 | 서버 (항상) | 로컬 CLI로 돌린 실행만 |
| 남기는 것 | 진단 흐름의 주요 지점 한 줄씩 | 단계 결과·모델 호출 입출력 원문·Tool 안 판단 근거 |
| 상품 원문·모델 응답 | 남기지 않음 | 남김 |
| 저장 | `docker logs` | `logs/traces/` 아래 JSON (git에 안 올라감) |

- 서버에서는 기록기가 없어 trace 코드가 아무것도 안 함 (`trace_run()`으로 감싼 블록 안에서만 기록)
- 기록기는 문맥 변수로 찾음 → 단계·Tool 코드는 기록기를 넘겨받지 않음

## 2. 실행

`ai/` 폴더에서 실행. 서버·세션 관리자·BE 콜백은 거치지 않고 진단 함수만 돌림.

- 모델·외부 API는 실제로 부름 → `.env` 키 필요, 비용 발생
- `DATABASE_URL`이 없어도 됨. 관세 Tool은 CLIP만 조회
- 실행 종류(`run_type`)는 `evaluation`

### 2.1 처음부터

```bash
venv/bin/python -m app.diagnosis.trace_cli logs/trace-inputs/kc-fan.json
```

입력 파일은 `/diagnose` 요청의 상품 하나와 같은 모양. `productId`가 없으면 파일 이름을 씀.

```json
{
  "textBlocks": ["무선 선풍기 USB 충전식", "정격전압 5V"],
  "imageUrls": ["https://example.com/1.jpg"],
  "sourceUrl": "https://example.com/products/1"
}
```

- 저장 위치는 `logs/traces/<입력 파일 이름>/run-N.json`. 번호는 폴더의 마지막 번호 다음 (`--out`으로 폴더 변경)
- 터미널엔 단계·Tool 진행, 결말, 질문, 마지막 줄에 trace 파일 경로

### 2.2 질문에 답해 재진단

```bash
venv/bin/python -m app.diagnosis.trace_cli logs/trace-inputs/kc-fan.json --answer r1_q1=네 --answer r1_q2=아니요
```

- 같은 폴더의 마지막 실행이 질문하고 멈춘 실행이어야 함. 그 파일의 최종 결과·질문·이전 답변으로 재진단 입력을 만듦
- 그 회차 질문에 모두 답해야 함 (서버와 같은 규칙). 빠지거나 다른 키면 거절

### 2.3 단계 다시 실행

```bash
# run-1의 추출 결과를 그대로 쓰고 선택부터 끝까지
venv/bin/python -m app.diagnosis.trace_cli --from logs/traces/kc-fan/run-1.json --stage selection
# 선택 단계 하나만 돌리고 멈춤
venv/bin/python -m app.diagnosis.trace_cli --from logs/traces/kc-fan/run-1.json --stage selection --only
```

- 실행 입력은 이전 trace의 추출 단계 `input`에서 읽음 (입력 파일 불필요)
- 시작 단계 앞 단계는 이전 trace의 결과를 씀. 그 trace 단계에 `replayed: true`
- 첫 회차(round 0)만 저장한 결과를 씀. Tool 재실행 회차는 앞 결과에 따라 달라져 항상 실제로 돎
- 결과는 이전 trace와 같은 폴더에 다음 번호로. `info.replay`에 어느 파일·어느 단계부터인지
- `--only`면 시작 단계를 마치고 멈춤. 결말은 `{"reason": "stopped", "stage": ...}`
- 단계: `extraction` → `selection` → `tool_execution` → `aggregation` → `verification`
- 앞 단계 모델 출력이 매번 달라 생기는 흔들림을 고정하고 한 단계만 비교할 때 씀

## 3. 파일 구조

실행 하나 = 파일 하나.

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

(값은 모양 설명용 예시)

| 키 | 내용 |
|---|---|
| `info` | 실행 정보 (입력 출처, 다시 실행 정보). 열린 단계 밖에서 남긴 값도 여기 |
| `steps` | 단계. 실행 순서대로, 단계 안에 하위 단계(`steps`) |
| `finish` | 결말 |
| `prompts` | 시스템 프롬프트 원문 (지문 → 원문). 호출에는 지문만 |

- ID는 실행 안에서 나온 순서대로 (`s1`, `c1`, …). 같은 입력이면 같은 ID라 diff로 비교 가능
- 실행마다 새로 만드는 ID(uuid)도 실행 안 번호로 바꿔 저장. 판단 ID `f1`·`f2`…, Tool 실행 ID `e1`…, 진단서 ID `a1`, 검증 지적 ID `i1`…. 검증 호출 본문 속 ID도 같이 바뀜
- 이미지는 링크만. 링크가 없는 data URI(긴 이미지 조각)는 본문 대신 `data:image/jpeg;base64,…(생략)`

### 3.1 단계

| `kind` | 남기는 것 |
|---|---|
| `extraction` | `input`(실행 입력 전체: 원래 입력·이전 결과·답변), `output`(상품 정보, 답변 붙인 뒤), `seller_region`(판매자 영역 자르기), `postprocess`(후처리로 바꾼 값), `image_split`(이미지별 자르기 결과) |
| `selection` | `output`(Tool 6개 선택 결과) |
| `tool_execution` | `round`, `output`(선택 내역·Tool 결과), 하위 `tool` 단계 |
| `tool` | `tool`·`selected`·`reason`, `result`(상태·판단 요약·재질문·할 일). 근거 조회형 Tool은 아래 값도 |
| `aggregation` | `round`, `output`(종합 초안) |
| `verification` | `round`, `output`(검증 결과) |

- 다음 단계의 입력은 앞 단계 `output`이라 따로 안 남김 (추출 `input`만)
- 재실행 회차는 `round` 1, 2, …의 `tool_execution`·`aggregation`·`verification`이 이어서 붙음

근거 조회형 Tool(관세·전파·식품의약·전기·어린이)의 `tool` 단계:

| 키 | 내용 |
|---|---|
| `snippet_ids` | 모델에 보여 준 원문 조각 ID |
| `facts` | 상품 조건 대조. `kept`(쓴 조건), `dropped`(버린 조건) |
| `picks` | 후보 고르기마다 `candidates`(후보 ID)와 `selections`(선택별 `outcome`) |
| `conflicted`·`assumptions`·`query` | 충돌한 조건, 가정, 조회 기록 |

`picks`의 `outcome`: `chosen`(채택) · `not_applicable`(해당 없음) · `not_in_candidates`(후보에 없는 ID) · `duplicate`(중복) · `no_confirmed_fact`(확인된 조건 없음) · `rule`(코드 규칙으로 뺌) · `over_limit`(개수 상한 초과).

표시·광고 Tool의 `tool` 단계엔 `claims`: `kept`(남긴 주장), `dropped_quotes`(원문에 없어 버린 인용), `kc_added`(코드로 더한 KC 주장).

`image_split`의 이미지별 `result`: `split`(조각으로 나눔, 조각 수) · `not_split`(짧은 이미지거나 받기·읽기 실패, 둘은 구분 안 됨) · `over_limit`(길지만 상품당 조각 상한 초과로 원래 주소로).

### 3.2 모델 호출

모델 호출은 그때 열린 단계의 `calls`에 원문째. 열린 단계가 없으면 `info.calls`.

| 키 | 내용 |
|---|---|
| `id`·`component` | 호출 ID (`c1`, …), 에이전트 이름 |
| `request` | 보낸 메시지 (시스템 프롬프트는 지문만) 또는 판단 모델 요청 |
| `output` | 스키마로 검증한 출력. 해석 실패면 `null` |
| `raw` | 해석에 실패했거나 잘린 응답 본문 |
| `error` | 호출 실패 원인 |
| `meta` | 모델·토큰·비용·시간 등 실행마다 달라지는 값 |

### 3.3 결말

| `reason` | 같이 남는 것 |
|---|---|
| `completed`·`revision_required`·`retry_limit_exceeded`·`no_progress` 등 종료 이유 | `result`(최종 결과) |
| `user_input_required` | `result`, `question_round`, `questions` |
| `failed` (단계 실패) | `stage`·`code`·`retryable`, `error`, `at` |
| `error` (그 밖의 예외) | `error`, `at` |
| `stopped` (`--only`) | `stage` |

실패 위치:

- 예외가 처음 빠져나간 가장 안쪽 단계: `error`에 예외 이름·메시지·원인(`cause`), 실패한 호출이면 호출 ID(`call`)
- 그 바깥 단계: 같은 예외(또는 `raise ... from`으로 감싼 예외)면 `{"type", "from": 처음 실패한 단계 ID}`만
- `finish.at`: 처음 실패한 단계 ID·종류·경로(`path`)·호출 ID

## 4. 비교

`meta`(시간·토큰·비용)는 매번 달라 빼고 비교.

```bash
diff <(jq -S 'del(.. | .meta?)' logs/traces/kc-fan/run-1.json) \
     <(jq -S 'del(.. | .meta?)' logs/traces/kc-fan/run-2.json)
```

단계 하나만 비교:

```bash
jq '.steps[] | select(.kind == "selection") | .output' logs/traces/kc-fan/run-1.json
```

## 5. 주의

- trace 파일에는 상품 원문·모델 응답 원문이 들어감. 예외 메시지 속 URL의 키도 가리지 않음 → `logs/` 밖으로 옮기거나 공유하지 않음 (입력 파일도 `logs/trace-inputs/`처럼 git이 무시하는 곳에)
- 파일을 못 쓰면 경고 로그만 남기고 진단 결과·예외는 그대로
- 저장한 결과는 그때 스키마 모양. 스키마가 바뀐 뒤 옛 trace로 단계 다시 실행하면 읽기 오류
- 재진단할 때 이전 결과는 trace 파일에서 읽어 판단 · 진단서 ID 등이 이미 `f1`, `a1`처럼 번호. 새 실행의 번호와 이름이 겹칠 수 있음 (진단 동작엔 영향 없음)
- 이미지 자르기 기록(`app/diagnosis/tracing.py`)은 `ImageSplitter`의 내부 메서드(`_tiles`)·값(`_max_tiles`)에 기대고, 상한 판단을 같은 순서로 다시 셈. `ImageSplitter`를 바꾸면 같이 확인
