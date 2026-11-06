# BE 테스트 정책

BE 테스트를 **어떤 종류로, 어디에, 어떻게** 쓰는지 정합니다.
테스트 이름과 given-when-then 형식은 [코드 컨벤션 1-2. Test 규칙](CODE_CONVENTION.md#1-2-test-규칙)을 따릅니다.

## 목차

1. [원칙](#1-원칙)
2. [테스트 종류](#2-테스트-종류)
3. [어떤 테스트로 검증할지 고르는 기준](#3-어떤-테스트로-검증할지-고르는-기준)
4. [작성 규칙](#4-작성-규칙)
5. [E2E 테스트](#5-e2e-테스트)
6. [커버리지](#6-커버리지)
7. [실행 방법](#7-실행-방법)
8. [CI](#8-ci)

## 1. 원칙

- **경우의 수는 단위 테스트로 검증합니다.** 상태 변경, 재요청 판단, 권한·존재 여부 확인처럼 분기가 많은 로직은 스프링 컨텍스트 없이 빠르게 확인합니다.
- **여러 구성 요소가 맞물려야 의미 있는 흐름만 통합 테스트로 올립니다.** 보안 필터 체인, Redis, DB, 트랜잭션처럼 실제로 함께 돌려 봐야 아는 것만 다룹니다.
- **같은 검증을 무거운 테스트로 반복하지 않습니다.** 단위 테스트가 이미 확인한 분기를 통합 테스트에서 다시 돌리지 않습니다.
- **사용자 흐름 전체는 E2E 테스트로 확인합니다.** 화면 → BE → AI로 이어지는 흐름이 끝까지 동작하는지만 보고, 세부 분기는 단위·통합 테스트에 맡깁니다.

## 2. 테스트 종류

| 종류 | 검증하는 것 | 도구 | 위치 | 실행 시점 |
|---|---|---|---|---|
| 단위 | 메서드 하나의 판단과 분기 | JUnit 5, Mockito, AssertJ | `src/test/java` (태그 없음) | `./gradlew test`, PR·develop CI |
| 통합 | 스프링 빈, 보안 필터, DB, Redis가 함께 동작하는 흐름 | `@SpringBootTest`, `@WebMvcTest`, `@DataJpaTest`, `@DataRedisTest`, `@JsonTest`, Testcontainers | `src/test/java` (`@Tag("integration")`) | `./gradlew integrationTest`, PR·develop CI |
| E2E | 화면에서 시작하는 사용자 흐름 전체 | Playwright, mock-ai | 저장소 루트 `e2e/` | develop 머지, 수동 실행 |

- 단위와 통합은 같은 폴더에 두고 `@Tag("integration")`으로만 구분합니다. 태그를 빠뜨리면 통합 테스트가 단위 테스트로 실행되고 단위 커버리지에도 섞이므로 반드시 붙입니다.
- 통합 테스트에서 DB는 H2(PostgreSQL 호환 모드)를, Redis는 Testcontainers로 띄운 실제 Redis 7을 씁니다. Redis 테스트는 Docker가 꺼져 있으면 실패하지 않고 건너뛰므로, 로컬에서 돌릴 때는 Docker를 켭니다.

## 3. 어떤 테스트로 검증할지 고르는 기준

**스프링 컨텍스트 없이 확인할 수 있으면 단위 테스트로 씁니다.** 아래 중 하나라도 해당할 때만 통합 테스트로 올립니다.

- 보안 필터와 경로별 접근 제어가 실제로 적용되는지 확인할 때
- DB 쿼리, 락, 트랜잭션 경계가 실제로 동작하는지 확인할 때
- Redis에 저장하고 꺼내는 동작을 확인할 때
- JSON 직렬화 결과(필드명, enum 값)가 다른 파트와 맞춘 계약대로인지 확인할 때
- 여러 빈이 이어지는 흐름(요청 → 저장 → 커밋 후 이벤트 → 후속 처리)을 확인할 때

E2E 테스트는 **사용자가 화면에서 겪는 핵심 흐름**이 새로 생기거나 바뀔 때 추가합니다. 화면의 세부 분기나 오류 문구는 E2E로 늘리지 않습니다.

| 확인하고 싶은 것 | 종류 | 예시 |
|---|---|---|
| 엔티티 상태 변경, 잘못된 상태 전이 거부 | 단위 | `ProductTest`, `DiagnosesTest` |
| 서비스의 판단과 예외 | 단위 | `ProductServiceTest`, `UserServiceTest` |
| 스케줄러의 재요청·실패 처리 판단 | 단위 | `PendingDiagnosesRetrySchedulerTest` |
| 외부 API 호출과 응답 처리 | 단위 | `AiDiagnosesClientTest` |
| JWT 발급·검증 | 단위 | `JwtProviderTest` |
| 경로별 접근 제어 (내부 토큰, actuator 노출 범위) | 통합 | `InternalApiAccessTest`, `ActuatorAccessTest` |
| 컨트롤러 요청 검증과 응답 형식 | 통합 | `ProductControllerTest`, `AiCallbackControllerTest` |
| 조회 순서, 연관 데이터 삭제 | 통합 | `DiagnosesRepositoryTest` |
| 동시 요청 시 락 동작 | 통합 | `ProductServiceConcurrencyTest` |
| 리프레시 토큰 저장·조회 | 통합 | `RefreshTokenRepositoryTest` |
| AI 콜백 JSON 형식 | 통합 | `ProductEventJsonTest` |
| 질문 답변·실패 재시도 흐름 | 통합 | `ProductAnswerFlowTest`, `ProductRetryFlowTest` |
| 업로드 → 진단 → 결과 화면 | E2E | `e2e/tests/diagnosis.spec.ts` |

## 4. 작성 규칙

### 공통

- `@DisplayName` 작성법과 given-when-then 구조는 [코드 컨벤션 1-2](CODE_CONVENTION.md#1-2-test-규칙)를 따릅니다.
- 메서드 이름은 영어로 짓고, `@DisplayName`에 결과까지 담은 한국어 문장을 씁니다.
- 본문은 `// given`, `// when`, `// then` 주석으로 나눕니다. `assertThatThrownBy`처럼 실행과 검증을 나눌 수 없으면 `// when & then`으로 합칩니다.
- 자동으로 실행되는 테스트에서는 외부 서비스(AI 서버, S3, SES, 소셜 로그인)를 실제로 호출하지 않습니다. 외부 상태에 따라 테스트 결과가 달라지지 않게 하기 위해서입니다.

### 단위 테스트

- 스프링 컨텍스트를 띄우지 않습니다. 협력 객체가 필요하면 Mockito `@Mock`으로 대신합니다.
- HTTP로 외부를 호출하는 클래스는 `MockRestServiceServer`로 가짜 응답을 만들어 검증합니다 (`AiDiagnosesClientTest`).

### 통합 테스트

- 클래스에 `@Tag("integration")`과 `@ActiveProfiles("test")`를 붙입니다. `test` 프로필은 H2와 테스트용 설정값을 씁니다.
- 검증 대상이 아닌 빈은 `@MockitoBean`으로 대신합니다.
  - 외부 연동: `AiDiagnosesClient`, `S3PresignedUrlProvider`, OAuth2 관련 빈
  - 컨트롤러 테스트(`@WebMvcTest`)의 유스케이스: `ProductUseCase` 등
- 실제 Redis가 필요하면 `support/RedisContainerSupport`를 상속합니다. 직렬화나 TTL처럼 mock으로는 확인할 수 없는 동작만 여기서 검증합니다.
- `@Async` 이벤트처럼 비동기로 끝나는 동작은 `Thread.sleep` 대신 Awaitility(`await()`)로 기다립니다.

### 수동 테스트

실제 외부 서비스와의 연동을 확인하는 테스트입니다. 클래스 이름을 `*ManualTest`로 짓고, 환경변수가 있을 때만 실행되게 해서 CI와 평소 실행에서는 건너뜁니다.

| 테스트 | 확인하는 것 | 실행 조건 |
|---|---|---|
| `SesMailManualTest` | 실제 SES 메일 발송 | `MAIL_TEST_TO`에 받을 주소 |
| `RateLimitRedisManualTest` | 로컬 Redis와 Bucket4j 연동 | `RATE_LIMIT_REDIS_TEST=1`, 로컬 Redis 실행 |

수동 테스트에도 `@Tag("integration")`이 붙어 있어 `test`가 아니라 `integrationTest`로 실행합니다.

```bash
MAIL_TEST_TO=받을주소 ./gradlew integrationTest --tests '*SesMailManualTest'
RATE_LIMIT_REDIS_TEST=1 ./gradlew integrationTest --tests '*RateLimitRedisManualTest'
```

## 5. E2E 테스트

사용자가 화면에서 겪는 흐름이 FE → BE → AI까지 끝까지 동작하는지 브라우저로 확인합니다. 코드는 저장소 루트 `e2e/`에 있습니다.

### 구성

| 구성 | 내용 |
|---|---|
| 화면 | Playwright가 운영과 같은 빌드 명령으로 FE를 빌드해 `vite preview`(4173 포트)로 띄웁니다 |
| 서버 | `e2e/compose.e2e.yml`이 BE(소스에서 빌드), PostgreSQL, Redis, mock-ai를 띄웁니다 |
| AI | 실제 AI 대신 `loadtest/mock-ai`가 정해진 결과를 돌려줍니다 |
| 로그인 | 소셜 로그인을 거치지 않고, 리프레시 토큰을 Redis와 쿠키에 넣어 로그인 상태를 만듭니다 (`e2e/fixtures/auth.ts`) |
| 시나리오 | `e2e/tests/` 아래 기능별 파일 (실행 환경, 로그인, 진단, 질문 답변, 실패 재시도, 여러 상품, 마이페이지, 토큰 재발급) |

- 상품 입력에 `[e2e:question]`(텍스트) 또는 `?e2e=question`(URL) 같은 표시를 넣어 mock-ai 결과를 고정합니다. 표시가 없으면 mock-ai가 무작위로 질문·실패를 보내므로 E2E 상품에는 항상 표시를 넣습니다. 표시 종류는 `loadtest/mock-ai/app.py`를 참고합니다.
- E2E는 버튼·링크 같은 역할과 화면 문구로 요소를 찾습니다. 문구나 흐름을 바꿨다면 머지 전에 로컬에서 E2E를 실행합니다.

### 실행

Docker가 켜져 있어야 합니다. 서버 스택은 테스트 시작 때 자동으로 띄우고 끝나면 내립니다.

```bash
cd frontend/palgijeonae && npm ci
cd ../../e2e && npm ci && npx playwright install chromium
npx playwright test
```

- 화면을 보면서 단계별로 확인하려면 `npx playwright test --ui`로 실행합니다.

## 6. 커버리지

JaCoCo로 단위, 통합, 합산(단위 + 통합) 커버리지를 따로 측정합니다. 합산 수치 하나만 보면 통합 테스트가 이미 검증한 줄에 단위 테스트의 공백이 가려지기 때문입니다.

### 리포트

| 리포트 | 측정 범위 | 생성 명령 | 위치 (`backend/beforeselling/` 기준) |
|---|---|---|---|
| 단위 | 도메인·애플리케이션 계층 | `./gradlew test` | `build/reports/jacoco/test/html/index.html` |
| 통합 | 전체 | `./gradlew integrationTest` | `build/reports/jacoco/jacocoIntegrationTestReport/html/index.html` |
| 합산 | 전체 | `./gradlew check` | `build/reports/jacoco/jacocoMergedReport/html/index.html` |

- 단위 리포트는 판단 로직이 모인 `domain`(`entity`, `service`, `event`)과 `application`(`usecase`, `mapper`, `scheduler`, `event`) 패키지만 측정합니다.
- `dto`, `repository`, `presentation`, `global`은 통합·합산 리포트에서 확인합니다.

### 최소 기준

| 대상 | 라인 | 브랜치 | 검사 명령 |
|---|---|---|---|
| 단위 | 90% | 90% | `./gradlew jacocoTestCoverageVerification` |
| 합산 | 85% | 80% | `./gradlew jacocoMergedCoverageVerification` |

- 통합에는 기준을 두지 않습니다. 기준을 맞추려고 단위 테스트가 이미 확인한 분기를 통합 테스트로 다시 쓰게 되기 때문입니다.
- 기준 검사는 `check`에 연결돼 있어, 기준에 못 미치면 빌드와 CI가 실패합니다. 긴급 배포처럼 검사를 잠시 빼야 할 때는 `./gradlew build -x jacocoTestCoverageVerification -x jacocoMergedCoverageVerification`로 실행합니다.

## 7. 실행 방법

명령은 모두 `backend/beforeselling`에서 실행합니다.

| 용도 | 명령 |
|---|---|
| 단위 테스트 실행 | `./gradlew test` |
| 통합 테스트 실행 | `./gradlew integrationTest` |
| 전체 테스트 실행 + 합산 리포트 생성 + 커버리지 기준 검사 | `./gradlew check` |
| 특정 단위 테스트만 실행 | `./gradlew test --tests '*ProductTest'` |
| 특정 통합 테스트만 실행 | `./gradlew integrationTest --tests '*ProductControllerTest'` |
| 이전 결과를 쓰지 않고 다시 실행 | `./gradlew test --rerun`, `./gradlew integrationTest --rerun` |

E2E 테스트 실행은 [5절](#5-e2e-테스트)을 참고합니다.

## 8. CI

| 워크플로 | 실행 시점 | 실행하는 테스트 |
|---|---|---|
| `backend.yml` | `backend/beforeselling/`이 바뀐 PR(develop·main 대상), develop push, 수동 실행 | 배포 스크립트 테스트, `./gradlew build`(단위·통합 테스트, 커버리지 기준 검사) |
| `e2e.yml` | FE·BE·mock-ai·`e2e/` 변경이 develop에 반영될 때, 수동 실행 | E2E 테스트 전체 |

- develop에 반영된 코드의 테스트가 실패하거나 커버리지가 기준에 못 미치면 배포하지 않습니다.
- 실패한 실행의 리포트는 Actions 실행 화면 아래 Artifacts에서 받습니다.
  - `backend.yml`: `test-report` (단위·통합 테스트 리포트와 커버리지 리포트, 7일 보관)
  - `e2e.yml`: `e2e-report` (Playwright 리포트와 스택 로그, 7일 보관)
- E2E가 실패하면 Discord로 알림이 갑니다.
- E2E는 전체 스택을 띄워 오래 걸리므로 PR마다 돌리지 않습니다. 그래서 화면이나 API를 바꾼 PR은 머지 전에 로컬에서 실행합니다([5절](#5-e2e-테스트)).
