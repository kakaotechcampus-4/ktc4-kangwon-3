import { http } from 'msw'
import { Route } from 'react-router-dom'

import { ResultStatus } from '@/api/types/common'
import ProductsPage from '@/pages/Products'
import ResultPage from '@/pages/Result'
import { productsPage } from '@/test/drivers/productsPage'
import { resultPage } from '@/test/drivers/resultPage'
import { buildMyProduct } from '@/test/mocks/fixtures'
import { API_URL } from '@/test/mocks/handlers'
import { successResponse } from '@/test/mocks/responses'
import { server } from '@/test/mocks/server'
import { getCurrentLocation, renderRoutes } from '@/test/utils/renderWithProviders'

// 테스트가 응답에 넣는 데이터. 화면 문구가 아니라 이 테스트의 입력값이다.
const PRODUCT_NAME = buildMyProduct().productName

// 이전 화면의 링크가 넘긴 state를 도착 화면의 이전으로 버튼이 쓰는지, 실제 화면 둘을 함께 렌더해서 사용자 흐름으로 확인한다.
// 진단 진행 화면을 스텁으로 둔 이유: state가 아니라 진단 진행 화면으로 가는 경로(폴백)를 탔다면 진단 결과 페이지가 아니라 이 화면이 보여 테스트가 실패한다.
const renderApp = (route: string) =>
  renderRoutes(
    <>
      <Route path="/products" element={<ProductsPage />} />
      <Route path="/result/product/:productId" element={<ResultPage />} />
      <Route path="/judgement/:diagnosesId" element={<p>진단 진행 화면</p>} />
    </>,
    { route },
  )

describe('이전으로 버튼 - 화면 이동 흐름', () => {
  it('진단 결과에서 상품을 눌러 결과 화면으로 간 뒤 이전으로를 누르면 진단 결과로 돌아온다', async () => {
    renderApp('/products')
    const products = productsPage()
    const result = resultPage()
    await products.waitForProduct(PRODUCT_NAME)

    await products.openProduct(PRODUCT_NAME)
    await result.waitUntilLoaded()
    expect(getCurrentLocation()).toBe('/result/product/product-1')

    await result.clickBack()

    await products.waitForProduct(PRODUCT_NAME)
    expect(getCurrentLocation()).toBe('/products')
  })

  it('진단 결과에서 정한 조건(필터·검색어·정렬·페이지)은 결과 화면에 다녀온 뒤에도 같은 주소와 화면으로 돌아온다', async () => {
    // 조건과 상관없이 2페이지 분량이 있는 것처럼 응답한다. 이 테스트는 조건 복원만 본다.
    server.use(
      http.get(`${API_URL}/api/v1/products`, ({ request }) => {
        const page = Number(new URL(request.url).searchParams.get('page') ?? 0)
        return successResponse({
          products: [buildMyProduct()],
          pageInfo: { page, size: 10, totalElements: 11, totalPages: 2, hasNext: page + 1 < 2 },
        })
      }),
    )
    renderApp('/products')
    const products = productsPage()
    const result = resultPage()
    await products.waitForProduct(PRODUCT_NAME)
    await products.selectFilter(ResultStatus.RecheckRequired)
    await products.search('abc')
    await products.sortBy('오래된순')
    await products.goToPage(2)
    await products.waitForProduct(PRODUCT_NAME)
    const locationBefore = getCurrentLocation()
    expect(locationBefore).toContain('page=2')

    await products.openProduct(PRODUCT_NAME)
    await result.waitUntilLoaded()
    await result.clickBack()

    await products.waitForProduct(PRODUCT_NAME)
    expect(getCurrentLocation()).toBe(locationBefore)
    expect(products.isFilterSelected(ResultStatus.RecheckRequired)).toBe(true)
    expect(products.isSortSelected('오래된순')).toBe(true)
    expect(products.searchValue()).toBe('abc')
  })
})
