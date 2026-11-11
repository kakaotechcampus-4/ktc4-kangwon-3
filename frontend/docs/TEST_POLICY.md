# FE 테스트 정책

FE 테스트를 **어떤 종류로, 어디에, 어떻게** 쓰고 실행하는지 정합니다.
코드 작성 규칙은 [FE 코드 컨벤션](CODE_CONVENTION.md)을 따릅니다.

## 목차

1. [원칙](#1-원칙)
2. [테스트 종류](#2-테스트-종류)
3. [어떤 테스트로 검증할지 고르는 기준](#3-어떤-테스트로-검증할지-고르는-기준)
4. [폴더 구조](#4-폴더-구조)
5. [테스트 환경](#5-테스트-환경)
6. [API 모킹 (MSW)](#6-api-모킹-msw)
7. [화면 렌더: 라우터·QueryClient·인증](#7-화면-렌더-라우터queryclient인증)
8. [브라우저 API 스텁](#8-브라우저-api-스텁)
9. [작성 규칙](#9-작성-규칙)
10. [실행 방법](#10-실행-방법)
11. [CI](#11-ci)
12. [문제 해결](#12-문제-해결)

## 1. 원칙

- **경우의 수는 단위 테스트로 검증합니다.** 입력 검증, 글자 수 계산, 상태 판단처럼 분기가 많은 로직은 화면 없이 빠르게 확인합니다.
- **화면 동작은 통합 테스트로 검증합니다.** 화면 하나를 실제 라우터·QueryClient와 함께 렌더한 뒤 사용자가 하는 대로 입력하고 누르고 기다려서 결과(화면 변화, 안내 문구, 이동, 보낸 요청)를 확인합니다.
- **외부 API는 항상 모킹합니다.** 테스트는 BE·S3·AI에 실제로 요청하지 않습니다. 외부 상태에 따라 테스트 결과가 달라지지 않게 하기 위해서입니다.
- **같은 검증을 반복하지 않습니다.** 단위 테스트가 이미 확인한 분기를 통합 테스트에서 다시 돌리지 않습니다.
- **버그를 고치면 같은 버그를 잡는 테스트를 함께 추가합니다.** 회귀 테스트로 고정해 다시 생기지 않게 합니다.

## 2. 테스트 종류

| 종류 | 검증하는 것 | 도구 | 위치 | 실행 |
|---|---|---|---|---|
| 단위 | 함수·훅·공용 컴포넌트 하나의 판단과 동작 | Vitest, React Testing Library | `src/test/unit/` | `npm test`, PR·develop CI |
| 통합 | 화면 하나의 동작(조작 → 요청 → 화면 변화·이동) | Vitest, React Testing Library, user-event, MSW, jsdom | `src/test/integration/` | `npm test`, PR·develop CI |

- 단위와 통합은 같은 명령(`npm test`)으로 함께 실행됩니다.
- E2E 테스트는 저장소 루트 `e2e/`에서 진행합니다.
- 시각적인 모양(색, 간격, 반응형 배치)은 자동 테스트로 검증하지 않습니다. 눈으로 확인하거나, 동작에 영향을 주는 경우(예: `disabled`, `aria-*`)만 테스트합니다.
- `src/test/infra/`는 테스트 기반(MSW, 렌더 유틸, 스텁) 자체가 동작하는지 확인하는 테스트입니다. 기능 테스트가 아니라서 기능을 추가할 때는 건드리지 않습니다.

## 3. 어떤 테스트로 검증할지 고르는 기준

**화면 없이 확인할 수 있으면 단위 테스트로 씁니다.** 아래 중 하나라도 해당할 때만 통합 테스트로 올립니다.

- 사용자 조작에 따라 화면이 바뀌거나 이동하는지 확인할 때
- 여러 컴포넌트·훅·API 호출이 맞물려야 의미 있는 흐름일 때 (입력 → 검증 → 요청 → 성공·실패 처리)
- 보낸 요청의 경로·본문이 맞는지, 요청을 보내지 않아야 하는 경우인지 확인할 때
- 라우팅(리다이렉트, 경로 파라미터)이나 인증 상태에 따라 보이는 화면이 달라질 때

| 확인하고 싶은 것 | 종류 | 예시 |
|---|---|---|
| 상품명·내용·이미지 검증 | 단위 | `unit/pages/Upload/utils/validation.test.ts` |
| 이모지·조합 문자 글자 수 계산과 자르기 | 단위 | `unit/lib/text.test.ts` |
| 이미지 업로드와 진단 payload 조립, 업로드 실패 메시지 | 단위 | `unit/pages/Upload/utils/diagnosisPipeline.test.ts` |
| 답변 여부, 최신 회차 질문 계산 | 단위 | `unit/pages/Question/utils/answerState.test.ts`, `unit/lib/questions.test.ts` |
| URL·라우트 파라미터 판별 | 단위 | `unit/lib/url.test.ts`, `unit/lib/routeParams.test.ts` |
| 오류 코드별 Sentry 레벨, 경로 템플릿 | 단위 | `unit/api/core/sentryErrorPolicy.test.ts` |
| 유효하지 않은 ID(400·404)·세션 거부 판별 | 단위 | `unit/api/core/invalidId.test.ts`, `unit/api/core/sessionRejected.test.ts` |
| 로그인 상태 저장 | 단위 | `unit/store/useAuthStore.test.ts` |
| 상품 추가·삭제, 입력 검증, 진단 요청 성공·실패 | 통합 | `integration/pages/Upload.test.tsx` |
| 미응답 안내, 답변 제출, 제출 후 이동 | 통합 | `integration/pages/Question.test.tsx` |
| 폴링, 상태별 카드, 진단서 이동 | 통합 | `integration/pages/Judgement.test.tsx` |
| 검색·필터·정렬·선택·페이지 이동, 상품 삭제, 법령 개정 알림·재진단, 주소(URL)로 조건 유지 | 통합 | `integration/pages/Products.test.tsx` |
| 회원 정보 조회·이름 수정, 회원 탈퇴, 알림 설정 | 통합 | `integration/pages/Mypage.test.tsx` |
| 재진단 성공·실패·중복 클릭 방지 | 통합 | `integration/pages/ResultRetry.test.tsx` |
| 인증 준비 전 대기, 비로그인 리다이렉트 | 통합 | `integration/components/ProtectedRoute.test.tsx` |
| 로그인 버튼, 약관 동의 안내 링크 | 통합 | `integration/pages/Login.test.tsx` |
| 이용약관·개인정보처리방침 탭 전환, 목차 이동 | 통합 | `integration/pages/Policy.test.tsx` |
| 푸터 메뉴, 정책 링크, 문의 메일 | 통합 | `integration/components/Footer.test.tsx` |

## 4. 폴더 구조

```
src/test/
├── vitest.setup.ts          # 모든 테스트 전에 실행: MSW 시작, 브라우저 API 스텁, 상태 초기화
├── unit/                    # 소스 경로를 그대로 따라갑니다 (src/lib/text.ts → unit/lib/text.test.ts)
│   ├── api/
│   ├── components/
│   ├── hooks/
│   ├── lib/
│   ├── store/
│   └── pages/{Question,Upload}/utils/
├── integration/
│   ├── components/          # 컴포넌트 단위 통합 (ProtectedRoute, Header, Footer, 업로드 입력·상품 카드, 진단 카드, 진단 결과 목록 등)
│   └── pages/               # 화면 단위 통합 (Upload, Question, Judgement, Products, Mypage, ResultRetry, ResultBack, BackNavigation, Login, Policy)
├── drivers/                 # 화면별 드라이버: 통합 테스트가 화면을 조작·조회하는 통로 (uploadPage, judgementPage ...)
├── constants/               # messages.ts: 통합 테스트가 비교하는 알림·안내 문구
├── infra/                   # 테스트 기반 자체 검증
├── mocks/                   # MSW 서버·핸들러·응답 헬퍼·요청 기록·픽스처
├── utils/                   # renderWithProviders, 인증 시나리오, 알림·확인 헬퍼, 모바일 폭 스텁(viewport), createGate, LocationDisplay
├── smoke.test.tsx           # 테스트 환경이 동작하는지 확인하는 최소 테스트
└── browserStubs.test.tsx    # 브라우저 API 스텁 확인
```

- 테스트 파일 이름은 `*.test.ts` 또는 `*.test.tsx`입니다. 이 패턴이 아니면 실행되지 않습니다 (`include: src/**/*.test.{ts,tsx}`).
- 테스트는 소스 옆이 아니라 `src/test/` 아래에 모읍니다. 소스 폴더에는 `*.test.*` 파일을 두지 않습니다.
- 통합 테스트는 `drivers/`의 드라이버를 거쳐 작성하고 문구는 `constants/messages.ts`의 상수로 비교합니다. 규칙은 [FE 코드 컨벤션의 테스트 작성](CODE_CONVENTION.md#테스트-작성)을 따릅니다.
- 테스트 코드도 `npm run build`의 `tsc -b`와 ESLint(import 정렬 포함) 대상입니다.

## 5. 테스트 환경

설정은 [`vite.config.ts`](../palgijeonae/vite.config.ts)의 `test` 블록과 [`src/test/vitest.setup.ts`](../palgijeonae/src/test/vitest.setup.ts)에 있습니다.

| 설정 | 값 | 이유 |
|---|---|---|
| `environment` | `jsdom` | 브라우저 없이 DOM·이벤트를 흉내 냅니다 |
| `globals` | `true` | `describe`, `it`, `expect`, `vi`를 import 없이 씁니다. 타입은 `tsconfig.app.json`의 `vitest/globals` |
| `env.VITE_API_URL` | `''` (빈 값) | API를 jsdom과 같은 출처(`/api/...`)로 요청합니다. 개발용 `.env` 값과 상관없이 실제 서버로 나가지 않습니다 |
| `asyncUtilTimeout` | 5초 | `findBy*`·`waitFor`의 대기 시간. 병렬 실행에서 각 파일의 첫 렌더가 느릴 때를 견딥니다 |
| `testTimeout` | 15초 | 렌더하고 조작을 이어 가는 통합 테스트가 부하에서 기본 5초를 넘길 때를 견딥니다 |

- **API 주소는 절대 URL로 쓰지 않습니다.** jsdom의 XHR은 다른 출처 응답에 CORS 헤더가 없으면 MSW가 만든 응답도 `Network Error`로 처리합니다. 다른 출처로 나가는 요청(S3)만 응답에 CORS 헤더를 넣습니다.
- 테스트 사이에 상태가 새지 않도록 매 테스트 후 응답 오버라이드, 요청 기록, 인증 스토어, 세션 저장소(답변 임시 저장), 브라우저 API 스텁을 모두 초기화합니다.

## 6. API 모킹 (MSW)

[MSW](https://mswjs.io/)로 네트워크 요청을 가로챕니다. 서버·핸들러는 `src/test/mocks/`에 있습니다.

| 파일 | 내용 |
|---|---|
| `handlers.ts` | 모든 테스트가 기본으로 쓰는 **성공** 핸들러 |
| `server.ts` | MSW 서버. `vitest.setup.ts`가 시작·초기화·종료합니다 |
| `responses.ts` | `successResponse`, `errorResponse`, `s3Response` 응답 헬퍼 |
| `requestLog.ts` | 핸들러가 받은 요청의 경로·헤더·본문을 기록 (`requestLog`, `recordRequest`) |
| `fixtures.ts` | 응답 데이터를 만드는 빌더 (`buildProductResult`, `buildQuestion` 등) |

- **핸들러가 없는 요청은 오류로 처리합니다** (`onUnhandledFrame: 'error'`). 새 API를 호출하는 화면을 테스트하면 먼저 기본 핸들러를 추가해야 하고, 실수로 실제 네트워크에 나가는 일이 없습니다.
- 기본 핸들러가 다루는 API: presigned URL 발급, S3 업로드(PUT), 진단 제출, 상품 단건 조회, 질문 답변 제출, 진단서 조회, 재진단, 진단 결과 상품 목록·삭제, 법령 개정 알림 조회, 개정 상품 재진단, 알림 설정 조회·수정, 회원 정보 조회·수정·탈퇴.

### 응답 덮어쓰기

실패 응답이나 다른 데이터는 테스트 안에서 `server.use(...)`로 그 테스트에만 덮어씁니다. 테스트가 끝나면 기본 핸들러로 돌아갑니다.

```ts
server.use(
  http.post(`${API_URL}/api/v1/diagnoses`, () => errorResponse(400, { detailMessage: '진단할 수 없는 상품입니다.' })),
)
```

- 첫 요청만 실패시키고 재시도는 성공시키려면 세 번째 인자로 `{ once: true }`를 줍니다.
- `errorResponse`의 `detailMessage`는 응답의 `details[0].message`로, `message`는 `message`로 담깁니다. 화면은 `details[0].message`를 우선해서 안내하고 없으면 `message`를 씁니다.

### 보낸 요청 검증

기본 핸들러는 받은 요청을 `requestLog`에 기록합니다. 화면이 **무엇을 보냈는지, 보내지 않았는지** 확인할 때 씁니다.

```ts
expect(requestLog.find('POST', '/api/v1/products/product-1/answers')[0].body).toEqual({
  answers: [{ questionId: 'q1', answerText: '네' }],
})
expect(requestLog.all()).toEqual([]) // 요청을 보내지 않아야 하는 경우
```

- **덮어쓴 핸들러는 직접 `await recordRequest(request)`를 호출해야 기록됩니다.** 호출하지 않으면 그 요청은 로그에 남지 않습니다. 실패한 첫 시도의 본문까지 확인하려면 오버라이드 핸들러에서도 호출합니다.
- 쿼리스트링은 `new URL(entry.url).searchParams`로 읽습니다.

### 요청 중 상태 확인

"요청하는 동안 버튼이 비활성화된다"처럼 진행 중 상태를 보려면, 응답을 붙잡아 두는 문(gate)을 씁니다. `src/test/utils/createGate.ts`의 `createGate()`로 만듭니다.

```ts
const gate = createGate()
server.use(http.post(url, async () => { await gate.promise; return successResponse(null) }))

// ... 버튼을 누르고 진행 중 상태를 확인한 뒤
gate.release() // 응답을 풀어 줍니다
```

### 테스트 데이터 규칙

- 질문 회차(`questionRound`)는 **1~2만 가능합니다** (BE 콜백 검증 `@Min(1) @Max(2)`). `buildQuestion`은 범위를 벗어나면 에러를 냅니다. `questionOrder`는 회차가 아니라 한 회차 안의 순서입니다.
- 목록의 상품 이름처럼 서로 부분 문자열이 될 수 있는 값은 자릿수를 맞춥니다 (`상품-01`, `상품-10`). 검색 테스트에서 의도하지 않은 항목이 걸리지 않게 하기 위해서입니다.

## 7. 화면 렌더: 라우터·QueryClient·인증

화면은 `src/test/utils/renderWithProviders.tsx`의 헬퍼로 렌더합니다. 실제 `MemoryRouter`와 재시도를 끈 QueryClient 안에서 렌더되며 **`useNavigate`·`useLocation`·`useParams`는 모킹하지 않고 실제 라우터로 동작합니다.**

```tsx
renderWithProviders(<QuestionPage />, {
  path: '/question/:productId',          // 화면을 붙일 Route 경로 패턴
  route: '/question/product-1',          // 처음 열려 있는 주소 (state가 필요하면 { pathname, state })
  extraRoutes: <Route path="/judgement/:diagnosesId" element={<p>진단 진행 화면</p>} />, // 이동 결과를 확인할 도착 화면
})

expect(await screen.findByText('진단 진행 화면')).toBeInTheDocument()
expect(getCurrentLocation()).toBe('/judgement/diagnoses-77')
```

- 보호 라우트처럼 중첩 `Route`가 필요하면 `renderRoutes(<Route ...>...</Route>, { route })`를 씁니다.
- 이동한 화면은 실제 화면 대신 텍스트로 구분되는 도착 화면으로 대신합니다. 도착 화면의 내용은 그 화면의 테스트에서 검증합니다.
- 인증 상태는 렌더하기 **전에** `setAuthState('restoring' | 'loggedOut' | 'loggedIn')`으로 설정합니다. 테스트가 끝나면 스토어는 자동으로 초기화됩니다.

| 시나리오 | `isAuthReady` | `isLoggedIn` | 의미 |
|---|---|---|---|
| `restoring` | false | false | 새로고침 직후 세션 복구가 끝나기 전 |
| `loggedOut` | true | false | 복구가 끝났고 로그인하지 않음 |
| `loggedIn` | true | true | 로그인함 |

## 8. 브라우저 API 스텁

jsdom에는 없거나 동작하지 않는 브라우저 API는 `vitest.setup.ts`에서 매 테스트 전에 `vi.fn`으로 바꾸고 끝나면 원래 구현으로 되돌립니다. 그래서 호출 인자를 바로 검증할 수 있습니다.

| API | 스텁 동작 | 검증 예 |
|---|---|---|
| `URL.createObjectURL` / `revokeObjectURL` | `'blob:mock-object-url'`을 반환 / 아무것도 안 함 | `expect(URL.createObjectURL).toHaveBeenCalledWith(file)` |
| `window.alert` | 아무것도 안 함 | `expectNotified(QUESTION_MESSAGES.ANSWER_ALL)` (`utils/notifications.ts`) |
| `window.confirm` | 기본은 **확인(true)** | `expectConfirmed(...)`, 취소는 `declineConfirm()` (`utils/confirmations.ts`) |
| `Element.scrollIntoView` | 아무것도 안 함 | `expect(Element.prototype.scrollIntoView).toHaveBeenCalled()` |
| `window.matchMedia` | `matches: false` ("동작 줄이기" 꺼짐, 화면 폭은 데스크톱) | 모바일 폭이 필요하면 테스트에서 `setMobileViewport()` (`utils/viewport.ts`) |
| `Element.animate` | `cancel`이 있는 mock | - |

- **`FormData`는 모킹하지 않고 기본 구현을 씁니다.** 앱 코드가 쓰지 않는 `FileReader`도 스텁하지 않습니다.
- 앱 코드가 새 브라우저 API를 쓰게 되어 jsdom에서 오류가 나면, 테스트마다 따로 막지 말고 `vitest.setup.ts`에 같은 방식으로 추가합니다. (`beforeEach`에서 교체, `afterEach`에서 원복)
- `afterEach`는 스텁을 되돌리기 전에 렌더된 화면부터 내립니다(`cleanup()`). 화면이 남은 채로 스텁이 사라지면 `useIsMobile`처럼 렌더 중에 `matchMedia`를 부르는 훅이 오류를 냅니다.

## 9. 작성 규칙

### 공통

- **테스트 이름은 사용자가 보는 결과를 한국어 문장으로 씁니다.** 구현이 아니라 동작을 적습니다. 예: `제출에 실패하면 서버의 오류 메시지를 안내하고, 화면과 입력한 답변은 그대로 둔다`
- `describe`는 `화면 - 기능` 형식으로 묶습니다. 예: `마이페이지 - 상품 삭제`
- 한 테스트는 한 가지 동작만 확인합니다. 경계값(100자 통과 / 101자 실패)은 각각 따로 씁니다.
- 안내 문구와 오류 메시지는 값을 검증하되, 리터럴을 테스트마다 반복하지 않고 `constants/messages.ts`의 상수로 비교합니다. 소스에서 export된 상수가 있으면 그것을 import합니다. 문구를 바꾸면 이 파일만 고치면 되고, 문구 변경이 의도한 것인지 한 곳에서 확인하게 됩니다.
- 버그를 고친 테스트에는 어떤 버그를 막는 것인지 주석으로 남깁니다.

### 통합 테스트

화면을 찾고 조작하는 규칙(드라이버, 셀렉터 우선순위, 문구 상수, 알림 헬퍼, `NOTE(source)`)은 [FE 코드 컨벤션의 테스트 작성](CODE_CONVENTION.md#테스트-작성)을 따릅니다. 여기서는 그 위에서 시나리오를 쓸 때의 규칙을 정합니다.

- 요소는 **사용자가 보는 방식**(`getByRole` → `getByLabelText` → `getByText`)으로 찾습니다. 이 찾기는 드라이버 안에서만 하고 테스트 본문은 드라이버의 함수를 호출합니다. `data-testid`는 쓰지 않습니다.
- 사용자 조작은 드라이버가 `userEvent.setup()`으로 만든 `user`로 합니다 (`fireEvent` 대신). 긴 입력은 한 글자씩 치면 느리므로 `user.click(input)` 뒤 `user.paste(text)`로 채웁니다. (드라이버가 이렇게 합니다)
- 비동기 결과는 드라이버의 `waitFor...`/`waitUntil...`이나 `findBy*`로 기다립니다. `setTimeout`으로 기다리는 것은 "더 이상 요청하지 않는다"처럼 **일어나지 않음**을 확인할 때만 씁니다.
- 화면 이동은 `getCurrentLocation()`과 도착 화면의 문구를 함께 확인합니다.
- 실패 시나리오는 "안내 문구를 보여준다"에서 끝내지 않고 **화면이 그대로인지, 입력한 값이 남아 있는지, 다시 시도할 수 있는지**까지 확인합니다.
- 요청을 보내지 않아야 하는 분기(검증 실패, 확인 취소, 잘못된 접근)는 `requestLog`로 요청이 없음을 확인합니다.

### 테스트가 실제로 잡는지 확인하기

새 테스트는 통과하는 것만으로는 충분하지 않습니다. 확인하려는 동작의 소스를 **임시로 망가뜨려** 그 테스트가 실패하는지 한 번 확인한 뒤 되돌립니다. 항상 통과하는 테스트는 회귀를 막지 못합니다.

## 10. 실행 방법

명령은 모두 `frontend/palgijeonae`에서 실행합니다. Node 22.13 이상이 필요합니다 (jsdom 29가 `^22.13`, MSW 3가 `>=22.12`를 요구합니다. CI는 Node 22).

| 용도 | 명령 |
|---|---|
| 의존성 설치 | `npm ci` |
| 전체 테스트 실행 | `npm test` |
| 커버리지 측정 | `npm run test:coverage` |
| 파일을 저장할 때마다 다시 실행 (watch) | `npm run test:watch` |
| 특정 파일만 실행 | `npx vitest run src/test/unit/lib/text.test.ts` |
| 특정 폴더만 실행 | `npx vitest run src/test/integration` |
| 이름에 문구가 들어간 테스트만 실행 | `npx vitest run -t "탈퇴에 실패하면"` |
| 테스트 이름을 모두 보면서 실행 | `npx vitest run --reporter=verbose` |
| 린트 | `npm run lint` |
| 타입 검사 + 빌드 | `npm run build` |

- PR을 올리기 전에 `npm run lint`, `npm run test:coverage`, `npm run build`를 로컬에서 모두 통과시킵니다.
- 전체 실행은 1분 안팎이 걸립니다. 대부분 테스트 환경을 만드는 시간이라, 하나만 고칠 때는 특정 파일만 실행하는 것이 빠릅니다.
- 커버리지는 `npm run test:coverage`로 측정합니다. 구문(statements)·분기(branches)·함수(functions)·줄(lines) 모두 70% 이상이어야 하며([`vite.config.ts`](../palgijeonae/vite.config.ts)의 `thresholds`), 못 미치면 명령이 실패합니다. 결과는 터미널 표와 `coverage/index.html`(파일별로 비어 있는 줄 확인)로 볼 수 있습니다.
- 측정 대상은 `src/` 아래 소스입니다. 테스트 코드와 보조 파일(`src/test/`), BE 없이 화면을 볼 때만 쓰는 목업(`src/api/mock/`), 타입 선언, 앱 시작 코드(`main.tsx`, `instrument.ts`)는 제외합니다.

## 11. CI

| 워크플로 | 실행 시점 | 하는 일 |
|---|---|---|
| [`frontend-ci.yml`](../../.github/workflows/frontend-ci.yml) | `frontend/palgijeonae/`가 바뀐 PR(develop·main 대상), develop push, 수동 실행 | `npm ci`, `npm run lint`, `npm run test:coverage`, `npm run build` |

- 단위·통합 테스트는 PR마다 CI에서 실행됩니다. **테스트가 하나라도 실패하거나 커버리지가 기준에 못 미치면 CI가 실패하므로, 고친 뒤에 머지합니다.**
- develop에서는 CI가 성공해야 [`frontend-deploy.yml`](../../.github/workflows/frontend-deploy.yml)이 배포하므로, 테스트가 실패하면 배포되지 않습니다.
- 긴급 배포가 필요하면 Actions에서 `Frontend CI`를 수동 실행하고 `skip-coverage`를 켭니다. 테스트는 그대로 돌고 커버리지 기준 검사만 건너뜁니다. 이 경우 자동 배포는 일어나지 않으므로 `Deploy Frontend to EC2`를 수동 실행합니다.
- CI는 커버리지 리포트를 `frontend-coverage` 아티팩트(7일 보관)로 올립니다.
- CI에서 실패했는데 로컬에서는 통과한다면, 같은 순서로 `npm ci` → `npm run lint` → `npm run test:coverage` → `npm run build`를 실행해 봅니다. 운영체제(대소문자를 구분하는 파일 경로)나 설치된 의존성 차이가 원인인 경우가 많습니다.

## 12. 문제 해결

| 증상 | 원인과 해결 |
|---|---|
| 테스트에서 `Network Error`가 납니다 | API를 절대 URL(다른 출처)로 요청하고 있습니다. jsdom XHR이 CORS 헤더 없는 모킹 응답을 막습니다. 상대 경로(`/api/...`)를 쓰고 다른 출처라면 응답에 CORS 헤더를 넣습니다 |
| 콘솔에 `intercepted a request without a matching request handler`가 나오고 요청이 실패합니다 | 기본 핸들러에 없는 API를 호출했습니다. `mocks/handlers.ts`에 기본 핸들러를 추가하거나, 테스트에서 `server.use`로 응답을 지정합니다 |
| `expect(window.alert)...`에서 `is not a spy or a call to a mock function` 오류가 납니다 | 스텁이 적용되지 않은 환경입니다. `vite.config.ts`의 `setupFiles`가 `src/test/vitest.setup.ts`를 가리키는지 확인합니다 |
| `matchMedia is not a function`, `animate is not a function` 오류 | 같은 원인입니다. 새로 필요한 브라우저 API는 `vitest.setup.ts`에 스텁을 추가합니다 |
| 혼자 실행하면 통과하는데 전체 실행에서만 가끔 실패합니다 | 병렬 실행의 부하로 첫 렌더가 느려진 경우입니다. 대기 시간(`asyncUtilTimeout`, `testTimeout`)이 이미 늘어나 있으므로, 그래도 실패하면 테스트가 다른 테스트의 상태(전역 값, 오버라이드)에 기대고 있지 않은지 봅니다 |
| 요청 기록(`requestLog`)에 요청이 없습니다 | 응답을 덮어쓴 핸들러가 `recordRequest(request)`를 호출하지 않았습니다 ([6절](#보낸-요청-검증)) |
| Windows에서 `npm ci`가 `EPERM: unlink ... rolldown-binding...node`로 실패합니다 | 실행 중인 `vite`(dev 서버·`vite preview`)가 파일을 잡고 있습니다. 서버를 모두 종료한 뒤 다시 실행합니다. `node_modules`가 반쯤 지워졌다면 `npm install`로 복구합니다 |

## 새 테스트를 추가할 때 체크리스트

- [ ] 단위와 통합 중 맞는 종류인지 [3절](#3-어떤-테스트로-검증할지-고르는-기준)로 정했다
- [ ] `src/test/unit/<소스 경로>` 또는 `src/test/integration/` 아래에 `*.test.ts(x)`로 만들었다
- [ ] 새 API를 호출한다면 기본 핸들러를 추가했다
- [ ] 통합 테스트라면 드라이버를 거쳐 썼고 문구는 `messages.ts` 상수로, 알림은 헬퍼로 확인했다 ([컨벤션](CODE_CONVENTION.md#테스트-작성))
- [ ] 성공뿐 아니라 실패·경계·요청을 보내지 않는 경우를 함께 확인했다
- [ ] 소스를 임시로 망가뜨려 테스트가 실패하는 것을 확인했다
- [ ] `npm run lint`, `npm test`, `npm run build`가 모두 통과한다
