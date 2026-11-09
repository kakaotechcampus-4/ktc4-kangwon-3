import { screen } from '@testing-library/react'
import { http } from 'msw'
import { type InitialEntry, Route } from 'react-router-dom'

import ResultPage from '@/pages/Result'
import { RESULT_MESSAGES } from '@/test/constants/messages'
import { resultPage } from '@/test/drivers/resultPage'
import { buildProductResult } from '@/test/mocks/fixtures'
import { API_URL } from '@/test/mocks/handlers'
import { errorResponse, successResponse } from '@/test/mocks/responses'
import { server } from '@/test/mocks/server'
import { getCurrentLocation, renderWithProviders } from '@/test/utils/renderWithProviders'

const PRODUCT_URL = `${API_URL}/api/v1/products/:productId`

// 결과 화면의 이전으로 버튼을 실제 라우터·QueryClient·MSW(API 모킹) 위에서 사용자처럼 조작한다.
// 화면 조작·조회는 드라이버(resultPage)를 거친다. 이동한 화면은 텍스트로 구분할 수 있는 도착 화면으로 대신한다.
// route에 객체를 주면 이전 화면이 넘긴 state를 흉내 낼 수 있고, history는 그 앞에 쌓인 이전 항목이다.
const renderResultPage = (route: InitialEntry, path: string, history: InitialEntry[] = []) => {
  renderWithProviders(<ResultPage />, {
    path,
    route,
    history,
    extraRoutes: (
      <>
        <Route path="/mypage" element={<p>마이페이지 화면</p>} />
        <Route path="/judgement/:diagnosesId" element={<p>진단 진행 화면</p>} />
        <Route path="/" element={<p>메인 화면</p>} />
      </>
    ),
  })
  return resultPage()
}

const PRODUCT_PATH = '/result/product/:productId'
const DIAGNOSES_PATH = '/result/diagnoses/:diagnosesId'

// 이전 화면이 이동하면서 넘기는 state. 이 값이 있으면 바로 이전 히스토리 항목이 그 화면이다.
const cameFrom = (pathname: string, from: string) => ({ pathname, state: { from } })

describe('결과 화면 이전으로 버튼 - 상품 단건', () => {
  const productRoute = '/result/product/product-1'

  it('이전 경로(state)가 있으면 히스토리를 되돌려 이전 화면으로 돌아간다', async () => {
    const page = renderResultPage(cameFrom(productRoute, '/mypage'), PRODUCT_PATH, ['/mypage'])
    await page.waitUntilLoaded()

    await page.clickBack()

    expect(await screen.findByText('마이페이지 화면')).toBeInTheDocument()
    expect(getCurrentLocation()).toBe('/mypage')
  })

  it('이전 경로가 없으면 히스토리와 상관없이 상품의 진단 진행 화면으로 이동한다', async () => {
    server.use(http.get(PRODUCT_URL, () => successResponse(buildProductResult({ diagnosesId: 'diagnoses-7' }))))
    const page = renderResultPage(productRoute, PRODUCT_PATH, ['/mypage'])
    await page.waitForBackButton()

    await page.clickBack()

    expect(await screen.findByText('진단 진행 화면')).toBeInTheDocument()
    expect(getCurrentLocation()).toBe('/judgement/diagnoses-7')
  })

  it('이전 경로가 없으면 상품을 불러오기 전에는 돌아갈 곳을 몰라 버튼을 보여주지 않고, 불러온 뒤에 보여준다', async () => {
    const page = renderResultPage(productRoute, PRODUCT_PATH)

    expect(page.hasBackButton()).toBe(false)

    await page.waitForBackButton()
  })

  it('이전 경로가 없는데 조회에 실패하면 버튼을 보여주지 않는다', async () => {
    server.use(http.get(PRODUCT_URL, () => errorResponse(500)))
    const page = renderResultPage(productRoute, PRODUCT_PATH)

    await page.waitForText(RESULT_MESSAGES.LOAD_FAILED)

    expect(page.hasBackButton()).toBe(false)
  })

  it('이전 경로가 있으면 상품을 불러오기 전에도 버튼을 보여준다', async () => {
    const page = renderResultPage(cameFrom(productRoute, '/mypage'), PRODUCT_PATH, ['/mypage'])

    expect(page.hasBackButton()).toBe(true)

    await page.waitUntilLoaded()
  })
})

describe('결과 화면 이전으로 버튼 - 진단서', () => {
  const diagnosesRoute = '/result/diagnoses/diagnoses-7'

  it('이전 경로가 없어도 URL의 진단서 id를 알아서, 불러오기 전부터 버튼을 보여주고 진단 진행 화면으로 이동한다', async () => {
    const page = renderResultPage(diagnosesRoute, DIAGNOSES_PATH, ['/mypage'])

    expect(page.hasBackButton()).toBe(true)

    await page.clickBack()

    expect(await screen.findByText('진단 진행 화면')).toBeInTheDocument()
    expect(getCurrentLocation()).toBe('/judgement/diagnoses-7')
  })

  it('이전 경로(state)가 있으면 히스토리를 되돌려 이전 화면으로 돌아간다', async () => {
    const page = renderResultPage(cameFrom(diagnosesRoute, '/mypage'), DIAGNOSES_PATH, ['/mypage'])
    await page.waitUntilLoaded()

    await page.clickBack()

    expect(await screen.findByText('마이페이지 화면')).toBeInTheDocument()
    expect(getCurrentLocation()).toBe('/mypage')
  })
})
