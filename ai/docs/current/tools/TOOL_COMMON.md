# 규제 Tool 공통

규제 Tool 6개가 공통으로 사용하는 실행 틀과 규칙을 설명한다. Tool별 판정 규칙과 화면 문구는 각 Tool 문서에서 설명한다.

## 1. 개요

규제 Tool은 선택 에이전트가 선택한 분야별로 실행되며, 상품이 해당 분야 법령의 규제 대상일 가능성과 판매 전 할 일을 제시한다.

- 확정 판단을 내리지 않는다. 판단은 "대상일 수 있음", "확인 필요", "정보 부족" 등 후보 형태로 제시한다.
- 모델은 후보 선택과 조건 해석만 담당한다. 법령 문구는 코드가 법제처 원문에서 조회하여 그대로 근거로 첨부한다.
- 조회 실패를 비대상으로 처리하지 않는다. 근거를 확인하지 못하면 정보 부족 판단 또는 Tool 실패로 기록한다.

| Tool | `ToolName` 값 | 문서 |
|---|---|---|
| 통관 요건 | `customs_requirements` | [CUSTOMS_TOOL.md](CUSTOMS_TOOL.md) |
| 전파 | `radio_compliance` | [RADIO_TOOL.md](RADIO_TOOL.md) |
| 식품·의약품 | `food_drug_safety` | [FOOD_DRUG_TOOL.md](FOOD_DRUG_TOOL.md) |
| 전기용품 안전 | `electrical_safety` | [ELECTRICAL_TOOL.md](ELECTRICAL_TOOL.md) |
| 어린이제품 안전 | `children_product_safety` | [CHILDREN_TOOL.md](CHILDREN_TOOL.md) |
| 표시·광고 | `labeling_advertising_detection` | [ADVERTISING_TOOL.md](ADVERTISING_TOOL.md) |

## 2. 구성

### 실행 틀

| 틀 | 위치 | 사용하는 Tool | 역할 |
|---|---|---|---|
| `RegulatoryTool` | `app/tools/base/tool.py` | 6개 전체 | 실행 진입점 `execute`. 선택되지 않은 Tool은 조회 없이 `SKIPPED`를 반환하고, 선택된 Tool만 `_run`을 실행 |
| `EvidenceSearchTool` | `app/tools/base/evidence_search.py` | 표시·광고를 제외한 5개 | 조건 추출 → 원문 대조 → 판단 → 결과 조립의 공통 흐름. Tool은 판단(`_judge`)과 상세 결과(`_detail`)만 구현 |

표시·광고 Tool은 조건 추출과 후보 조회 단계가 없으므로 `RegulatoryTool`을 직접 상속한다.

### 공용 모듈

| 위치 | 내용 |
|---|---|
| `app/tools/base/run.py` | 실행 1회의 상태 `ToolRun` (원문 조각, 조건, 질문할 필드, 가정, 할 일, 조회 기록) |
| `app/tools/base/steps.py` | Tool 내부의 모델 호출 단계 `ToolStep` (조건 추출, 후보 선택). 공통 에이전트 베이스 `BaseAgent`를 상속 |
| `app/tools/base/errors.py` | 모델 호출·구조화 출력 실패 `ToolModelError` |
| `app/tools/common/facts.py` | 상품 원문 조각 생성, 조건의 원문 대조, 조사(을·를, 은·는) 선택 |
| `app/tools/common/law.py` | 법제처 법령·행정규칙 조회, 버전 선택, 조문·별표 해석, 근거 캐시 |
| `app/tools/common/law_sources.py` | Tool들이 근거로 사용하는 법령·행정규칙 목록. 법령 점검 스케줄러가 사용 |
| `app/tools/common/questions.py` | 판매자 질문 문장과 도움말 카탈로그 |
| `app/tools/common/ranking.py` | 품목표 행을 상품 용어와의 글자 유사도로 선정하는 조회 |
| `app/tools/registry.py` | `ToolName`과 Tool 클래스의 대응 |
| `app/diagnosis/assembly.py` | 서버가 사용하는 Tool 6개를 조회 객체와 함께 조립 |

## 3. 처리 흐름

`EvidenceSearchTool`을 사용하는 5개 Tool은 아래 순서로 실행된다.

```text
① 원문 조각 생성     판매 글과 속성 원문만 조각으로 생성
   └ 조각이 없으면 → 정보 부족 판단 + Tool이 지정한 필드 질문으로 종료
② 준비 (_prepare)    Tool에 따라 품목 목록·근거를 미리 조회
③ 조건 추출          모델이 조건과 해당 원문 인용을 추출
④ 원문 대조          인용이 원문에 없거나 값이 인용에 없는 조건은 제외
⑤ 조건 해석          Tool별 상태 정리 (주파수·연령·충돌 등)
⑥ 판단 (_judge)      Tool별 조회·규칙·후보 선택으로 판단 생성
⑦ 결과 조립          판단이 없으면 정보 부족 판단 하나를 추가
```

- 원문 조각이 있으면 가정 첫 줄에 "전체 상품 원문이 아니라 전달된 설명·속성 근거만 확인했습니다."를 기록한다.
- ④에서 제외한 조건이 있으면 "원문과 대조되지 않은 상품 조건 N개를 제외했습니다." 가정을 기록한다.
- 추출 에이전트가 상품 정보의 모순을 표시한 경우, 조회를 중단하지 않고 가정으로만 기록한다.
- ⑦에서 판단이 없으면 Tool이 지정한 제목·요약·근거로 `INSUFFICIENT_INFORMATION`·`UNKNOWN` 판단 하나를 추가한다. 빈 후보를 비대상의 근거로 사용하지 않기 위함이다.
- 질문과 할 일은 결과 조립 시 중복을 제거한다.

### 실패 처리

| 상황 | 처리 |
|---|---|
| 근거 문서를 확인할 수 없음 (`EvidenceUnavailable`) | Tool이 지정한 가정을 기록하고 해당 조회만 생략. Tool 실행은 계속 |
| 조회 중 그 밖의 예외 | Tool별 실패 예외(`ToolModelError` 하위)로 변환하여 발생. 원인은 예외 체인에 보존 |
| 모델 호출·구조화 출력 실패 | `ToolModelError`. 실패 문구에 원인 예외 내용은 포함하지 않음 |

Tool에서 발생한 예외는 파이프라인의 Tool 실행기(`app/pipeline/tool_executor.py`)가 처리하며, 해당 Tool 결과를 `FAILED`로 기록한다.

## 4. 원문 대조

모델이 추출한 조건은 상품 원문과 대조하여 일치하는 것만 사용한다. 원문에 없는 값이 판단 근거가 되는 것을 방지하기 위함이다.

- 인용 근거로 인정하는 원문은 판매 글(`listing_text`)과 속성 원문(`Attribute.source_text`)뿐이다. 조각 ID는 `listing-0`, `attribute-0` 형식이다.
- 조건은 조각 ID, 인용, 값으로 구성된다. 인용이 지정한 조각 안에 연속으로 존재하고, 값이 인용 안에 존재하는 경우에만 유지한다.
- 대조 시 전각·호환 문자(NFKC), 공백, 표 테두리, 대소문자 차이는 무시한다.
- 값의 낱말이 인용 안에 같은 순서로 존재하면, 사이에 다른 낱말이 있어도 일치로 인정한다. 예: 인용 "탁상용 미니 선풍기", 값 "탁상용 선풍기".
- 단, 숫자가 포함된 낱말과 부정 표현(아님, 없음, 미포함, 제외, not, without 등)은 생략할 수 없다. 원문에 없는 수치 조합이나 의미가 반대인 값을 방지하기 위함이다.
- 낱말 단위로 완전히 일치해야 한다. "포함"은 "미포함"의 일부로 인정하지 않는다.
- 값이 판단 결과("예"·"아니오")인 조건은 인용만 대조한다.

## 5. 후보 선택 대조

후보 행을 선택하는 Tool은 선택 모델의 결과를 후보 목록 및 대조된 조건과 다시 대조한다(`EvidenceSearchTool._pick`).

| 선택 | 처리 | 조회 기록(`query`) |
|---|---|---|
| 모델이 해당 없음(`applies=false`)으로 표시 | 사용하지 않음 | `not_applicable` |
| 후보 목록에 없는 ID | 제외 | `dropped_candidates` |
| 이미 선택된 ID | 제외 | `dropped_candidates` |
| 근거로 제시한 조건 중 원문과 대조된 조건이 없음 | 제외 | `dropped_candidates` |
| Tool의 코드 규칙상 허용되지 않는 후보 | 제외 | `dropped_candidates` |
| 상한 초과 | 사용하지 않음 | `over_limit` |

- 무효한 선택을 먼저 제외한 뒤 상한을 적용한다. 앞 순서의 무효한 선택 때문에 유효한 후보가 상한에서 밀려나지 않도록 하기 위함이다.
- 기본 상한은 3개(`SELECTIONS_LIMIT`)다.
- 근거로 제시한 조건 중 일부만 대조된 경우, 대조된 조건만 근거로 유지하고 선택은 사용한다.
- 판단에 사용한 조건은 "{표시 이름}: {값} (근거: {인용})" 형식으로 판단의 `product_facts_used`에 기록된다.

## 6. 질문

Tool은 판단에 필요하지만 확인되지 않은 조건을 결과의 `missing_information`에 질문 문장으로 기록한다.

질문 문장은 아래 우선순위로 결정한다.

1. 값이 서로 달라 판단하지 않은 조건: "{표시 이름} 정보가 서로 달라 확인이 필요합니다."
2. Tool 고유 문장
3. 공통 카탈로그(`app/tools/common/questions.py`)의 문장
4. 해당 문장이 없으면 "{표시 이름} 정보가 필요합니다."

- 같은 조건은 어느 Tool에서 질문하더라도 같은 문장을 사용한다. 진단 단계는 문장이 같은 질문을 하나로 합치며, 이전 회차에 질문한 문장은 다시 질문하지 않는다.
- 도움말(답변 방법 안내)은 Tool 결과에 포함하지 않는다. 진단 단계가 질문 문장으로 카탈로그에서 도움말을 찾아 추가한다.
- 질문 카탈로그와 검증 모델 질문의 중복 제거는 [AI_COMMON_CONTRACT.md](../contract/AI_COMMON_CONTRACT.md) 8.1장에서 설명한다.

## 7. 법령 근거 조회

### 버전 선택

법제처 검색 결과에서 기준일에 시행 중인 버전을 선택한다(`select_version`).

- 문서 ID와 이름이 정확히 일치하는 항목 중 시행일이 기준일 이전인 항목만 대상으로 한다.
- 공포·발령일을 함께 확인하는 문서는 가장 최근에 공포·발령된 버전들 중에서 선택한다.
- 그중 시행일이 가장 늦은 버전을 사용한다.
- 다음의 경우에는 임의로 선택하지 않고 `EvidenceUnavailable`로 처리한다.
  - 검색 목록이 불완전함
  - 후보가 없음
  - 같은 시행일에 버전이 둘 이상임
  - 일련번호 형식이 잘못됨

### 본문 확인

본문을 수신하면 검색에서 선택한 문서와 일치하는지 확인한다(`check_body`).

- 문서 ID나 이름이 다르면 `EvidenceUnavailable`로 처리한다.
- 시행일은 대조하지 않고, 다른 경우 로그만 기록한다. 시행일이 나뉜 개정판은 검색 결과와 본문의 시행일이 다르게 반환되기 때문이다. 근거의 시행일은 검색 결과의 값을 사용한다.

### 조회 경로와 캐시

- Tool은 법제처 응답을 DB 캐시에서 우선 조회하고, 없으면 법제처 API를 호출한다(`open_law_fetchers`). `DATABASE_URL`이 설정되지 않으면 API만 사용한다.
- DB 캐시는 검색 결과를 `LAW_SEARCH_RECHECK_SECONDS`(2일)가 지나면 다시 조회하며, 본문은 계속 보관한다. 상세 내용은 [DB_CACHE.md](../storage/DB_CACHE.md)에서 설명한다.
- Tool은 조회한 근거 묶음을 기준일별로 6시간 동안 메모리에 보관한다(`CachedLoader`). 동시에 여러 요청이 들어와도 한 번만 조회하며, 실패 결과는 캐시하지 않는다.
- 법제처 인증값은 `LAW_GO_KR_OC` 환경변수로 설정한다.

## 8. 결과와 화면

Tool 결과(`ToolResult`)의 주요 칸은 다음과 같다.

| 칸 | 내용 |
|---|---|
| `status` | `SUCCESS`, `SKIPPED`(선택되지 않음), `FAILED`(Tool 실행기가 기록), `PARTIAL`(재실행이 실패했으나 검증이 지적하지 않은 이전 회차 판단을 유지함. 분야 카드는 `INCOMPLETE`) |
| `findings` | 판단 목록. 판단별 제목, 판정, 위험도, 요약, 근거 설명, 근거 조문, 할 일, 사용한 조건, 가정 |
| `required_actions` | 판매 전 할 일 |
| `missing_information` | 판매자 질문 문장 |
| `result` | Tool별 상세 결과 |
| `query` | 조회·선택 기록. 제외한 조건·후보 수, 후보 ID 등 |

공개 진단서(`app/results/presenter.py`)로 변환할 때는 다음과 같이 처리한다.

- 분야 카드에는 판단의 제목, 판정, 위험도, 요약, 근거 설명, 근거 조문만 포함한다. 가정과 사용한 조건은 포함하지 않는다.
- 제목이 255자를 초과하면 잘라낸다. 요약이 비어 있으면 제목을, 근거 설명이 비어 있으면 요약을 사용한다.
- 할 일은 분야 순서로 모은 뒤 중복을 제거한다.
- 질문으로 전달되지 않은 부족 정보는 안내(`notices`)에 포함한다.

## 9. 설정

| 항목 | 값 | 위치 |
|---|---|---|
| 모델 프로필 | 6개 Tool 모두 `luna-low` | `app/config/profiles.py`의 `TOOL_PROFILES` |
| 프로필 임시 변경 | `MODEL_PROFILE_OVERRIDES=tool.<ToolName 값>=<프로필>` | 환경변수 |
| 후보 수 | 생성자 `top_k`. 기본 8, Tool별로 다를 수 있음 | 각 Tool 생성자 |
| 선택 상한 | 3 | `SELECTIONS_LIMIT` |
| 근거 캐시 | 기준일별 6시간 | `CachedLoader` |
| 법제처 인증값 | `LAW_GO_KR_OC` | 환경변수 |

- 조건 추출과 후보 선택 두 단계는 Tool 최초 실행 시 생성한 모델 하나를 공유한다.
- 가드레일(`guardrail.md`)은 표시·광고 Tool의 검토 단계에만 적용된다. 나머지 5개 Tool의 `ToolStep`에는 가드레일을 적용하지 않는다.
- Tool은 생성 시점에 설정·모델·API 연결을 만들지 않고, 최초 실행 시 생성한다.

## 10. 관련 코드·테스트

| 위치 | 내용 |
|---|---|
| `tests/tools/base/` | 실행 틀(`RegulatoryTool`, `EvidenceSearchTool`, `ToolRun`, `ToolStep`) |
| `tests/tools/common/` | 원문 대조, 질문 카탈로그, 근거 문서 목록 |
| `tests/tools/test_common_law.py` | 법제처 조회, 버전 선택, 본문 확인, 근거 캐시 |
| `tests/tools/test_registry.py` | Tool 등록 |

```bash
cd ai
python -m pytest tests/tools/base tests/tools/common tests/tools/test_common_law.py tests/tools/test_registry.py
```

---

변경 이력: [history/TOOL_COMMON.md](../../history/tools/TOOL_COMMON.md)
