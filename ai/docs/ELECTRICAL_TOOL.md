# 전기안전 Tool — 조건 추출 · 품목 조회 · 품목 선택

## 파일 구성

| 위치 | 내용 |
|---|---|
| `app/tools/electrical/tool.py` | `ElectricalTool` 흐름 (조건 추출 → 조회 → 규칙 → 선택 → 결과 조립) |
| `app/tools/electrical/rules.py` | 코드 규칙(저전압·전지 전용·ESS 필터)과 구매대행 안내 문구 |
| `app/tools/electrical/search.py` | 품목 조회 인터페이스 `ElectricalItemSearch`, `LawApiItemSearch`, `DatabaseItemSearch`(스텁) |
| `app/tools/electrical/evidence.py` | 법령 버전 선택, 품목표·공통 비고·별표 13 파서, 캐시 |
| `app/schemas/electrical.py`, `app/prompts/electrical/facts.md`·`review.md` | LLM 입출력 |
| `app/eval/electrical_runner.py` | 실제 실행·모델 비교·평가 채점·재채점 (`python -m app.eval.electrical_runner`) |
| `tests/tools/electrical/` | 단위 테스트(`test_tool.py`, `test_evidence.py`)와 법제처 Fake(`conftest.py`) |
| `tests/fixtures/electrical_law/` | 실제 법제처 응답 원문 |
| `tests/eval_truth_electrical/holdout.json` | 홀드아웃 평가셋 |

`app.tools.registry`는 그대로 `from .electrical import ElectricalTool`로 가져온다.

## 흐름

법령 원문 전체를 모델에 넣지 않는다. 운용요령 품목표에서 상품과 비슷한 **행 몇 개만** 조회해, 그중 맞는 행을 모델이 고른다.

```text
Product (추출 에이전트 결과)
→ ① LLM 조건 추출     제품 종류·전원·전압 등 + 상품 원문 인용         (prompts/electrical/facts.md)
→ ② 코드 품목 조회    운용요령 별표 1~3 품목 행 중 비슷한 상위 8개     (electrical/search.py)
→ ③ 코드 규칙         저전압 제외 · 전지 전용 구조 제외 · 전기저장장치 구성품 행 제외
→ ④ LLM 품목 선택     후보 행 중 맞는 행 최대 3개 + 이유             (prompts/electrical/review.md)
→ ⑤ 코드 결과 조립    근거(행 원문·공개 URL) + 구매대행 특례(시행규칙 별표 13) 대조 + 판매 전 할 일
```

### 코드 규칙

**법령 제외 규칙** (법령 문구에 근거)

| 규칙 | 근거 | 동작 |
|---|---|---|
| 저전압 제외 | 운용요령 제3조 ③ + 행 비고 "…포함한다" | 교류 30V·직류 42V 이하가 명시되면, 저전압 포함 비고가 없는 행은 고를 수 없다 |
| 전지 전용 구조 제외 | 운용요령 별표 1~3 끝 공통 비고 | `battery_only=예`(원문 근거)면 본체 행을 빼고 전지·충전기·전원장치·전격살충기 행만 남긴다. 전지 사용이 보이는데 불명이면 본체 후보에 제외 가능성을 붙이고 질문한다 |
| 구매대행 특례 대조 | 법 제35조, 시행규칙 제56조·별표 13 | 선택된 행의 품목명이 별표 13 목록에 있는지 대조해 `required_actions`로 구매대행/사입별 할 일을 낸다 |

**오답 감소용 후보 필터** (법령 제외 규칙이 아니다)

| 필터 | 이유 | 동작 |
|---|---|---|
| 전기저장장치 구성품 | 소비자용 배터리에 반복해서 잘못 붙음(실측) | 상품 원문에 전기저장장치·ESS 용도가 없으면 분류 "전기저장장치구성품" 행을 후보에서 뺀다. 원문에 용도가 빠진 실제 ESS 부품은 놓칠 수 있다 |

표 끝 공통 비고(전지 전용 구조, 차량 등 전용구조 제외)는 선택 단계 LLM 입력에도 함께 넣는다.

### 구매대행 특례 상태 (`query.purchase_agent`)

품목 분류 자체가 후보이므로 **모든 안내는 조건부**다("이 품목으로 분류되면 …").

| 상태 | 뜻 | 안내 |
|---|---|---|
| `listed` | 별표 13에 품목명이 있다 | 이 품목으로 분류되면 구매대행은 KC 표시 없이 가능(고지 의무). 사입·수입은 KC 필요 |
| `listed_with_exclusion` | 있지만 "…는 제외한다"가 붙는다 (예: 직류전원장치 중 휴대전화 충전기) | 분류되고 **제외 조건에 해당하지 않으면** 특례 적용. 제외 조건 해당 여부를 먼저 확인 |
| `unmatched` | 별표 13에서 품목명을 찾지 못했다 (표현이 달라 못 찾았을 수 있음) | "특례 없음"으로 확정하지 않는다. 확인 전까지는 KC 받은 제품만 판매하는 것이 안전 |
| `similar_clause` | 품목표의 "그 밖에 유사한 기기" 행 | 유사 기기 조항 해당 여부 확인 필요 |
| `unknown` | 공급자적합성확인(법 제35조 밖) 또는 별표 13 미확인 | 사입·수입 KC 확인. 구매대행 의무는 확인 필요 |

"특례 없음"을 확정하려면 사람이 검토한 품목 ↔ 별표 13 대응 규칙이 필요하다(미구현).
판매 방식(구매대행/사입)은 상품 글에서 알 수 없으므로 두 경우의 할 일을 함께 낸다. 판매 방식을 진단 입력으로 받는 것은 BE·FE와 합의할 사항이다.

| 역할 | 담당 |
|---|---|
| 상품 조건 값과 원문 인용 추출 | LLM |
| 인용 대조, 누락·모순, 저전압 판정, 조회, 근거 연결, 결과 상태 | 코드 |
| 후보 행 중 상품에 맞는 행 고르기와 이유 | LLM |
| 확정 판단(`REQUIRED`/`NOT_REQUIRED`) | 사람이 검토한 코드 규칙만. **아직 없음** |

## 입력 조건

- 품목 조회에는 **제품 종류만 있으면 된다.** 없거나 상품 모순이 있으면 조회하지 않고 정보 부족을 반환한다.
- 전원 방식·정격 전압이 없으면 `missing_information`(질문)으로 남기고 품목 검토는 계속한다.
- `Product.listing_text`와 `Attribute.source_text`만 상품 인용 근거로 쓴다. 나머지 Product 값은 조회용 힌트이며, boolean만으로 판단하지 않는다.

## 품목 조회 (`app/tools/electrical/search.py`)

- `ElectricalItemSearch.search(terms, top_k) -> ItemCandidates`로 추상화했다. 조회는 "비슷한 물건 고르기"이지 판단이 아니다.
- `LawApiItemSearch` (현재):
  - 법제처 API로 시행규칙 제3조, 운용요령 제3조, 운용요령 별표 1~3(184개 품목 행)을 받아 파싱한다(`electrical/evidence.py`).
  - 기준일별로 캐시한다(6시간). 상품마다 API를 다시 부르지 않는다.
  - 순위는 품목·세부품목 이름과 상품 용어의 글자 2개 단위 유사도(IDF 가중, 용어별 최댓값)에 세부품목 이름 포함 가산점을 더한 것이다.
  - **상품별 동의어 사전은 두지 않는다.** 상품명을 품목표의 보통 명칭으로 바꾸는 일은 조건 추출 LLM의 `search_terms`(조회어 2~3개)가 맡는다. 조회어는 판단 근거가 아니며, 원문 대조를 하지 않는다.
- `DatabaseItemSearch` (스텁): 품목표 행 테이블과 임베딩 적재 후 벡터 조회로 바꿀 자리다. 같은 `ItemCandidates`를 돌려주면 Tool은 바꾸지 않는다. 현재 DB에는 조문 테이블(`law_articles`)만 있어 별표·행정규칙 테이블과 적재 작업이 먼저 필요하다.
- 정답 품목이 후보에 없을 수 있다. 후보가 없거나 맞는 행이 없으면 정보 부족이며, 비대상으로 바꾸지 않는다.

## 법령 버전

- 법령 ID로 검색해 기준일(한국 날짜)에 시행 중인 최신 버전을 고른다. 미래 시행 버전, 불완전한 목록, 같은 시행일의 복수 버전은 거부한다.
- 본문의 문서 ID·이름·시행일을 검색 결과와 다시 대조한다. 확인할 수 없으면 `EvidenceUnavailable` → Tool은 정보 부족(SUCCESS)을 반환한다.
- 근거 URL은 버전을 고정한 공개 열람 주소다(API 요청 URL·OC 키를 쓰지 않는다).

## 결과

- 선택된 행: `POSSIBLY_REQUIRED`, subject `"{제도}대상 후보 — {품목}"`. 근거는 그 행 원문(분류·품목·세부품목·비고)이고, 저전압이면 운용요령 제3조도 붙인다.
- 조건 부족·빈 후보·맞는 행 없음: `INSUFFICIENT_INFORMATION`. 비대상으로 해석하지 않는다.
- 모델 출력 중 대조되지 않는 항목은 **그 항목만 버리고** 계속한다(원문에 없는 조건, 후보에 없는 행, 미확인 조건 참조, 저전압 제외 행, 중복 선택). 버린 수는 `query`와 `assumptions`에 남는다.
- `query`: `dropped_facts`, `dropped_candidates`, `candidate_items`, `filtered_items`, `selected_items`, `low_voltage`, `battery_only`, `battery_only_excluded`, `purchase_agent`, `documents`.
- `required_actions`: 선택된 후보 품목 기준의 구매대행·사입별 할 일(위 표).
- `ElectricalAssessment.legal_sources`는 비운다. 긴 근거는 findings에만 둔다(Verification 입력 중복 방지). `safety_management_required`는 확정이 아니므로 `None`이다.
- 모델 호출·구조화 출력 실패, 법령 조회 오류는 `ElectricalToolError`로 전파한다(원인은 예외 체인).
- 모델 두 호출을 `electrical-facts`, `electrical-review` 사용량 기록으로 구분한다.

## 남은 작업

- 확정 규칙: 반복 실행에서 매번 같은 행이 나오는 품목부터, 사람이 법령 원문과 대조해 검토한 규칙으로 `REQUIRED`를 낸다.
- 조회 품질: 평가셋으로 정답 행이 상위 8개에 드는지(recall@8)를 측정한다. DB 벡터 조회로 바꿀 때 같은 지표로 비교한다.
- 비고의 제도 변경("이 경우 공급자적합성확인대상으로 한다", 6행)과 정격·용도 조건의 코드 판정.
- 공급자적합성확인대상의 구매대행 의무, 병행수입·수입 중고 특례, 안전성검사대상전기용품.
- 별표 13 대조는 품목명 일치다. 표현이 다르면 `unmatched`(확인 필요)로 나온다. 사람이 검토한 대응 규칙을 만들어야 "특례 없음"을 확정할 수 있다.
- 상품 본체와 동봉 부속품(어댑터·전지)의 조건을 구분하지 않는다. 저전압 판정은 상품 전체의 전원·전압 값을 한데 모아 모든 후보 행에 적용하므로, 본체 DC 5V와 어댑터 AC 220V처럼 부품마다 다른 값은 모순(판정 보류)으로 처리된다. 부속품별 판단에는 조건에 대상(본체/어댑터/전지) 구분이 필요하다.
- ToolExecutor 연결은 agent-pipeline 머지 후 진행한다.

## 검증

- 단위 테스트(모델·API는 Fake, 품목표는 실제 법제처 응답 픽스처 `tests/fixtures/electrical_law/`): `ai/`에서

  ```bash
  uv run --python 3.11 pytest tests/tools/electrical tests/tools/test_registry.py -q
  ```
- 파이프라인 연결 전이라, 대표 결과를 실제 `VerificationAgent().verify_rules()`에 넣어 재실행 요청·이슈가 없는지 테스트로 확인한다.

## 평가셋

- `tests/eval_truth_electrical/holdout.json`: 개발 샘플과 겹치지 않는 18개 상품과 예상 행(운용요령 별표 원문 기준, 사람 검토 전).
- **이 셋을 보고 코드·프롬프트를 고치지 않는다.** 고치면 새 셋을 만든다.
- 프롬프트에는 상품 예시를 넣지 않는다(형식 규칙만 말로 설명).
- 실행: `python -m app.eval.electrical_runner --eval tests/eval_truth_electrical/holdout.json --runs 3`
  - 품목 행 선택 정확도를 잰다. 법적 판정이나 판매 안내(`required_actions`)의 정확도는 재지 않는다.
  - 실행 실패는 따로 세고 정답에서 뺀다. 조회 recall@k와 정답률은 정답 행이 있는 사례만으로, 정답 행이 없는 사례(본체 행을 고르지 않아야 함)는 별도 지표로 낸다.
  - 저장한 원자료는 `--eval … --rescore 원자료.json`으로 API 호출 없이 다시 채점할 수 있다.

## 단독 실행

파이프라인 없이 실제 모델·법제처 API로 Tool 하나를 돌려 볼 수 있다(비용 발생). `ai/`에서

```bash
python -m app.eval.electrical_runner                   # 내장 상품 6개
python -m app.eval.electrical_runner --only 전기포트 --runs 3
python -m app.eval.electrical_runner --model openai/gpt-4.1-mini --model openai/gpt-6-luna@LUNA \
    --default-temperature openai/gpt-6-luna --price openai/gpt-6-luna=152,15,761 --runs 3 \
    --out logs/eval/electrical-compare.json
python -m app.eval.electrical_runner --product product.json --json
```

- 품목표는 한 번 받아 캐시하고 최초 로드 시간을 따로 출력한다.
- 회차마다 모델 호출별 입력(캐시)·출력 토큰과 지연, 전체 시간, 조회 후보·선택 행·저전압 판정을 출력한다.
- 마지막에 모델별 평균·최대, 예상 비용, 상품별 결과가 회차마다 같은지를 요약한다.
- `--out` 파일에는 모델의 원래 출력이 남아, 무엇을 왜 버렸는지 볼 수 있다.
- `이름@접두어`는 `.env`의 `{접두어}_BASE_URL`(키는 `{접두어}_API_KEY`, 없으면 `OPENAI_API_KEY`)로 호출한다. 추론 모델은 `--default-temperature`로 temperature를 보내지 않는다.
