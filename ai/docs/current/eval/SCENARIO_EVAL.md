# 사용자 시나리오 끝단 평가 (추출 → 선택)

실제 Temu·AliExpress 상품 원문을 사용자가 입력하는 형태 그대로 사용하여 추출 → 선택까지 실행하여, **해당하는 규제 심사(6개 Tool)를 누락 없이 선택하였는지**를 상품 단위로 측정한다. 추출 평가([EXTRACTION_EVAL.md](EXTRACTION_EVAL.md))와 선택 평가([SELECTION_EVAL.md](SELECTION_EVAL.md))가 각 단계를 따로 측정한다면, 이 평가는 두 단계를 연결하여 측정한다. Tool 판정·검증·재질문은 포함하지 않는다. 결과 저장·측정 조건 기록 등 공통 규칙은 [EVAL_COMMON.md](EVAL_COMMON.md)를 참고한다.

## 1. 측정 항목

| 항목 | 정의 |
|---|---|
| 빠뜨림 | 정답 `selected=true`인데 선택하지 않음. 규제가 사용자에게 드러나지 않게 누락되므로 무겁게 본다 |
| 과잉 선택 | 정답 `false`인데 선택함. 비용·지연만 늘어나므로 가볍게 본다 |
| 무누락 상품 | N회 반복하여 **모든 회차에서** 빠뜨림이 없는 상품. 한 회차라도 누락하면 실패이다 |

- 재시도 후에도 실패한 회차(추출·선택 예외)는 진단서가 생성되지 않으므로 선택해야 할 Tool을 전부 빠뜨린 것으로 센다. 재시도 대상이 아닌 예외가 발생한 상품은 해당 상품의 전 회차를 실패로 기록한다.
- 빠뜨림 원인은 다음과 같이 분류한다. 실패한 회차와 글 입력에 근거가 없는 Tool을 먼저 구분하고, 나머지는 추출 정답이 있을 때 판단 필드로 나눈다. [SELECTION_EVAL.md](SELECTION_EVAL.md) 1장의 원인 분류를 모드 B만으로 축소한 것이다.

| 원인 | 의미 |
|---|---|
| 추출이 false로 넘김 | 판단 필드를 추출이 근거 없이 `false`로 확정 |
| 선택이 null을 없음으로 봄 | 추출은 `null`로 넘겼으나 선택이 해당 없음으로 처리 |
| 선택이 근거를 보고도 놓침 | 위 두 경우에 해당하지 않는데 선택하지 않음 |
| 판단 칸 없는 Tool | 판단 필드가 없는 Tool(통관·표시·광고) |
| 글 입력에 근거 없음 | 정답 근거가 상세 이미지·AliExpress 설명 글에만 있음(정답의 `image_only`) |
| 실행 실패 | 실패한 회차 |
| 분류 안 함 | 해당 상품의 추출 정답이 없음 |

- 보고서에는 무누락 상품 수와 함께 재시도 횟수, 실패한 회차, 글 입력에 근거가 없어 누락한 Tool 수, 펼치기 전 글이 없어 펼친 글로 대체한 상품 수를 표시한다.

채점은 `app/eval/scenario_scoring.py`, 러너는 `app/eval/scenario_runner.py`이며, 둘 다 모델 호출 없이 테스트된다.

## 2. 데이터

| 항목 | 위치 |
|---|---|
| 선택 정답 (개발 50, 홀드아웃 15) | `tests/eval_truth_scenario/dev/`, `tests/eval_truth_scenario/holdout/` |
| 상품 원문 (글) | [팀 노션](https://app.notion.com/p/ZIP-3f15a820b2b88076ba5fd83f164adc4f) `scenario_raw_text.zip` |
| 상세 이미지 (정답 근거 확인용, 실행에는 불필요) | 용량(140MB) 때문에 노션에 없음. 필요하면 gityhb에게 요청 |

- 저장소가 public이므로 상용 페이지 원문은 커밋하지 않는다([tests/fixtures/README.md](../../../tests/fixtures/README.md)). zip을 `ai/tests/fixtures/_raw/`에 그대로 풀고, zip 안 `MANIFEST_scenario.txt`의 지문(줄바꿈을 LF로 통일한 SHA-256 앞 12자)으로 같은 원문인지 확인한다.
- 압축을 풀면 다음 폴더가 생성된다.
  - `strat_NN/`: 개발 표본
  - `holdout_scenario/holdout_NN/`: 홀드아웃 표본
  - `truth_drafts/`: 개발 50의 추출 정답 초안(**미확정**, 원인 분류용)
  - `scenario_truth/results/`: 측정 결과 원본(재채점용)
- 상품 폴더마다 `text.txt`(더보기를 펼친 뒤 전체 선택한 글, 주 입력), `text_as_pasted.txt`(펼치기 전 글, 보조)가 있으며, AliExpress 상품은 `description.txt`(상세 설명 글)가 추가로 있다.
- 개발 50은 카테고리를 나누어 선정한 표본으로, 추출 규칙 조정에 사용한다. **발표 수치는 홀드아웃 15로만 산출한다.** 홀드아웃은 프롬프트·규칙을 수정하는 동안 열지 않는다([EVAL_COMMON.md](EVAL_COMMON.md) 5장).
- `tests/eval/test_truth_scenario.py`가 모델 호출 없이 정답표를 검사한다. 표본별 정답 수, 6개 Tool의 참·거짓과 원문 경로, 검토자와 Tool별 근거 기재 여부를 확인한다.

## 3. 정답 기준

정답은 "이 상품의 **실제 사실**(판매자 제목·스펙표·상세 글·상세 이미지 전부)에 선택 프롬프트 기준을 적용하면 선택해야 하는 Tool"이다. 선택 평가의 정답은 추출 결과를 입력받았을 때의 정답이지만, 이 평가는 끝단이므로 **추출이 누락한 사실도 정답에 포함된다.** 정답은 추출 결과·모델 출력을 참고하지 않고 작성한다.

| Tool | true 기준 |
|---|---|
| 통관 | 해외 직구 수입품. 원산지 국내·국내 사업자·국내 발송이 명시되면 false (개발 6·30) |
| 전파 | 무선 통신·무선충전·전파 차폐(RFID 차단) 중 하나. 무선 기능이 없는 전자기기는 false (5장 한계) |
| 식약 | 음식 접촉·의료 효능 표방·미용 효과 표방. 피부 접촉은 용도로 판단한다: 귓구멍·점막에 삽입하는 용도(인이어 이어폰, 코털 트리머, 칫솔)는 true, 손목·손에 닿는 용도는 false |
| 전기 | 전기 구동·전지 포함·전지 자체·발열. 정격·전압·mAh 표기가 있으면 true |
| 어린이 | 연령·어린이 대상 표기, 또는 학용품·완구. 어린이도 사용할 수 있다는 것만으로는 false |
| 표시·광고 | 판매자 문구에 효능 표방 / 최상급·절대 표현 / 미검증 인증(해외 인증 표기 포함) / 의료·미용 주장 / 과장 수치 중 하나가 **분명히** 있을 때. "미끄럼 방지", "친환경", "논스틱", "고속" 같은 기능·사양 설명은 false. 리뷰·쇼핑몰 공통 문구는 근거가 아님 |

- 애매하면 true로 두고 `notes`에 "애매"라고 기재한다.
- false는 "어떤 사실로 해당 없음이 확인되는지"를 `evidence`에 기재한다.
- 위 기준을 정하면서 값이 바뀐 곳은 `notes` 끝에 `[기준N: Tool True→False]` 형식으로 남긴다.

## 4. 실행

```bash
cd ai
# 개발 50, 펼친 글, 3회
python -m app.eval.scenario_runner --truth-dir tests/eval_truth_scenario/dev --raw-dir tests/fixtures/_raw \
    --extraction-truth-dir tests/fixtures/_raw/truth_drafts --runs 3 --report dev_expanded.md --title "개발 (펼친 글)"
# 홀드아웃 15, 펼치기 전 글
python -m app.eval.scenario_runner --truth-dir tests/eval_truth_scenario/holdout --raw-dir tests/fixtures/_raw/holdout_scenario \
    --input-file text_as_pasted.txt --runs 3 --report holdout_pasted.md --title "홀드아웃 (펼치기 전 글)"
# 저장된 결과 재채점 (모델 호출 없음)
python -m app.eval.scenario_runner --rescore tests/fixtures/_raw/scenario_truth/results/<결과>.json \
    --truth-dir tests/eval_truth_scenario/holdout --report again.md --title "홀드아웃 (펼친 글)"
```

| 옵션 | 내용 |
|---|---|
| `--truth-dir` | 선택 정답 폴더. 재채점에서 지정하면 결과 파일에 저장된 경로 대신 사용 |
| `--raw-dir` | 원문 폴더. 정답의 `fixture` 경로 기준 |
| `--extraction-truth-dir` | 추출 정답 폴더. 지정하면 빠뜨림 원인을 분류 |
| `--input-file` | 상품 폴더 안의 입력 파일(기본 `text.txt`). 해당 파일이 없는 상품은 `text.txt`로 대체 |
| `--runs` | 상품당 추출 횟수(기본 3) |
| `--retries` | 실패한 회차의 재시도 횟수(기본 2) |
| `--report`·`--title` | 마크다운 보고서 경로와 제목 |
| `--rescore` | 저장된 결과 파일을 모델 호출 없이 재채점 |

- 상품마다 추출을 N회 실행하고, 추출 결과마다 선택을 1회 실행한다. 추출·선택 에이전트는 운영 기본 프로필을 사용한다.
- 원문이 하나라도 없거나 정답 형식이 깨졌으면 모델을 생성하기 전에 중단한다. `--extraction-truth-dir`에 존재하지 않는 폴더를 지정하여도 중단한다.
- 원문은 `--raw-dir`로 직접 지정한다. **워크트리 안에 `_raw`로 연결되는 링크(정션)를 만들지 않는다.** `git worktree remove`가 링크를 따라가 원본을 삭제할 수 있다.
- 결과는 `logs/eval/scenario-<시각>.json`에 저장된다. `meta`에는 공통 측정 조건과 함께 선택 모델(`selection_model`)과 선택 프롬프트 지문(`selection_prompt_sha256`)을 기록한다.
- 결과 파일의 정답 경로는 측정한 PC 기준이므로, 다른 PC에서 재채점할 때는 `--truth-dir`·`--extraction-truth-dir`로 다시 지정한다.

## 5. 한계

- **표시·광고 칸은 모델의 판단을 측정하지 않는다.** 선택 에이전트가 표시·광고를 코드로 항상 선택하므로(`ALWAYS_RUN_TOOLS`), '6개 Tool 무누락'에는 고정 선택의 효과가 포함된다. 결과는 '표시·광고 제외 무누락'과 '표시·광고 Tool 탐지 결과'를 구분하여 기재한다. 선택에서 누락하지 않아도 Tool이 문구를 탐지하는지는 별개이다.
- **유선 전자파적합성은 확인하지 않는다.** 무선 기능이 없는 유선 전기제품도 전파법상 적합성평가 대상일 수 있으나, 전파 Tool은 무선 기기만 판정한다([RADIO_TOOL.md](../tools/RADIO_TOOL.md)). 실제 예: 개발 33번 핫팩 겸 보조배터리가 방송통신기자재 적합성평가 번호를 표시하고 있다.
- 진단서 끝까지(Tool 판정·검증·재질문)는 측정 범위에 포함하지 않는다.
- 정답은 한 사람이 확정하였다. 표시·광고·식약 경계는 사람마다 판단이 다를 수 있다.
- 입력에 이미지를 포함하지 않는다. 근거가 이미지에만 있는 빠뜨림은 '글 입력에 근거 없음'으로 별도 집계한다.

---

변경 이력: [history/SCENARIO_EVAL.md](../../history/eval/SCENARIO_EVAL.md)
