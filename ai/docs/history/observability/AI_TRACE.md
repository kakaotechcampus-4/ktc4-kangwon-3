# AI_TRACE 변경 이력

[AI_TRACE.md](../../current/observability/AI_TRACE.md)의 변경 경위를 최신순으로 기록한다.

## #823 현재 동작 기준 재작성 (2026-11-11)

- develop c57f1c29 기준 코드와 대조하여 본문을 문어체로 재작성하였다. 기존 본문에는 PR 번호·날짜나 경위 설명이 없었으므로 이력으로 옮긴 내용은 없다.
- 단계 hook 순서 설명에 재실행 회차 로그 표시 hook(`mark_retry_round`)이 누락되어 있었으므로 맨 앞에 추가하였다(`app/diagnosis/job.py`의 `_stage_hooks`). 기존 문장은 다음과 같다(185줄).

> - 파이프라인 단계 기록은 단계 hook(`app/diagnosis/tracing.py`·`replay.py`)으로 붙임. 묶는 순서는 `app/diagnosis/job.py`의 `_stage_hooks` 한 곳 (진행 알림 → 다시 실행 멈춤 → trace → 다시 실행 건너뛰기 → LangSmith). 순서를 바꾸면 `replayed` 표시·멈춤 결말 위치가 달라짐

- 다음 현재 동작을 추가하였다.
  - 기록 중 Tool 순차 실행과 그로 인한 실행 시간 차이(2장)
  - CLI 옵션 조합 규칙과 종료 코드(2.4절)
  - 검증 모델 검토 실패 시 `model_review_error` 기록, 선택되지 않은 Tool의 `skipped` 상태(3.1절)
- 5장의 구현 내부 설명(이미지 자르기 기록, hook 순서)을 5.1절 개발자 참고로 분리하였다.
