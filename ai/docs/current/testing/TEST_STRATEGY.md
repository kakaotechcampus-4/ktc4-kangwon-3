# AI 테스트 전략

AI 서버 코드를 무엇으로 테스트하는지, 테스트를 어디에 두고 어떻게 실행하는지, 커버리지를 어떤 기준으로 검사하는지 정리한다. 실제 모델을 호출하여 판단 정확도를 측정하는 평가는 [EVAL_COMMON.md](../eval/EVAL_COMMON.md)와 평가별 문서를 참고한다.

## 1. 테스트 계층

| 계층 | 확인하는 것 | 모델·외부 API | 실행 |
|---|---|---|---|
| 단위 | 규칙·계산·분기(저전압 판정, 연령 읽기, 법령 이름 대조 등), 예외 처리, 채점기·정답셋 형식 | 가짜 | `pytest`, CI |
| 통합 (`integration`) | 앱을 실행하여 요청·세션·콜백이 이어지는 흐름 | 가짜 부품 | `pytest`, CI |
| 외부 API (`external_api`) | 법제처 등 실제 외부 API 응답 | 실제 외부 API | `pytest -m external_api`, CI 제외 |
| 단계별 평가 | 추출·선택·입력 가드·가드레일·Tool 하나의 판단 | 실제 모델 | `python -m app.eval.<러너>` |
| 시나리오 끝단 평가 | 원문 → 추출 → 선택 | 실제 모델 | `python -m app.eval.scenario_runner` |

- **결정적인 원인은 아래 계층으로 내려 고정한다.** 평가에서 발견한 문제 중 원인이 결정적인 것(규칙·정규식·분기)은 단위·통합 테스트로 남긴다. 단위·통합 테스트는 빠르고 비용이 없어 CI에서 실행된다.
- **통합 테스트가 필요한 경우**: 주석에 "다른 부품이 처리한다"고 기재하였을 때, 스키마 칸을 새로 만들거나 의미를 바꾸었을 때, 새 예외를 발생시킬 때. 가짜 부품은 앞 단계가 실제로 반환할 수 있는 값만 반환한다.
- **실패 상황은 가짜 부품으로 만든다**: 모델 호출 실패·스키마 위반, 법령 조회 실패, 결정사례 DB 무응답, 일부 Tool 실패, 재실행해도 같은 결과, 검증 모델의 잘못된 ID. 실패 전까지 얻은 결과를 보존하는지부터 확인한다.
- 실제 모델 평가는 결과가 확률적이고 비용이 들기 때문에 CI의 통과 기준으로 사용하지 않는다. 프롬프트·모델·판단 규칙을 수정하면 해당 평가를 CLI로 실행하여 기준선과 비교한다.

## 2. 디렉터리

| 위치 | 내용 |
|---|---|
| `tests/<app 패키지>/` | `app/` 구조에 대응하는 단위·통합 테스트(`agents`, `tools`, `pipeline`, `diagnosis`, `routers` 등) |
| `tests/test_main.py`, `tests/test_flow.py` | 앱 기동과 진단 흐름 통합 테스트 |
| `tests/eval/` | 평가 채점기·러너의 결정적 동작과 정답셋 형식 검사(모델 호출 없음) |
| `tests/eval_truth*/` | 평가 정답셋. 평가별 위치는 [EVAL_COMMON.md](../eval/EVAL_COMMON.md) 1장 |
| `tests/fixtures/` | 테스트·평가 입력. 상용 원문은 `tests/fixtures/_raw/`(git 추적 제외)에 둔다([tests/fixtures/README.md](../../../tests/fixtures/README.md)) |
| `tests/integration/` | 실제 외부 API 테스트(`external_api`). 키가 없으면 건너뛴다 |
| `tests/scripts/` | `scripts/` 도구 테스트 |

- `--import-mode=importlib`로 실행하므로 폴더가 다르면 같은 이름의 테스트 파일을 둘 수 있다.

### 공용 fixture

| 위치 | 내용 |
|---|---|
| `tests/conftest.py` | LangSmith 기록을 끄고, 사용량 기록 파일을 테스트마다 임시 경로로 돌린다(autouse). 가짜 쇼핑몰 페이지 fixture(`aliexpress_page`·`temu_page`·`coupang_page`) |
| `tests/app_harness.py` | 실제 `.env`·DB·Sentry 없이 앱을 기동하는 도구. `app_env`(기동 설정), `FakeBackend`(콜백을 받는 가짜 BE), `fake_parts`·`client`(가짜 부품 묶음과 앱 클라이언트) |
| 하위 `conftest.py` | 패키지별로 공유하는 fixture |

## 3. 마커와 실행

`pytest.ini`에 마커 2개를 정의한다.

| 마커 | 대상 | 기본 실행 |
|---|---|---|
| `integration` | 앱을 실행하여 요청·세션·콜백이 이어지는 흐름을 확인하는 테스트. 파일에 `pytestmark = pytest.mark.integration`을 기재한다 | 포함 |
| `external_api` | 실제 외부 API를 호출하는 테스트(키 필요) | 제외 |

- 표시가 없으면 단위 테스트로 실행·측정되므로, 흐름 테스트를 새로 작성하면 `integration` 표시를 반드시 기재한다.

```bash
cd ai
pytest                                        # 단위 + 통합 (external_api 제외)
pytest -m "not external_api and not integration"  # 단위만
pytest -m integration                         # 통합만
pytest -m external_api                        # 실제 외부 API
```

CI(`.github/workflows/ai.yml`)는 `ai/**`를 변경한 PR(develop·main 대상)과 develop 푸시에서 단위·통합 테스트와 커버리지 검사를 실행한다.

## 4. 커버리지

`pytest-cov`(coverage.py)로 단위, 통합, 합산(단위 + 통합) 커버리지를 라인·분기 기준으로 각각 측정한다. BE(JaCoCo)와 동일한 구성이다. 합산 수치만 확인하면 통합 테스트가 실행한 줄에서 단위 테스트의 공백이 드러나지 않는다.

커버리지는 코드가 테스트로 실행되었는지만 확인한다. 실제 모델의 판단이 맞는지는 평가셋 지표로 별도 확인한다.

- 통합: `integration` 표시가 있는 테스트(3장).
- 단위: 나머지 전부.
- 실제 외부 API를 호출하는 테스트(`external_api`)는 둘 다에서 제외된다.

**리포트**

| 리포트 | 측정 범위 | 위치 (`ai/` 기준) |
|---|---|---|
| 단위 | 판단 로직 패키지(`agents`·`tools`·`pipeline`·`diagnosis`·`sessions`·`callbacks`·`results`) | `htmlcov-unit/index.html`, `coverage-unit.json` |
| 합산 | `app/` 전체에서 `app/eval` 제외 | `htmlcov/index.html`, `coverage.json`, `coverage.xml` |

- `app/eval`은 실제 모델을 호출하여 정답률을 측정하는 평가 실행 코드이므로 측정 범위에서 제외한다(`.coveragerc`).
- 통합 리포트는 별도로 생성하지 않으며, 통합 테스트만의 수치는 기준으로 사용하지 않는다.

**기준**

| 대상 | 라인 | 분기 | 검사 시점 |
|---|---|---|---|
| 단위 | 90% | 90% | PR·develop 푸시 |
| 합산 | 85% | 80% | PR·develop 푸시 |
| PR에서 바뀐 줄 | 90% | — | PR (`diff-cover`, base 브랜치 대비) |

- 통합에는 기준을 두지 않는다. 기준 충족을 위해 단위 테스트가 이미 확인한 분기를 통합 테스트로 중복 작성하게 되기 때문이다.
- 단위·합산 기준은 큰 하락을 방지하는 용도이며, 새 코드의 테스트 누락은 바뀐 줄 기준으로 검사한다.
- 기준에 미달하면 CI가 실패하고 배포도 중단된다. 실패하면 Actions 산출물 `coverage-report`에 HTML 리포트가 업로드된다(7일 보관).
- 긴급 배포가 필요하면 Actions에서 `AI CI/CD`를 수동 실행하고 `skip-coverage`를 활성화한다.

**로컬 실행** (`ai/`에서)
```
pytest --cov --cov-report=html                          # 전체(단위 + 통합) 측정, htmlcov/index.html
pytest -m "not external_api and not integration" --cov  # 단위만
pytest -m integration --cov                             # 통합만
python scripts/check_coverage.py coverage.json --line 85 --branch 80  # --cov-report=json 결과로 기준 검사
```

---

변경 이력: [history/TEST_STRATEGY.md](../../history/testing/TEST_STRATEGY.md)
