import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http } from 'msw'
import { Route } from 'react-router-dom'

import { PipelineStage, StageStatus } from '@/api/product'
import { ProcessingStatusType, ResultStatus } from '@/api/types'
import JudgementPage from '@/pages/Judgement'
import { buildDiagnosesDetail, buildFailure, buildProductResult, buildQuestion } from '@/test/mocks/fixtures'
import { API_URL } from '@/test/mocks/handlers'
import { recordRequest, requestLog } from '@/test/mocks/requestLog'
import { errorResponse, successResponse } from '@/test/mocks/responses'
import { server } from '@/test/mocks/server'
import { getCurrentLocation, renderWithProviders } from '@/test/utils/renderWithProviders'

const DIAGNOSES_URL = `${API_URL}/api/v1/diagnoses/:diagnosesId`

// 진단 진행 화면을 실제 라우터·QueryClient·MSW(API 모킹) 위에서 사용자처럼 조작한다.
// 이동한 화면은 텍스트로 구분할 수 있는 도착 화면으로 대신한다.
const renderJudgementPage = (route = '/judgement/diagnoses-1') =>
  renderWithProviders(<JudgementPage />, {
    path: '/judgement/:diagnosesId',
    route,
    extraRoutes: (
      <>
        <Route path="/" element={<p>메인 화면</p>} />
        <Route path="/upload" element={<p>업로드 화면</p>} />
        <Route path="/question/:productId" element={<p>질문 화면</p>} />
        <Route path="/result/product/:productId" element={<p>결과 화면</p>} />
        <Route path="/result/diagnoses/:diagnosesId" element={<p>진단서 화면</p>} />
      </>
    ),
  })

const mockDiagnoses = (detail = buildDiagnosesDetail()) => server.use(http.get(DIAGNOSES_URL, () => successResponse(detail)))

const progressProduct = (overrides = {}) =>
  buildProductResult({
    productId: 'p1',
    productName: '진행 상품',
    processingStatus: ProcessingStatusType.InProgress,
    questions: [],
    progresses: [{ stage: PipelineStage.Extraction, toolName: null, stageStatus: StageStatus.Started }],
    ...overrides,
  })

const completedProduct = (overrides = {}) =>
  buildProductResult({
    productId: 'p3',
    productName: '완료 상품',
    processingStatus: ProcessingStatusType.Completed,
    resultStatus: ResultStatus.PurchasingAgentAllowed,
    summary: '구매대행이 가능해요.',
    questions: [],
    ...overrides,
  })

// 상품 카드(li)를 이름으로 찾는다.
const cardOf = (productName: string) => within(screen.getByRole('heading', { name: productName }).closest('li') as HTMLElement)

const reportButton = () => screen.getByRole('button', { name: '진단서 보기 →' })
const waitForList = () => screen.findByRole('list', { name: '진단 중인 상품' })

describe('진단 진행 화면 - 조회', () => {
  it('불러오는 동안 로딩을 보여주고, 불러오면 상품 수와 카드를 보여준다', async () => {
    mockDiagnoses(buildDiagnosesDetail({ products: [progressProduct(), completedProduct()] }))
    renderJudgementPage()

    expect(screen.getByRole('status', { name: '로딩 중' })).toBeInTheDocument()

    await waitForList()
    expect(screen.getByText(/^2개 상품을 동시에 확인하고 있어요/)).toBeInTheDocument()
    expect(screen.queryByRole('status', { name: '로딩 중' })).not.toBeInTheDocument()
    expect(screen.getByRole('heading', { name: '진행 상품' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: '완료 상품' })).toBeInTheDocument()
  })

  it('요청한 diagnosesId의 진단서를 조회한다', async () => {
    renderJudgementPage('/judgement/diagnoses-42')

    await waitForList()

    expect(requestLog.find('GET', '/api/v1/diagnoses/diagnoses-42')).toHaveLength(1)
  })

  it('상품이 하나도 없으면 안내 문구를 보여준다', async () => {
    mockDiagnoses(buildDiagnosesDetail({ products: [] }))
    renderJudgementPage()

    expect(await screen.findByText('확인할 상품이 없어요.')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: '진단서 보기 →' })).not.toBeInTheDocument()
  })

  it('조회에 실패하면 오류 안내와 다시 시도 버튼을 보여주고, 다시 시도하면 불러온다', async () => {
    const user = userEvent.setup()
    server.use(http.get(DIAGNOSES_URL, () => errorResponse(500), { once: true }))
    renderJudgementPage()

    expect(await screen.findByText('진행 상황을 불러오지 못했어요.')).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: '다시 시도' }))

    await waitForList()
    expect(screen.queryByText('진행 상황을 불러오지 못했어요.')).not.toBeInTheDocument()
  })

  it('존재하지 않는 진단서(404)면 오류 화면 없이 안내하고 메인으로 돌려보낸다', async () => {
    server.use(http.get(DIAGNOSES_URL, () => errorResponse(404, { code: 'DIAGNOSIS-404', message: '진단서를 찾을 수 없습니다.' })))
    renderJudgementPage()

    expect(await screen.findByText('메인 화면')).toBeInTheDocument()
    expect(window.alert).toHaveBeenCalledWith('유효하지 않은 진단서 id 입니다.')
    expect(getCurrentLocation()).toBe('/')
    expect(screen.queryByText('진행 상황을 불러오지 못했어요.')).not.toBeInTheDocument()
  })

  it.each(['undefined', 'null'])('diagnosesId가 "%s"로 들어오면 안내하고 요청 없이 업로드 화면으로 돌려보낸다', async (diagnosesId) => {
    renderJudgementPage(`/judgement/${diagnosesId}`)

    expect(await screen.findByText('업로드 화면')).toBeInTheDocument()
    expect(window.alert).toHaveBeenCalledWith('잘못된 접근입니다. 진단서를 업로드한 후 다시 시도해주세요.')
    expect(requestLog.all()).toEqual([])
  })
})

describe('진단 진행 화면 - 상태별 카드', () => {
  beforeEach(() => {
    mockDiagnoses(
      buildDiagnosesDetail({
        products: [
          progressProduct(),
          buildProductResult({
            productId: 'p2',
            productName: '답변 대기 상품',
            processingStatus: ProcessingStatusType.AwaitingInput,
            questions: [buildQuestion({ questionId: 'q1' }), buildQuestion({ questionId: 'q2', questionOrder: 2 })],
          }),
          completedProduct(),
          buildProductResult({
            productId: 'p4',
            productName: '실패 상품',
            processingStatus: ProcessingStatusType.Failed,
            questions: [],
            failure: buildFailure({ errorMessage: '분석 중 오류가 발생했어요.' }),
          }),
        ],
      }),
    )
  })

  it('진행 중인 상품은 진행 단계 막대를 보여주고, 이동 버튼은 없다', async () => {
    renderJudgementPage()
    await waitForList()

    const card = cardOf('진행 상품')
    // "진행 중"은 상태 배지와 진행 막대의 현재 단계(스크린리더용 문구) 두 곳에 나온다.
    expect(card.getAllByText('진행 중')).toHaveLength(2)
    expect(card.getByText('상세페이지에서 상품 정보를 읽고 있어요.')).toBeInTheDocument()

    const steps = card.getByRole('list', { name: '진단 단계' })
    const currentStep = within(steps).getAllByRole('listitem').find((step) => step.getAttribute('aria-current') === 'step')
    expect(currentStep).toHaveTextContent('상세페이지 읽기')
    expect(card.queryByRole('link')).not.toBeInTheDocument()
  })

  it('답변이 필요한 상품은 질문 개수와 안내를 보여주고, 질문 화면으로 가는 버튼을 노출한다', async () => {
    renderJudgementPage()
    await waitForList()

    const card = cardOf('답변 대기 상품')
    expect(card.getByText('답변 필요')).toBeInTheDocument()
    expect(card.getByText('확인이 필요한 질문 2개')).toBeInTheDocument()
    expect(card.getByText('답변하면 처음부터 다시 진단해요. 다른 상품은 기다리지 않고 계속 진행돼요.')).toBeInTheDocument()
    expect(card.getByRole('link', { name: '질문에 답변하기 →' })).toHaveAttribute('href', '/question/p2')
    expect(card.queryByRole('list', { name: '진단 단계' })).not.toBeInTheDocument()
  })

  it('완료된 상품은 요약과 결과 보기 버튼을 노출한다', async () => {
    renderJudgementPage()
    await waitForList()

    const card = cardOf('완료 상품')
    expect(card.getByText('완료')).toBeInTheDocument()
    expect(card.getByText('구매대행이 가능해요.')).toBeInTheDocument()
    expect(card.getByRole('link', { name: '결과 보기' })).toHaveAttribute('href', '/result/product/p3')
  })

  it('실패한 상품은 오류 메시지를 안내하고, 이동 버튼은 없다', async () => {
    renderJudgementPage()
    await waitForList()

    const card = cardOf('실패 상품')
    expect(card.getByText('실패')).toBeInTheDocument()
    // 설명 줄과 하단 안내 박스에 같은 오류 메시지가 보인다.
    expect(card.getAllByText('분석 중 오류가 발생했어요.')).toHaveLength(2)
    expect(card.queryByRole('link')).not.toBeInTheDocument()
  })

  it('질문에 답변하기 버튼을 누르면 그 상품의 질문 화면으로 이동한다', async () => {
    const user = userEvent.setup()
    renderJudgementPage()
    await waitForList()

    await user.click(cardOf('답변 대기 상품').getByRole('link', { name: '질문에 답변하기 →' }))

    expect(await screen.findByText('질문 화면')).toBeInTheDocument()
    expect(getCurrentLocation()).toBe('/question/p2')
  })

  it('결과 보기 버튼을 누르면 그 상품의 결과 화면으로 이동한다', async () => {
    const user = userEvent.setup()
    renderJudgementPage()
    await waitForList()

    await user.click(cardOf('완료 상품').getByRole('link', { name: '결과 보기' }))

    expect(await screen.findByText('결과 화면')).toBeInTheDocument()
    expect(getCurrentLocation()).toBe('/result/product/p3')
  })
})

describe('진단 진행 화면 - 폴링과 진단서 이동', () => {
  // 첫 응답은 진행 중(30ms 뒤 다시 조회), 두 번째 응답부터는 모두 완료(폴링 종료)다.
  const mockProgressThenDone = () => {
    let calls = 0
    server.use(
      http.get(DIAGNOSES_URL, async ({ request }) => {
        await recordRequest(request)
        calls += 1
        return successResponse(
          calls === 1
            ? buildDiagnosesDetail({ processingStatus: ProcessingStatusType.InProgress, pollIntervalMs: 30, products: [progressProduct()] })
            : buildDiagnosesDetail({ processingStatus: ProcessingStatusType.Completed, pollIntervalMs: null, products: [completedProduct({ productName: '진행 상품' })] }),
        )
      }),
    )
  }

  it('진단이 끝나기 전에는 진단서 보기가 비활성이고, 눌러도 이동하지 않는다', async () => {
    const user = userEvent.setup()
    mockDiagnoses(buildDiagnosesDetail({ processingStatus: ProcessingStatusType.InProgress, pollIntervalMs: null, products: [progressProduct()] }))
    renderJudgementPage()
    await waitForList()

    expect(reportButton()).toHaveAttribute('aria-disabled', 'true')
    expect(screen.getByText('진행 중인 상품이 끝나면 진단서를 볼 수 있어요.')).toBeInTheDocument()

    await user.click(reportButton())

    expect(getCurrentLocation()).toBe('/judgement/diagnoses-1')
  })

  it('폴링 응답으로 진단이 끝나면 카드가 갱신되고 진단서 보기가 활성화되어 진단서로 이동한다', async () => {
    const user = userEvent.setup()
    mockProgressThenDone()
    renderJudgementPage()
    await waitForList()
    expect(reportButton()).toHaveAttribute('aria-disabled', 'true')

    expect(await screen.findByText('페이지를 나가도 진단은 계속돼요. 마이페이지에서 다시 볼 수 있어요.')).toBeInTheDocument()
    expect(cardOf('진행 상품').getByRole('link', { name: '결과 보기' })).toBeInTheDocument()
    expect(reportButton()).not.toHaveAttribute('aria-disabled')

    await user.click(reportButton())

    expect(await screen.findByText('진단서 화면')).toBeInTheDocument()
    expect(getCurrentLocation()).toBe('/result/diagnoses/diagnoses-1')
  })

  it('진단이 끝나면 폴링을 멈춘다', async () => {
    mockProgressThenDone()
    renderJudgementPage()
    await screen.findByText('페이지를 나가도 진단은 계속돼요. 마이페이지에서 다시 볼 수 있어요.')

    // 폴링 간격(30ms)보다 충분히 오래 기다려도 더 이상 조회하지 않는다.
    await new Promise((resolve) => setTimeout(resolve, 200))

    expect(requestLog.find('GET', '/api/v1/diagnoses/diagnoses-1')).toHaveLength(2)
  })

  it('상태가 바뀐 상품을 스크린리더용 안내로 알린다', async () => {
    mockProgressThenDone()
    renderJudgementPage()
    await waitForList()

    await waitFor(() => expect(screen.getByRole('status')).toHaveTextContent('진행 상품 진단이 끝났어요'))
    expect(screen.getByRole('status')).toHaveTextContent('모든 진단이 끝났어요. 진단서를 볼 수 있어요')
  })

  it('처음 응답을 받았을 때는 상태 변화로 알리지 않는다', async () => {
    mockDiagnoses(buildDiagnosesDetail({ processingStatus: ProcessingStatusType.Completed, products: [completedProduct()] }))
    renderJudgementPage()
    await waitForList()

    expect(screen.getByRole('status')).toBeEmptyDOMElement()
  })

  it('처음부터 진단이 모두 끝난 진단서는 바로 진단서로 이동할 수 있다', async () => {
    const user = userEvent.setup()
    mockDiagnoses(buildDiagnosesDetail({ processingStatus: ProcessingStatusType.Completed, products: [completedProduct()] }))
    renderJudgementPage()
    await waitForList()

    expect(reportButton()).not.toHaveAttribute('aria-disabled')

    await user.click(reportButton())

    expect(await screen.findByText('진단서 화면')).toBeInTheDocument()
  })

  it('진단이 실패로 끝난 진단서도 진단서로 이동할 수 있다', async () => {
    const user = userEvent.setup()
    mockDiagnoses(
      buildDiagnosesDetail({
        processingStatus: ProcessingStatusType.Failed,
        products: [progressProduct({ processingStatus: ProcessingStatusType.Failed, failure: buildFailure() })],
      }),
    )
    renderJudgementPage()
    await waitForList()

    await user.click(reportButton())

    expect(await screen.findByText('진단서 화면')).toBeInTheDocument()
  })
})
