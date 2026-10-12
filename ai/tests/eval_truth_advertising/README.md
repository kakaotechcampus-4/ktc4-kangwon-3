# 표시·광고 Tool 평가셋

`dev.json`은 상품별로 꼭 잡아야 할 문구(`must_flag`), 잡으면 안 되는 문구(`must_not_flag`),
판단 보류(`acceptable`)를 짧은 인용으로 적은 정답이다. 문구마다 근거(실증 고시·지정고시·심사지침 항목)를 남겼다.

입력 listing_text는 판매자 문장 원문이라 저장소에 올리지 않는다(`tests/fixtures/README.md`).
`tests/fixtures/_raw/advertising_dev_inputs.json`으로 로컬에 두고 `_raw`와 같이 노션 zip으로 받는다.
`dev.json`의 `inputs_sha256_12`(줄바꿈을 LF로 맞춘 SHA-256 앞 12자)와 다르면 러너가 실행하지 않는다.

```bash
python -m app.eval.advertising_runner --runs 3                                # .env 모델
python -m app.eval.advertising_runner --runs 3 --model "openai/gpt-6-luna#low"
python -m app.eval.advertising_runner --rescore logs/eval/advertising-<시각>.json   # 정답만 고친 뒤 다시 채점
```

- 개발 중 보고 고치는 셋이라 홀드아웃이 아니다. 최종 확인은 `_raw`의 `ali_holdout_*`로 한 번만 한다.
- 셋이 작아(상품 14개, `must_flag` 17개) 비율 대신 건수로 본다.
- 판단 기준은 SELECTION_EVAL.md 5절과 맞춘다. 인증 이름만 나열한 사양은 잡지 않는다(5절 ③).
- "고농도 화학 물질 없음"(AliExpress 사양 항목)과 수치 없는 기능 주장("RFID 차단" 등)은 팀 논의 전까지 판단 보류다(#295).
