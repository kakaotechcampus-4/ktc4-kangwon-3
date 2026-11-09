import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

// 결과 화면 드라이버. 테스트 본문은 이 파일의 함수만 거쳐서 화면을 조작·조회한다.
// 화면 구성(문구, 구조)이 바뀌면 테스트 본문은 두고 이 파일만 고친다.
//
//   const page = resultPage()
//   await page.waitForRetryButton()
//   await page.clickRetry()

type User = ReturnType<typeof userEvent.setup>

interface TextOptions {
  /** true면 그 문구와 정확히 같은 글자만, 아니면 그 문구를 포함한 글자도 찾는다. (실패 배너는 문구 뒤에 실패 원인이 이어 붙는다) */
  exact?: boolean
}

export function resultPage(user: User = userEvent.setup()) {
  // 장식 화살표(→)는 빼고 핵심어로 찾는다. 불러오기 실패 화면의 "다시 시도" 버튼과 이름이 겹치므로, 상품이 불러와진 뒤에 쓴다.
  const retryButton = () => screen.getByRole('button', { name: /다시 시도/ })

  const textMatcher = (text: string, { exact = false }: TextOptions) => (content: string) => (exact ? content === text : content.includes(text))

  return {
    // ── 불러오기 ─────────────────────────────────────────────
    /** 상품 결과가 나타날 때까지 기다린다. (상품·결과 탭이 보이면 불러온 것이다) */
    waitUntilLoaded: () => screen.findAllByRole('tab'),

    // ── 상품 고르기 (진단서 결과 화면) ─────────────────────────
    // 상품 탭의 이름은 10자까지만 보여 주므로, 긴 상품명은 줄어든 이름으로 찾아야 한다.
    waitForProductTab: (name: string) => screen.findByRole('tab', { name }),
    selectProduct: (name: string) => user.click(screen.getByRole('tab', { name })),

    // ── 배너 문구 ────────────────────────────────────────────
    hasText: (text: string, options: TextOptions = {}) => screen.queryAllByText(textMatcher(text, options)).length > 0,
    waitForText: async (text: string, options: TextOptions = {}) => {
      await screen.findByText(textMatcher(text, options))
    },

    // ── 이전으로 ─────────────────────────────────────────────
    hasBackButton: () => screen.queryByRole('button', { name: '이전으로' }) !== null,
    waitForBackButton: async () => {
      await screen.findByRole('button', { name: '이전으로' })
    },
    clickBack: () => user.click(screen.getByRole('button', { name: '이전으로' })),

    // ── 다시 시도 (재진단) ────────────────────────────────────
    hasRetryButton: () => screen.queryByRole('button', { name: /다시 시도/ }) !== null,
    waitForRetryButton: async () => {
      await screen.findByRole('button', { name: /다시 시도/ })
    },
    isRetryEnabled: () => !(retryButton() as HTMLButtonElement).disabled,
    /** 요청이 진행되는 동안 버튼이 비활성화될 때까지 기다린다. */
    waitUntilRetryDisabled: () => waitFor(() => expect((retryButton() as HTMLButtonElement).disabled).toBe(true)),
    clickRetry: () => user.click(retryButton()),

    // ── 진행 중인 상품의 안내 ─────────────────────────────────
    hasProgressLink: () => screen.queryByRole('link', { name: /진행 상황 확인/ }) !== null,
    waitForProgressLink: async () => {
      await screen.findByRole('link', { name: /진행 상황 확인/ })
    },
  }
}

export type ResultPage = ReturnType<typeof resultPage>
