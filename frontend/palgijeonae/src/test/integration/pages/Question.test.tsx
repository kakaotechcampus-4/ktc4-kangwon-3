import { cleanup, screen } from '@testing-library/react'
import { http } from 'msw'
import { type InitialEntry, Route } from 'react-router-dom'

import { ProcessingStatusType } from '@/api/types/common'
import type { ProductResult } from '@/api/types/product'
import QuestionPage from '@/pages/Question'
import { loadAnswerDraft, saveAnswerDraft } from '@/pages/Question/utils/answerDraft'
import { COMMON_MESSAGES, QUESTION_MESSAGES, SERVER_MESSAGES } from '@/test/constants/messages'
import { questionPage } from '@/test/drivers/questionPage'
import { buildProductResult, buildQuestion } from '@/test/mocks/fixtures'
import { API_URL } from '@/test/mocks/handlers'
import { recordRequest, requestLog } from '@/test/mocks/requestLog'
import { errorResponse, successResponse } from '@/test/mocks/responses'
import { server } from '@/test/mocks/server'
import { createGate } from '@/test/utils/createGate'
import { expectNotified, expectNotNotified, waitForNotificationCount, waitForNotified } from '@/test/utils/notifications'
import { getCurrentLocation, renderWithProviders } from '@/test/utils/renderWithProviders'

const PRODUCT_URL = `${API_URL}/api/v1/products/:productId`
const ANSWERS_URL = `${API_URL}/api/v1/products/:productId/answers`

// 테스트가 응답에 넣는 데이터. 화면 문구가 아니라 이 테스트의 입력값이다.
const PRODUCT_NAME = buildProductResult().productName
const BATTERY = '배터리가 내장되어 있나요?'
const CHILDREN = '어린이용 제품인가요?'
const POWER = '전원을 연결해 쓰나요?'
const OLD_ROUND_QUESTION = '지난 회차 질문'
const NEW_ROUND_QUESTION = '이번 회차 질문'

// 질문 화면을 실제 라우터·QueryClient·MSW(API 모킹) 위에서 사용자처럼 조작한다.
// 화면 조작·조회는 드라이버(questionPage)를 거친다. 이동한 화면은 텍스트로 구분할 수 있는 도착 화면으로 대신한다.
// route에 객체를 주면 이전 화면이 넘긴 state를 흉내 낼 수 있고, history는 그 앞에 쌓인 이전 항목이다.
const renderQuestionPage = (route: InitialEntry = '/question/product-1', history: InitialEntry[] = []) => {
  renderWithProviders(<QuestionPage />, {
    path: '/question/:productId',
    route,
    history,
    extraRoutes: (
      <>
        <Route path="/mypage" element={<p>마이페이지 화면</p>} />
        <Route path="/" element={<p>메인 화면</p>} />
        <Route path="/judgement/:diagnosesId" element={<p>진단 진행 화면</p>} />
        <Route path="/upload" element={<p>업로드 화면</p>} />
        <Route path="/result/product/:productId" element={<p>결과 화면</p>} />
      </>
    ),
  })
  return questionPage()
}

// 이동한 도착 화면(이 파일이 만든 스텁)이 보일 때까지 기다린다.
const findStubScreen = (text: string) => screen.findByText(text)

// 조회되는 상품을 바꾼다. 기본값은 답변 대기 중인 상품과 1회차 질문 하나다.
const mockProduct = (overrides: Partial<ProductResult> = {}) =>
  server.use(http.get(PRODUCT_URL, () => successResponse(buildProductResult(overrides))))

// 모두 같은 1회차의 질문.
const threeQuestions = [
  buildQuestion({ questionId: 'q1', questionOrder: 1, questionText: BATTERY }),
  buildQuestion({ questionId: 'q2', questionOrder: 2, questionText: CHILDREN }),
  buildQuestion({ questionId: 'q3', questionOrder: 3, questionText: POWER }),
]

describe('질문 화면 - 질문 표시', () => {
  it('불러오는 동안 로딩을 보여주고, 불러오면 상품 정보와 현재 회차의 질문을 보여준다', async () => {
    const page = renderQuestionPage()

    expect(page.isLoading()).toBe(true)

    await page.waitUntilLoaded()
    expect(page.hasProductName(PRODUCT_NAME)).toBe(true)
    expect(page.answerValue(BATTERY)).toBe('')
    expect(page.hasProgress(0, 1)).toBe(true)
    expect(page.isLoading()).toBe(false)
  })

  it('요청한 productId의 상품을 조회한다', async () => {
    const page = renderQuestionPage('/question/product-42')

    await page.waitUntilLoaded()

    expect(requestLog.find('GET', '/api/v1/products/product-42')).toHaveLength(1)
  })

  it('과거 회차 질문이 섞여 있으면 가장 최근 회차의 질문만 보여준다', async () => {
    mockProduct({
      questions: [
        buildQuestion({ questionId: 'old', questionRound: 1, questionText: OLD_ROUND_QUESTION }),
        buildQuestion({ questionId: 'new', questionRound: 2, questionText: NEW_ROUND_QUESTION }),
      ],
    })
    const page = renderQuestionPage()

    await page.waitUntilLoaded(2)
    expect(page.hasQuestion(NEW_ROUND_QUESTION)).toBe(true)
    expect(page.hasText(OLD_ROUND_QUESTION)).toBe(false)
  })

  it('질문이 하나도 없으면 안내 문구를 보여준다', async () => {
    mockProduct({ questions: [] })
    const page = renderQuestionPage()

    await page.waitForText(QUESTION_MESSAGES.NO_QUESTIONS)
    expect(page.hasSubmitButton()).toBe(false)
  })

  it('조회에 실패하면 오류 안내와 다시 시도 버튼을 보여주고, 다시 시도하면 질문을 불러온다', async () => {
    server.use(http.get(PRODUCT_URL, () => errorResponse(500), { once: true }))
    const page = renderQuestionPage()

    await page.waitForText(QUESTION_MESSAGES.LOAD_FAILED)

    await page.clickRetry()

    await page.waitUntilLoaded()
    expect(page.hasText(QUESTION_MESSAGES.LOAD_FAILED)).toBe(false)
  })
})

describe('질문 화면 - 답변 진행 상황', () => {
  it('답변을 입력하면 하단 바의 답변 수가 갱신된다', async () => {
    mockProduct({ questions: threeQuestions })
    const page = renderQuestionPage()
    await page.waitUntilLoaded()

    expect(page.hasProgress(0, 3)).toBe(true)

    await page.answer(BATTERY, '네')
    expect(page.hasProgress(1, 3)).toBe(true)

    await page.answer(CHILDREN, '아니요')
    await page.answer(POWER, '아니요')
    expect(page.hasProgress(3, 3)).toBe(true)
  })

  it('답변을 지우면 다시 미답변으로 돌아간다', async () => {
    const page = renderQuestionPage()
    await page.waitUntilLoaded()

    await page.answer(BATTERY, '네')
    expect(page.hasProgress(1, 1)).toBe(true)

    await page.clearAnswer(BATTERY)
    expect(page.hasProgress(0, 1)).toBe(true)
  })

  it('공백만 입력한 답변은 답변하지 않은 것으로 센다', async () => {
    const page = renderQuestionPage()
    await page.waitUntilLoaded()

    await page.answer(BATTERY, '   ')

    expect(page.hasProgress(0, 1)).toBe(true)
  })
})

describe('질문 화면 - 미응답 안내', () => {
  it('답변하지 않고 제출하면 안내하고, 첫 번째 미답변 질문으로 포커스·스크롤하며 요청은 보내지 않는다', async () => {
    const page = renderQuestionPage()
    await page.waitUntilLoaded()

    await page.submit()

    expectNotified(QUESTION_MESSAGES.ANSWER_ALL)
    expect(page.isQuestionFocused(BATTERY)).toBe(true)
    expect(Element.prototype.scrollIntoView).toHaveBeenCalledWith({ behavior: 'smooth', block: 'center' })
    expect(requestLog.find('POST', '/api/v1/products/product-1/answers')).toHaveLength(0)
    expect(getCurrentLocation()).toBe('/question/product-1')
  })

  it('일부만 답했다면 질문 순서상 가장 먼저 만나는 미답변 질문으로 포커스한다', async () => {
    mockProduct({ questions: threeQuestions })
    const page = renderQuestionPage()
    await page.waitUntilLoaded()

    await page.answer(BATTERY, '네')
    await page.answer(POWER, '아니요')
    await page.submit()

    expectNotified(QUESTION_MESSAGES.ANSWER_ALL)
    expect(page.isQuestionFocused(CHILDREN)).toBe(true)
    expect(requestLog.find('POST', '/api/v1/products/product-1/answers')).toHaveLength(0)
  })

  it('공백만 입력한 답변도 미응답으로 안내한다', async () => {
    const page = renderQuestionPage()
    await page.waitUntilLoaded()

    await page.answer(BATTERY, '   ')
    await page.submit()

    expectNotified(QUESTION_MESSAGES.ANSWER_ALL)
    expect(requestLog.find('POST', '/api/v1/products/product-1/answers')).toHaveLength(0)
  })
})

describe('질문 화면 - 답변 제출', () => {
  it('모두 답하고 제출하면 답변을 보내고, 상품의 진단서 진행 화면으로 이동한다', async () => {
    mockProduct({ diagnosesId: 'diagnoses-77', questions: threeQuestions })
    const page = renderQuestionPage()
    await page.waitUntilLoaded()

    await page.answer(BATTERY, '네')
    await page.answer(CHILDREN, '아니요')
    await page.answer(POWER, '배터리로만 써요')
    await page.submit()

    expect(await findStubScreen('진단 진행 화면')).toBeInTheDocument()
    expect(getCurrentLocation()).toBe('/judgement/diagnoses-77')
    expect(requestLog.find('POST', '/api/v1/products/product-1/answers')[0].body).toEqual({
      answers: [
        { questionId: 'q1', answerText: '네' },
        { questionId: 'q2', answerText: '아니요' },
        { questionId: 'q3', answerText: '배터리로만 써요' },
      ],
    })
    expectNotNotified()
  })

  it('과거 회차가 있으면 현재 회차 질문의 답변만 보낸다', async () => {
    mockProduct({
      questions: [
        buildQuestion({ questionId: 'old', questionRound: 1, questionText: OLD_ROUND_QUESTION, answerText: '이미 한 답변' }),
        buildQuestion({ questionId: 'new', questionRound: 2, questionText: NEW_ROUND_QUESTION }),
      ],
    })
    const page = renderQuestionPage()
    await page.waitUntilLoaded(2)

    await page.answer(NEW_ROUND_QUESTION, '새 답변')
    await page.submit()

    expect(await findStubScreen('진단 진행 화면')).toBeInTheDocument()
    expect(requestLog.find('POST', '/api/v1/products/product-1/answers')[0].body).toEqual({
      answers: [{ questionId: 'new', answerText: '새 답변' }],
    })
  })

  it('제출하는 동안에는 버튼을 비활성화하고, 완료되면 이동한다', async () => {
    const gate = createGate()
    server.use(
      http.post(ANSWERS_URL, async () => {
        await gate.promise
        return successResponse(null)
      }),
    )
    const page = renderQuestionPage()
    await page.waitUntilLoaded()

    await page.answer(BATTERY, '네')
    await page.submit()

    await page.waitUntilSubmitDisabled()
    expect(getCurrentLocation()).toBe('/question/product-1')

    gate.release()

    expect(await findStubScreen('진단 진행 화면')).toBeInTheDocument()
  })

  it('제출에 실패하면 서버의 오류 메시지를 안내하고, 화면과 입력한 답변은 그대로 둔다', async () => {
    server.use(http.post(ANSWERS_URL, () => errorResponse(400, { detailMessage: SERVER_MESSAGES.ANSWER_NOT_SAVED })))
    const page = renderQuestionPage()
    await page.waitUntilLoaded()

    await page.answer(BATTERY, '네')
    await page.submit()

    await waitForNotified(SERVER_MESSAGES.ANSWER_NOT_SAVED)
    expect(getCurrentLocation()).toBe('/question/product-1')
    expect(page.answerValue(BATTERY)).toBe('네')
    expect(page.isSubmitEnabled()).toBe(true)
  })

  it('실패한 뒤 같은 답변으로 다시 제출하면 성공해서 이동한다', async () => {
    // 오버라이드 핸들러도 recordRequest로 요청을 기록하면, 실패한 시도의 본문까지 검증할 수 있다.
    server.use(
      http.post(
        ANSWERS_URL,
        async ({ request }) => {
          await recordRequest(request)
          return errorResponse(500)
        },
        { once: true },
      ),
    )
    const page = renderQuestionPage()
    await page.waitUntilLoaded()

    await page.answer(BATTERY, '네')
    await page.submit()
    await waitForNotificationCount(1)

    await page.submit()

    expect(await findStubScreen('진단 진행 화면')).toBeInTheDocument()
    const bodies = requestLog.find('POST', '/api/v1/products/product-1/answers').map((entry) => entry.body)
    expect(bodies).toEqual([
      { answers: [{ questionId: 'question-1', answerText: '네' }] },
      { answers: [{ questionId: 'question-1', answerText: '네' }] },
    ])
  })
})

describe('질문 화면 - 답변 임시 저장', () => {
  // 새로고침을 흉내 낸다. 화면을 내렸다가 같은 주소로 다시 연다.
  const reload = async () => {
    cleanup()
    const page = renderQuestionPage()
    await page.waitUntilLoaded()
    return page
  }

  it('답변을 쓰다가 새로고침하면 같은 회차의 답변을 복원한다', async () => {
    mockProduct({ questions: threeQuestions })
    const page = renderQuestionPage()
    await page.waitUntilLoaded()
    await page.answer(BATTERY, '네')
    await page.answer(CHILDREN, '아니요')

    const reloaded = await reload()

    expect(reloaded.answerValue(BATTERY)).toBe('네')
    expect(reloaded.answerValue(CHILDREN)).toBe('아니요')
    expect(reloaded.answerValue(POWER)).toBe('')
    expect(reloaded.hasProgress(2, 3)).toBe(true)
  })

  it('복원한 답변을 고치면 다음 새로고침에도 고친 값이 남는다', async () => {
    mockProduct({ questions: threeQuestions })
    saveAnswerDraft('product-1', 1, { q1: '네' })
    const page = renderQuestionPage()
    await page.waitUntilLoaded()
    expect(page.answerValue(BATTERY)).toBe('네')

    await page.clearAnswer(BATTERY)
    await page.answer(BATTERY, '아니요')

    const reloaded = await reload()
    expect(reloaded.answerValue(BATTERY)).toBe('아니요')
  })

  it('다른 회차에 저장된 답변은 복원하지 않는다', async () => {
    saveAnswerDraft('product-1', 1, { old: '지난 회차 답변', new: '엉뚱한 값' })
    mockProduct({
      questions: [
        buildQuestion({ questionId: 'old', questionRound: 1, questionText: OLD_ROUND_QUESTION }),
        buildQuestion({ questionId: 'new', questionRound: 2, questionText: NEW_ROUND_QUESTION }),
      ],
    })
    const page = renderQuestionPage()

    await page.waitUntilLoaded(2)

    expect(page.answerValue(NEW_ROUND_QUESTION)).toBe('')
  })

  it('현재 회차 질문에 없는 질문의 저장된 답변은 무시하고, 제출에도 포함하지 않는다', async () => {
    mockProduct({ questions: [buildQuestion({ questionId: 'q1', questionText: BATTERY })] })
    saveAnswerDraft('product-1', 1, { q1: '네', ghost: '사라진 질문의 답변' })
    const page = renderQuestionPage()
    await page.waitUntilLoaded()
    expect(page.answerValue(BATTERY)).toBe('네')

    await page.submit()

    expect(await findStubScreen('진단 진행 화면')).toBeInTheDocument()
    expect(requestLog.find('POST', '/api/v1/products/product-1/answers')[0].body).toEqual({
      answers: [{ questionId: 'q1', answerText: '네' }],
    })
  })

  it('다른 상품의 임시 저장은 복원하지 않는다', async () => {
    saveAnswerDraft('product-other', 1, { q1: '다른 상품의 답변' })
    const page = renderQuestionPage()

    await page.waitUntilLoaded()

    expect(page.answerValue(BATTERY)).toBe('')
  })

  it('답변을 제출하면 그 회차의 임시 저장을 지운다', async () => {
    mockProduct({ questions: threeQuestions })
    const page = renderQuestionPage()
    await page.waitUntilLoaded()
    await page.answer(BATTERY, '네')
    await page.answer(CHILDREN, '아니요')
    await page.answer(POWER, '배터리로만 써요')
    expect(loadAnswerDraft('product-1', 1)).not.toEqual({})

    await page.submit()

    expect(await findStubScreen('진단 진행 화면')).toBeInTheDocument()
    expect(loadAnswerDraft('product-1', 1)).toEqual({})
  })

  it('제출에 실패하면 임시 저장을 그대로 둔다', async () => {
    mockProduct({ questions: threeQuestions })
    server.use(http.post(ANSWERS_URL, () => errorResponse(400, { detailMessage: SERVER_MESSAGES.ANSWER_NOT_SAVED })))
    const page = renderQuestionPage()
    await page.waitUntilLoaded()
    await page.answer(BATTERY, '네')
    await page.answer(CHILDREN, '아니요')
    await page.answer(POWER, '배터리로만 써요')

    await page.submit()

    await waitForNotified(SERVER_MESSAGES.ANSWER_NOT_SAVED)
    expect(loadAnswerDraft('product-1', 1)).toEqual({ q1: '네', q2: '아니요', q3: '배터리로만 써요' })
  })
})

describe('질문 화면 - 잘못된 접근', () => {
  it.each(['undefined', 'null'])('productId가 "%s"로 들어오면 안내하고 요청 없이 업로드 화면으로 돌려보낸다', async (productId) => {
    renderQuestionPage(`/question/${productId}`)

    expect(await findStubScreen('업로드 화면')).toBeInTheDocument()
    expectNotified(COMMON_MESSAGES.INVALID_ACCESS_TO_UPLOAD)
    expect(getCurrentLocation()).toBe('/upload')
    expect(requestLog.all()).toEqual([])
  })

  it.each([400, 404])('존재하지 않거나 형식이 잘못된 상품 id(%i)면 오류 화면 없이 안내하고 메인으로 돌려보낸다', async (status) => {
    server.use(http.get(PRODUCT_URL, () => errorResponse(status)))
    const page = renderQuestionPage()

    expect(await findStubScreen('메인 화면')).toBeInTheDocument()
    expectNotified(QUESTION_MESSAGES.INVALID_PRODUCT_ID)
    expect(getCurrentLocation()).toBe('/')
    expect(page.hasText(QUESTION_MESSAGES.LOAD_FAILED)).toBe(false)
  })

  it('답변을 기다리는 상품이 아니면 안내하고 결과 화면으로 돌려보낸다', async () => {
    mockProduct({ processingStatus: ProcessingStatusType.Completed })
    renderQuestionPage()

    expect(await findStubScreen('결과 화면')).toBeInTheDocument()
    expectNotified(COMMON_MESSAGES.INVALID_ACCESS)
    expect(getCurrentLocation()).toBe('/result/product/product-1')
  })
})

describe('질문 화면 - 이전으로 버튼', () => {
  // 이전 화면이 이동하면서 넘기는 state. 이 값이 있으면 바로 이전 히스토리 항목이 그 화면이다.
  const cameFrom = (from: string) => ({ pathname: '/question/product-1', state: { from } })

  it('이전 경로(state)가 있으면 히스토리를 되돌려 이전 화면으로 돌아간다', async () => {
    const page = renderQuestionPage(cameFrom('/mypage'), ['/mypage'])
    await page.waitUntilLoaded()

    await page.clickBack()

    expect(await findStubScreen('마이페이지 화면')).toBeInTheDocument()
    expect(getCurrentLocation()).toBe('/mypage')
  })

  it('이전 경로가 없으면 히스토리와 상관없이 상품의 진단 진행 화면으로 이동한다', async () => {
    mockProduct({ diagnosesId: 'diagnoses-7' })
    const page = renderQuestionPage('/question/product-1', ['/mypage'])
    await page.waitForBackButton()

    await page.clickBack()

    expect(await findStubScreen('진단 진행 화면')).toBeInTheDocument()
    expect(getCurrentLocation()).toBe('/judgement/diagnoses-7')
  })

  it('이전 경로가 있으면 상품을 불러오기 전에도 버튼을 보여준다', async () => {
    const page = renderQuestionPage(cameFrom('/mypage'), ['/mypage'])

    expect(page.isLoading()).toBe(true)
    expect(page.hasBackButton()).toBe(true)

    await page.waitUntilLoaded()
  })

  it('이전 경로가 없으면 상품을 불러오기 전에는 돌아갈 곳을 몰라 버튼을 보여주지 않고, 불러온 뒤에 보여준다', async () => {
    const page = renderQuestionPage()

    expect(page.isLoading()).toBe(true)
    expect(page.hasBackButton()).toBe(false)

    await page.waitForBackButton()
  })

  it('이전 경로가 없는데 조회에 실패하면 버튼을 보여주지 않는다', async () => {
    server.use(http.get(PRODUCT_URL, () => errorResponse(500)))
    const page = renderQuestionPage()

    await page.waitForText(QUESTION_MESSAGES.LOAD_FAILED)

    expect(page.hasBackButton()).toBe(false)
  })
})
