# 표시·광고 Tool 평가셋

`dev.json`은 상품별로 꼭 잡아야 할 문구(`must_flag`), 잡으면 안 되는 문구(`must_not_flag`),
판단 보류(`acceptable`)를 짧은 인용으로 적은 정답이다. 문구마다 근거(실증 고시·지정고시·심사지침 항목)를 남겼다.

입력 listing_text는 판매자 문장 원문이라 저장소에 올리지 않는다(`tests/fixtures/README.md`).
`tests/fixtures/_raw/advertising_dev_inputs.json`으로 로컬에 두고, 노션 원문 페이지의 `advertising_inputs.zip`으로 받는다.
`dev.json`의 `inputs_sha256_12`(줄바꿈을 LF로 맞춘 SHA-256 앞 12자)와 다르면 러너가 실행하지 않는다.

```bash
python -m app.eval.advertising_runner --runs 3                                # .env 모델
python -m app.eval.advertising_runner --runs 3 --model "openai/gpt-6-luna#low"
python -m app.eval.advertising_runner --rescore logs/eval/advertising-<시각>.json   # 정답만 고친 뒤 다시 채점
python -m app.eval.advertising_runner --truth tests/eval_truth_advertising/holdout.json --runs 5
```

- 개발 중 보고 고치는 셋이라 홀드아웃이 아니다.
- 셋이 작아(상품 14개, `must_flag` 18개) 비율 대신 건수로 본다.
- `_raw`의 `ali_holdout_*`는 추출 평가 홀드아웃(#279)이라 이 Tool 평가에 쓰지 않는다.
- 판단 기준은 SELECTION_EVAL.md 5절과 맞춘다. 인증 이름만 나열한 사양은 잡지 않는다(5절 ③).
- "고농도 화학 물질 없음"(AliExpress 사양 항목)과 수치 없는 기능 주장("RFID 차단" 등)은 팀 논의 전까지 판단 보류다(#295).

## 홀드아웃 (`holdout.json`)

`dev.json`·추출 홀드아웃과 겹치지 않는 `_raw` 원문 9개. 입력은 서비스 추출 모델(gpt-4.1-mini)이 원문에서 한 번 뽑은
listing_text를 `tests/fixtures/_raw/advertising_holdout_inputs.json`으로 고정했다. 정답은 dev와 같은 기준이다.

| 측정 | 프롬프트 | 맞힘 | 오탐 | 미분류 |
|---|---|---|---|---|
| 2026-10-13, mini 5회 | e39d15ab | 39/50 | 13 | 80 |
| 위 결과 + KC 표기 코드 규칙(저장 결과 재채점) | e39d15ab | 44/50 | 13 | 80 |
| 정답 보강 후 같은 결과 재채점 (참고값) | e39d15ab | 88/100 | 23 | 6 |
| 정답 보강 + KC 규칙 (참고값) | e39d15ab | 93/100 | 23 | 6 |

- 같은 프롬프트로 dev는 90/90(mini 5회)이었다. 숫자를 보고할 때는 홀드아웃 값을 쓴다.
- KC 표기 코드 규칙은 이 홀드아웃에서 "KC인증"을 0/5로 놓친 것을 보고 넣었다. 그래서 44/50의 KC 항목은 처음 보는 상품 성능이 아니다.
- 미분류 80개는 대부분 헤어드라이어(e2e_page_01)의 판매자 주장이었다. 정답표가 이 상품의 주장을 다 담지 못해서,
  5회 중 2회 이상 나온 17개를 dev와 같은 원칙(성능 수준을 평가하는 말이 붙으면 잡고, 기능이 있다는 서술은 보류)으로
  추가했다. 결과를 본 뒤 정한 정답이라 "참고값" 줄은 오탐률을 보기 위한 값이고 처음 보는 상품 성능으로 쓰지 않는다.
- 이 결과를 보고 프롬프트를 고치면 이 셋은 더 이상 홀드아웃이 아니다. 다음 확인에는 새 페이지가 필요하다.
