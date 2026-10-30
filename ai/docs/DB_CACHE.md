# DB 캐시 (#362)

Tool이 부르던 외부 API 응답과 관세청 결정사례를 DB에 쌓아 두고, Tool은 DB를 먼저 본다.
Tool 코드는 클라이언트 자리에 조회 객체를 넣기만 하고 데이터 로직은 바꾸지 않는다(DB 값은 클라이언트가 해석한 응답 스키마 그대로).

`DATABASE_URL`이 없거나 DB가 죽어 있으면 캐시 없이 클라이언트만 쓴다. DB 실패 뒤 60초(`CACHE_DB_RETRY_SECONDS`)는 DB를 건너뛴다.

## 표

| 표 | 내용 | 키 |
|---|---|---|
| `api_response_cache` | 클라이언트 응답(jsonb)과 만료 시각 | (client, request_key) — 요청 스키마 JSON의 sha256 |
| `hs_cases` | CLIP 품목분류 결정사례(품명·설명·결정 이유·HS·시행일) + 임베딩 `halfvec(1536)` HNSW | doc_id |

## 무엇을 언제 받는가

| 데이터 (client) | 조회 객체 | 쌓는 시점 | 보관 | 외부 호출 실패 때 |
|---|---|---|---|---|
| 법령 검색 `law.eflaw_search` (현행·시행예정만) | `ScheduledFetcher` | 매일 법령 점검 | 2일 지나면 Tool 조회 때 다시 받음 | 만료된 값 사용 |
| 행정규칙 검색 `admrul.search` | `ScheduledFetcher` | 매일 법령 점검 | 위와 같음 | 만료된 값 사용 |
| 법령 본문 `law.text`, 행정규칙 본문 `admrul.text` | `ScheduledFetcher` | 법령 점검이 현행·시행예정 버전마다 미리 받음 | 영구(버전 번호가 키) | 오류 |
| 세관장확인 GW `customs.gw` | `OnDemandFetcher` | Tool이 HS를 조회할 때 | 1일 | 오류(만료 값으로 판정하지 않음) |
| 결정사례 `hs_cases` | `ClipCaseDatabase` | 매주 결정사례 적재 | 사라진 사례만 삭제 | DB에 가까운 사례가 없거나 DB 장애면 CLIP API로 찾음 |

- 법령 점검 대상은 `tools/common/law_sources.LAW_SOURCES`(Tool 근거 문서 21개)다.
- KC·전파 인증, CLIP 검색 결과는 바뀌는 데이터라 캐시하지 않는다.
- 법령·행정규칙 검색은 빈 결과를 저장하지 않는다. 매일 점검은 검색 결과에 그 문서 ID가 없으면 저장하지 않는다.

## 서버가 하는 일 (`app.main`)

| 시점 | 할 일 |
|---|---|
| 기동 | vector 확장과 표 생성(`init_db`, 있으면 건너뜀) → 법령 점검 1회 → 만료된 `customs.gw` 행 정리 |
| 매일 00:05 KST (`LAW_REFRESH_AT`) | 법령 점검 → 만료된 `customs.gw` 행 정리 |
| 매주 일요일 03:00 KST (`CLIP_INGEST_WEEKLY_AT`) | 결정사례 적재. `hs_cases`가 비어 있으면 건너뜀(첫 적재는 아래 CLI·덤프로). 기동 때는 돌지 않음 |

- 법령 검색의 만료 행은 지우지 않는다. 법제처 장애 때 대신 쓸 값이다.
- 결정사례 적재는 목록 전체(약 544페이지, 10분 안팎)를 받고, 새 사례만 상세·임베딩을 받는다. 목록에서 사라진 사례는 목록을 끝까지 받은 경우에만 지운다.

## 법령 버전

- Tool은 DB의 버전 목록에서 오늘 시행 중인 버전을 고른다(`tools/common/law.select_version`). 시행일이 되면 외부 호출 없이 새 버전으로 바뀐다.
- 시행 중인 버전이 여럿이면 가장 나중에 공포·발령된 버전 안에서 고른다. 법제처의 시행예정 본문은 공포 시점 본문이라, 그 뒤 공포돼 먼저 시행된 개정이 빠져 있기 때문이다(2026-10-27 확인: 21개 중 7개 문서).

## 법령 변경 이벤트 (`app.db.law_changes`)

매일 점검이 덮어쓰기 전 DB 목록과 새 목록을 비교해 `LawChange`를 낸다. 변경마다 그 문서를 근거로 쓰는 Tool(`tool`)이 실려 영향받는 분야를 알 수 있다.

| 종류 | 뜻 |
|---|---|
| `ANNOUNCED` | 목록에 새 버전이 생김(개정 공포·발령) |
| `APPLIED` | 서비스가 근거로 고른 버전이 어제와 달라짐. 실제 개정 시행과 같다는 뜻은 아님(시행일이 와도 본문 누락 등으로 고르지 않으면 `SKIPPED`) |
| `SKIPPED` | 어제와 오늘 사이 시행일인 버전이 적용되지 않음(같은 날 더 나중 공포 버전 등) |

- `refresh_laws(..., on_change=)`에 받는 함수를 넘긴다(`LawChangeSink`). 지금은 `log_law_changes`로 로그만 남긴다. BE로 보내는 방식은 미정이라, 정해지면 이 자리에 함수만 바꿔 끼운다.
- 전달이 실패해도 점검 결과는 남는다.

## CLI (`python -m app.db.cli`)

| 명령 | 하는 일 |
|---|---|
| `init` | vector 확장과 표 생성 |
| `law-refresh` | 법령 점검을 지금 실행(변경 수 출력) |
| `clear-cache <client>` | 한 캐시 이름의 행을 모두 삭제(예: `law.text`) |
| `clip-ingest [--workers 4] [--limit N] [--raw-dir 폴더]` | DB에 없는 결정사례를 받아 임베딩해 저장. 처음 전체 적재는 수 시간 걸린다 |

## 서버 첫 결정사례 적재 (덤프·복원)

전체 적재는 오래 걸리므로 로컬에서 적재한 `hs_cases`를 덤프해 서버에 복원한다. 로컬과 서버 DB 이미지가 같아야 한다(`pgvector/pgvector:pg16`).

```bash
# 로컬
docker exec <로컬 DB 컨테이너> pg_dump -U <유저> -d <DB> -t hs_cases --data-only -Fc > hs_cases.dump

# 서버: 서버를 한 번 띄워 표를 만든 뒤(또는 init)
docker exec -i <서버 DB 컨테이너> pg_restore -U <유저> -d <DB> --data-only -t hs_cases < hs_cases.dump
```

- 서버의 `OPENAI_EMBEDDING_MODEL`이 적재 때 모델과 같아야 한다. 검색은 같은 모델로 만든 행만 본다.
- 실측(2026-10-27): 5만 4,303건, 덤프 41초·복원 1분 39초.

## 검증

```bash
python -m pytest tests/db -q
```
