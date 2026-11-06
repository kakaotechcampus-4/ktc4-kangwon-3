import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http } from 'msw'
import { Route } from 'react-router-dom'

import type { ProductResult } from '@/api/product'
import { ProcessingStatusType } from '@/api/types'
import QuestionPage from '@/pages/Question'
import { buildProductResult, buildQuestion } from '@/test/mocks/fixtures'
import { API_URL } from '@/test/mocks/handlers'
import { recordRequest, requestLog } from '@/test/mocks/requestLog'
import { errorResponse, successResponse } from '@/test/mocks/responses'
import { server } from '@/test/mocks/server'
import { getCurrentLocation, renderWithProviders } from '@/test/utils/renderWithProviders'

const PRODUCT_URL = `${API_URL}/api/v1/products/:productId`
const ANSWERS_URL = `${API_URL}/api/v1/products/:productId/answers`

// 질문 화면을 실제 라우터·QueryClient·MSW(API 모킹) 위에서 사용자처럼 조작한다.
// 이동한 화면은 텍스트로 구분할 수 있는 도착 화면으로 대신한다.
const renderQuestionPage = (route = '/question/product-1') =>
  renderWithProviders(<QuestionPage />, {
    path: '/question/:productId',
    route,
    extraRoutes: (
      <>
        <Route path="/judgement/:diagnosesId" element={<p>진단 진행 화면</p>} />
        <Route path="/upload" element={<p>업로드 화면</p>} />
        <Route path="/result/product/:productId" element={<p>결과 화면</p>} />
      </>
    ),
  })

// 조회되는 상품을 바꾼다. 기본값은 답변 대기 중인 상품과 1회차 질문 하나다.
const mockProduct = (overrides: Partial<ProductResult> = {}) =>
  server.use(http.get(PRODUCT_URL, () => successResponse(buildProductResult(overrides))))

// 모두 같은 1회차의 질문.
const threeQuestions = [
  buildQuestion({ questionId: 'q1', questionOrder: 1, questionText: '배터리가 내장되어 있나요?' }),
  buildQuestion({ questionId: 'q2', questionOrder: 2, questionText: '어린이용 제품인가요?' }),
  buildQuestion({ questionId: 'q3', questionOrder: 3, questionText: '전원을 연결해 쓰나요?' }),
]

const textboxOf = (questionText: string) => screen.getByRole('textbox', { name: questionText })
const submitButton = () => screen.getByRole('button', { name: '답변 완료하기' })

type User = ReturnType<typeof userEvent.setup>

const answer = async (user: User, questionText: string, text: string) => {
  await user.click(textboxOf(questionText))
  await user.paste(text)
}

describe('질문 화면 - 질문 표시', () => {
  it('불러오는 동안 로딩을 보여주고, 불러오면 상품 정보와 현재 회차의 질문을 보여준다', async () => {
    renderQuestionPage()

    expect(screen.getByRole('status', { name: '로딩 중' })).toBeInTheDocument()

    expect(await screen.findByRole('heading', { name: '1차 질문' })).toBeInTheDocument()
    expect(screen.getByText('테스트 상품')).toBeInTheDocument()
    expect(textboxOf('배터리가 내장되어 있나요?')).toHaveValue('')
    expect(screen.getByText('0/1')).toBeInTheDocument()
    expect(screen.queryByRole('status')).not.toBeInTheDocument()
  })

  it('요청한 productId의 상품을 조회한다', async () => {
    renderQuestionPage('/question/product-42')

    await screen.findByRole('heading', { name: '1차 질문' })

    expect(requestLog.find('GET', '/api/v1/products/product-42')).toHaveLength(1)
  })

  it('과거 회차 질문이 섞여 있으면 가장 최근 회차의 질문만 보여준다', async () => {
    mockProduct({
      questions: [
        buildQuestion({ questionId: 'old', questionRound: 1, questionText: '지난 회차 질문' }),
        buildQuestion({ questionId: 'new', questionRound: 2, questionText: '이번 회차 질문' }),
      ],
    })
    renderQuestionPage()

    expect(await screen.findByRole('heading', { name: '2차 질문' })).toBeInTheDocument()
    expect(textboxOf('이번 회차 질문')).toBeInTheDocument()
    expect(screen.queryByText('지난 회차 질문')).not.toBeInTheDocument()
  })

  it('질문이 하나도 없으면 안내 문구를 보여준다', async () => {
    mockProduct({ questions: [] })
    renderQuestionPage()

    expect(await screen.findByText('확인이 필요한 질문이 없어요.')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: '답변 완료하기' })).not.toBeInTheDocument()
  })

  it('조회에 실패하면 오류 안내와 다시 시도 버튼을 보여주고, 다시 시도하면 질문을 불러온다', async () => {
    const user = userEvent.setup()
    server.use(http.get(PRODUCT_URL, () => errorResponse(500), { once: true }))
    renderQuestionPage()

    expect(await screen.findByText('질문을 불러오지 못했어요.')).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: '다시 시도' }))

    expect(await screen.findByRole('heading', { name: '1차 질문' })).toBeInTheDocument()
    expect(screen.queryByText('질문을 불러오지 못했어요.')).not.toBeInTheDocument()
  })
})

describe('질문 화면 - 답변 진행 상황', () => {
  it('답변을 입력하면 진행 요약이 갱신되고, 모두 답하면 답변 완료로 바뀐다', async () => {
    const user = userEvent.setup()
    mockProduct({ questions: threeQuestions })
    renderQuestionPage()
    await screen.findByRole('heading', { name: '1차 질문' })

    expect(screen.getByText('0/3')).toBeInTheDocument()

    await answer(user, '배터리가 내장되어 있나요?', '네')
    expect(screen.getByText('1/3')).toBeInTheDocument()

    await answer(user, '어린이용 제품인가요?', '아니요')
    await answer(user, '전원을 연결해 쓰나요?', '아니요')
    expect(screen.getByText('답변 완료')).toBeInTheDocument()
  })

  it('답변을 지우면 다시 미답변으로 돌아간다', async () => {
    const user = userEvent.setup()
    renderQuestionPage()
    await screen.findByRole('heading', { name: '1차 질문' })

    await answer(user, '배터리가 내장되어 있나요?', '네')
    expect(screen.getByText('답변 완료')).toBeInTheDocument()

    await user.clear(textboxOf('배터리가 내장되어 있나요?'))
    expect(screen.getByText('0/1')).toBeInTheDocument()
  })

  it('공백만 입력한 답변은 답변하지 않은 것으로 센다', async () => {
    const user = userEvent.setup()
    renderQuestionPage()
    await screen.findByRole('heading', { name: '1차 질문' })

    await answer(user, '배터리가 내장되어 있나요?', '   ')

    expect(screen.getByText('0/1')).toBeInTheDocument()
  })
})

describe('질문 화면 - 미응답 안내', () => {
  it('답변하지 않고 제출하면 안내하고, 첫 번째 미답변 질문으로 포커스·스크롤하며 요청은 보내지 않는다', async () => {
    const user = userEvent.setup()
    renderQuestionPage()
    await screen.findByRole('heading', { name: '1차 질문' })

    await user.click(submitButton())

    expect(window.alert).toHaveBeenCalledWith('질문에 모두 답변해 주세요.')
    expect(textboxOf('배터리가 내장되어 있나요?')).toHaveFocus()
    expect(Element.prototype.scrollIntoView).toHaveBeenCalledWith({ behavior: 'smooth', block: 'center' })
    expect(requestLog.find('POST', '/api/v1/products/product-1/answers')).toHaveLength(0)
    expect(getCurrentLocation()).toBe('/question/product-1')
  })

  it('일부만 답했다면 질문 순서상 가장 먼저 만나는 미답변 질문으로 포커스한다', async () => {
    const user = userEvent.setup()
    mockProduct({ questions: threeQuestions })
    renderQuestionPage()
    await screen.findByRole('heading', { name: '1차 질문' })

    await answer(user, '배터리가 내장되어 있나요?', '네')
    await answer(user, '전원을 연결해 쓰나요?', '아니요')
    await user.click(submitButton())

    expect(window.alert).toHaveBeenCalledWith('질문에 모두 답변해 주세요.')
    expect(textboxOf('어린이용 제품인가요?')).toHaveFocus()
    expect(requestLog.find('POST', '/api/v1/products/product-1/answers')).toHaveLength(0)
  })

  it('공백만 입력한 답변도 미응답으로 안내한다', async () => {
    const user = userEvent.setup()
    renderQuestionPage()
    await screen.findByRole('heading', { name: '1차 질문' })

    await answer(user, '배터리가 내장되어 있나요?', '   ')
    await user.click(submitButton())

    expect(window.alert).toHaveBeenCalledWith('질문에 모두 답변해 주세요.')
    expect(requestLog.find('POST', '/api/v1/products/product-1/answers')).toHaveLength(0)
  })
})

describe('질문 화면 - 답변 제출', () => {
  it('모두 답하고 제출하면 답변을 보내고, 상품의 진단서 진행 화면으로 이동한다', async () => {
    const user = userEvent.setup()
    mockProduct({ diagnosesId: 'diagnoses-77', questions: threeQuestions })
    renderQuestionPage()
    await screen.findByRole('heading', { name: '1차 질문' })

    await answer(user, '배터리가 내장되어 있나요?', '네')
    await answer(user, '어린이용 제품인가요?', '아니요')
    await answer(user, '전원을 연결해 쓰나요?', '배터리로만 써요')
    await user.click(submitButton())

    expect(await screen.findByText('진단 진행 화면')).toBeInTheDocument()
    expect(getCurrentLocation()).toBe('/judgement/diagnoses-77')
    expect(requestLog.find('POST', '/api/v1/products/product-1/answers')[0].body).toEqual({
      answers: [
        { questionId: 'q1', answerText: '네' },
        { questionId: 'q2', answerText: '아니요' },
        { questionId: 'q3', answerText: '배터리로만 써요' },
      ],
    })
    expect(window.alert).not.toHaveBeenCalled()
  })

  it('과거 회차가 있으면 현재 회차 질문의 답변만 보낸다', async () => {
    const user = userEvent.setup()
    mockProduct({
      questions: [
        buildQuestion({ questionId: 'old', questionRound: 1, questionText: '지난 회차 질문', answerText: '이미 한 답변' }),
        buildQuestion({ questionId: 'new', questionRound: 2, questionText: '이번 회차 질문' }),
      ],
    })
    renderQuestionPage()
    await screen.findByRole('heading', { name: '2차 질문' })

    await answer(user, '이번 회차 질문', '새 답변')
    await user.click(submitButton())

    expect(await screen.findByText('진단 진행 화면')).toBeInTheDocument()
    expect(requestLog.find('POST', '/api/v1/products/product-1/answers')[0].body).toEqual({
      answers: [{ questionId: 'new', answerText: '새 답변' }],
    })
  })

  it('제출하는 동안에는 버튼을 비활성화하고, 완료되면 이동한다', async () => {
    const user = userEvent.setup()
    let release!: () => void
    const gate = new Promise<void>((resolve) => {
      release = resolve
    })
    server.use(
      http.post(ANSWERS_URL, async () => {
        await gate
        return successResponse(null)
      }),
    )
    renderQuestionPage()
    await screen.findByRole('heading', { name: '1차 질문' })

    await answer(user, '배터리가 내장되어 있나요?', '네')
    await user.click(submitButton())

    await waitFor(() => expect(submitButton()).toBeDisabled())
    expect(getCurrentLocation()).toBe('/question/product-1')

    release()

    expect(await screen.findByText('진단 진행 화면')).toBeInTheDocument()
  })

  it('제출에 실패하면 서버의 오류 메시지를 안내하고, 화면과 입력한 답변은 그대로 둔다', async () => {
    const user = userEvent.setup()
    server.use(http.post(ANSWERS_URL, () => errorResponse(400, { detailMessage: '답변을 저장하지 못했습니다.' })))
    renderQuestionPage()
    await screen.findByRole('heading', { name: '1차 질문' })

    await answer(user, '배터리가 내장되어 있나요?', '네')
    await user.click(submitButton())

    await waitFor(() => expect(window.alert).toHaveBeenCalledWith('답변을 저장하지 못했습니다.'))
    expect(getCurrentLocation()).toBe('/question/product-1')
    expect(textboxOf('배터리가 내장되어 있나요?')).toHaveValue('네')
    expect(submitButton()).toBeEnabled()
  })

  it('실패한 뒤 같은 답변으로 다시 제출하면 성공해서 이동한다', async () => {
    const user = userEvent.setup()
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
    renderQuestionPage()
    await screen.findByRole('heading', { name: '1차 질문' })

    await answer(user, '배터리가 내장되어 있나요?', '네')
    await user.click(submitButton())
    await waitFor(() => expect(window.alert).toHaveBeenCalledTimes(1))

    await user.click(submitButton())

    expect(await screen.findByText('진단 진행 화면')).toBeInTheDocument()
    const bodies = requestLog.find('POST', '/api/v1/products/product-1/answers').map((entry) => entry.body)
    expect(bodies).toEqual([
      { answers: [{ questionId: 'question-1', answerText: '네' }] },
      { answers: [{ questionId: 'question-1', answerText: '네' }] },
    ])
  })
})

describe('질문 화면 - 잘못된 접근', () => {
  it.each(['undefined', 'null'])('productId가 "%s"로 들어오면 안내하고 요청 없이 업로드 화면으로 돌려보낸다', async (productId) => {
    renderQuestionPage(`/question/${productId}`)

    expect(await screen.findByText('업로드 화면')).toBeInTheDocument()
    expect(window.alert).toHaveBeenCalledWith('잘못된 접근입니다. 진단서를 업로드한 후 다시 시도해주세요.')
    expect(getCurrentLocation()).toBe('/upload')
    expect(requestLog.all()).toEqual([])
  })

  it('답변을 기다리는 상품이 아니면 안내하고 결과 화면으로 돌려보낸다', async () => {
    mockProduct({ processingStatus: ProcessingStatusType.Completed })
    renderQuestionPage()

    expect(await screen.findByText('결과 화면')).toBeInTheDocument()
    expect(window.alert).toHaveBeenCalledWith('잘못된 접근입니다.')
    expect(getCurrentLocation()).toBe('/result/product/product-1')
  })
})
