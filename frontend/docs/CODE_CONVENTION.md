# 프론트엔드 코드 컨벤션

`frontend/palgijeonae` 코드를 작성할 때 따르는 규칙입니다. 브랜치·이슈·PR·커밋 규칙은 루트 [`CONTRIBUTING.md`](../../CONTRIBUTING.md)를 참고하세요.

자동으로 강제되는 규칙(import 정렬, 미사용 import 제거)은 ESLint([`eslint.config.js`](../palgijeonae/eslint.config.js))가 처리하므로, `npm run lint`(가능하면 `--fix`)를 커밋 전에 돌리면 아래 규칙 상당수가 저절로 맞춰집니다.

## 목차

1. [폴더·파일 구조](#폴더파일-구조)
2. [네이밍](#네이밍)
3. [컴포넌트 작성 규칙](#컴포넌트-작성-규칙)
4. [import 규칙](#import-규칙)
5. [API·타입 정의 위치](#api타입-정의-위치)
6. [상태 관리](#상태-관리)
7. [에러 처리](#에러-처리)
8. [스타일](#스타일)
9. [접근성](#접근성)
10. [테스트 작성](#테스트-작성)

## 폴더·파일 구조

```
src/
├── api/            # BE 리소스별 API 함수(products.ts, diagnoses.ts, uploads.ts, users.ts, lawAmendments.ts)
│   ├── core/       # axios 인스턴스·인터셉터(client.ts), 쿼리 재시도 정책, Sentry 전송 정책, 유효하지 않은 ID·세션 거부 판별
│   ├── types/      # 여러 페이지가 함께 쓰는 도메인 타입·enum(product.ts, common.ts)
│   └── mock/       # BE 없이 화면을 볼 때 쓰는 목업(실제 API와 같은 이름·시그니처)
├── components/
│   ├── common/     # 여러 페이지에서 쓰는 공용 컴포넌트
│   └── layout/     # Header + 본문 레이아웃
├── pages/          # 페이지별 폴더
├── store/          # Zustand 스토어
├── hooks/          # 여러 페이지·컴포넌트가 함께 쓰는 훅
├── constants/      # 여러 페이지가 함께 쓰는 상수(상태 배지 라벨 등)
├── lib/            # 범용 유틸(클래스 병합, 글자 수 계산, 라우트 파라미터 검사 등)
└── test/           # 단위·통합 테스트, 화면 드라이버, MSW 핸들러, 테스트 유틸 (소스 폴더에는 테스트 파일을 두지 않음)
```

- **`test/`**: 테스트는 소스 옆이 아니라 이곳에 모읍니다. 테스트 종류·폴더 구조·실행 방법은 [TEST_POLICY.md](TEST_POLICY.md)를, 통합 테스트 작성 규칙은 [테스트 작성](#테스트-작성)을 따릅니다.
- **`components/common/`**: 2곳 이상에서 재사용하는 컴포넌트만 둡니다. 컴포넌트마다 폴더를 만들고 그 안에 `index.tsx` 하나로 작성합니다(예: `components/common/Button/index.tsx`).
- **`pages/<Page>/`**: 그 페이지에서만 쓰는 파일을 역할별 폴더에 나눠 둡니다. 컴포넌트는 `components/`, 훅은 `hooks/`, 순수 함수는 `utils/`에 두고, `index.tsx`(페이지 진입점), `types.ts`, `constants.ts`만 페이지 폴더 바로 아래에 둡니다(예: `pages/Products/components/MyProductList.tsx`, `pages/Mypage/hooks/useMyInfo.ts`, `pages/Mypage/constants.ts`). 파일이 하나뿐인 폴더(예: `pages/NotFound/`)는 나누지 않습니다.
- 페이지 안에서 하나의 하위 기능이 파일 여러 개로 묶일 만큼 커지면(탭 하나, 섹션 하나 등) 그 폴더를 페이지의 `components/` 아래에 두고, 그 폴더 안에서 다시 같은 구조(진입점 `index.tsx` + `components/`, `utils/` …)를 반복합니다(예: `pages/Result/components/DiagnosisResult/`에 `index.tsx`, `components/FindingCard.tsx`, `utils/bannerConfig.ts`가 함께 있음).
- 2번 이상 반복되는 마크업·로직만 별도 파일/컴포넌트로 분리합니다. 한 번만 쓰이는 조각을 미리 분리하지 않습니다.

## 네이밍

| 대상 | 규칙 | 예시 |
|---|---|---|
| 컴포넌트 파일·함수 | PascalCase | `ProductPreview`, `MyProductList.tsx` |
| 훅 파일·함수 | `use` + PascalCase/camelCase | `useMyInfo.ts`, `useRetryDiagnosis.ts` |
| 일반 함수·변수 | camelCase | `getErrorMessage`, `handleSubmitAnswers` |
| 상수 | SCREAMING_SNAKE_CASE | `PAGE_SIZE`, `NAME_MAX_LENGTH` |
| enum 타입 | PascalCase | `ResultStatus`, `SourceType` |
| enum 멤버 | PascalCase 키 + BE와 동일한 문자열 값 | `InProgress = "IN_PROGRESS"` |

- 상태값은 느슨한 문자열 리터럴 대신 꼭 enum으로 다룹니다([`api/types/common.ts`](../palgijeonae/src/api/types/common.ts), [`api/types/product.ts`](../palgijeonae/src/api/types/product.ts)). enum에는 멤버별 의미를 설명하는 JSDoc을 답니다.

## 컴포넌트 작성 규칙

```tsx
interface ExampleProps {
    title: string
    onClick: () => void
}

function Example({ title, onClick }: ExampleProps) {
    return <button onClick={onClick}>{title}</button>;
}

export default Example;
```

- 함수 선언(`function Example() {}`) 뒤에 `export default Example;`을 파일 맨 아래에 따로 씁니다. `export default function`으로 한 줄에 합치지 않습니다.
- Props는 `ComponentNameProps` 인터페이스로 정의합니다.
- 여러 스타일 변형이 필요하면 `class-variance-authority`(`cva`)로 variant를 정의하고, 클래스 조합·조건부 적용은 `cn()`([`lib/cn.ts`](../palgijeonae/src/lib/cn.ts))으로 합칩니다(예: [`components/common/Button`](../palgijeonae/src/components/common/Button/index.tsx)).
- 주석은 한국어로, 코드만 읽어서는 알기 어려운 "왜"를 설명합니다. 코드가 그대로 보여주는 내용은 주석으로 반복하지 않습니다.

## import 규칙

- 다른 폴더의 모듈은 `@/` 별칭으로 가져옵니다(`@/api/core/client`, `@/components/common/Button`). 같은 폴더 안의 파일만 `./`로 가져옵니다. `../` 같은 상위 폴더 상대 경로는 쓰지 않습니다.
- 페이지·컴포넌트 import에는 `.tsx`/`.ts` 확장자를 붙입니다(`"./MyProductList.tsx"`, `"@/api/users.ts"`). 기존 코드 중 일부는 아직 확장자 없이 돼 있지만 새로 작성하는 코드는 확장자를 붙입니다.
- import 순서·그룹(외부 패키지 → `@/` → `./`)과 정렬은 직접 맞추지 않고 `eslint-plugin-simple-import-sort`가 자동으로 처리합니다. `npm run lint -- --fix`로 정리하세요.
- 쓰지 않는 import는 `eslint-plugin-unused-imports`가 에러로 잡습니다. 의도적으로 안 쓰는 매개변수는 `_` 접두사를 붙이면 허용됩니다(`unused-imports/no-unused-vars`).

## API·타입 정의 위치

- API 함수는 BE 리소스(요청 URL의 첫 경로)별로 `src/api/*.ts`에 둡니다(`api/products.ts`, `api/diagnoses.ts`, `api/uploads.ts`, `api/users.ts`). 화면 이름이 아니라 리소스 이름으로 파일을 나누고, 새 엔드포인트는 같은 리소스 파일에 추가합니다. `apiClient`([`api/core/client.ts`](../palgijeonae/src/api/core/client.ts))를 사용하고, 함수는 BE 응답의 `data`만 꺼내 돌려줍니다.
  ```ts
  export async function getMyInfo(): Promise<UserInfo> {
      const response = await apiClient.get("/api/v1/users/me");
      return response.data.data as UserInfo;
  }
  ```
- 여러 페이지가 함께 쓰는 도메인 타입·enum은 `api/types/`(`common.ts`의 상태값 등 전역 enum, `product.ts`의 `ToolName`, `Determination` 등)에 둡니다. 한 API 파일에서만 쓰는 요청 타입·enum은 그 파일에 둡니다(`api/products.ts`의 `SortType`).
- 한 페이지에서만 쓰는 타입은 그 페이지 폴더의 `types.ts`에 둡니다(`pages/Products/types.ts`, `pages/Result/types.ts`).
- BE API가 아직 준비되지 않았을 때는 `api/*.ts` 함수 내부를 모듈 상태 기반 목업으로 임시 대체하고, 연동되면 `api/mock/` 아래 같은 이름의 파일로 옮깁니다(기존 [`api/mock/`](../palgijeonae/src/api/mock) 참고). 이미 연동된 API 함수를 다시 목업으로 보고 싶을 때는 호출부의 import만 `@/api/X` → `@/api/mock/X`로 바꾸면 됩니다. 목업 파일은 실제 API 파일과 같은 이름으로 둡니다(`api/products.ts` ↔ `api/mock/products.ts`).

## 상태 관리

- 서버 데이터는 TanStack Query로 관리합니다. 페이지 폴더의 `use*.ts` 훅 하나가 조회(`useQuery`) 또는 수정(`useMutation`) 하나를 책임집니다(`useMyProducts.ts`, `useDeleteProducts.ts`). `queryKey`는 `[도메인, 식별자]` 형태로 짓습니다.
- 수정 후 목록을 다시 불러와야 하면 `invalidateQueries`, 응답으로 캐시만 바로 갱신해도 되면 `setQueryData`를 씁니다.
- 로그인 등 클라이언트 전역 상태는 Zustand로 관리합니다([`store/useAuthStore.ts`](../palgijeonae/src/store/useAuthStore.ts)). Access Token은 메모리에만 두고 새로고침하면 refresh token 쿠키로 다시 발급받습니다.

## 에러 처리

- 401(`AUTH-001`, 토큰 만료)은 `apiClient`의 응답 인터셉터([`api/core/client.ts`](../palgijeonae/src/api/core/client.ts))가 자동으로 토큰을 재발급받아 원래 요청을 한 번 재시도합니다. 개별 호출부에서 따로 처리하지 않습니다. 재발급도 실패하면 로그아웃 후 `/login`으로 보냅니다.
- BE 에러 메시지는 직접 파싱하지 않고 `getErrorMessage(error, fallback)`([`api/core/client.ts`](../palgijeonae/src/api/core/client.ts))로 꺼냅니다. `details[0].message` → `message` → `fallback` 순으로 찾고, 429(`COMMON-011`)는 `Retry-After` 헤더로 만든 전용 문구를 우선합니다.
- 진단서·상품 id를 주소로 받는 화면(진행, 질문, 결과)은 조회가 400이나 404로 실패하면 둘 다 "유효하지 않은 ID"로 안내합니다. 사용자가 주소를 직접 바꿀 수 있어 두 상태가 모두 나올 수 있고, 사용자에게는 같은 상황이기 때문입니다. 판별은 `isInvalidIdError`([`api/core/invalidId.ts`](../palgijeonae/src/api/core/invalidId.ts))를 씁니다.
- 세션 복구(reissue) 요청이 4xx(429 제외)로 거절되면 다시 로그인해야 하는 상태로 봅니다. 네트워크 오류·타임아웃·5xx는 일시 실패일 수 있어 세션이 끝났다고 보지 않습니다. 판별은 `isSessionRejectedError`([`api/core/sessionRejected.ts`](../palgijeonae/src/api/core/sessionRejected.ts))를 씁니다.
- 요청 실패 알림과 삭제·탈퇴 같은 되돌릴 수 없는 액션의 사전 확인은 `alert`/`confirm`으로 처리합니다(커스텀 토스트·모달 없음).

## 스타일

- Tailwind CSS만 쓰고 별도 CSS 파일은 만들지 않습니다.
- 색상·폰트는 [`src/index.css`](../palgijeonae/src/index.css)의 `@theme` 토큰만 씁니다.

## 접근성

- 상태가 바뀌면 화면 낭독기가 읽도록 `role="status"` 같은 영역에 알립니다.
- 순서가 있는 단계는 `ol`과 `aria-current`로 현재 단계를 알리고, 색으로만 구분하지 않고 텍스트로도 보충합니다.
- 탭·토글·툴팁·이미지 확대 창 등에는 맞는 role·aria 속성을 붙입니다. 포커스를 가두는 요소는 닫을 때 원래 위치로 포커스를 돌려줍니다.
- 버튼을 누를 수 없을 때는 막지 않고 그 이유를 안내합니다.
- `prefers-reduced-motion` 설정이면 애니메이션을 끕니다.
- 장식용 이미지는 `alt=""`로 낭독에서 뺍니다.

## 테스트 작성

테스트 종류·폴더 구조·실행 방법은 [TEST_POLICY.md](TEST_POLICY.md)를 따르고, 여기서는 **통합 테스트**(`src/test/integration/`)를 쓸 때 지키는 규칙을 정합니다. 목표는 화면 문구나 마크업이 바뀌어도 테스트 본문은 그대로 두고, 셀렉터와 문구를 모아 둔 한 곳만 고치는 것입니다. 단위 테스트에는 적용하지 않습니다.

### 드라이버를 거쳐 작성

- 통합 테스트는 화면 요소에 직접 접근하지 않고 화면별 드라이버(`src/test/drivers/<화면>Page.ts`)를 거칩니다. 본문에서 `screen.getBy...`, `within`, `userEvent`를 직접 쓰지 않습니다.
- 드라이버는 `uploadPage()`처럼 함수로 만듭니다. 조작은 `async` 함수(`addUrlProduct`, `removeProduct(name)`), 조회는 값을 돌려주는 함수(`productNames()`, `isFormVisible()`), 기다림은 `waitFor...`/`waitUntil...`로 이름을 짓습니다.
- 상태는 요소의 유무로 우회해서 확인하지 않고 드라이버가 의미 있는 값으로 답하게 합니다. 예: "heading이 없다"가 아니라 `productNames()`가 빈 배열인지로 확인합니다.
- 렌더(라우터·도착 화면 스텁)는 테스트 파일에 둡니다. 도착 화면을 확인하려고 **테스트가 직접 만든 스텁**은 `screen`으로 찾아도 됩니다. (예외)

```tsx
const page = renderUploadPage()

await page.addUrlProduct({ title: '이어폰' })
await page.removeProduct('이어폰')

expect(page.productNames()).toEqual([])
```

### 셀렉터 원칙

- 우선순위는 `getByRole`(+ name) → `getByLabelText` → `getByText`(핵심어 정규식) → `getByTestId` 순입니다. `data-testid`를 새로 붙이지 않고, 찾을 수 없으면 소스에 role·aria 속성을 붙입니다.
- 장식 문자(`→`, `...`)는 매칭에서 뺍니다. 예: `'진단서 보기 →'` 대신 `/진단서 보기/`
- 인덱스(`[0]`, `[1]`)로 고르지 않습니다. 이름으로 항목을 찾고 그 안에서 `within`으로 버튼을 찾습니다. 예: `removeProduct('상품 2')`
- `closest`, `querySelector`, `getElementById`, `heading level`처럼 구조에 묶인 셀렉터는 **드라이버 안에서만** 쓰고 `NOTE(source)`를 답니다.

### 문구는 상수로 비교

- 알림·안내 문구는 리터럴 문자열을 테스트마다 반복하지 않고 `src/test/constants/messages.ts`의 상수(`UPLOAD_MESSAGES.TITLE_REQUIRED` 등)로 비교합니다.
- 소스에서 export된 상수(상태 라벨, 입력 제한값 등)가 있으면 그것을 import하고, 없을 때만 `messages.ts`에 직접 정의하며 `NOTE(source)`를 답니다.
- 테스트가 MSW 응답에 직접 넣는 서버 메시지는 화면 문구가 아니므로 `SERVER_MESSAGES`에 둡니다. 상품 이름처럼 이 테스트의 입력값은 테스트 파일 위쪽에 상수로 둡니다.

### 알림은 헬퍼로 확인

- `window.alert`·`window.confirm`을 본문에서 직접 단언하지 않고 헬퍼를 씁니다. 알림 방식이 토스트나 모달로 바뀌면 이 파일들만 고칩니다.
  - 알림: `src/test/utils/notifications.ts`의 `expectNotified`, `expectNotNotified`, `waitForNotified`, `waitForNotificationCount`
  - 확인: `src/test/utils/confirmations.ts`의 `expectConfirmed`, `declineConfirm`
- 요청이 진행 중인 상태(버튼 비활성화, 로딩)는 응답을 붙잡는 `createGate()`(`src/test/utils/createGate.ts`)로 확인합니다.

### 구조 의존은 NOTE(source)와 함께 드라이버에 격리

- 소스에 접근성 속성이 없어서 구조에 기댈 수밖에 없을 때는 그 코드를 드라이버 한 곳에 두고, 이유와 소스에서 고칠 방법을 적습니다.

```ts
// NOTE(source): 상품 목록(ul)에는 이름이 없고 이 화면의 유일한 list라서 role만으로 찾는다.
// 소스에서 목록에 aria-label(예: "진단한 상품")을 붙이면 getByRole('list', { name })으로 찾을 수 있다.
```

- `NOTE(source)`는 소스 개선 후보 목록이기도 합니다. `grep -rn "NOTE(source)" src/test`로 모아 볼 수 있습니다. 소스에 속성이 추가되면 드라이버를 단순하게 바꾸고 주석을 지웁니다.
- 컴포넌트를 새로 만들 때 목록·그룹·입력에 이름(`aria-label`, `aria-labelledby`, `<label>`)을 붙여 두면 드라이버가 단순해집니다. 접근성에도 좋습니다.
