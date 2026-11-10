import { screen, waitFor } from '@testing-library/react'
import { http } from 'msw'
import { Route } from 'react-router-dom'

import { ResultStatus } from '@/api/types/common'
import ProductsPage from '@/pages/Products'
import type { MyProductItem } from '@/pages/Products/types'
import { PRODUCTS_MESSAGES, SERVER_MESSAGES } from '@/test/constants/messages'
import { productsPage } from '@/test/drivers/productsPage'
import { buildLawAmendment, buildMyProduct, buildRecheckProduct } from '@/test/mocks/fixtures'
import { API_URL } from '@/test/mocks/handlers'
import { recordRequest, requestLog } from '@/test/mocks/requestLog'
import { errorResponse, successResponse } from '@/test/mocks/responses'
import { server } from '@/test/mocks/server'
import { declineConfirm, expectConfirmed } from '@/test/utils/confirmations'
import { createGate } from '@/test/utils/createGate'
import { expectNotNotified, waitForNotified } from '@/test/utils/notifications'
import { getCurrentLocation, renderWithProviders } from '@/test/utils/renderWithProviders'

const PRODUCTS_URL = `${API_URL}/api/v1/products`
const PRODUCT_URL = `${API_URL}/api/v1/products/:productId`
const LAW_AMENDMENTS_URL = `${API_URL}/api/v1/law-amendments`
const REDIAGNOSIS_URL = `${API_URL}/api/v1/products/:productId/rediagnosis`

// 진단 결과 페이지를 실제 라우터·QueryClient·MSW(API 모킹) 위에서 사용자처럼 조작한다.
// 화면 조작·조회는 드라이버(productsPage)를 거친다.
const renderProductsPage = () => {
  const { queryClient } = renderWithProviders(<ProductsPage />, {
    path: '/products',
    route: '/products',
    extraRoutes: (
      <>
        <Route path="/" element={<p>메인 화면</p>} />
        <Route path="/result/product/:productId" element={<p>결과 화면</p>} />
        <Route path="/judgement/:diagnosesId" element={<p>진행 화면</p>} />
      </>
    ),
  })
  return { page: productsPage(), queryClient }
}

// 이동한 도착 화면(이 파일이 만든 스텁)이 보일 때까지 기다린다.
const findStubScreen = (text: string) => screen.findByText(text)

// 상품 이름이 서로 부분 문자열이 되지 않도록 번호를 두 자리로 맞춘다. (검색에서 '상품-01'이 '상품-10'에 걸리지 않게)
const makeProducts = (count: number, overrides: (index: number) => Partial<MyProductItem> = () => ({})): MyProductItem[] =>
  Array.from({ length: count }, (_, index) => {
    const number = index + 1
    return buildMyProduct({ productId: `product-${number}`, productName: `상품-${String(number).padStart(2, '0')}`, ...overrides(number) })
  })

// 서버처럼 동작하는 메모리 목록. GET은 쿼리(resultStatus, keyword, sortType, page, size)대로 거르고 정렬하고 나누고, DELETE는 목록에서 뺀다.
// beforeDelete를 주면 삭제 요청이 그 Promise를 기다린 뒤에 처리된다. ("삭제 중" 상태 확인용)
const mockProductServer = (initial: MyProductItem[], { beforeDelete }: { beforeDelete?: () => Promise<void> } = {}) => {
  let products = [...initial]
  server.use(
    http.get(PRODUCTS_URL, async ({ request }) => {
      await recordRequest(request)
      const params = new URL(request.url).searchParams
      const resultStatus = params.get('resultStatus')
      const keyword = params.get('keyword') ?? ''
      const sortType = params.get('sortType')
      const page = Number(params.get('page') ?? 0)
      const size = Number(params.get('size') ?? 10)

      const matched = products.filter((product) => (!resultStatus || product.resultStatus === resultStatus) && product.productName.includes(keyword))
      // 목록은 최신순으로 쌓아 두었으니, 오래된순이면 거른 뒤 페이지로 나누기 전에 뒤집는다.
      const filtered = sortType === 'OLDEST' ? [...matched].reverse() : matched
      const totalPages = Math.max(1, Math.ceil(filtered.length / size))
      return successResponse({
        products: filtered.slice(page * size, (page + 1) * size),
        pageInfo: { page, size, totalElements: filtered.length, totalPages, hasNext: page + 1 < totalPages },
      })
    }),
    http.delete(PRODUCT_URL, async ({ request, params }) => {
      await recordRequest(request)
      await beforeDelete?.()
      products = products.filter((product) => product.productId !== params.productId)
      return successResponse(null)
    }),
  )
}


describe('진단 결과 - 조회', () => {
  it('불러오는 동안 로딩을 보여주고, 불러오면 상품 목록을 보여준다', async () => {
    mockProductServer(makeProducts(3))
    const { page } = renderProductsPage()

    expect(page.loadingIndicatorCount()).toBe(1)

    await page.waitForProductNames(['상품-01', '상품-02', '상품-03'])
    expect(page.loadingIndicatorCount()).toBe(0)
  })

  it('목록 제목 옆에 전체 개수를 보여준다', async () => {
    mockProductServer(makeProducts(25))
    const { page } = renderProductsPage()

    await page.waitForText('25개')
    // 한 페이지(10개)만 보여주더라도 개수는 필터된 전체 기준이다.
    expect(page.productNames()).toHaveLength(10)
  })

  it('처음에는 필터 없이 첫 페이지를 조회한다', async () => {
    mockProductServer(makeProducts(3))
    const { page } = renderProductsPage()
    await page.waitForProduct('상품-01')

    const query = page.lastListQuery()
    expect(query.get('page')).toBe('0')
    expect(query.get('size')).toBe('10')
    expect(query.has('resultStatus')).toBe(false)
    expect(query.has('keyword')).toBe(false)
  })

  it('상품을 누르면 그 상품의 결과 화면으로 이동한다', async () => {
    mockProductServer(makeProducts(2))
    const { page } = renderProductsPage()
    await page.waitForProduct('상품-02')

    await page.openProduct('상품-02')

    expect(await findStubScreen('결과 화면')).toBeInTheDocument()
    expect(getCurrentLocation()).toBe('/result/product/product-2')
  })

  it('상품이 없으면 안내 문구를 보여준다', async () => {
    mockProductServer([])
    const { page } = renderProductsPage()

    await page.waitForText(PRODUCTS_MESSAGES.EMPTY)
  })

  it('목록 조회에 실패하면 오류 안내와 다시 시도 버튼을 보여주고, 다시 시도하면 불러온다', async () => {
    mockProductServer(makeProducts(2))
    server.use(http.get(PRODUCTS_URL, () => errorResponse(500), { once: true }))
    const { page } = renderProductsPage()

    await page.waitForText(PRODUCTS_MESSAGES.LIST_LOAD_FAILED)

    await page.clickRetry()

    await page.waitForProductNames(['상품-01', '상품-02'])
    expect(page.hasText(PRODUCTS_MESSAGES.LIST_LOAD_FAILED)).toBe(false)
  })
})

describe('진단 결과 - 검색', () => {
  it('검색어를 입력하고 Enter를 누르면 그 검색어로 조회한다', async () => {
    mockProductServer(makeProducts(5))
    const { page } = renderProductsPage()
    await page.waitForProduct('상품-01')

    await page.search('상품-03')

    await page.waitForProductNames(['상품-03'])
    expect(page.lastListQuery().get('keyword')).toBe('상품-03')
  })

  it('입력만 하고 Enter를 누르기 전에는 조회하지 않는다', async () => {
    mockProductServer(makeProducts(5))
    const { page } = renderProductsPage()
    await page.waitForProduct('상품-01')
    const requestCount = page.listRequestCount()

    await page.typeSearch('상품-03')

    expect(page.listRequestCount()).toBe(requestCount)
    expect(page.productNames()).toHaveLength(5)
  })

  it('검색 버튼을 눌러도 검색한다', async () => {
    mockProductServer(makeProducts(5))
    const { page } = renderProductsPage()
    await page.waitForProduct('상품-01')

    await page.typeSearch('상품-02')
    await page.submitSearch()

    await page.waitForProductNames(['상품-02'])
  })

  it('검색어를 모두 지우면 Enter 없이 바로 전체 목록으로 돌아간다', async () => {
    mockProductServer(makeProducts(5))
    const { page } = renderProductsPage()
    await page.waitForProduct('상품-01')
    await page.search('상품-03')
    await page.waitForProductNames(['상품-03'])

    await page.clearSearchText()

    await page.waitForProductCount(5)
    expect(page.lastListQuery().has('keyword')).toBe(false)
  })

  it('검색어 지우기 버튼을 누르면 검색어를 비우고 전체 목록으로 돌아간다', async () => {
    mockProductServer(makeProducts(5))
    const { page } = renderProductsPage()
    await page.waitForProduct('상품-01')
    await page.search('상품-03')
    await page.waitForProductNames(['상품-03'])

    await page.clickClearSearch()

    await page.waitForProductCount(5)
    expect(page.searchValue()).toBe('')
  })

  it('일치하는 상품이 없으면 안내 문구를 보여준다', async () => {
    mockProductServer(makeProducts(3))
    const { page } = renderProductsPage()
    await page.waitForProduct('상품-01')

    await page.search('없는 상품')

    await page.waitForText(PRODUCTS_MESSAGES.EMPTY)
  })
})

describe('진단 결과 - 필터', () => {
  // 사입 가능 3개, 사입 인증 필요 2개, 재확인 필요 1개
  const statusProducts = () =>
    makeProducts(6, (number) => ({
      resultStatus:
        number <= 3
          ? ResultStatus.PurchasingAgentAllowed
          : number <= 5
            ? ResultStatus.DirectImportCertificationRequired
            : ResultStatus.RecheckRequired,
    }))

  it('필터 탭을 누르면 그 결과 상태로 조회한다', async () => {
    mockProductServer(statusProducts())
    const { page } = renderProductsPage()
    await page.waitForProduct('상품-01')

    await page.selectFilter(ResultStatus.DirectImportCertificationRequired)

    await page.waitForProductNames(['상품-04', '상품-05'])
    expect(page.lastListQuery().get('resultStatus')).toBe(ResultStatus.DirectImportCertificationRequired)
  })

  it('다른 탭으로 바꾸거나 전체를 누르면 그에 맞게 다시 조회한다', async () => {
    mockProductServer(statusProducts())
    const { page } = renderProductsPage()
    await page.waitForProduct('상품-01')

    await page.selectFilter(ResultStatus.RecheckRequired)
    await page.waitForProductNames(['상품-06'])
    expect(page.lastListQuery().get('resultStatus')).toBe(ResultStatus.RecheckRequired)

    await page.selectFilter('all')
    await page.waitForProductCount(6)
    expect(page.lastListQuery().has('resultStatus')).toBe(false)
  })

  it('필터와 검색어를 함께 적용한다', async () => {
    mockProductServer(statusProducts())
    const { page } = renderProductsPage()
    await page.waitForProduct('상품-01')

    await page.selectFilter(ResultStatus.PurchasingAgentAllowed)
    await page.search('상품-02')

    await page.waitForProductNames(['상품-02'])
    expect(page.lastListQuery().get('resultStatus')).toBe(ResultStatus.PurchasingAgentAllowed)
    expect(page.lastListQuery().get('keyword')).toBe('상품-02')
  })

  it('필터를 바꾸면 첫 페이지부터 다시 조회한다', async () => {
    mockProductServer(makeProducts(25))
    const { page } = renderProductsPage()
    await page.waitForProduct('상품-01')
    await page.goToPage(3)
    await waitFor(() => expect(page.lastListQuery().get('page')).toBe('2'))

    await page.selectFilter(ResultStatus.PurchasingAgentAllowed)

    await waitFor(() => expect(page.lastListQuery().get('page')).toBe('0'))
  })

  it('검색어를 바꾸면 첫 페이지부터 다시 조회한다', async () => {
    mockProductServer(makeProducts(25))
    const { page } = renderProductsPage()
    await page.waitForProduct('상품-01')
    await page.goToPage(2)
    await waitFor(() => expect(page.lastListQuery().get('page')).toBe('1'))

    await page.search('상품-')

    await waitFor(() => expect(page.lastListQuery().get('page')).toBe('0'))
  })
})

describe('진단 결과 - 정렬', () => {
  it('처음에는 최신순이 선택되어 있고, 최신순으로 조회한다', async () => {
    mockProductServer(makeProducts(3))
    const { page } = renderProductsPage()
    await page.waitForProduct('상품-01')

    expect(page.isSortSelected('최신순')).toBe(true)
    expect(page.isSortSelected('오래된순')).toBe(false)
    expect(page.lastListQuery().get('sortType')).toBe('LATEST')
  })

  it('오래된순을 누르면 오래된순으로 다시 조회하고, 목록 순서가 뒤집힌다', async () => {
    mockProductServer(makeProducts(3))
    const { page } = renderProductsPage()
    await page.waitForProductNames(['상품-01', '상품-02', '상품-03'])

    await page.sortBy('오래된순')

    await page.waitForProductNames(['상품-03', '상품-02', '상품-01'])
    expect(page.lastListQuery().get('sortType')).toBe('OLDEST')
    expect(page.isSortSelected('오래된순')).toBe(true)
    expect(page.isSortSelected('최신순')).toBe(false)
  })

  it('다른 페이지에 있다가 정렬을 바꾸면 첫 페이지부터 다시 조회한다', async () => {
    mockProductServer(makeProducts(25))
    const { page } = renderProductsPage()
    await page.waitForProduct('상품-01')
    await page.goToPage(2)
    await page.waitForFirstProduct('상품-11')

    await page.sortBy('오래된순')

    await page.waitForFirstProduct('상품-25')
    expect(page.lastListQuery().get('page')).toBe('0')
  })

  it('정렬과 필터·검색어를 함께 적용한다', async () => {
    mockProductServer(
      makeProducts(6, (number) => ({
        resultStatus: number <= 3 ? ResultStatus.PurchasingAgentAllowed : ResultStatus.RecheckRequired,
      })),
    )
    const { page } = renderProductsPage()
    await page.waitForProduct('상품-01')

    await page.selectFilter(ResultStatus.PurchasingAgentAllowed)
    await page.search('상품-0')
    await page.sortBy('오래된순')

    await page.waitForProductNames(['상품-03', '상품-02', '상품-01'])
    const query = page.lastListQuery()
    expect(query.get('resultStatus')).toBe(ResultStatus.PurchasingAgentAllowed)
    expect(query.get('keyword')).toBe('상품-0')
    expect(query.get('sortType')).toBe('OLDEST')
  })
})

describe('진단 결과 - 페이지 이동', () => {
  it('상품이 한 페이지(10개) 이하면 페이지 이동 버튼을 보여주지 않는다', async () => {
    mockProductServer(makeProducts(10))
    const { page } = renderProductsPage()
    await page.waitForProduct('상품-01')

    expect(page.hasPagination()).toBe(false)
  })

  it('페이지 번호를 누르면 그 페이지의 상품을 보여준다', async () => {
    mockProductServer(makeProducts(25))
    const { page } = renderProductsPage()
    await page.waitForProduct('상품-01')
    expect(page.productNames()).toHaveLength(10)

    await page.goToPage(2)

    await page.waitForFirstProduct('상품-11')
    expect(page.productNames()).toHaveLength(10)
    expect(page.lastListQuery().get('page')).toBe('1')
  })

  it('다음·이전·마지막·처음 버튼으로 이동하고, 끝에서는 해당 버튼이 비활성이 된다', async () => {
    mockProductServer(makeProducts(25))
    const { page } = renderProductsPage()
    await page.waitForProduct('상품-01')

    // 첫 페이지에서는 처음·이전이 비활성
    expect(page.isPageNavDisabled('first')).toBe(true)
    expect(page.isPageNavDisabled('previous')).toBe(true)

    await page.goTo('last')
    await page.waitForProductNames(['상품-21', '상품-22', '상품-23', '상품-24', '상품-25'])
    expect(page.lastListQuery().get('page')).toBe('2')
    expect(page.isPageNavDisabled('next')).toBe(true)
    expect(page.isPageNavDisabled('last')).toBe(true)

    await page.goTo('previous')
    await page.waitForFirstProduct('상품-11')

    await page.goTo('first')
    await page.waitForFirstProduct('상품-01')
  })
})

describe('진단 결과 - 상품 삭제', () => {
  it('삭제 버튼을 누르면 상품 이름을 넣은 확인 문구를 보여준다', async () => {
    mockProductServer(makeProducts(3))
    const { page } = renderProductsPage()
    await page.waitForProduct('상품-01')

    await page.deleteProduct('상품-02')

    expectConfirmed(PRODUCTS_MESSAGES.deleteConfirm('상품-02'))
  })

  it('확인을 취소하면 삭제 요청을 보내지 않고 목록도 그대로다', async () => {
    declineConfirm()
    mockProductServer(makeProducts(3))
    const { page } = renderProductsPage()
    await page.waitForProduct('상품-01')

    await page.deleteProduct('상품-02')

    expect(requestLog.find('DELETE', '/api/v1/products/product-2')).toHaveLength(0)
    expect(page.productNames()).toEqual(['상품-01', '상품-02', '상품-03'])
  })

  it('확인하면 삭제 요청을 보내고, 목록을 다시 불러와 그 상품만 사라진다', async () => {
    mockProductServer(makeProducts(3))
    const { page } = renderProductsPage()
    await page.waitForProduct('상품-01')
    const listRequestsBefore = page.listRequestCount()

    await page.deleteProduct('상품-02')

    await page.waitForProductNames(['상품-01', '상품-03'])
    expect(requestLog.find('DELETE', '/api/v1/products/product-2')).toHaveLength(1)
    expect(page.listRequestCount()).toBeGreaterThan(listRequestsBefore)
    expectNotNotified()
  })

  it('삭제하는 동안에는 그 상품의 버튼만 "삭제 중"으로 비활성화한다', async () => {
    const gate = createGate()
    mockProductServer(makeProducts(3), { beforeDelete: () => gate.promise })
    const { page } = renderProductsPage()
    await page.waitForProduct('상품-01')

    await page.deleteProduct('상품-02')

    await page.waitUntilDeleteDisabled('상품-02')
    expect(page.isDeleting('상품-02')).toBe(true)
    expect(page.isDeleteEnabled('상품-01')).toBe(true)
    expect(page.isDeleteEnabled('상품-03')).toBe(true)

    gate.release()

    await page.waitUntilProductGone('상품-02')
  })

  it('삭제에 실패하면 서버의 오류 메시지를 안내하고, 상품은 그대로 두며 버튼을 다시 활성화한다', async () => {
    mockProductServer(makeProducts(3))
    server.use(http.delete(PRODUCT_URL, () => errorResponse(400, { detailMessage: SERVER_MESSAGES.PRODUCT_NOT_DELETABLE })))
    const { page } = renderProductsPage()
    await page.waitForProduct('상품-01')

    await page.deleteProduct('상품-02')

    await waitForNotified(SERVER_MESSAGES.PRODUCT_NOT_DELETABLE)
    expect(page.productNames()).toEqual(['상품-01', '상품-02', '상품-03'])
    expect(page.isDeleteEnabled('상품-02')).toBe(true)
    expect(page.isDeleting('상품-02')).toBe(false)
  })

  it('마지막 페이지의 마지막 상품을 삭제하면 이전 페이지로 이동한다', async () => {
    mockProductServer(makeProducts(11))
    const { page } = renderProductsPage()
    await page.waitForProduct('상품-01')
    await page.goToPage(2)
    await page.waitForProductNames(['상품-11'])

    await page.deleteProduct('상품-11')

    await page.waitForProductCount(10)
    expect(page.productNames()[0]).toBe('상품-01')
    expect(page.lastListQuery().get('page')).toBe('0')
    // 상품이 10개가 되어 페이지가 하나뿐이다.
    expect(page.hasPagination()).toBe(false)
  })

  it('페이지에 상품이 남아 있으면 삭제해도 같은 페이지에 머문다', async () => {
    mockProductServer(makeProducts(12))
    const { page } = renderProductsPage()
    await page.waitForProduct('상품-01')
    await page.goToPage(2)
    await page.waitForProductNames(['상품-11', '상품-12'])

    await page.deleteProduct('상품-11')

    await page.waitForProductNames(['상품-12'])
    expect(page.lastListQuery().get('page')).toBe('1')
  })

  it('첫 페이지의 마지막 상품을 삭제하면 페이지는 그대로 두고 빈 목록 안내를 보여준다', async () => {
    mockProductServer(makeProducts(1))
    const { page } = renderProductsPage()
    await page.waitForProduct('상품-01')

    await page.deleteProduct('상품-01')

    await page.waitForText(PRODUCTS_MESSAGES.EMPTY)
    expect(page.lastListQuery().get('page')).toBe('0')
  })
})

// 개정 알림 테스트가 응답에 넣는 데이터. 화면 문구가 아니라 이 테스트의 입력값이다.
const ELECTRICAL_LAW = '전기용품 안전기준'
const CHILDREN_LAW = '어린이제품 안전 특별법'
const LAW_AMENDMENTS = [
  buildLawAmendment({
    lawAmendmentId: 'law-amendment-1',
    lawName: ELECTRICAL_LAW,
    products: [
      buildRecheckProduct({ productId: 'product-1', productName: '무드등' }),
      buildRecheckProduct({ productId: 'product-2', diagnosesId: 'diagnoses-2', productName: '선풍기' }),
    ],
  }),
  buildLawAmendment({
    lawAmendmentId: 'law-amendment-2',
    lawName: CHILDREN_LAW,
    revisionType: null,
    enforceDate: null,
    products: [buildRecheckProduct({ productId: 'product-3', productName: '물놀이 튜브' })],
  }),
]

describe('진단 결과 - 개정 알림', () => {
  const renderWithAmendments = async () => {
    server.use(
      http.get(LAW_AMENDMENTS_URL, async ({ request }) => {
        await recordRequest(request)
        return successResponse({ lawAmendments: LAW_AMENDMENTS })
      }),
    )
    mockProductServer(makeProducts(1))
    const { page } = renderProductsPage()
    await page.waitForAmendment(ELECTRICAL_LAW)
    return page
  }

  it('개정 목록이 있으면 배너에 개정과 상품을 보여준다', async () => {
    const page = await renderWithAmendments()

    expect(page.hasAmendment(ELECTRICAL_LAW)).toBe(true)
    expect(page.hasAmendment(CHILDREN_LAW)).toBe(true)
    expect(page.recheckProductNames()).toEqual(['무드등', '선풍기', '물놀이 튜브'])
  })

  it('개정 목록이 비어 있으면 배너를 보여주지 않는다', async () => {
    mockProductServer(makeProducts(1))
    const { page } = renderProductsPage()
    await page.waitForProduct('상품-01')
    await page.waitForLawAmendmentsRequest()

    expect(page.hasRevisionBanner()).toBe(false)
  })

  it('개정을 누르면 상품이 보이고, 다시 누르면 접힌다', async () => {
    const page = await renderWithAmendments()

    await page.expandAmendment(CHILDREN_LAW)

    expect(page.isAmendmentExpanded(CHILDREN_LAW)).toBe(true)
    expect(page.visibleRecheckProductNames()).toContain('물놀이 튜브')

    await page.toggleAmendment(CHILDREN_LAW)

    expect(page.isAmendmentExpanded(CHILDREN_LAW)).toBe(false)
    expect(page.visibleRecheckProductNames()).not.toContain('물놀이 튜브')
  })

  it('재진단하기를 누르고 확인하면 재진단을 요청하고 진행 화면으로 이동한다', async () => {
    const page = await renderWithAmendments()

    await page.rediagnose('선풍기')

    expectConfirmed(PRODUCTS_MESSAGES.rediagnoseConfirm('선풍기'))
    expect(await findStubScreen('진행 화면')).toBeInTheDocument()
    expect(requestLog.find('POST', '/api/v1/products/product-2/rediagnosis')).toHaveLength(1)
    expect(getCurrentLocation()).toBe('/judgement/diagnoses-2')
    // 개정 알림 응답의 diagnosesId로 이동하므로 상품을 따로 조회하지 않는다.
    expect(requestLog.find('GET', '/api/v1/products/product-2')).toHaveLength(0)
    expectNotNotified()
  })

  it('확인을 취소하면 재진단 요청을 보내지 않는다', async () => {
    declineConfirm()
    const page = await renderWithAmendments()

    await page.rediagnose('선풍기')

    expect(requestLog.find('POST', '/api/v1/products/product-2/rediagnosis')).toHaveLength(0)
    expect(getCurrentLocation()).toBe('/products')
    expect(page.isRediagnoseEnabled('선풍기')).toBe(true)
  })

  it('재진단을 요청하는 동안에는 그 상품의 버튼만 비활성화한다', async () => {
    const gate = createGate()
    server.use(
      http.post(REDIAGNOSIS_URL, async ({ request }) => {
        await recordRequest(request)
        await gate.promise
        return successResponse(null)
      }),
    )
    const page = await renderWithAmendments()

    await page.rediagnose('선풍기')

    await page.waitUntilRediagnoseDisabled('선풍기')
    expect(page.isRediagnoseEnabled('무드등')).toBe(true)
    expect(page.isRediagnoseEnabled('물놀이 튜브')).toBe(true)

    gate.release()

    expect(await findStubScreen('진행 화면')).toBeInTheDocument()
  })

  it('재진단에 실패하면 서버의 오류 메시지를 안내하고, 화면을 그대로 두며 버튼을 다시 활성화한다', async () => {
    server.use(http.post(REDIAGNOSIS_URL, () => errorResponse(409, { detailMessage: SERVER_MESSAGES.REDIAGNOSE_NOT_ALLOWED })))
    const page = await renderWithAmendments()

    await page.rediagnose('선풍기')

    await waitForNotified(SERVER_MESSAGES.REDIAGNOSE_NOT_ALLOWED)
    expect(getCurrentLocation()).toBe('/products')
    expect(page.isRediagnoseEnabled('선풍기')).toBe(true)
  })
})
