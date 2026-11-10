import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

import { ResultStatus } from '@/api/types/common'
import type { ProductFilter } from '@/pages/Products/types'
import { requestLog } from '@/test/mocks/requestLog'

// 진단 결과 페이지 드라이버. 테스트 본문은 이 파일의 함수만 거쳐서 화면을 조작·조회한다.
// 화면 구성(문구, 구조)이 바뀌면 테스트 본문은 두고 이 파일만 고친다.
//
//   const page = productsPage()
//   await page.waitForProductNames(['상품-01'])
//   await page.deleteProduct('상품-01')

type User = ReturnType<typeof userEvent.setup>

const FILTER_LABELS: Record<ProductFilter, RegExp> = {
  all: /^전체$/,
  [ResultStatus.PurchasingAgentAllowed]: /^사입 가능$/,
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

export type SortLabel = '최신순' | '오래된순'

export function productsPage(user: User = userEvent.setup()) {
  // ── 상품 목록 ───────────────────────────────────────────────
  const productItems = (): HTMLElement[] => {
    const list = screen.queryByRole('list', { name: /전체 상품/ })
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

  // ── 개정 알림 배너 ───────────────────────────────────────────
  const banner = () => screen.queryByRole('region', { name: '법령 개정 알림' })
  const bannerScope = () => within(banner() as HTMLElement)
  const amendmentToggle = (lawName: string) => bannerScope().getByRole('button', { name: (accessibleName) => accessibleName.includes(lawName) })
  const isExpanded = (lawName: string) => amendmentToggle(lawName).getAttribute('aria-expanded') === 'true'
  const productNameOf = (button: HTMLElement) => (button.getAttribute('aria-label') ?? '').replace(/ 재진단하기$/, '')
  // 접힌 개정의 상품은 화면에 보이지 않는다. 접힘 여부와 상관없이 읽으려면 hidden을 포함한다.
  const rediagnoseButton = (name: string) => bannerScope().getByRole('button', { name: `${name} 재진단하기`, hidden: true })
  const expandAllAmendments = async (user: User) => {
    for (const toggle of bannerScope().queryAllByRole('button', { expanded: false })) {
      await user.click(toggle)
    }
  }

  // ── 검색 ────────────────────────────────────────────────────
  const searchBox = () => screen.getByRole('textbox', { name: /상품명 검색/ })

  const sortButton = (label: SortLabel) => within(screen.getByRole('group', { name: '정렬' })).getByRole('button', { name: label })

  const productCheckbox = (name: string) => within(productItem(name)).getByRole('checkbox', { name: `${name} 선택` })
  const selectAllCheckbox = () => screen.getByRole('checkbox', { name: '현재 페이지 전체 선택' })
  // 툴바 왼쪽의 글자("전체 선택" / "3개 선택됨")는 전체 선택 체크박스와 같은 줄에 있다.
  const selectionSummary = () => selectAllCheckbox().closest('div')?.textContent?.trim() ?? ''

  const pageNavButton = (nav: PageNav) => screen.getByRole('button', { name: PAGE_NAV_LABELS[nav] })

  const searchTypedText = async (keyword: string) => {
    await user.click(searchBox())
    await user.paste(keyword)
  }

  return {
    // ── 불러오기 ─────────────────────────────────────────────
    /** 상품 목록의 로딩 표시가 몇 개 보이는지 */
    loadingIndicatorCount: () => screen.queryAllByRole('status', { name: /로딩/ }).length,
    /** 불러오기 실패 화면의 "다시 시도"를 누른다. */
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

    // ── 선택 ────────────────────────────────────────────────
    toggleProduct: (name: string) => user.click(productCheckbox(name)),
    isProductSelected: (name: string) => (productCheckbox(name) as HTMLInputElement).checked,
    toggleSelectAll: () => user.click(selectAllCheckbox()),
    isSelectAllChecked: () => (selectAllCheckbox() as HTMLInputElement).checked,
    isSelectAllPartial: () => (selectAllCheckbox() as HTMLInputElement).indeterminate,
    isSelectAllEnabled: () => !(selectAllCheckbox() as HTMLInputElement).disabled,
    selectionSummary,
    waitForSelectionSummary: (text: string) => waitFor(() => expect(selectionSummary()).toBe(text)),

    // ── 정렬 ────────────────────────────────────────────────
    sortBy: (label: SortLabel) => user.click(sortButton(label)),
    isSortSelected: (label: SortLabel) => sortButton(label).getAttribute('aria-pressed') === 'true',

    // ── 목록 조회 요청 (마지막으로 보낸 조회의 쿼리) ────────────────
    lastListQuery: () => new URL(requestLog.find('GET', '/api/v1/products').at(-1)!.url).searchParams,
    listRequestCount: () => requestLog.find('GET', '/api/v1/products').length,

    // ── 상품 삭제 ────────────────────────────────────────────
    deleteProduct: (name: string) => user.click(deleteButton(name)),
    isDeleteEnabled: (name: string) => !(deleteButton(name) as HTMLButtonElement).disabled,
    /** 삭제 요청이 진행 중이라 "삭제 중"으로 보이는지 */
    isDeleting: (name: string) => deleteButton(name).textContent?.includes('삭제 중') ?? false,
    waitUntilDeleteDisabled: (name: string) => waitFor(() => expect((deleteButton(name) as HTMLButtonElement).disabled).toBe(true)),

    // ── 개정 알림 배너 ───────────────────────────────────────
    hasRevisionBanner: () => banner() !== null,
    /** 개정 알림 조회 요청을 보낼 때까지 기다린다. (배너가 없어야 하는 경우, 요청 전에 확인하지 않도록) */
    waitForLawAmendmentsRequest: () => waitFor(() => expect(requestLog.find('GET', '/api/v1/law-amendments').length).toBeGreaterThan(0)),
    waitForAmendment: async (lawName: string) => {
      await waitFor(() => expect(banner()).not.toBeNull())
      await waitFor(() => expect(amendmentToggle(lawName)).toBeInTheDocument())
    },
    hasAmendment: (lawName: string) => banner() !== null && bannerScope().queryAllByRole('button', { name: (accessibleName) => accessibleName.includes(lawName) }).length > 0,
    /** 접힘 여부와 상관없이 배너에 담긴 모든 상품 이름 */
    recheckProductNames: () => bannerScope().queryAllByRole('button', { name: / 재진단하기$/, hidden: true }).map(productNameOf),
    /** 지금 화면에 보이는(펼쳐진 개정의) 상품 이름 */
    visibleRecheckProductNames: () => bannerScope().queryAllByRole('button', { name: / 재진단하기$/ }).map(productNameOf),
    isAmendmentExpanded: isExpanded,
    toggleAmendment: (lawName: string) => user.click(amendmentToggle(lawName)),
    /** 접혀 있을 때만 눌러 펼친다. (처음 펼침 상태에 기대지 않는다) */
    async expandAmendment(lawName: string) {
      if (!isExpanded(lawName)) {
        await user.click(amendmentToggle(lawName))
      }
    },
    /** 상품의 재진단 버튼을 누른다. 접힌 개정이 있으면 먼저 모두 펼친다. */
    async rediagnose(name: string) {
      await expandAllAmendments(user)
      await user.click(rediagnoseButton(name))
    },
    isRediagnoseEnabled: (name: string) => !(rediagnoseButton(name) as HTMLButtonElement).disabled,
    waitUntilRediagnoseDisabled: (name: string) => waitFor(() => expect((rediagnoseButton(name) as HTMLButtonElement).disabled).toBe(true)),
  }
}

export type ProductsPage = ReturnType<typeof productsPage>
