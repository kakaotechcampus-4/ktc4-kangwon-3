# 통관 요건 Tool — HS 후보 · 세관장확인 요건

## 파일 구성

| 위치 | 내용 |
|---|---|
| `app/tools/customs/tool.py` | `CustomsTool` 흐름 (결정 요소 추출 → 결정사례 조회 → 결정사례 선택 → 요건 조회 → 결과 조립) |
| `app/tools/customs/search.py` | 결정사례 조회 `CaseSearch`(`ClipCaseSearch`), 요건 조회 `RequirementLookup`(`GwRequirementLookup`), 근거 캐시 |
| `app/tools/customs/evidence.py` | 관세법 제226조, 세관장확인 고시 제7조·별표 2, 대외무역법 시행령 제19조 읽기 |
| `app/tools/customs/rules.py` | HS 표기, 요건 법령 ↔ 다른 규제 Tool 대응, 판매 방식별 안내 |
| `app/tools/common/` | 규제 Tool 공용 모듈(어린이 Tool #313과 같은 내용): 법제처 조회, 모델 호출 단계, 원문 대조, 행 순위 |
| `app/schemas/customs.py`, `app/prompts/customs/facts.md`·`review.md` | LLM 입출력 |
| `app/eval/customs_runner.py` | 실제 실행·평가 채점 (`python -m app.eval.customs_runner`) |
| `tests/tools/customs/` | 단위 테스트와 Fake(`conftest.py`) |
| `tests/fixtures/customs_law/` | 실제 법제처·CLIP 응답 (출처·버전은 README) |
| `tests/eval_truth_customs/holdout.json` | 홀드아웃 평가셋 16개 (예상 HS 앞자리, 사람 검토 전) |

`app.tools.registry`는 그대로 `from .customs import CustomsTool`로 가져온다.

## 흐름

HS 분류는 관세청이 정한다. 이 Tool은 **비슷한 품목분류 결정사례로 HS 후보**를 찾고, 그 HS에 걸리는 **세관장확인 요건 후보**를 낸다.
다른 Tool과 달리 규칙(요건 조회)이 선택 뒤에 온다. HS 후보가 정해져야 요건을 찾을 수 있기 때문이다.

```text
Product (추출 에이전트 결과)
→ ① LLM 결정 요소 추출   제품 종류·재질·기능·용도·구성품 + 원문 인용, 검색어 3~4개(영문 1개 포함)   (prompts/customs/facts.md)
→ ② 코드 결정사례 조회   CLIP 검색어별 30건 → 합쳐서 상품 용어와 글자 유사도 상위 8건          (customs/search.py)
→ ③ LLM 결정사례 선택   후보 중 같은 물품의 사례 최대 3건 + 이유. HS는 사례에 적힌 값을 코드가 쓴다  (prompts/customs/review.md)
→ ④ 코드 요건 조회       HS 10자리마다 세관장확인 GW → 대상 법령·요건확인기관·제출 서류
→ ⑤ 코드 결과 조립       법령별 판단 + 근거(관세법 제226조, 고시 별표 2 행·제7조, 시행령 제19조, 결정사례) + 판매 방식별 할 일
```

### 결정사례 조회 (CLIP)

- CLIP은 검색어가 물품명·설명에 들어 있는 사례를 **최신순**으로 준다(관련도순 아님). 그래서 검색어마다 30건을 받아 합친 뒤 `common.ranking.rank_rows`로 다시 고른다.
- CLIP은 검색어를 구절 그대로 찾아 **두 낱말 이상이면 결과가 거의 없다**(예: "자동 우산", "양수 냄비" 0건, 실측). 그래서 여러 낱말 검색어는 마지막 낱말(중심 명사)도 함께 찾는다. 상품별 동의어 사전은 두지 않는다.
- 결정사례 물품명은 영문 품목분류 표현이 많다("Umbrellas, …", "POWER BANK"). 조건 추출 모델이 영문 보통 명칭 하나를 검색어에 넣는다.
- 일부 검색어는 10초 넘게 응답이 없다(시간 초과, 실측으로 검색어 셋 중 하나꼴). 검색어를 **동시에** 보내고, 실패한 검색어는 건너뛰며 `query.failed_terms`에 남긴다. 모두 실패하면 Tool 오류다.
- DB 조회: `hs_cases` 테이블(결정사례 + 임베딩, `HsCaseRepository.search_by_vector`) 적재 후 `CaseSearch`를 구현한 벡터 조회 객체를 Tool에 넘기면 된다(#362). 같은 `CaseCandidates`를 돌려주면 Tool은 바꾸지 않는다.

### 세관장확인 요건 (GW)

- `GwRequirementLookup`은 관세청 세관장확인대상물품 GW(`CustomsGwClient`, 공공데이터포털 키 `DATA_GO_KR_KEY`)로 HS 10자리를 조회한다. HS별로 6시간 캐시한다.
- 빈 목록은 **통관 단계의 세관장확인이 없다**는 뜻일 뿐 국내 판매 규제가 없다는 뜻이 아니다.
- 키가 없으면 `EvidenceUnavailable` → 요건 "조회하지 못함"(정보 부족) + UNI-PASS 확인 안내. 6자리 HS도 GW를 조회할 수 없어 같은 처리다.
- GW 실제 응답으로 확인했다(2026-10-19, HS 12개). 법령 이름은 별표 2 행·제7조 단서와 모두 대응됐다.
  - GW는 같은 법령에 요건 종류를 붙여 줄 때가 있다(예: "야생생물 보호 및 관리에 관한 법률(허가)"). 비교 키에서 끝의 괄호를 떼고, 판단도 이 키로 묶어 법령마다 하나로 낸다.
  - 같은 법령이 요건확인기관 수만큼 반복해 온다(전안법 5행 등). 판단은 법령마다 하나로 묶는다.

### 근거 법령 (법제처)

| 문서 | 쓰는 곳 |
|---|---|
| 관세법 제226조 | 모든 요건 판단의 근거(수입 시 다른 법령의 조건을 세관장에게 증명) |
| 세관장확인 고시 별표 2 | GW가 준 법령 이름으로 행을 찾아 "대상 법령 및 물품의 범위 — 구비요건" 원문을 인용(40행, 삭제 행 제외) |
| 세관장확인 고시 제7조 제2항 | 대외무역법 시행령 제19조 사유 물품은 세관장확인 생략 가능. 단서의 18개 법령은 생략하지 않음 |
| 대외무역법 시행령 제19조 | 수출입승인 면제 사유(상행위 이외 목적 등). 구매대행 안내의 근거 |

법령 이름은 공백·가운뎃점 차이를 무시하고 비교한다(고시 "안전 관리법"·"ㆍ", GW "안전관리법"·"·").

## 결과

| 경우 | 판단 |
|---|---|
| HS 후보에 요건 법령이 있음 | 법령마다 `POSSIBLY_REQUIRED`, subject `"세관장확인 대상 후보 — {법령}"`, summary "HS …로 분류되면 … 가능성이 있습니다(확정 아님)" |
| HS 후보에 요건 법령이 없음 | `NOT_REQUIRED`, risk LOW, "세관장확인 대상 법령 — HS 후보 기준 없음". 근거 관세법 제226조. assumptions에 "다른 HS로 분류되면 요건이 생길 수 있음", "국내 판매 규제가 없다는 뜻은 아님". 조회해서 받은 답이라 정보 부족으로 내지 않는다(정보 부족이면 종합 단계가 상품 전체를 정보 부족으로 만듦). 판단을 빼면 검증 규칙이 재실행을 요청하므로 #315 표시·광고 Tool의 "주장 없음"과 같이 판단 하나로 낸다 |
| 위와 같지만 근거 법령(관세법)을 읽지 못함 | `INSUFFICIENT_INFORMATION`, risk LOW, "조회되지 않음". 확정 판단에 붙일 인용이 없어서 |
| 요건을 조회하지 못함(키 없음·6자리) | `INSUFFICIENT_INFORMATION`, "조회하지 못함" + UNI-PASS·관세사 확인 할 일 |
| 제품 종류 없음·사례 없음·맞는 사례 없음 | `INSUFFICIENT_INFORMATION`. 비대상으로 해석하지 않는다 |

- 판단마다 `requirements`에 그 법령의 판매 안내를 넣는다(재실행에서 판단이 빠지면 ToolExecutor가 그 할 일만 지운다).
- **판매 방식별 할 일**(`rules.sale_actions`, 모두 조건부):
  - 사입·수입: 이 HS로 분류되면 수입신고 때 세관장확인. 요건확인기관·제출 서류(GW) 또는 별표 2 구비요건.
  - 구매대행: 법령이 고시 제7조 제2항 제1호 단서에 있으면 "시행령 제19조 사유의 수입이어도 생략 대상에서 빠짐"(조건 원문 포함), 없으면 "시행령 제19조 사유면 생략할 수 있음, 해당 여부 확인 필요". 고시를 못 읽었으면 "확인 필요".
- 요건 법령이 다른 규제 Tool의 법이면(전안법 → 전기, 전파법 → 전파, 어린이제품법 → 어린이, 수입식품법·의료기기법·화장품법 등 → 식약) `query.related_tools`와 판단 assumptions에 남겨, 검증 단계가 같은 법의 제품 판단과 함께 보게 한다.
- 결정사례 근거는 `source_name="관세청 품목분류 결정사례(CLIP)"`, 공개 열람 주소가 없어 `source_url`은 비운다(확정 판단의 근거로 쓰지 않는다).
- 질문은 HS를 가르는 조건(제품 종류·재질·기능)만 낸다. 선택 모델이 더 필요하다고 한 그 밖의 조건은 assumptions에 "HS 확정에는 … 확인이 더 필요합니다"로 남긴다.
- `CustomsAssessment`: `hs_code_candidates`(표기 "8516.79-9000"), `applicable_requirements`(법령), `required_documents`, `customs_confirmation_required=None`(확정 아님).
- `query`: `search_terms`, `failed_terms`, `candidate_cases`, `selected_cases`, `hs_candidates`, `requirements`(HS → 법령), `related_tools`, `documents`, 버린 수.
- 모델 호출은 공통 `ToolStep`(BaseAgent #284). 사용량 이름은 `customs-facts`, `customs-review`.
- 모델·CLIP 전체 실패·GW 오류·법령 조회 오류는 `CustomsToolError`(원인은 예외 체인). 법령 버전·본문을 확인할 수 없으면 근거 조문 없이 안내를 계속한다.

## 검증

```bash
python -m pytest tests/tools/customs tests/tools/test_registry.py -q
```

- 법제처·CLIP은 실제 응답 픽스처, GW는 응답 형식을 따른 Fake, 모델은 Fake.
- 대표 결과(요건 있음·없음·미확인·정보 부족)를 실제 `VerificationAgent().verify_rules()`에 넣어 이슈가 없는지 확인한다.

## 평가 (2026-10-15, gpt-4.1-mini, 1회)

`python -m app.eval.customs_runner --eval tests/eval_truth_customs/holdout.json`

| 실행 | HS 정답(예상 앞자리 일치) | 비고 |
|---|---|---|
| 1차 | 6/16 | 두 낱말 검색어가 CLIP에서 0건인 문제로 6건이 후보 없음 |
| 2차 | 9/16 | 중심 명사·영문 검색어 추가 후. **1차 결과를 보고 고친 뒤라 이 셋은 더 이상 홀드아웃이 아니다** |

- 남은 오답 유형: 유리컵 → 도자기 사례(6912), 립스틱·마스크팩 → 인접 소호(3304.99/3307.90), 지갑·드라이버·스마트워치 → 맞는 사례가 조회되지 않음.
- 예상 HS는 사람 검토 전이다(스마트워치 8517.62 등 판단이 갈릴 수 있음). 관세청 품목분류표와 대조한 새 평가셋이 필요하다.
- 조회 품질의 근본 한계는 CLIP 키워드 검색이다. `hs_cases` 임베딩 적재 후 벡터 조회 객체로 바꾸고 같은 평가로 비교한다.

## 남은 작업

- GW 실제 응답 확인(배포 키), 요건 법령 이름이 별표 2 행과 모두 대응하는지 확인.
- 고시 별표 2의 하위 구분((가)안전인증대상 등)과 GW 요건의 대응. 지금은 법령 단위로만 묶는다.
- 목록통관·소액 면세와 세관장확인의 관계, 별표 5(자율확인우수기업 등 생략 대상 수출입자)는 다루지 않는다.
- HS 6단위 사례의 10단위 후보 찾기.
- 판매 방식(구매대행/사입)을 진단 입력으로 받는 것은 BE·FE와 합의할 사항이다. 지금은 두 경우의 할 일을 함께 낸다.
