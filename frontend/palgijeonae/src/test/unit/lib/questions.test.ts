import type { Question } from '@/api/product'
import { getCurrentRoundQuestions } from '@/lib/questions'

const makeQuestion = (questionId: string, questionRound: number, questionOrder = 1): Question => ({
  questionId,
  questionRound,
  questionOrder,
  questionText: `질문 ${questionId}`,
  helpText: null,
  answerText: null,
})

describe('getCurrentRoundQuestions', () => {
  it('질문이 없으면 빈 배열이다', () => {
    expect(getCurrentRoundQuestions([])).toEqual([])
  })

  it('회차가 하나뿐이면 모든 질문을 돌려준다', () => {
    const questions = [makeQuestion('a', 1, 1), makeQuestion('b', 1, 2)]

    expect(getCurrentRoundQuestions(questions)).toEqual(questions)
  })

  it('과거 회차가 섞여 있으면 가장 최근 회차의 질문만 남긴다', () => {
    const round1 = makeQuestion('r1', 1)
    const round2a = makeQuestion('r2a', 2, 1)
    const round2b = makeQuestion('r2b', 2, 2)

    expect(getCurrentRoundQuestions([round1, round2a, round2b])).toEqual([round2a, round2b])
  })

  it('입력 순서와 상관없이 가장 큰 회차를 고른다', () => {
    const round3 = makeQuestion('r3', 3)
    const round1 = makeQuestion('r1', 1)
    const round2 = makeQuestion('r2', 2)

    expect(getCurrentRoundQuestions([round3, round1, round2])).toEqual([round3])
  })

  it('회차가 연속되지 않아도 가장 큰 회차를 고른다', () => {
    const round1 = makeQuestion('r1', 1)
    const round3 = makeQuestion('r3', 3)

    expect(getCurrentRoundQuestions([round1, round3])).toEqual([round3])
  })

  it('남긴 질문의 원래 순서를 유지한다', () => {
    const second = makeQuestion('second', 2, 2)
    const first = makeQuestion('first', 2, 1)

    expect(getCurrentRoundQuestions([second, makeQuestion('old', 1), first])).toEqual([second, first])
  })

  it('입력 배열을 바꾸지 않는다', () => {
    const questions = [makeQuestion('r1', 1), makeQuestion('r2', 2)]
    const snapshot = [...questions]

    getCurrentRoundQuestions(questions)

    expect(questions).toEqual(snapshot)
  })
})
