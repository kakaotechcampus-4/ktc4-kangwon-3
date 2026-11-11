# 평가 공통

AI 에이전트·Tool 평가의 목록과 모든 평가에 공통으로 적용하는 규칙을 정리한다. 평가별 정답 기준과 채점 방식은 각 평가 문서를 참고한다.

## 1. 평가 목록

모든 평가는 `ai/` 폴더에서 `python -m app.eval.<러너>`로 실행한다.

| 평가 | 대상 | 러너 | 정답셋 | 문서 |
|---|---|---|---|---|
| 추출 | 추출 에이전트 | `runner` | `tests/eval_truth/` | [EXTRACTION_EVAL.md](EXTRACTION_EVAL.md) |
| 선택 | 선택 에이전트, 판단 선택 에이전트 | `selection_runner` | `tests/eval_truth_selection/` | [SELECTION_EVAL.md](SELECTION_EVAL.md) |
| 시나리오 | 원문 → 추출 → 선택 끝단 | `scenario_runner` | `tests/eval_truth_scenario/` (`dev`·`holdout`) | [SCENARIO_EVAL.md](SCENARIO_EVAL.md) |
| 입력 가드 | 입력 가드(판단 모델) | `guard_runner` | `tests/eval_truth_guard/` (`dev`·`holdout`) | [GUARD_EVAL.md](GUARD_EVAL.md) |
| 에이전트 가드레일 | 추출·선택 에이전트 가드레일 | `guardrail_runner` | `tests/eval_truth_guardrail/` | [GUARDRAIL_EVAL.md](GUARDRAIL_EVAL.md) |
| 표시·광고 Tool | 표시·광고 Tool | `advertising_runner` | `tests/eval_truth_advertising/` (`dev`·`holdout`) | [ADVERTISING_TOOL.md](../tools/ADVERTISING_TOOL.md) |
| 전기안전 Tool | 전기안전 Tool | `electrical_runner` | `tests/eval_truth_electrical/` | [ELECTRICAL_TOOL.md](../tools/ELECTRICAL_TOOL.md) |
| 통관 Tool | 통관 Tool | `customs_runner` | `tests/eval_truth_customs/` | [CUSTOMS_TOOL.md](../tools/CUSTOMS_TOOL.md) |
| 식품·의약품 Tool | 식품·의약품 Tool | `food_drug_runner` | `tests/eval_truth_food_drug/` | [FOOD_DRUG_TOOL.md](../tools/FOOD_DRUG_TOOL.md) |
| 별표 파서 | 별표 원본 파일 규칙 파서 | `annex_file_runner` | `tests/eval_truth_annex/` | 모듈 docstring |

다음 러너는 정답셋으로 채점하지 않는다.

| 러너 | 용도 |
|---|---|
| `collect_runner` | 상품 주소 수집 → 이미지 분류 → 추출을 실행하여, 추출에 입력하는 이미지 방식별 결과를 비교용으로 저장 |
| `verify_cli` | 검증 에이전트 단독 실행(`--rules-only`이면 규칙 검사만) |

## 2. 실행 결과 저장

- 모델을 호출하는 평가는 실행 결과 원본을 파일로 저장한다. 기본 위치는 `logs/eval/`이며(git 추적 제외), 파일 이름은 평가 종류와 실행 시각으로 구성된다(예: `selection-<시각>.json`). 추출 러너만 평가 종류 없이 `<시각>.json`으로 저장한다. 전기안전·통관·식품·의약품 러너는 `--out`을 지정한 경우에만 저장한다.
- 저장한 결과는 `--rescore`로 모델을 다시 호출하지 않고 현재 정답셋으로 재채점할 수 있다(추출·선택·시나리오·입력 가드·에이전트 가드레일·표시·광고·전기안전). 채점 기준을 수정한 뒤 동일한 데이터로 다시 비교하기 위함이다.
- 별표 파서·수집 러너는 결과를 `data/` 아래에 저장한다. 실행 결과이므로 저장소에 커밋하지 않는다.

## 3. 측정 조건 기록

결과 파일의 `meta`에 측정 조건을 기록한다(`app/eval/runner.py`의 `run_metadata`).

| 키 | 내용 |
|---|---|
| `run_at` | 측정 시각(UTC) |
| `git_commit`·`git_dirty` | 커밋과 `ai/` 아래 커밋하지 않은 수정 여부. 수정이 있으면 해당 커밋의 코드로 측정한 값이 아니다 |
| `model`·`model_profile` | 모델과 모델 프로필 전체(추론 강도 등) |
| `prompt_path`·`prompt_sha256` | 프롬프트 파일 경로와 지문 |
| `runs` | 입력당 회차 수 |

- 프롬프트 지문은 `prompt.md` 파일이 아니라 에이전트가 모델에 전송하는 시스템 프롬프트 전체(가드레일 포함) 기준이다. 가드레일만 바꾸어도 다른 프롬프트로 구분된다. 줄바꿈(CRLF·LF) 차이는 지문에 영향을 주지 않는다.
- 판단 모델로 측정한 결과(입력 가드, 판단 선택)는 `decision_profile`을 기록하며, 프롬프트 지문 자리에 질문 목록 지문을 기록한다(`decision_run_metadata`).
- 추출·선택 재채점 시 기록된 지문이 현재 프롬프트와 다르면 경고한다. 지문이 다른 두 측정치는 동일한 기준선으로 비교하지 않는다.

## 4. 원문 비공개와 지문 대조

- 저장소가 public이므로 상용 상세페이지 원문과 공격 문장이 포함된 입력은 커밋하지 않는다. 원문은 `tests/fixtures/_raw/`(git 추적 제외)에 두며, 받는 방법은 [tests/fixtures/README.md](../../../tests/fixtures/README.md)를 참고한다.
- 추출 러너는 측정할 원문이 하나라도 없으면 모델을 호출하기 전에 중단하고 원문 위치를 안내한다.
- 입력 가드·에이전트 가드레일·표시·광고 평가셋은 입력 파일 지문(`inputs_sha256_12`, 줄바꿈을 LF로 통일한 SHA-256 앞 12자)을 기록하며, 로컬 입력 파일의 지문이 다르면 실행하지 않는다.
- 추출·시나리오 원문은 원문 묶음의 `MANIFEST` 파일 지문으로 동일한 원문인지 확인한다.

## 5. 평가셋 구분

- dev는 프롬프트·규칙을 조정하면서 확인하는 셋이고, holdout은 조정을 마친 뒤 한 번만 확인하는 셋이다.
- holdout을 확인한 뒤 그 결과를 보고 수정하면 해당 상품은 dev로 옮기고 holdout에 새 상품을 채운다.
- holdout 원문 폴더(`holdout_DO_NOT_OPEN` 등)는 프롬프트·정제 규칙을 수정하는 동안 열지 않는다.

## 6. 비용 기록

평가 러너는 에이전트를 운영과 다른 기록 이름(`usage_agent`)으로 생성한다. 사용량 기록(`logs/usage.jsonl`)과 `python -m app.observability.usage` 집계에서 이 이름별로 운영 호출과 구분된다.

| 러너 | 기록 이름 |
|---|---|
| `runner` | `extraction-eval` |
| `selection_runner` | `selection-eval`, 판단 선택이면 `decision-selection-eval` |
| `scenario_runner` | `scenario-eval` |
| `guard_runner` | `input-guard-eval` |
| `guardrail_runner` | `guardrail-eval` |
| `advertising_runner` | `advertising-eval` |
| `collect_runner` | `image_triage-eval`, `extraction-eval` |

전기안전·통관·식품·의약품 러너는 Tool 기본 기록 이름을 사용한다.

## 7. 테스트

- 채점기·정답셋 형식·러너의 결정적 동작은 `tests/eval/`의 테스트가 모델 호출 없이 확인하며, CI에서 실행된다.
- 모델을 실제로 호출하는 평가는 결과가 확률적이므로 CI의 통과 기준으로 사용하지 않고, CLI로 실행하여 기준선과 비교한다.

---

변경 이력: [history/EVAL_COMMON.md](../../history/eval/EVAL_COMMON.md)
