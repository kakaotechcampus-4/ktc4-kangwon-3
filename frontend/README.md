# 팔기전에 FE

상품을 팔기 전 상품 진단을 요청하고, 진행 상황과 해야할 일을 포함한 진단서를 보여주는 프로젝트 입니다.

- 서비스: https://palgijeone.com

## 목차

1. [화면 구성](#화면-구성)
2. [기술 스택](#기술-스택)
3. [디렉터리 구조](#디렉터리-구조)
4. [화면 흐름](#화면-흐름)
5. [상태 관리](#상태-관리)
6. [API 연동](#api-연동)
7. [에러·로딩·빈 상태](#에러로딩빈-상태)
8. [접근성](#접근성)
9. [로컬 실행](#로컬-실행)
10. [빌드와 배포](#빌드와-배포)
11. [린트와 테스트](#린트와-테스트)
12. [코드 작성 관례](#코드-작성-관례)
13. [알려진 한계](#알려진-한계)

---

## 화면 구성

라우트는 [`src/App.tsx`](palgijeonae/src/App.tsx)에 있습니다.

| 경로 | 화면 | 로그인 필요 |
|---|---|---|
| `/` | 메인. 서비스 소개 | - |
| `/login` | 카카오·네이버·구글 로그인 | - |
| `/oauth/callback` | 로그인 후 토큰을 받아 메인으로 이동 | - |
| `/upload` | 상품 입력(URL 또는 글·이미지, 최대 10개)과 진단 요청 | 필요 |
| `/judgement/:diagnosesId` | 상품별 진단 진행 상황 | 필요 |
| `/question/:productId` | AI 추가 질문에 답변 | 필요 |
| `/result/product/:productId` | 상품 하나의 진단 결과 | 필요 |
| `/result/diagnoses/:diagnosesId` | 진단서 전체 결과 | 필요 |
| `/mypage` | 진단한 상품 목록(검색·필터·페이지), 회원 정보 조회·수정, 상품 삭제, 회원 탈퇴 | 필요 |

- 로그인이 필요한 화면에 로그인하지 않고 들어오면 `/login`으로 보냅니다([`ProtectedRoute`](palgijeonae/src/components/common/ProtectedRoute/index.tsx)).

### 화면별 동작

#### 메인

- 로그인 상태면 CTA가 `/upload`로, 아니면 `/login`으로 이동

#### 로그인

- 카카오·네이버·구글 버튼 → BE의 `/oauth2/authorization/{provider}`로 이동, `redirect_uri=/oauth/callback` 전달
- 이미 로그인된 상태로 들어오면 안내 후 메인으로 이동

#### OAuth 콜백

- refresh token 쿠키로 액세스 토큰 재발급 → 성공 시 메인, 실패(쿠키 없음·만료 등) 시 로그인으로 이동
- BE가 `?error=`를 붙여 리다이렉트하면 바로 로그인으로 이동

#### 상품 업로드

![상품 업로드 화면](docs/images/readme-upload.png)

- URL / 텍스트·이미지 탭 중 골라 최대 10개까지 상품을 담음
- 10개가 차면 입력 폼 대신 안내 문구만 표시
- 상품별 유효성 검증 후 한 번에 진단 요청

#### 진행 상황

![진단 진행 화면](docs/images/readme-judgement.gif)

진단은 상품마다 1~2분 이상 걸립니다. `GET /api/v1/diagnoses/{id}`를 숏폴링하면서 기다리는 동안의 상태를 보여줍니다.

- 폴링 간격은 BE 응답의 `pollIntervalMs`(기본 3초)를 따르고, 진행 중인 상품이 없으면 BE가 이 값을 비워 보내 폴링이 멈춤
- 상품마다 따로 진행 — 먼저 끝난 상품은 다른 상품을 기다리지 않고 바로 결과 확인 가능

| 요소 | 내용 |
|---|---|
| 요약 바 | 상태별 상품 수, 갱신 간격("3초마다 불러오는 중") 또는 종료 표시 |
| 4단계 진행 막대 | 상세페이지 읽기 → 검토 분야 선택 → 법령 검토 → 정리·검증 |
| 단계 설명 | "분야별 전문가가 법령을 확인하고 있어요." 같은 현재 단계 문구. 검증에서 보완이 필요해 법령을 다시 확인하면 그 사실도 알려줌 |
| 상태 배지 | 진행 중 / 답변 필요 / 완료 / 실패 |
| 상태 변화 효과 | 상태가 바뀌면 카드 배경이 잠깐 바뀜. 동작 줄이기 설정이면 재생하지 않음 |

- 답변이 필요하면 "답변하면 처음부터 다시 진단해요. 다른 상품은 기다리지 않고 계속 진행돼요." 안내
- 실패하면 재시도 가능 여부에 따라 "진단에 실패했어요. 다시 시도해 주세요." 또는 "진단을 완료할 수 없어요." 표시
- 페이지를 나가도 진단은 계속되고, 마이페이지에서 다시 확인 가능
- 진행 상황을 불러오지 못하면 안내 문구와 "다시 시도" 버튼 표시

#### 질문 답변

![질문 답변 화면](docs/images/readme-question.png)

- 답변이 필요한 질문 라운드만 표시
- 모두 답하지 않고 제출하면 막고, 처음 미답변 질문으로 스크롤·포커스 이동
- 답변 대기 상태가 아닌 상품에 직접 접근하면 결과 화면으로 이동

#### 진단 결과

![진단 결과 화면](docs/images/readme-result.png)

- 상품 탭(여러 상품일 때) + 진단 결과·다음 단계·상품 정보 3개 탭
- 진단이 끝나기 전엔 "다음 단계" 탭 비활성화
- id가 잘못됐거나 존재하지 않으면 안내 후 메인으로 이동

#### 마이페이지

![마이페이지 화면](docs/images/readme-mypage.png)

- 상품 검색·필터·페이지네이션
- 회원 정보 조회·수정(이름만 인라인 수정), 상품 삭제, 회원 탈퇴
- 법령 개정 알림 배너 클릭 시 "재확인 필요" 필터로 전환하고 상품 목록까지 스크롤

<!-- TODO: 확인 필요 - 메인/로그인/OAuth 콜백 화면 캡처 -->

## 기술 스택

| 분류 | 사용 기술 |
|---|---|
| 프레임워크 | React 19, TypeScript 6, Vite 8 |
| 라우팅 | React Router 7 |
| 서버 상태 | TanStack Query 5 |
| 클라이언트 상태 | Zustand 5 |
| HTTP | Axios |
| 스타일 | Tailwind CSS 4, class-variance-authority, tailwind-merge, Pretendard 글꼴 |
| 린트 | ESLint 10 (typescript-eslint, react-hooks, import 정렬, 미사용 import 제거) |

Node는 CI와 같은 22를 기준으로 합니다.

## 디렉터리 구조

```
src/
├── api/            # Axios 클라이언트, 도메인별 API 함수, 응답 타입
│   └── mock/       # BE 없이 화면을 볼 때 쓰는 목업 데이터
├── components/
│   ├── common/     # 공용 컴포넌트 (Button, Header, Pagination, HelpTooltip 등)
│   └── layout/     # Header + 본문 레이아웃
├── pages/          # 페이지별 폴더. 페이지 전용 컴포넌트·훅·타입을 같은 폴더에 둠
├── store/          # Zustand 스토어 (인증)
├── constants/      # 상태 배지 라벨
└── lib/            # 유틸 (클래스 병합, 글자 수 계산, 라우트 파라미터 검사)
```

## 화면 흐름

```mermaid
flowchart LR
    M[메인] -->|로그인 안 됨| L[로그인]
    L --> O[소셜 로그인] --> CB[OAuth 콜백] --> M
    M -->|로그인 됨| U[상품 입력]
    U -->|진단 요청| J[진행 상황]
    J -->|답변 필요| Q[질문 답변]
    Q -->|제출| J
    J -->|상품 완료| RP[상품 결과]
    J -->|전체 완료| RD[진단서]
    MY[마이페이지] --> RP
```

진단 요청은 다음 순서로 보냅니다([`pages/Upload/diagnosisPipeline.ts`](palgijeonae/src/pages/Upload/diagnosisPipeline.ts)).

1. `POST /api/v1/presigned-url`로 이미지 업로드 URL을 받습니다.
2. S3에 이미지를 직접 올립니다.
3. `POST /api/v1/diagnoses`로 진단을 요청하고, 받은 `diagnosesId`의 진행 화면으로 이동합니다.

## 상태 관리

| 종류 | 도구 | 내용 |
|---|---|---|
| 서버 데이터 | TanStack Query | 진행 상황, 질문, 결과, 내 상품 목록, 회원 정보. queryKey는 `[도메인, 식별자]` 형태 |
| 인증 | Zustand ([`useAuthStore`](palgijeonae/src/store/useAuthStore.ts)) | `accessToken`, 로그인 여부, 인증 확인 완료 여부 |

- Access Token은 메모리에만 둡니다. 새로고침하면 사라지므로, 앱이 시작될 때 refresh token 쿠키로 다시 발급받습니다([`App.tsx`](palgijeonae/src/App.tsx)).
- 페이지별 데이터는 각 페이지 폴더의 `use*.ts` 훅에서 가져옵니다.

## API 연동

[`src/api/client.ts`](palgijeonae/src/api/client.ts)의 Axios 인스턴스를 씁니다.

- `baseURL`은 `VITE_API_URL`입니다. 쿠키를 보내도록 `withCredentials`를 켭니다.
- 요청마다 `Authorization: Bearer <accessToken>`을 붙입니다.
- **401 처리**
  - 응답 코드가 `AUTH-001`(토큰 만료)이면 토큰을 다시 받고 원래 요청을 한 번 더 보냅니다.
  - 여러 요청이 동시에 401을 받아도 재발급은 한 번만 합니다. refresh token이 재발급마다 바뀌기 때문입니다.
  - 그 밖의 401이거나 재발급이 실패하면 로그아웃하고 `/login`으로 보냅니다.
- **429 처리**: 응답 코드가 `COMMON-011`(요청 한도 초과)이면 `Retry-After` 헤더(초)를 읽어 "N초 후 다시 시도해주세요." 문구를 만듭니다. 헤더가 없으면 "잠시 후 다시 시도해주세요."로 대신합니다.
- 에러 문구는 `getErrorMessage`로 꺼냅니다. BE 응답의 `details[0].message` → `message` → 기본 문구 순서이고, 429는 위 전용 문구가 우선합니다.
- S3 업로드는 인증 헤더가 붙지 않도록 Axios 기본 인스턴스로 보냅니다.
- BE 응답은 `{ code, message, details, data }` 형식이고, API 함수는 `data`만 돌려줍니다.

## 에러·로딩·빈 상태

| 상태 | 처리 |
|---|---|
| 로딩 | 공용 [`LoadingSpinner`](palgijeonae/src/components/common/LoadingSpinner/index.tsx). 상황별 문구("진단 요청을 보내는 중...", "로그인 처리 중입니다...") |
| 조회 실패 | 페이지마다 안내 문구와 "다시 시도" 버튼 |
| 빈 목록 | "확인할 상품이 없어요.", "조건에 맞는 상품이 없어요." 등 |
| 없는 리소스(404) | 안내 후 메인으로 이동 |
| 잘못된 경로 | 파라미터가 없거나 잘못되면 안내 후 적절한 화면으로 이동 |
| 요청 실패 | `alert`로 BE 에러 문구 표시 |

## 접근성

- 진행 상황이 바뀌면 화면 낭독기가 읽도록 `role="status"` 영역에 알립니다.
- 진행 막대는 순서 목록(`ol`)과 `aria-current="step"`으로 현재 단계를 알리고, 색으로만 구분하던 상태를 텍스트로 보충합니다.
- 탭·토글·툴팁·이미지 확대 창에 맞는 role과 aria 속성을 붙였습니다. 이미지 확대 창은 키보드(←, →, Esc)로 조작할 수 있고, 닫으면 포커스를 원래 위치로 돌려줍니다.
- 버튼을 누를 수 없을 때는 막지 않고 그 이유를 안내합니다.
- `prefers-reduced-motion` 설정이면 애니메이션을 끕니다.
- 장식용 이미지는 `alt=""`로 낭독에서 뺍니다.

## 로컬 실행

```bash
cd frontend/palgijeonae
npm ci
echo "VITE_API_URL=http://localhost:8080" > .env.local
npm run dev        # http://localhost:5173
```

- 환경변수는 `VITE_API_URL`(BE 주소) 하나입니다.
- 로그인까지 하려면 BE를 로컬에서 띄워야 합니다([BE 로컬 실행](../backend/README.md#로컬-실행)). BE 기본 설정이 `http://localhost:5173`을 CORS와 로그인 리다이렉트 주소로 허용합니다.
- Vite 프록시는 쓰지 않습니다. 브라우저가 BE로 직접 요청합니다.

| 명령 | 내용 |
|---|---|
| `npm run dev` | 개발 서버 |
| `npm run build` | 타입 검사(`tsc -b`) 후 빌드 |
| `npm run lint` | ESLint |
| `npm run preview` | 빌드 결과 미리보기 |

## 빌드와 배포

| 워크플로 | 하는 일 |
|---|---|
| [`frontend-ci.yml`](../.github/workflows/frontend-ci.yml) | `frontend/palgijeonae/` 아래가 바뀐 PR과 develop push에서 `npm ci` → lint → build |
| [`frontend-deploy.yml`](../.github/workflows/frontend-deploy.yml) | develop의 CI가 성공하면 빌드 결과를 S3에 올리고, SSM으로 EC2의 릴리스 폴더에 풀어 `current` 링크를 바꿈 |

- 운영에서는 EC2의 nginx가 정적 파일을 서빙합니다. 없는 경로는 `index.html`로 보냅니다(SPA).
- 중간에 실패하면 기존 `current`가 그대로 서비스됩니다.
- 이전 버전으로 되돌리려면 `frontend-deploy.yml`을 수동 실행하면서 이전 커밋 SHA를 넣습니다.
- 운영 `VITE_API_URL`은 GitHub 저장소 변수로 넣습니다.

## 린트와 테스트

- CI는 PR마다 ESLint와 타입 검사를 포함한 빌드를 돌립니다.
- ESLint 규칙: import 자동 정렬, 사용하지 않는 import는 에러로 처리합니다.
- **자동 테스트(단위·E2E)는 아직 없습니다.**

## 코드 작성 관례

FE 코드 컨벤션(네이밍, 폴더·파일 구조, 컴포넌트 작성 규칙, import 순서, API·타입 정의 위치 등)은 [`CONVENTIONS.md`](CONVENTIONS.md)에 정리했습니다. 브랜치·이슈·PR·커밋 규칙은 루트 [`CONTRIBUTING.md`](../CONTRIBUTING.md)를 참고하세요.

## 알려진 한계

- 자동 테스트가 없습니다.
- 요청 실패와 삭제·탈퇴 확인을 대부분 `alert`/`confirm`으로 처리합니다. 토스트나 커스텀 모달 같은 화면 내 알림은 없습니다.
- 화면 오류를 잡는 ErrorBoundary가 없습니다.
- 요청 타임아웃은 따로 처리하지 않습니다.
- 페이지를 나눠 불러오는 코드 스플리팅을 하지 않습니다.
- 마이페이지의 법령 개정 알림 배너와 알림 설정은 화면만 있고 실제 기능은 연결되지 않았습니다.
