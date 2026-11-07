import { screen } from '@testing-library/react'
import { http } from 'msw'
import { Route } from 'react-router-dom'

import { ProcessingStatusType, ResultStatus } from '@/api/types/common'
import { PipelineStage, StageStatus } from '@/api/types/product'
import JudgementPage from '@/pages/Judgement'
import { COMMON_MESSAGES, JUDGEMENT_MESSAGES } from '@/test/constants/messages'
import { judgementPage } from '@/test/drivers/judgementPage'
import { buildDiagnosesDetail, buildFailure, buildProductResult, buildQuestion } from '@/test/mocks/fixtures'
import { API_URL } from '@/test/mocks/handlers'
import { recordRequest, requestLog } from '@/test/mocks/requestLog'
import { errorResponse, successResponse } from '@/test/mocks/responses'
import { server } from '@/test/mocks/server'
import { expectNotified } from '@/test/utils/notifications'
import { getCurrentLocation, renderWithProviders } from '@/test/utils/renderWithProviders'

const DIAGNOSES_URL = `${API_URL}/api/v1/diagnoses/:diagnosesId`

const { STATUS_LABELS } = JUDGEMENT_MESSAGES

// 테스트가 응답에 넣는 데이터. 화면 문구가 아니라 이 테스트의 입력값이다.
const PROGRESS_NAME = '진행 상품'
const AWAITING_NAME = '답변 대기 상품'
const COMPLETED_NAME = '완료 상품'
const FAILED_NAME = '실패 상품'
const COMPLETED_SUMMARY = '구매대행이 가능해요.'
const FAILURE_MESSAGE = '분석 중 오류가 발생했어요.'

// 진단 진행 화면을 실제 라우터·QueryClient·MSW(API 모킹) 위에서 사용자처럼 조작한다.
// 화면 조작·조회는 드라이버(judgementPage)를 거친다. 이동한 화면은 텍스트로 구분할 수 있는 도착 화면으로 대신한다.
const renderJudgementPage = (route = '/judgement/diagnoses-1') => {
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
  return judgementPage()
}

// 이동한 도착 화면(이 파일이 만든 스텁)이 보일 때까지 기다린다.
const findStubScreen = (text: string) => screen.findByText(text)

const mockDiagnoses = (detail = buildDiagnosesDetail()) => server.use(http.get(DIAGNOSES_URL, () => successResponse(detail)))

const progressProduct = (overrides = {}) =>
  buildProductResult({
    productId: 'p1',
    productName: PROGRESS_NAME,
    processingStatus: ProcessingStatusType.InProgress,
    questions: [],
    progresses: [{ stage: PipelineStage.Extraction, toolName: null, stageStatus: StageStatus.Started }],
    ...overrides,
  })

const completedProduct = (overrides = {}) =>
  buildProductResult({
    productId: 'p3',
    productName: COMPLETED_NAME,
    processingStatus: ProcessingStatusType.Completed,
    resultStatus: ResultStatus.PurchasingAgentAllowed,
    summary: COMPLETED_SUMMARY,
    questions: [],
    ...overrides,
  })

describe('진단 진행 화면 - 조회', () => {
  it('불러오는 동안 로딩을 보여주고, 불러오면 상품 수와 카드를 보여준다', async () => {
    mockDiagnoses(buildDiagnosesDetail({ products: [progressProduct(), completedProduct()] }))
    const page = renderJudgementPage()

    expect(page.isLoading()).toBe(true)

    await page.waitUntilLoaded()
    expect(page.hasProductCountIntro(2)).toBe(true)
    expect(page.isLoading()).toBe(false)
    expect(page.productNames()).toEqual([PROGRESS_NAME, COMPLETED_NAME])
  })

  it('요청한 diagnosesId의 진단서를 조회한다', async () => {
    const page = renderJudgementPage('/judgement/diagnoses-42')

    await page.waitUntilLoaded()

    expect(requestLog.find('GET', '/api/v1/diagnoses/diagnoses-42')).toHaveLength(1)
  })

  it('상품이 하나도 없으면 안내 문구를 보여준다', async () => {
    mockDiagnoses(buildDiagnosesDetail({ products: [] }))
    const page = renderJudgementPage()

    await page.waitForMessage(JUDGEMENT_MESSAGES.EMPTY)
    expect(page.hasReportButton()).toBe(false)
  })

  it('조회에 실패하면 오류 안내와 다시 시도 버튼을 보여주고, 다시 시도하면 불러온다', async () => {
    server.use(http.get(DIAGNOSES_URL, () => errorResponse(500), { once: true }))
    const page = renderJudgementPage()

    await page.waitForMessage(JUDGEMENT_MESSAGES.LOAD_FAILED)

    await page.clickRetry()

    await page.waitUntilLoaded()
    expect(page.hasMessage(JUDGEMENT_MESSAGES.LOAD_FAILED)).toBe(false)
  })

  it('존재하지 않는 진단서(404)면 오류 화면 없이 안내하고 메인으로 돌려보낸다', async () => {
    server.use(http.get(DIAGNOSES_URL, () => errorResponse(404, { code: 'DIAGNOSIS-404', message: '진단서를 찾을 수 없습니다.' })))
    const page = renderJudgementPage()

    expect(await findStubScreen('메인 화면')).toBeInTheDocument()
    expectNotified(JUDGEMENT_MESSAGES.NOT_FOUND)
    expect(getCurrentLocation()).toBe('/')
    expect(page.hasMessage(JUDGEMENT_MESSAGES.LOAD_FAILED)).toBe(false)
  })

  it.each(['undefined', 'null'])('diagnosesId가 "%s"로 들어오면 안내하고 요청 없이 업로드 화면으로 돌려보낸다', async (diagnosesId) => {
    renderJudgementPage(`/judgement/${diagnosesId}`)

    expect(await findStubScreen('업로드 화면')).toBeInTheDocument()
    expectNotified(COMMON_MESSAGES.INVALID_ACCESS_TO_UPLOAD)
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
            productName: AWAITING_NAME,
            processingStatus: ProcessingStatusType.AwaitingInput,
            questions: [buildQuestion({ questionId: 'q1' }), buildQuestion({ questionId: 'q2', questionOrder: 2 })],
          }),
          completedProduct(),
          buildProductResult({
            productId: 'p4',
            productName: FAILED_NAME,
            processingStatus: ProcessingStatusType.Failed,
            questions: [],
            failure: buildFailure({ errorMessage: FAILURE_MESSAGE }),
          }),
        ],
      }),
    )
  })

  it('진행 중인 상품은 진행 단계 막대를 보여주고, 이동 버튼은 없다', async () => {
    const page = renderJudgementPage()
    await page.waitUntilLoaded()

    const card = page.card(PROGRESS_NAME)
    expect(card.hasStatusLabel(STATUS_LABELS[ProcessingStatusType.InProgress])).toBe(true)
    expect(card.hasText(JUDGEMENT_MESSAGES.STAGE_EXTRACTION)).toBe(true)
    expect(card.hasProgressSteps()).toBe(true)
    expect(card.currentStep()).toContain(JUDGEMENT_MESSAGES.PROGRESS_STEP_EXTRACTION)
    expect(card.hasAnyLink()).toBe(false)
  })

  it('답변이 필요한 상품은 질문 개수와 안내를 보여주고, 질문 화면으로 가는 버튼을 노출한다', async () => {
    const page = renderJudgementPage()
    await page.waitUntilLoaded()

    const card = page.card(AWAITING_NAME)
    expect(card.hasStatusLabel(STATUS_LABELS[ProcessingStatusType.AwaitingInput])).toBe(true)
    expect(card.hasText(JUDGEMENT_MESSAGES.awaitingInputQuestions(2))).toBe(true)
    expect(card.hasText(JUDGEMENT_MESSAGES.AWAITING_INPUT_NOTICE)).toBe(true)
    expect(card.answerLinkHref()).toBe('/question/p2')
    expect(card.hasProgressSteps()).toBe(false)
  })

  it('완료된 상품은 요약과 결과 보기 버튼을 노출한다', async () => {
    const page = renderJudgementPage()
    await page.waitUntilLoaded()

    const card = page.card(COMPLETED_NAME)
    expect(card.hasStatusLabel(STATUS_LABELS[ProcessingStatusType.Completed])).toBe(true)
    expect(card.hasText(COMPLETED_SUMMARY)).toBe(true)
    expect(card.resultLinkHref()).toBe('/result/product/p3')
  })

  it('실패한 상품은 오류 메시지를 안내하고, 이동 버튼은 없다', async () => {
    const page = renderJudgementPage()
    await page.waitUntilLoaded()

    const card = page.card(FAILED_NAME)
    expect(card.hasStatusLabel(STATUS_LABELS[ProcessingStatusType.Failed])).toBe(true)
    // 설명 줄과 하단 안내 박스에 같은 오류 메시지가 보인다.
    expect(card.textCount(FAILURE_MESSAGE)).toBe(2)
    expect(card.hasAnyLink()).toBe(false)
  })

  it('질문에 답변하기 버튼을 누르면 그 상품의 질문 화면으로 이동한다', async () => {
    const page = renderJudgementPage()
    await page.waitUntilLoaded()

    await page.card(AWAITING_NAME).goToQuestion()

    expect(await findStubScreen('질문 화면')).toBeInTheDocument()
    expect(getCurrentLocation()).toBe('/question/p2')
  })

  it('결과 보기 버튼을 누르면 그 상품의 결과 화면으로 이동한다', async () => {
    const page = renderJudgementPage()
    await page.waitUntilLoaded()

    await page.card(COMPLETED_NAME).goToResult()

    expect(await findStubScreen('결과 화면')).toBeInTheDocument()
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
            : buildDiagnosesDetail({ processingStatus: ProcessingStatusType.Completed, pollIntervalMs: null, products: [completedProduct({ productName: PROGRESS_NAME })] }),
        )
      }),
    )
  }

  it('진단이 끝나기 전에는 진단서 보기가 비활성이고, 눌러도 이동하지 않는다', async () => {
    mockDiagnoses(buildDiagnosesDetail({ processingStatus: ProcessingStatusType.InProgress, pollIntervalMs: null, products: [progressProduct()] }))
    const page = renderJudgementPage()
    await page.waitUntilLoaded()

    expect(page.isReportEnabled()).toBe(false)
    expect(page.hasMessage(JUDGEMENT_MESSAGES.REPORT_HINT_RUNNING)).toBe(true)

    await page.openReport()

    expect(getCurrentLocation()).toBe('/judgement/diagnoses-1')
  })

  it('폴링 응답으로 진단이 끝나면 카드가 갱신되고 진단서 보기가 활성화되어 진단서로 이동한다', async () => {
    mockProgressThenDone()
    const page = renderJudgementPage()
    await page.waitUntilLoaded()
    expect(page.isReportEnabled()).toBe(false)

    await page.waitForMessage(JUDGEMENT_MESSAGES.REPORT_HINT_DONE)
    expect(page.card(PROGRESS_NAME).resultLinkHref()).not.toBeNull()
    expect(page.isReportEnabled()).toBe(true)

    await page.openReport()

    expect(await findStubScreen('진단서 화면')).toBeInTheDocument()
    expect(getCurrentLocation()).toBe('/result/diagnoses/diagnoses-1')
  })

  it('진단이 끝나면 폴링을 멈춘다', async () => {
    mockProgressThenDone()
    const page = renderJudgementPage()
    await page.waitForMessage(JUDGEMENT_MESSAGES.REPORT_HINT_DONE)

    // 폴링 간격(30ms)보다 충분히 오래 기다려도 더 이상 조회하지 않는다.
    await new Promise((resolve) => setTimeout(resolve, 200))

    expect(requestLog.find('GET', '/api/v1/diagnoses/diagnoses-1')).toHaveLength(2)
  })

  it('상태가 바뀐 상품을 스크린리더용 안내로 알린다', async () => {
    mockProgressThenDone()
    const page = renderJudgementPage()
    await page.waitUntilLoaded()

    await page.waitForAnnouncement(JUDGEMENT_MESSAGES.announceCompleted(PROGRESS_NAME))
    expect(page.announcement()).toContain(JUDGEMENT_MESSAGES.ANNOUNCE_ALL_DONE)
  })

  it('처음 응답을 받았을 때는 상태 변화로 알리지 않는다', async () => {
    mockDiagnoses(buildDiagnosesDetail({ processingStatus: ProcessingStatusType.Completed, products: [completedProduct()] }))
    const page = renderJudgementPage()
    await page.waitUntilLoaded()

    expect(page.announcement()).toBe('')
  })

  it('처음부터 진단이 모두 끝난 진단서는 바로 진단서로 이동할 수 있다', async () => {
    mockDiagnoses(buildDiagnosesDetail({ processingStatus: ProcessingStatusType.Completed, products: [completedProduct()] }))
    const page = renderJudgementPage()
    await page.waitUntilLoaded()

    expect(page.isReportEnabled()).toBe(true)

    await page.openReport()

    expect(await findStubScreen('진단서 화면')).toBeInTheDocument()
  })

  it('진단이 실패로 끝난 진단서도 진단서로 이동할 수 있다', async () => {
    mockDiagnoses(
      buildDiagnosesDetail({
        processingStatus: ProcessingStatusType.Failed,
        products: [progressProduct({ processingStatus: ProcessingStatusType.Failed, failure: buildFailure() })],
      }),
    )
    const page = renderJudgementPage()
    await page.waitUntilLoaded()

    await page.openReport()

    expect(await findStubScreen('진단서 화면')).toBeInTheDocument()
  })
})
