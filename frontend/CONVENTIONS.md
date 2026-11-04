# 프론트엔드 코드 컨벤션

`frontend/palgijeonae` 코드를 작성할 때 따르는 규칙입니다. 브랜치·이슈·PR·커밋 규칙은 루트 [`CONTRIBUTING.md`](../CONTRIBUTING.md)를 참고하세요.

자동으로 강제되는 규칙(import 정렬, 미사용 import 제거)은 ESLint([`eslint.config.js`](palgijeonae/eslint.config.js))가 처리하므로, `npm run lint`(가능하면 `--fix`)를 커밋 전에 돌리면 아래 규칙 상당수가 저절로 맞춰집니다.

## 목차

1. [폴더·파일 구조](#폴더파일-구조)
2. [네이밍](#네이밍)
3. [컴포넌트 작성 규칙](#컴포넌트-작성-규칙)
4. [import 규칙](#import-규칙)
5. [API·타입 정의 위치](#api타입-정의-위치)
6. [상태 관리](#상태-관리)
7. [에러 처리](#에러-처리)
8. [스타일](#스타일)

## 폴더·파일 구조

```
src/
├── api/            # 도메인별 API 함수(product.ts, result.ts, user.ts ...), client.ts, types.ts
│   └── mock/       # BE 없이 화면을 볼 때 쓰는 목업(실제 API와 같은 이름·시그니처)
├── components/
│   ├── common/     # 여러 페이지에서 쓰는 공용 컴포넌트
│   └── layout/     # Header + 본문 레이아웃
├── pages/          # 페이지별 폴더
├── store/          # Zustand 스토어
├── constants/      # 여러 페이지가 함께 쓰는 상수(상태 배지 라벨 등)
└── lib/            # 범용 유틸(클래스 병합, 글자 수 계산, 라우트 파라미터 검사 등)
```

- **`components/common/`**: 2곳 이상에서 재사용하는 컴포넌트만 둡니다. 컴포넌트마다 폴더를 만들고 그 안에 `index.tsx` 하나로 작성합니다(예: `components/common/Button/index.tsx`).
- **`pages/<Page>/`**: 그 페이지에서만 쓰는 컴포넌트·훅·타입·상수를 전부 같은 폴더에 flat 구조로 둡니다. 파일명은 `index.tsx`(페이지 진입점), `ComponentName.tsx`, `useSomething.ts`, `types.ts`, `constants.ts`처럼 역할이 드러나게 짓습니다(예: `pages/Mypage/MyProductList.tsx`, `pages/Mypage/useMyInfo.ts`).
- 페이지 안에서 하나의 하위 기능이 파일 여러 개로 묶일 만큼 커지면(탭 하나, 섹션 하나 등) 그 하위 기능만의 폴더를 만들고, 그 폴더 안에서 다시 같은 flat 구조(진입점 `index.tsx` + 나머지 파일들)를 반복합니다(예: `pages/Result/DiagnosisResult/`에 `index.tsx`, `FindingCard.tsx`, `bannerConfig.ts`가 함께 있음).
- 같은 역할의 여러 하위 컴포넌트를 모아둘 땐 `components/`, 로직용 훅을 모아둘 땐 `hooks/`, 순수 함수를 모아둘 땐 `utils/`처럼 역할별 하위 폴더를 쓸 수 있습니다(예: `pages/Judgement/components/`, `pages/Judgement/hooks/`).
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

- 상태값은 느슨한 문자열 리터럴 대신 꼭 enum으로 다룹니다([`api/types.ts`](palgijeonae/src/api/types.ts), [`api/product.ts`](palgijeonae/src/api/product.ts)). enum에는 멤버별 의미를 설명하는 JSDoc을 답니다.

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
- 여러 스타일 변형이 필요하면 `class-variance-authority`(`cva`)로 variant를 정의하고, 클래스 조합·조건부 적용은 `cn()`([`lib/cn.ts`](palgijeonae/src/lib/cn.ts))으로 합칩니다(예: [`components/common/Button`](palgijeonae/src/components/common/Button/index.tsx)).
- 주석은 한국어로, 코드만 읽어서는 알기 어려운 "왜"를 설명합니다. 코드가 그대로 보여주는 내용은 주석으로 반복하지 않습니다.

## import 규칙

- 다른 폴더의 모듈은 `@/` 별칭으로 가져옵니다(`@/api/client`, `@/components/common/Button`). 같은 폴더 안의 파일만 `./`로 가져옵니다. `../` 같은 상위 폴더 상대 경로는 쓰지 않습니다.
- 페이지·컴포넌트 import에는 `.tsx`/`.ts` 확장자를 붙입니다(`"./MyProductList.tsx"`, `"@/api/user.ts"`). 기존 코드 중 일부는 아직 확장자 없이 돼 있지만, 새로 작성하는 코드는 확장자를 붙입니다.
- import 순서·그룹(외부 패키지 → `@/` → `./`)과 정렬은 직접 맞추지 않고 `eslint-plugin-simple-import-sort`가 자동으로 처리합니다. `npm run lint -- --fix`로 정리하세요.
- 쓰지 않는 import는 `eslint-plugin-unused-imports`가 에러로 잡습니다. 의도적으로 안 쓰는 매개변수는 `_` 접두사를 붙이면 허용됩니다(`unused-imports/no-unused-vars`).

## API·타입 정의 위치

- API 함수는 도메인별로 `src/api/*.ts`에 둡니다(`api/product.ts`, `api/result.ts`, `api/user.ts` ...). `apiClient`([`api/client.ts`](palgijeonae/src/api/client.ts))를 사용하고, 함수는 BE 응답의 `data`만 꺼내 돌려줍니다.
  ```ts
  export async function getMyInfo(): Promise<UserInfo> {
      const response = await apiClient.get("/api/v1/users/me");
      return response.data.data as UserInfo;
  }
  ```
- 여러 페이지가 함께 쓰는 도메인 타입·enum은 `api/types.ts`(상태값 등 전역 enum) 또는 해당 도메인 API 파일(`api/product.ts`의 `ToolName`, `Determination` 등)에 둡니다.
- 한 페이지에서만 쓰는 타입은 그 페이지 폴더의 `types.ts`에 둡니다(`pages/Mypage/types.ts`, `pages/Result/types.ts`).
- BE API가 아직 준비되지 않았을 때는 `api/*.ts` 함수 내부를 모듈 상태 기반 목업으로 임시 대체하고, 연동되면 `api/mock/*Mock.ts`로 옮깁니다(기존 [`api/mock/`](palgijeonae/src/api/mock) 참고). 이미 연동된 API 함수를 다시 목업으로 보고 싶을 때는 호출부의 import만 `@/api/X` → `@/api/mock/XMock`으로 바꾸면 됩니다.

## 상태 관리

- 서버 데이터는 TanStack Query로 관리합니다. 페이지 폴더의 `use*.ts` 훅 하나가 조회(`useQuery`) 또는 수정(`useMutation`) 하나를 책임집니다(`useMyProducts.ts`, `useDeleteProduct.ts`). `queryKey`는 `[도메인, 식별자]` 형태로 짓습니다.
- 수정 후 목록을 다시 불러와야 하면 `invalidateQueries`, 응답으로 캐시만 바로 갱신해도 되면 `setQueryData`를 씁니다.
- 로그인 등 클라이언트 전역 상태는 Zustand로 관리합니다([`store/useAuthStore.ts`](palgijeonae/src/store/useAuthStore.ts)).

## 에러 처리

- BE 에러 메시지는 직접 파싱하지 않고 `getErrorMessage(error, fallback)`([`api/client.ts`](palgijeonae/src/api/client.ts))로 꺼냅니다. `details[0].message` → `message` → `fallback` 순으로 찾고, 429(`COMMON-011`)는 `Retry-After` 헤더로 만든 전용 문구를 우선합니다.
- 요청 실패 알림과 삭제·탈퇴 같은 되돌릴 수 없는 액션의 사전 확인은 `alert`/`confirm`으로 처리합니다(커스텀 토스트·모달 없음).

## 스타일

- Tailwind CSS만 쓰고 별도 CSS 파일은 만들지 않습니다.
- 색상·폰트는 [`src/index.css`](palgijeonae/src/index.css)의 `@theme` 토큰만 씁니다.
- 접근성(aria 속성, 키보드 조작, `prefers-reduced-motion` 대응 등)은 [`README.md`의 접근성](README.md#접근성) 절을 참고하세요.
