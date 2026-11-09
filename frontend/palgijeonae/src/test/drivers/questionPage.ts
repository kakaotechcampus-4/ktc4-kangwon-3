import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

import { QUESTION_MESSAGES } from '@/test/constants/messages'

// 질문 화면 드라이버. 테스트 본문은 이 파일의 함수만 거쳐서 화면을 조작·조회한다.
// 화면 구성(문구, 구조)이 바뀌면 테스트 본문은 두고 이 파일만 고친다.
//
//   const page = questionPage()
//   await page.waitUntilLoaded()
//   await page.answer('배터리가 내장되어 있나요?', '네')
//   await page.submit()

type User = ReturnType<typeof userEvent.setup>

export function questionPage(user: User = userEvent.setup()) {
  // 질문마다 textarea가 있고, 접근 가능한 이름이 질문 문구이다.
  const answerBox = (questionText: string) => screen.getByRole('textbox', { name: questionText })
  const submitButton = () => screen.getByRole('button', { name: /답변 완료하기/ })

  return {
    // ── 불러오기 ─────────────────────────────────────────────
    /** 질문이 나타날 때까지 기다린다. (현재 회차 제목이 보이면 불러온 것이다) */
    waitUntilLoaded: async (round = 1) => {
      await screen.findByRole('heading', { name: QUESTION_MESSAGES.roundTitle(round) })
    },
    isLoading: () => screen.queryByRole('status') !== null,
    clickRetry: () => user.click(screen.getByRole('button', { name: /다시 시도/ })),

    // ── 화면 문구 ────────────────────────────────────────────
    hasText: (text: string) => screen.queryAllByText(text).length > 0,
    waitForText: async (text: string) => {
      await screen.findByText(text)
    },
    hasProductName: (name: string) => screen.queryAllByText(name).length > 0,

    // ── 질문과 답변 ──────────────────────────────────────────
    /** 그 질문이 화면에 있는지 (지난 회차 질문은 보이지 않는다) */
    hasQuestion: (questionText: string) => screen.queryByRole('textbox', { name: questionText }) !== null,
    answerValue: (questionText: string) => (answerBox(questionText) as HTMLTextAreaElement).value,
    isQuestionFocused: (questionText: string) => document.activeElement === answerBox(questionText),
    answer: async (questionText: string, text: string) => {
      await user.click(answerBox(questionText))
      await user.paste(text)
    },
    clearAnswer: (questionText: string) => user.clear(answerBox(questionText)),

    // ── 진행 요약 ────────────────────────────────────────────
    /** "답한 수/전체 수" 요약이 보이는지. 예: hasProgress(1, 3) */
    hasProgress: (answered: number, total: number) => screen.queryAllByText(QUESTION_MESSAGES.progress(answered, total)).length > 0,
    isAllAnswered: () => screen.queryAllByText(QUESTION_MESSAGES.PROGRESS_COMPLETE).length > 0,

    // ── 이전으로 ─────────────────────────────────────────────
    hasBackButton: () => screen.queryByRole('button', { name: '이전으로' }) !== null,
    waitForBackButton: async () => {
      await screen.findByRole('button', { name: '이전으로' })
    },
    clickBack: () => user.click(screen.getByRole('button', { name: '이전으로' })),

    // ── 제출 ────────────────────────────────────────────────
    submit: () => user.click(submitButton()),
    hasSubmitButton: () => screen.queryByRole('button', { name: /답변 완료하기/ }) !== null,
    isSubmitEnabled: () => !(submitButton() as HTMLButtonElement).disabled,
    /** 제출 요청이 진행되는 동안 버튼이 비활성화될 때까지 기다린다. */
    waitUntilSubmitDisabled: () => waitFor(() => expect((submitButton() as HTMLButtonElement).disabled).toBe(true)),
  }
}

export type QuestionPage = ReturnType<typeof questionPage>
