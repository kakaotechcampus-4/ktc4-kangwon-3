import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http } from 'msw'
import { Route } from 'react-router-dom'

import { ProcessingStatusType, ResultStatus } from '@/api/types'
import ResultPage from '@/pages/Result'
import { buildDiagnosesDetail, buildFailure, buildProductResult } from '@/test/mocks/fixtures'
import { API_URL } from '@/test/mocks/handlers'
import { recordRequest, requestLog } from '@/test/mocks/requestLog'
import { errorResponse, successResponse } from '@/test/mocks/responses'
import { server } from '@/test/mocks/server'
import { getCurrentLocation, renderWithProviders } from '@/test/utils/renderWithProviders'

const PRODUCT_URL = `${API_URL}/api/v1/products/:productId`
const RETRY_URL = `${API_URL}/api/v1/products/:productId/retry`
const DIAGNOSES_URL = `${API_URL}/api/v1/diagnoses/:diagnosesId`

// 결과 화면의 재진단(다시 시도) 흐름을 실제 라우터·QueryClient·MSW(API 모킹) 위에서 사용자처럼 조작한다.
const renderResultPage = (route = '/result/product/product-1', path = '/result/product/:productId') =>
  renderWithProviders(<ResultPage />, {
    path,
    route,
    extraRoutes: (
      <>
        <Route path="/judgement/:diagnosesId" element={<p>진단 진행 화면</p>} />
        <Route path="/" element={<p>메인 화면</p>} />
      </>
    ),
  })

// 조회되는 상품을 다시 진단할 수 있는 실패 상태로 바꾼다. (resultStatus가 없고, 실패 정보의 retryable이 true)
const failedProduct = (overrides = {}) =>
  buildProductResult({
    productId: 'product-1',
    diagnosesId: 'diagnoses-9',
    productName: '실패한 상품',
    processingStatus: ProcessingStatusType.Failed,
    resultStatus: null,
    questions: [],
    failure: buildFailure({ errorMessage: '일시적인 오류가 발생했어요.' }),
    ...overrides,
  })

const mockProduct = (product = failedProduct()) => server.use(http.get(PRODUCT_URL, () => successResponse(product)))

// 응답을 풀어 줄 때까지 붙잡아 두는 문. "요청 중" 상태를 확인할 때 쓴다.
const createGate = () => {
  let release!: () => void
  const promise = new Promise<void>((resolve) => {
    release = resolve
  })
  return { promise, release }
}

const retryButton = () => screen.getByRole('button', { name: '다시 시도 →' })
const findRetryButton = () => screen.findByRole('button', { name: '다시 시도 →' })
const retryRequests = (productId = 'product-1') => requestLog.find('POST', `/api/v1/products/${productId}/retry`)

describe('결과 화면 재진단 - 버튼 노출', () => {
  it('다시 시도하면 성공할 수 있는 실패면 실패 안내와 다시 시도 버튼을 보여준다', async () => {
    mockProduct()
    renderResultPage()

    expect(await findRetryButton()).toBeInTheDocument()
    expect(screen.getByText(/진단에 실패했어요\. 다시 시도해 주세요\./)).toBeInTheDocument()
    expect(screen.getByText(/일시적인 오류가 발생했어요\./)).toBeInTheDocument()
  })

  it('다시 시도해도 같은 결과인 실패(retryable=false)에는 버튼 없이 완료할 수 없다고 안내한다', async () => {
    mockProduct(failedProduct({ failure: buildFailure({ retryable: false, errorMessage: '지원하지 않는 상품입니다.' }) }))
    renderResultPage()

    expect(await screen.findByText(/진단을 완료할 수 없어요\./)).toBeInTheDocument()
    expect(screen.getByText(/지원하지 않는 상품입니다\./)).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: '다시 시도 →' })).not.toBeInTheDocument()
  })

  it('실패 정보가 없는 실패는 버튼 없이 실패했다고만 안내한다', async () => {
    mockProduct(failedProduct({ failure: null }))
    renderResultPage()

    expect(await screen.findByText('진단에 실패했어요.')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: '다시 시도 →' })).not.toBeInTheDocument()
  })

  it('진단이 끝난 상품에는 다시 시도 버튼이 없다', async () => {
    mockProduct(
      buildProductResult({
        productId: 'product-1',
        processingStatus: ProcessingStatusType.Completed,
        resultStatus: ResultStatus.PurchasingAgentAllowed,
        summary: '구매대행이 가능해요.',
        questions: [],
      }),
    )
    renderResultPage()

    expect(await screen.findByText('구매대행이 가능해요.')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: '다시 시도 →' })).not.toBeInTheDocument()
  })

  it('진행 중인 상품에는 다시 시도 대신 진행 상황 확인 버튼이 있다', async () => {
    mockProduct(buildProductResult({ productId: 'product-1', processingStatus: ProcessingStatusType.InProgress, questions: [] }))
    renderResultPage()

    expect(await screen.findByRole('link', { name: '진행 상황 확인 →' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: '다시 시도 →' })).not.toBeInTheDocument()
  })
})

describe('결과 화면 재진단 - 성공', () => {
  it('다시 시도를 누르면 그 상품의 재진단을 요청하고, 진단 진행 화면으로 이동한다', async () => {
    const user = userEvent.setup()
    mockProduct()
    renderResultPage()
    await findRetryButton()

    await user.click(retryButton())

    expect(await screen.findByText('진단 진행 화면')).toBeInTheDocument()
    expect(getCurrentLocation()).toBe('/judgement/diagnoses-9')
    expect(retryRequests()).toHaveLength(1)
    expect(window.alert).not.toHaveBeenCalled()
  })

  it('진단서 결과 화면에서 상품을 바꿔 고른 뒤에도, 고른 상품의 재진단을 요청한다', async () => {
    const user = userEvent.setup()
    server.use(
      http.get(DIAGNOSES_URL, () =>
        successResponse(
          buildDiagnosesDetail({
            diagnosesId: 'diagnoses-9',
            products: [
              buildProductResult({
                productId: 'product-1',
                diagnosesId: 'diagnoses-9',
                productName: '완료된 상품',
                processingStatus: ProcessingStatusType.Completed,
                resultStatus: ResultStatus.PurchasingAgentAllowed,
                questions: [],
              }),
              failedProduct({ productId: 'product-2', productName: '실패한 상품' }),
            ],
          }),
        ),
      ),
    )
    renderResultPage('/result/diagnoses/diagnoses-9', '/result/diagnoses/:diagnosesId')
    await screen.findByRole('tab', { name: '실패한 상품' })
    expect(screen.queryByRole('button', { name: '다시 시도 →' })).not.toBeInTheDocument()

    await user.click(screen.getByRole('tab', { name: '실패한 상품' }))
    await user.click(await findRetryButton())

    expect(await screen.findByText('진단 진행 화면')).toBeInTheDocument()
    expect(retryRequests('product-2')).toHaveLength(1)
    expect(retryRequests('product-1')).toHaveLength(0)
  })
})

describe('결과 화면 재진단 - 실패', () => {
  it('요청이 실패하면 서버의 오류 메시지를 안내하고, 화면에 머물며 버튼을 다시 활성화한다', async () => {
    const user = userEvent.setup()
    mockProduct()
    server.use(http.post(RETRY_URL, () => errorResponse(400, { detailMessage: '이미 재진단을 요청한 상품입니다.' })))
    renderResultPage()
    await findRetryButton()

    await user.click(retryButton())

    await waitFor(() => expect(window.alert).toHaveBeenCalledWith('이미 재진단을 요청한 상품입니다.'))
    expect(getCurrentLocation()).toBe('/result/product/product-1')
    expect(retryButton()).toBeEnabled()
  })

  it('실패한 뒤 다시 누르면 재진단을 요청해서 이동한다', async () => {
    const user = userEvent.setup()
    mockProduct()
    server.use(
      http.post(
        RETRY_URL,
        async ({ request }) => {
          await recordRequest(request)
          return errorResponse(500)
        },
        { once: true },
      ),
    )
    renderResultPage()
    await findRetryButton()

    await user.click(retryButton())
    await waitFor(() => expect(window.alert).toHaveBeenCalledTimes(1))

    await user.click(retryButton())

    expect(await screen.findByText('진단 진행 화면')).toBeInTheDocument()
    expect(retryRequests()).toHaveLength(2)
  })
})

describe('결과 화면 재진단 - 중복 클릭 방지', () => {
  it('요청하는 동안에는 버튼을 비활성화해서 여러 번 눌러도 요청은 한 번만 보낸다', async () => {
    const user = userEvent.setup()
    const gate = createGate()
    mockProduct()
    server.use(
      http.post(RETRY_URL, async ({ request }) => {
        await recordRequest(request)
        await gate.promise
        return successResponse(null)
      }),
    )
    renderResultPage()
    await findRetryButton()

    await user.click(retryButton())
    await waitFor(() => expect(retryButton()).toBeDisabled())

    await user.click(retryButton())
    await user.click(retryButton())

    expect(retryRequests()).toHaveLength(1)
    expect(getCurrentLocation()).toBe('/result/product/product-1')

    gate.release()

    expect(await screen.findByText('진단 진행 화면')).toBeInTheDocument()
    expect(retryRequests()).toHaveLength(1)
  })
})
