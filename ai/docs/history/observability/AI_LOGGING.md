# AI_LOGGING 변경 이력

[AI_LOGGING.md](../../current/observability/AI_LOGGING.md)의 변경 경위를 최신순으로 기록한다. 아래 인용은 재작성 전 문서(develop c57f1c29)의 문장을 수정 없이 옮긴 것이며, 괄호 안 줄 번호는 해당 문서 기준이다.

## #823 현재 동작 기준 재작성 (2026-11-11)

- develop c57f1c29 기준 코드와 대조하여 본문을 문어체로 재작성하였다. 형식 예시의 날짜는 특정 날짜로 오해되지 않도록 임의 날짜로 교체하였다.
- 코드와 일치하지 않던 내용을 수정하였다.
  - `run_type` 값에 `dummy`가 누락되어 있었다(`app/domain/context.py`).

> | `run_type` | production·evaluation·test | 실행 내내 | (32줄)

  - 실행 정보를 새 스레드로 전달하는 예로 관세 결정사례 검색어 스레드만 기술하였으나, Tool 병렬 실행과 입력 가드 이미지 병렬 판단도 동일한 방식으로 전달한다(`app/pipeline/tool_executor.py`, `app/agents/input_guard/agent.py`).

> - 새 스레드로는 자동으로 안 넘어감 → 스레드를 띄우는 쪽에서 `contextvars.copy_context().run`으로 넘김 (관세 결정사례 검색어 스레드) (37줄)

  - 사용량 기록은 현재 파일 외에 이전 파일 5개(`usage.jsonl.1`-`usage.jsonl.5`)를 보관하므로 모두 6개이다. 현재 파일을 포함하여 5개를 보관하는 `docker logs`와 동일하지 않다(`app/observability/usage.py`).

>   - 10MB를 넘으면 `usage.jsonl.1`부터 한 칸씩 밀고 새 파일로 시작, 5개까지만 보관 (`docker logs` 상한과 같음) (122줄)

- 다음 현재 동작을 추가하였다.
  - 입력 가드 일부 판단 실패, 검증 모델 검토 실패 로그 줄(4.1절)
  - 법령 점검·CLIP 주간 적재·캐시 DB 로그 줄(4.3절)
  - Sentry가 외부 요청에 추적 헤더를 덧붙이지 않는 점(`trace_propagation_targets=[]`, 7.2절)
- 5장의 서버 종료(drain) 설명은 [AI_SESSION_ARCHIVE.md](../../current/storage/AI_SESSION_ARCHIVE.md) 6장으로 이동하고 연결만 남겼다. 이동 전 문장은 [history/AI_SESSION_ARCHIVE.md](../storage/AI_SESSION_ARCHIVE.md)에 인용하였다.

## #497 로그 문서 신설 (2026-11-02)

- 로그 설정·형식·레벨 기준 논의는 #497에서 진행하였다.

> AI 서버가 남기는 앱 로그의 설정·형식·레벨 기준과 서버에서 보는 방법, 로그·오류를 Sentry로 보내는 방식을 정리한다. 로그 논의는 #497, 지표는 [AI_METRICS.md](AI_METRICS.md), 로컬 진단 trace는 [AI_TRACE.md](AI_TRACE.md). (3줄)
