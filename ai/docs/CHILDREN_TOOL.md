# 어린이제품 Tool — 조건 추출 · 품목 조회 · 품목 선택 (#296)

## 파일 구성

| 위치 | 내용 |
|---|---|
| `app/tools/children/tool.py` | `ChildrenTool` 흐름 (조건 추출 → 조회 → 규칙 → 선택 → 결과 조립) |
| `app/tools/children/rules.py` | 코드 규칙(연령·제외 물품)과 판매 안내 문구 |
| `app/tools/children/search.py` | 품목 조회 인터페이스 `ChildrenItemSearch`, `LawApiItemSearch`, `DatabaseItemSearch`(스텁) |
| `app/tools/children/evidence.py` | 법 제2조, 시행규칙 별표 1~3, 운용요령 별표 3~5 읽기 |
| `app/tools/common/` | 규제 Tool 공용: 법제처 조회·버전 선택·캐시(`law.py`), 품목 행 순위(`ranking.py`), 원문 대조(`facts.py`), 모델 호출 단계(`agent.py`, BaseAgent #284) |
| `app/schemas/children.py`, `app/prompts/children/facts.md`·`review.md` | 모델 입출력 |
| `tests/tools/children/` | 단위 테스트와 법제처 Fake(`conftest.py`) |
| `tests/fixtures/children_law/` | 실제 법제처 응답 원문 |

`app.tools.registry`는 그대로 `from .children import ChildrenTool`로 가져온다.
전기 Tool(#290)에도 같은 역할의 법제처 조회 코드가 있다. 전기 Tool 코드는 후속 PR에서 `app/tools/common/`으로 합친다.

## 흐름

```text
Product (추출 에이전트 결과)
→ ① 모델 조건 추출   제품 종류·사용 연령·용도·재질·제외 물품 + 상품 원문 인용, 조회어     (prompts/children/facts.md)
                     품목표가 35개로 짧아 품목명 목록을 함께 주고 조회어를 그 안에서 고르게 한다(동의어 사전 대신)
→ ② 코드 품목 조회   시행규칙 품목 + 운용요령 적용범위 중 비슷한 상위 6개                (children/search.py)
→ ③ 코드 규칙        연령(만 13세 이하 포함 여부) · 법 제2조 제1호 단서 제외 물품
→ ④ 모델 품목 선택   후보 행 중 맞는 행 최대 3개 + 이유 + 해당 여부(applies)             (prompts/children/review.md)
→ ⑤ 코드 결과 조립   근거(행 원문·적용범위 원문·법 제2조, 공개 URL) + 판매 전 할 일
```

## 코드 규칙

| 규칙 | 근거 | 동작 |
|---|---|---|
| 연령 | 법 제2조 제1호 "만 13세 이하" | 원문 연령 표기를 개월 범위로 읽는다(개월·세·이상·이하·미만·초과·범위·`+`). 하한이 만 13세 이하면 포함, 넘으면 미포함, 못 읽으면 불명. 표기끼리 어긋나면 충돌로 묻는다 |
| 연령 미포함 | 같음 | 품목을 조회하지 않고 "어린이제품이 아닐 가능성"(정보 부족)만 낸다. 확정하지 않는다 |
| 제외 물품 | 법 제2조 제1호 단서 | 상품이 의약품·의료기기·화장품·식품용 기구 등으로 표시되면 어린이제품 후보를 내지 않고 다른 법 검토를 안내한다. 값은 정해진 이름 중 하나만 받는다 |
| 맞는 품목 없음 | 법 제2조 제12호, 시행규칙 별표 3의 2. | 연령이 만 13세 이하로 확인되면 **공급자적합성확인 후보(공통안전기준)**. 연령 불명이면 정보 부족 + 연령 질문 |

- 전기 Tool과 달리 "맞는 행 없음"이 곧 정보 부족이 아니다. 어린이제품이면 안전인증·안전확인 품목이 아니어도 공급자적합성확인대상이다.
- 어린이제품법·시행규칙에서 구매대행 특례 조문을 찾지 못해(2026-10-12 조회) 구매대행·사입을 나누지 않고 "모두 KC 확인"으로 안내한다.

| 역할 | 담당 |
|---|---|
| 상품 조건 값과 원문 인용, 조회어 | 모델 |
| 인용 대조, 연령 판정, 제외 물품 값 검사, 조회, 근거 연결, 결과 상태 | 코드 |
| 후보 행 중 맞는 행 고르기와 이유 | 모델 |
| 확정 판단(`REQUIRED`/`NOT_REQUIRED`) | 사람이 검토한 코드 규칙만. **아직 없음** |

## 품목 조회 (`app/tools/children/search.py`)

- `ChildrenItemSearch.catalog()`(품목명 목록), `search(terms, top_k) -> ChildrenCandidates`로 추상화했다.
- `LawApiItemSearch` (현재): 법제처 API로 법·시행규칙·운용요령을 받아(요청 6회) 기준일별로 캐시한다(6시간).
  - 시행규칙 별표 1~3은 2칸 표(품목 | 적용 안전기준)라 코드로 행을 나눈다. 삭제된 품목은 뺀다.
  - 운용요령 별표 3~5는 적용범위가 긴 설명문이라 칸을 더 나누지 않고 품목 단위 원문 덩어리로 붙인다.
  - 운용요령 품목명은 시행규칙과 다르다(어린이용/아동용, 제품/용품). 같은 제도 안에서 ① 이름 일치 ② 포함 ③ 글자 유사도 순으로 잇고, 못 이은 이름은 `unlinked_scopes`로 남긴다(2026-10-12 기준 0개).
  - 운용요령(2024-07-10)이 시행규칙(2026-06-03)보다 오래돼 새 품목(비수면용 기울어진 요람)은 적용범위가 없다.
- `DatabaseItemSearch` (스텁): 파싱 에이전트가 품목표를 DB에 넣으면 쓸 자리다. 칸 정의는 "어린이·전파 품목표 칸 정의" 문서를 따른다.

## 결과

- 선택된 행: `POSSIBLY_REQUIRED`, subject `"{제도}대상 어린이제품 후보 — {품목}"`. 근거는 시행규칙 행 원문, 운용요령 적용범위 원문, 연령이 확인되면 법 제2조 제1호.
- `ChildrenAssessment`: `target_age_raw`(원문), `intended_for_children`(연령 표기를 읽은 결과, 확정 아님), `product_type`, `certification_type`(후보 제도), `safety_management_required=None`.
- 모델 출력 중 대조되지 않는 항목은 그 항목만 버린다(원문에 없는 조건, 정해진 이름이 아닌 제외 물품, 후보에 없는 행, 미확인 조건만 참조, 중복). `applies=false` 선택도 버린다.
- `query`: `dropped_facts`, `dropped_candidates`, `not_applicable`, `conflicted`, `age_state`, `excluded_kind`, `search_terms`, `candidate_items`, `selected_items`, `fallback`, `documents`.
- 모델 호출·구조화 출력 실패, 법령 조회 오류는 `ChildrenToolError`로 전파한다. 근거 버전을 확인하지 못하면(`EvidenceUnavailable`) 정보 부족(SUCCESS)으로 끝낸다.
- 사용량은 `children-facts`, `children-review`로 기록한다.

## 남은 작업

- 평가셋(장난감·유아 섬유·학용품·유모차·카시트·보행기·어린이 자전거, 성인용·연령 불명 포함)과 사람 검토 정답
- 적용범위의 연령·수치 조건(예: 스케이트보드 체중 20kg 초과, 유아용 섬유제품 36개월 미만) 코드화
- 어린이용 전기제품의 전기 Tool과 중복 적용 관계
- DB 품목표 조회, ToolExecutor 연결

## 검증

- 단위 테스트(모델·API는 Fake, 품목표는 실제 법제처 응답 픽스처): `ai/`에서

  ```bash
  uv run pytest tests/tools/children tests/tools/test_registry.py tests/prompts -q
  ```
- 대표 결과를 실제 `VerificationAgent().verify_rules()`에 넣어 재실행 요청·이슈가 없는지 테스트로 확인한다.
- 2026-10-14 실제 모델(gpt-4.1-mini) 확인: 원목 블록 장난감 → 완구(안전확인), 유모차 → 유모차(안전확인),
  아동용 옷걸이 → 어린이용 가구(공급자적합성확인), 성인용 퍼즐(14세 이상) → 어린이제품 아닐 가능성. 상품당 2~6초.
