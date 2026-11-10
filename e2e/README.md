# 팔기전에 E2E

화면에서 시작해 FE → BE → mock-AI → 다시 화면까지 이어지는 흐름을 브라우저로 검증합니다. Playwright를 쓰고 실제 AI 대신 결과를 고정할 수 있는 [mock-ai](../loadtest/mock-ai/app.py)를 씁니다.

## 시나리오

| 파일 | 검증하는 흐름 |
|---|---|
| `environment.spec.ts` | 메인 화면이 열린다 / 인증이 필요한 API에 401을 응답한다 |
| `auth.spec.ts` | 로그인 상태로 마이페이지에 들어갈 수 있다 |
| `token.spec.ts` | 요청 중 액세스 토큰이 만료되면 재발급받아 원래 요청을 이어간다 |
| `diagnosis.spec.ts` | 텍스트로, URL로 진단을 요청하면 진행 화면을 거쳐 결과에서 판정을 확인한다 |
| `multi-product.spec.ts` | 여러 상품을 한 번에 진단하면 상품별로 진행되고 상품마다 결과를 확인한다 |
| `question.spec.ts` | AI가 질문하면 답변을 제출하고 이어진 진단의 결과를 확인한다 |
| `retry.spec.ts` | 실패한 진단을 다시 시도해 결과를 확인한다 / 다시 해도 같은 실패는 재시도를 권하지 않는다 |
| `mypage.spec.ts` | 진단한 상품이 마이페이지 목록에 나오고 누르면 그 결과로 이동한다 |

모두 12개이고 스택 실행과 정리를 포함해 약 1분 30초가 걸립니다.

## 실행

Docker가 필요합니다.

```bash
cd frontend/palgijeonae && npm ci
cd ../../e2e && npm ci && npx playwright install chromium
npx playwright test          # 전체
npx playwright test --ui     # 화면을 보면서
```

테스트 전에 `global-setup.ts`가 스택을 띄우고 사용자를 넣으며, 끝나면 `global-teardown.ts`가 정리합니다.

## 구성

| 경로 | 역할 |
|---|---|
| `compose.e2e.yml` | BE, PostgreSQL, Redis, mock-ai. BE는 로컬에서는 이미지 안에서 소스로 빌드하고, CI에서는 러너가 Gradle 캐시로 미리 만든 jar를 씀(`E2E_APP_TARGET=deploy`, [#723](https://github.com/kakaotechcampus-4/ktc4-kangwon-3/pull/723)). 호스트 포트 2xxxx, 값은 모두 E2E 전용 더미 |
| `playwright.config.ts` | FE를 빌드해 `vite preview`로 띄움 |
| `seed/users.sql` | 테스트 사용자 1명 |
| `fixtures/auth.ts` | 로그인 우회. 리프레시 토큰을 Redis에 넣고 쿠키로 주입하면 FE가 실제 재발급 API로 액세스 토큰을 받음 |
| `helpers/upload.ts` | 업로드 화면 조작 |

- 소셜 로그인 화면은 자동화하지 않습니다. 실제 계정, 봇 탐지, 제공자 화면 변경 문제가 있어서 로그인된 상태를 직접 만듭니다.
- mock-ai는 상품에 결과 고정 표시가 있으면 그 결과를, 없으면 부하 테스트 때처럼 확률로 결과를 돌려줍니다.

## CI

[`e2e.yml`](../.github/workflows/e2e.yml)이 FE·BE·mock-ai·E2E가 바뀐 develop 대상 PR과 develop 병합에서 돌고 수동으로도 실행할 수 있습니다. 아직 필수 체크가 아니라 실패해도 병합할 수 있고 배포도 막지 않습니다. 실패하면 Playwright 리포트와 스택 로그를 남기고 병합 후·수동 실행에서는 Discord로 알립니다.

도입 PR: [#577](https://github.com/kakaotechcampus-4/ktc4-kangwon-3/pull/577)
