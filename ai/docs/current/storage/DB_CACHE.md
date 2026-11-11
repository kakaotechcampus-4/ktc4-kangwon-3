# DB 캐시

Tool이 호출하는 외부 API 응답과 관세청 결정사례를 DB에 저장해 두고, Tool은 DB를 먼저 조회한다.
Tool 코드는 클라이언트 자리에 조회 객체를 전달받을 뿐 데이터 로직은 동일하다(DB 값은 클라이언트가 해석한 응답 스키마 그대로 저장한다).

## 1. 개요

- `DATABASE_URL`이 없거나 DB에 연결할 수 없으면 캐시 없이 클라이언트만 사용한다.
- DB 실패 뒤 60초(`CACHE_DB_RETRY_SECONDS`) 동안은 DB를 건너뛴다. 응답 캐시와 결정사례 DB는 프로세스 공용 건너뛰기 상태(`SHARED_DB_SKIP`)를 공유하며, 진단 세션 보관은 별도 상태를 사용한다.
- 연결 풀은 5개(초과 5개)이고, 연결 제한 시간은 3초이다. HNSW 탐색 폭은 `hnsw.ef_search=100`으로 지정한다(`app/db/engine.py`).
- Tool의 캐시 조회 결과(hit·miss·stale·skipped)는 `ai_cache_lookups` 지표로 기록된다. 정의는 [AI_METRICS.md](../observability/AI_METRICS.md) 3.7절을 참고한다.

## 2. 표

| 표 | 내용 | 키 |
|---|---|---|
| `api_response_cache` | 클라이언트 응답(jsonb)과 만료 시각 | (client, request_key) — 요청 스키마 JSON의 sha256 |
| `hs_cases` | CLIP 품목분류 결정사례(품명·설명·결정 이유·HS 코드 배열·시행일), 임베딩 `halfvec(1536)` HNSW, 임베딩 모델 이름 | doc_id |
| `diagnosis_sessions` | 진단 세션 보관 ([AI_SESSION_ARCHIVE.md](AI_SESSION_ARCHIVE.md)) | product_id |

- 모든 표에는 행을 저장한 시각 `fetched_at`이 있다.
- `hs_cases.embedding_model`은 검색 전 모델 일치 확인에 사용한다. 모델이 다르면 벡터 공간이 다르기 때문이다.

## 3. 캐시 대상과 시점

| 데이터 (client) | 조회 객체 | 저장 시점 | 보관 | 외부 호출 실패 시 |
|---|---|---|---|---|
| 법령 검색 `law.eflaw_search` (현행·시행예정만) | `ScheduledFetcher` | 매일 법령 점검 | 2일이 지나면 Tool 조회 시 다시 받음 | 만료된 값 사용 |
| 행정규칙 검색 `admrul.search` | `ScheduledFetcher` | 매일 법령 점검 | 위와 동일 | 만료된 값 사용 |
| 법령 본문 `law.text`, 행정규칙 본문 `admrul.text` | `ScheduledFetcher` | 법령 점검이 현행·시행예정 버전마다 미리 받음 | 영구(버전 번호가 키) | 오류 |
| 세관장확인 GW `customs.gw` | `OnDemandFetcher` | Tool이 HS를 조회할 때 | 1일 | 오류(만료 값으로 판정하지 않음) |
| 결정사례 `hs_cases` | `ClipCaseDatabase` | 매주 결정사례 적재 | 사라진 사례만 삭제 | DB에 가까운 사례가 없거나 DB 장애이면 CLIP API로 조회 |

- 법령 점검 대상은 `tools/common/law_sources.LAW_SOURCES`(Tool 근거 문서 26개)이다. 표시·광고 Tool도 다른 Tool과 동일하게 적용 판 본문에서 근거 조문을 읽는다. 고시·지침은 본문이 한 덩어리이므로 항목의 시작 문구로 줄을 찾으며, 개정으로 시작 문구가 사라지면 Tool이 실패한다. 이 경우 `tools/advertising/evidence.py`의 시작 문구를 사람이 수정한다.
- KC·전파 인증, CLIP 검색 결과는 변경되는 데이터이므로 캐시하지 않는다.
- 법령·행정규칙 검색은 빈 결과를 저장하지 않는다. 매일 점검은 검색 결과에 해당 문서 ID가 없으면 저장하지 않는다.
- 외부 응답이 저장 조건에 해당하지 않으면 만료된 캐시 값이 있는 경우 그 값을 사용한다.
- 응답 스키마가 바뀌어 읽을 수 없는 캐시 값은 없는 값으로 간주하고 다시 받아 덮어쓴다.

## 4. 서버 예약 작업 (`app.startup`)

| 시점 | 작업 |
|---|---|
| 기동 | vector 확장과 표 생성(`init_db`, 이미 있으면 건너뜀). 법령 점검은 실행하지 않음(즉시 받으려면 7장 CLI `law-refresh`) |
| 매일 00:05 KST (`LAW_REFRESH_AT`) | 법령 점검 → 만료된 `customs.gw` 행 정리 |
| 매주 일요일 03:00 KST (`CLIP_INGEST_WEEKLY_AT`) | 결정사례 적재. `hs_cases`가 비어 있으면 건너뜀(첫 적재는 7장 CLI 또는 8장 덤프). 기동 시에는 실행하지 않음 |

- 법령 검색의 만료 행은 삭제하지 않는다. 법제처 장애 시 대신 사용할 값이기 때문이다.
- 결정사례 적재는 목록 전체를 받고, 새 사례만 상세·임베딩을 받는다. 목록에서 사라진 사례는 목록을 끝까지 받은 경우에만 삭제한다.

## 5. 법령 버전

- Tool은 DB의 버전 목록에서 오늘 시행 중인 버전을 선택한다(`tools/common/law.select_version`). 시행일이 되면 외부 호출 없이 새 버전으로 바뀐다.
- 시행 중인 버전이 여럿이면 가장 나중에 공포·발령된 버전 안에서 선택한다. 법제처의 시행예정 본문은 공포 시점의 본문이므로, 그 뒤 공포되어 먼저 시행된 개정이 반영되어 있지 않기 때문이다.

## 6. 법령 변경 이벤트 (`app.db.law_changes`)

매일 점검은 덮어쓰기 전 DB 목록과 새 목록을 비교하여 `LawChange`를 생성한다. 변경마다 그 문서를 근거로 사용하는 Tool(`tool`)이 포함되므로 영향을 받는 분야를 알 수 있다.

| 종류 | 의미 |
|---|---|
| `ANNOUNCED` | 목록에 새 버전이 생김(개정 공포·발령) |
| `APPLIED` | 서비스가 근거로 선택한 버전이 전날과 달라짐. 실제 개정 시행과 동일하다는 의미는 아님(시행일이 되어도 본문 누락 등으로 선택하지 않으면 `SKIPPED`) |
| `SKIPPED` | 전날과 당일 사이가 시행일인 버전이 적용되지 않음(같은 날 더 나중에 공포된 버전 등) |

- `refresh_laws(..., on_change=)`에 수신 함수를 전달한다(`LawChangeSink`). 서버는 전체 변경을 `log_law_changes`로 로그에 기록하고, `APPLIED`만 `LawChangeNotifier`로 묶어 BE(`POST /internal/v1/ai/law-changes`)에 전송한다.
  - `ANNOUNCED`는 시행 전이므로, `SKIPPED`는 사람이 확인할 사항이므로 전송하지 않는다.
- 전달에 실패하여도 점검 결과는 유지된다. 목록을 이미 덮어썼으므로 **전송하지 못한 변경은 다음 점검에서 다시 검출되지 않는다.**
  - 그러므로 5xx·전송 실패·`COMMON-003`·`COMMON-009`는 30초부터 2배씩(상한 5분) 5회 재시도한다. 대기 합계는 약 12.5분이다. BE가 동일한 변경을 무시하므로 묶음 전체를 다시 전송하여도 된다.
  - 그 밖의 거절은 즉시 포기한다. 포기하면 오류 로그에 법령명·문서 ID·판 번호를 기록하며, 재전송은 그 로그를 확인하여 사람이 수행한다.
  - 재시도 대기 중 서버가 종료되면 대기를 중단하고 포기한다.
- 시행일의 정기 점검을 놓치면 그날의 `APPLIED`·`SKIPPED`는 다음 날 점검에서도 검출되지 않는다. 지표상 의미는 [AI_METRICS.md](../observability/AI_METRICS.md) 3.7절을 참고한다.

## 7. CLI (`python -m app.db.cli`)

| 명령 | 작업 |
|---|---|
| `init` | vector 확장과 표 생성 |
| `law-refresh` | 법령 점검을 즉시 실행(변경 수 출력). 변경을 로그로만 기록하고 BE로 전송하지 않음. 서버 DB에 실행하면 목록이 갱신되므로 그 변경은 알림 없이 지나감 |
| `clear-cache <client>` | 한 캐시 이름의 행을 모두 삭제(예: `law.text`) |
| `clip-ingest [--workers 4] [--limit N] [--raw-dir 폴더]` | DB에 없는 결정사례를 받아 임베딩하여 저장. 처음 전체 적재는 수 시간이 소요됨 |
| `clip-refill-hs [--workers 4]` | HS 코드가 빈 결정사례의 상세를 다시 받아 HS 코드만 채움 |

종료 코드는 0 성공, 1 일부 실패, 2 설정 오류, 3 DB 연결 실패이다.

## 8. 서버 첫 결정사례 적재 (덤프·복원)

전체 적재는 시간이 오래 소요되므로 로컬에서 적재한 `hs_cases`를 덤프하여 서버에 복원한다. 로컬과 서버의 DB 이미지가 동일해야 한다(`pgvector/pgvector:pg16`).

```bash
# 로컬
docker exec <로컬 DB 컨테이너> pg_dump -U <유저> -d <DB> -t hs_cases --data-only -Fc > hs_cases.dump

# 서버: 서버를 한 번 띄워 표를 만든 뒤(또는 init)
docker exec -i <서버 DB 컨테이너> pg_restore -U <유저> -d <DB> --data-only -t hs_cases < hs_cases.dump
```

- 서버의 `OPENAI_EMBEDDING_MODEL`이 적재 시 모델과 동일해야 한다. 검색은 동일한 모델로 생성한 행만 조회한다.

## 9. 검증

```bash
python -m pytest tests/db -q
```

---

변경 이력: [history/DB_CACHE.md](../../history/storage/DB_CACHE.md)
