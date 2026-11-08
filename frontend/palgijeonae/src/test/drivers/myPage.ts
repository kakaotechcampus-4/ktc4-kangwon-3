import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

import { ResultStatus } from '@/api/types/common'
import type { ProductFilter } from '@/pages/Mypage/types'
import { requestLog } from '@/test/mocks/requestLog'

// 마이페이지 드라이버. 테스트 본문은 이 파일의 함수만 거쳐서 화면을 조작·조회한다.
// 화면 구성(문구, 구조)이 바뀌면 테스트 본문은 두고 이 파일만 고친다.
//
//   const page = myPage()
//   await page.waitForProductNames(['상품-01'])
//   await page.deleteProduct('상품-01')

type User = ReturnType<typeof userEvent.setup>

const FILTER_LABELS: Record<ProductFilter, RegExp> = {
  all: /^전체$/,
  [ResultStatus.PurchasingAgentAllowed]: /^구매 대행 가능$/,
  [ResultStatus.DirectImportCertificationRequired]: /^사입 인증 필요$/,
  [ResultStatus.RecheckRequired]: /^재확인 필요$/,
}

const PAGE_NAV_LABELS = {
  first: /^처음$/,
  previous: /^이전$/,
  next: /^다음$/,
  last: /^마지막 페이지$/,
}

export type PageNav = keyof typeof PAGE_NAV_LABELS

export function myPage(user: User = userEvent.setup()) {
  // ── 상품 목록 ───────────────────────────────────────────────
  // NOTE(source): 상품 목록(ul)에는 이름이 없고 이 화면의 유일한 list라서 role만으로 찾는다. 상품 이름은 각 항목의 제목 heading에서 읽는다.
  // 소스에서 목록에 aria-label(예: "진단한 상품")을 붙이면 getByRole('list', { name })으로 찾을 수 있다.
  const productItems = (): HTMLElement[] => {
    const list = screen.queryByRole('list')
    return list ? within(list).getAllByRole('listitem') : []
  }
  const nameOf = (item: HTMLElement) => within(item).getByRole('heading').textContent?.trim() ?? ''
  const productNames = () => productItems().map(nameOf)
  const productItem = (name: string): HTMLElement => {
    const item = productItems().find((candidate) => nameOf(candidate) === name)
    if (!item) {
      throw new Error(`"${name}" 상품을 찾을 수 없습니다. 현재 목록: ${JSON.stringify(productNames())}`)
    }
    return item
  }

  const deleteButton = (name: string) => screen.getByRole('button', { name: `${name} 삭제` })

  // ── 회원 정보 ───────────────────────────────────────────────
  const nameInput = () => screen.getByLabelText(/^이름$/)
  const saveButton = () => screen.getByRole('button', { name: /^저장$/ })
  const cancelButton = () => screen.getByRole('button', { name: /^취소$/ })

  // ── 검색 ────────────────────────────────────────────────────
  const searchBox = () => screen.getByRole('textbox', { name: /상품명 검색/ })

  const pageNavButton = (nav: PageNav) => screen.getByRole('button', { name: PAGE_NAV_LABELS[nav] })

  const searchTypedText = async (keyword: string) => {
    await user.click(searchBox())
    await user.paste(keyword)
  }

  return {
    // ── 불러오기 ─────────────────────────────────────────────
    /** 회원 정보와 상품 목록의 로딩 표시가 몇 개 보이는지 (처음에는 둘 다 불러오는 중이다) */
    loadingIndicatorCount: () => screen.queryAllByRole('status', { name: /로딩/ }).length,
    /** 불러오기 실패 화면의 "다시 시도"를 누른다. 회원 정보와 목록이 동시에 실패하면 버튼이 둘이라 쓸 수 없다. */
    clickRetry: () => user.click(screen.getByRole('button', { name: /다시 시도/ })),

    // ── 화면 문구 ────────────────────────────────────────────
    hasText: (text: string) => screen.queryAllByText(text).length > 0,
    waitForText: async (text: string) => {
      await screen.findByText(text)
    },

    // ── 상품 목록 ────────────────────────────────────────────
    productNames,
    waitForProduct: async (name: string) => {
      await waitFor(() => expect(productNames()).toContain(name))
    },
    waitForProductNames: (names: string[]) => waitFor(() => expect(productNames()).toEqual(names)),
    waitForProductCount: (count: number) => waitFor(() => expect(productNames()).toHaveLength(count)),
    waitForFirstProduct: (name: string) => waitFor(() => expect(productNames()[0]).toBe(name)),
    waitUntilProductGone: (name: string) => waitFor(() => expect(productNames()).not.toContain(name)),
    openProduct: (name: string) => user.click(within(productItem(name)).getByRole('link')),

    // ── 검색 ────────────────────────────────────────────────
    searchValue: () => (searchBox() as HTMLInputElement).value,
    /** 검색어를 입력만 한다. (Enter·검색 버튼 전에는 조회하지 않는다) */
    typeSearch: searchTypedText,
    /** 검색어를 입력하고 Enter로 검색한다. */
    async search(keyword: string) {
      await searchTypedText(keyword)
      await user.keyboard('{Enter}')
    },
    submitSearch: () => user.click(screen.getByRole('button', { name: /^검색$/ })),
    /** 검색어 입력창을 모두 지운다. (Enter 없이 바로 전체 목록으로 돌아간다) */
    clearSearchText: () => user.clear(searchBox()),
    clickClearSearch: () => user.click(screen.getByRole('button', { name: /검색어 지우기/ })),

    // ── 필터·페이지 ──────────────────────────────────────────
    selectFilter: (filter: ProductFilter) => user.click(screen.getByRole('button', { name: FILTER_LABELS[filter] })),
    hasPagination: () => screen.queryByRole('button', { name: PAGE_NAV_LABELS.next }) !== null,
    goToPage: (pageNumber: number) => user.click(screen.getByRole('button', { name: new RegExp(`^${pageNumber}$`) })),
    goTo: (nav: PageNav) => user.click(pageNavButton(nav)),
    isPageNavDisabled: (nav: PageNav) => (pageNavButton(nav) as HTMLButtonElement).disabled,

    // ── 목록 조회 요청 (마지막으로 보낸 조회의 쿼리) ────────────────
    lastListQuery: () => new URL(requestLog.find('GET', '/api/v1/products').at(-1)!.url).searchParams,
    listRequestCount: () => requestLog.find('GET', '/api/v1/products').length,

    // ── 상품 삭제 ────────────────────────────────────────────
    deleteProduct: (name: string) => user.click(deleteButton(name)),
    isDeleteEnabled: (name: string) => !(deleteButton(name) as HTMLButtonElement).disabled,
    /** 삭제 요청이 진행 중이라 "삭제 중"으로 보이는지 */
    isDeleting: (name: string) => deleteButton(name).textContent?.includes('삭제 중') ?? false,
    waitUntilDeleteDisabled: (name: string) => waitFor(() => expect((deleteButton(name) as HTMLButtonElement).disabled).toBe(true)),

    // ── 회원 정보 ────────────────────────────────────────────
    hasUserName: (name: string) => screen.queryAllByText(name).length > 0,
    waitForUserName: async (name: string) => {
      await screen.findByText(name)
    },

    // ── 이름 수정 ────────────────────────────────────────────
    startEditingName: () => user.click(screen.getByRole('button', { name: /이름 수정/ })),
    hasEditNameButton: () => screen.queryByRole('button', { name: /이름 수정/ }) !== null,
    isEditingName: () => screen.queryByLabelText(/^이름$/) !== null,
    nameInputValue: () => (nameInput() as HTMLInputElement).value,
    isNameInputFocused: () => document.activeElement === nameInput(),
    isNameInputEnabled: () => !(nameInput() as HTMLInputElement).disabled,
    waitUntilNameInputDisabled: () => waitFor(() => expect((nameInput() as HTMLInputElement).disabled).toBe(true)),
    /** 입력창의 이름을 모두 지운다. */
    clearName: () => user.clear(nameInput()),
    /** 입력창의 이름을 지우고 새 이름을 붙여 넣는다. */
    async replaceName(name: string) {
      await user.clear(nameInput())
      await user.paste(name)
    },
    saveName: () => user.click(saveButton()),
    cancelEditName: () => user.click(cancelButton()),
    pressEscape: () => user.keyboard('{Escape}'),
    hasSaveButton: () => screen.queryByRole('button', { name: /^저장$/ }) !== null,
    hasCancelButton: () => screen.queryByRole('button', { name: /^취소$/ }) !== null,
    isSaveEnabled: () => !(saveButton() as HTMLButtonElement).disabled,
    isCancelEnabled: () => !(cancelButton() as HTMLButtonElement).disabled,

    // ── 회원 탈퇴 ────────────────────────────────────────────
    clickWithdraw: () => user.click(screen.getByRole('button', { name: /^탈퇴하기$/ })),
    /** 탈퇴 요청이 진행 중이라 버튼이 "탈퇴 중"으로 바뀌어 비활성화되었는지 */
    isWithdrawing() {
      const button = screen.queryByRole('button', { name: /탈퇴 중/ })
      return button !== null && (button as HTMLButtonElement).disabled
    },
    waitUntilWithdrawing: async () => {
      await screen.findByRole('button', { name: /탈퇴 중/ })
    },
    isWithdrawEnabled() {
      const button = screen.queryByRole('button', { name: /^탈퇴하기$/ })
      return button !== null && !(button as HTMLButtonElement).disabled
    },
  }
}

export type MyPage = ReturnType<typeof myPage>
