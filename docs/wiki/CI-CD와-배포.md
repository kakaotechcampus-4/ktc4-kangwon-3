# CI/CD와 배포

## 전체 흐름

```mermaid
flowchart LR
    PR[PR 생성] --> CI[파트별 CI<br/>테스트·빌드]
    CI --> R[리뷰·승인]
    R --> M[develop 병합]
    M --> CD[파트별 배포]
    CD --> S3[(S3 / ECR)]
    S3 --> SSM[SSM으로 EC2 명령]
    SSM --> CHK[배포 후 확인]
```

- 바뀐 경로에 해당하는 파트의 워크플로만 돌아갑니다.
- 배포는 develop에 병합될 때 일어납니다. main 병합은 배포와 관계없습니다.
- AWS 인증은 GitHub OIDC로 역할을 맡는 방식이라, 저장소에 AWS 키를 두지 않습니다.
- EC2 명령은 공용 액션 [`ssm-run`](https://github.com/kakaotechcampus-4/ktc4-kangwon-3/blob/develop/.github/actions/ssm-run/action.yml)으로 보냅니다. EC2가 꺼져 있으면 켜고 기다립니다.

## 워크플로

| 워크플로 | 트리거 | 하는 일 |
|---|---|---|
| [`backend.yml`](https://github.com/kakaotechcampus-4/ktc4-kangwon-3/blob/develop/.github/workflows/backend.yml) | `backend/beforeselling/**` | 배포 스크립트 검사·테스트, `./gradlew build`(단위·통합 테스트, Flyway 마이그레이션 검증, 커버리지 최소 기준 검사) → 이미지를 ECR에 push → Blue-Green 배포 → API 응답 확인 |
| [`ai.yml`](https://github.com/kakaotechcampus-4/ktc4-kangwon-3/blob/develop/.github/workflows/ai.yml) | `ai/**` | `pytest`, Docker 빌드 → 이미지를 ECR에 push → `docker compose up --no-build --wait` → `/health/ready` 확인 |
| [`frontend-ci.yml`](https://github.com/kakaotechcampus-4/ktc4-kangwon-3/blob/develop/.github/workflows/frontend-ci.yml) | `frontend/palgijeonae/**` | `npm ci`, lint, build |
| [`frontend-deploy.yml`](https://github.com/kakaotechcampus-4/ktc4-kangwon-3/blob/develop/.github/workflows/frontend-deploy.yml) | develop의 Frontend CI 성공 | 빌드 → S3 → EC2 릴리스 폴더에 풀고 `current` 링크 교체 |
| [`infra-nginx.yml`](https://github.com/kakaotechcampus-4/ktc4-kangwon-3/blob/develop/.github/workflows/infra-nginx.yml) | `infra/nginx/**` | `nginx -t` 검증 → 설정 반영 → reload → 외부 확인 |
| [`infra-monitoring.yml`](https://github.com/kakaotechcampus-4/ktc4-kangwon-3/blob/develop/.github/workflows/infra-monitoring.yml) | `infra/monitoring/**` | 설정 검증 → Prometheus·Grafana 재기동 → 헬스 확인 |
| [`e2e.yml`](https://github.com/kakaotechcampus-4/ktc4-kangwon-3/blob/develop/.github/workflows/e2e.yml) | FE·BE·mock-ai·`e2e/`가 바뀐 develop 대상 PR, 같은 변경의 develop 병합, 수동 | 스택을 띄워 Playwright E2E 실행. 배포를 막지 않음. 실패 알림(Discord)은 병합 후·수동 실행에서만 보냄 |
| [`assign-part-reviewers.yml`](https://github.com/kakaotechcampus-4/ktc4-kangwon-3/blob/develop/.github/workflows/assign-part-reviewers.yml) | develop 대상 PR | 파트 리뷰어 자동 지정 |
| `assign-mentor.yml`, `notify-discord.yml`, `convention-check.yml` | main 대상 PR | 멘토 지정, Discord 알림, 컨벤션 안내(프로그램 운영진 관리 파일, 수정 금지) |

- 같은 파트의 배포가 겹치지 않도록 워크플로마다 `concurrency`를 겁니다.
- 모든 워크플로는 Actions 탭에서 수동으로도 실행할 수 있습니다.
- BE는 커버리지가 최소 기준에 못 미치면 빌드가 실패해 배포도 막힙니다. 긴급 배포가 필요하면 `Backend CI/CD`를 수동 실행하고 `skip-coverage`를 켭니다. 테스트는 그대로 돌고 커버리지 검사만 건너뜁니다.

## 파트별 배포 방식

| 파트 | 방식 | 실패하면 | 되돌리기 |
|---|---|---|---|
| BE | Blue-Green. 새 색을 띄워 헬스·스모크 확인 후 nginx 전환 | 새 컨테이너를 지우고 기존 색이 계속 서비스 | `blue-green.sh rollback` ([배포 문서](https://github.com/kakaotechcampus-4/ktc4-kangwon-3/blob/develop/backend/beforeselling/deploy/README.md)) |
| FE | 커밋별 릴리스 폴더 + `current` 링크 교체 | 기존 `current` 유지 | `frontend-deploy.yml`을 이전 SHA로 수동 실행 |
| AI | ECR 이미지를 받아 `docker compose up --no-build --wait` | 워크플로 실패로 알림 | 이전 커밋으로 되돌리는 PR을 병합해 재배포 |
| nginx | 설정 반영 후 `nginx -t` 통과 시에만 reload | reload하지 않음. 실행 중인 nginx는 이전 설정 유지 | 설정을 고쳐 다시 배포 |

- BE DB 스키마는 새 컨테이너가 기동할 때 Flyway가 마이그레이션을 적용합니다. 전환 전까지 옛 색이 같은 DB로 서비스하고, 롤백해도 스키마는 되돌아가지 않으므로 마이그레이션은 이전 버전 코드와도 호환되게 작성합니다([Flyway 마이그레이션 가이드](https://github.com/kakaotechcampus-4/ktc4-kangwon-3/blob/develop/backend/docs/guide/FLYWAY_MIGRATION_GUIDE.md)).

## 환경

| 환경 | 설명 |
|---|---|
| 로컬 | 개발자 PC. BE `local` 프로필 |
| 운영 | EC2 한 대. https://palgijeone.com. BE `prod` 프로필 |
| 부하테스트 | 운영 EC2에서 운영 BE를 잠시 내리고, 분리한 DB(`beforeselling_perf`)·Redis DB로 측정([loadtest](https://github.com/kakaotechcampus-4/ktc4-kangwon-3/blob/develop/loadtest/README.md)) |

별도 dev·staging 서버는 두지 않았습니다. 실사용자가 없는 단계라 운영 환경을 통합 검증에 함께 쓰고, 서버 메모리 용량에 여유가 많지 않기 때문입니다.
대신 CI 테스트·커버리지 기준과 Blue-Green 헬스·스모크 확인을 두어 문제 발생 시 배포 서버에 지장이 없도록 제한하였습니다.

## 비밀 값 관리

| 대상 | 보관 위치 |
|---|---|
| BE 운영 `.env` | GitHub Secret `BE_ENV_B64`(Base64). 배포 때 만들고, S3에 올린 사본은 배포 후 지움 |
| 모니터링 `.env` | GitHub Secret `MONITORING_ENV_B64` |
| AI 운영 `.env` | EC2 서버의 파일 |
| 배포 대상 정보 | GitHub 변수 `AWS_ACCOUNT_ID`, `INSTANCE_ID`, `S3_BUCKET`, `VITE_API_URL` |

<!-- TODO: 확인 필요 - AI 운영 .env를 처음 만들거나 바꾸는 절차 -->
