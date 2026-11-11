# AI_METRICS 변경 이력

[AI_METRICS.md](../../current/observability/AI_METRICS.md)의 변경 경위를 최신순으로 기록한다. 아래 인용은 재작성 전 문서(develop c57f1c29)의 문장을 수정 없이 옮긴 것이며, 괄호 안 줄 번호는 해당 문서 기준이다.

## #823 현재 동작 기준 재작성 (2026-11-11)

- develop c57f1c29 기준 코드와 대조하여 본문을 문어체로 재작성하였다. 1장에 포함되어 있던 대시보드 설명을 4장으로 분리하고, 기존 4장 "추가 예정"은 아래 "재작성 전 계획·남은 작업"으로 이동하였다.
- 법령 점검·CLIP 적재의 실행 시각은 [DB_CACHE.md](../../current/storage/DB_CACHE.md)를 정본으로 하고 본문에서는 연결만 한다.
- 코드와 일치하지 않던 내용을 삭제하였다. 서버는 실제 파이프라인으로 진단하므로 `ToolExecutor`와 추출 에이전트가 운영 서버에서도 실행되며, Tool·추출 지표가 서버 `/metrics`에 누적된다(`app/diagnosis/job.py`).

> - 지금 서버 앱은 `ToolExecutor`를 만들지 않음(평가 실행에서만 사용). 파이프라인 연결(#320) 전까지 서버 `/metrics`에서는 0 (138줄)

> - Tool과 같은 이유로 파이프라인 연결(#320) 전까지 서버 `/metrics`에서는 0 (`ExtractionAgent`는 평가 실행에서만 사용) (150줄)

- `ai_agent_calls`의 `outcome`에 실패 단계를 알 수 없는 실패(`failed`)가 누락되어 있었으므로 추가하였다(74줄).
- 다음 현재 동작을 추가하였다.
  - `ai_session_rejected`의 `reason` 값(`queue_full`·`conflict`), `ai_sessions`의 `status` 값
  - `ai_agent_tokens`의 `kind` 값, `ai_agent_call_seconds` 구간, `component`의 기록 이름 규칙
  - 개발용 샌드박스 진단이 `run_type=test`로 기록되는 점

## #609 대시보드 횟수 식 (2026-11-06)

- 대시보드 횟수·합계 패널을 `increase()` 대신 수집 한 번마다 증가한 양을 합산하는 식으로 변경하였다. 본문 4장에 식과 한계를 유지하고, PR 번호와 이후 계획은 이 파일로 이동하였다.

> - 대시보드 횟수·합계 패널은 `increase()` 대신 수집 한 번마다 늘어난 만큼을 더함 (#609) (18줄)

>   - 식이 길어 나중에 Prometheus 기록 규칙(recording rule)으로 줄이는 방안 있음 (36줄)

## #451 답변 대기 세션 교체 지표 (2026-10-31)

- 새 접수로 답변 대기 세션을 폐기한 횟수를 세는 `ai_session_awaiting_replaced`를 추가하였다.

> | `ai_session_awaiting_replaced` | Counter | (없음) | 새 접수로 버린 답변 대기 세션 누적 수 (#451) | (64줄)

## #410 지표 문서 신설 (2026-10-28)

- 지표 설계 논의는 #410에서 진행하였다.

> AI 서버가 `GET /metrics`로 내보내는 Prometheus 지표와 어디서 재는지를 정리한다. 지표 설계 논의는 #410. (3줄)

## 재작성 전 계획·남은 작업

재작성 전 문서의 4장 "추가 예정"이다. 파이프라인 연결(#320)과 진단서 변환(#408)은 완료되었으나, 아래 지표와 `ai_tool_runs`의 `run_type` 라벨은 2026-11-11 기준 구현되지 않았다.

> ## 4. 추가 예정
>
> | 지표 | 시점 | 비고 |
> |---|---|---|
> | `ai_build_info` | 버전 규칙 결정 후 | `version`, `model_profile`. 지금 배포는 서버에서 소스로 빌드해 앱 안에 버전 정보가 없음 |
> | `ai_result_status`, `ai_result_incomplete` | 진단서 변환(#408)·파이프라인 연결(#320) 후 | `reason` 라벨(#408 `DecisionReason`)로 재확인 필요가 미완료·Tool 실패·정보 부족·지원 분야 밖 중 어디서 오는지 구분 |
> | `ai_pipeline_end`, `ai_verification_results`, `ai_pipeline_retry_rounds`, `ai_question_rounds`, `ai_questions_asked`, `ai_diagnosis_cost_krw` | 파이프라인 연결(#320) 후 | |
> | `ai_tool_runs`에 `run_type` 추가 | 파이프라인 연결(#320) 후 | `ToolExecutor`가 실행 컨텍스트를 받게 되면. `ai_session_tool_progress`는 이때 합침 | (198-205줄)
