import type { Question } from '@/api/types/product'
import { computeAnswerState } from '@/pages/Question/utils/answerState'

const makeQuestion = (questionId: string): Question => ({
  questionId,
  questionRound: 1,
  questionOrder: 1,
  questionText: `질문 ${questionId}`,
  helpText: null,
  answerText: null,
})

const questions = [makeQuestion('q1'), makeQuestion('q2'), makeQuestion('q3')]

describe('computeAnswerState', () => {
  it('질문이 없으면 빈 상태이다', () => {
    expect(computeAnswerState([], {})).toEqual({ currentAnswered: [], firstUnansweredId: null })
  })

  it('모든 질문에 답했으면 미답변이 없다', () => {
    const result = computeAnswerState(questions, { q1: 'a', q2: 'b', q3: 'c' })

    expect(result.currentAnswered).toEqual([true, true, true])
    expect(result.firstUnansweredId).toBeNull()
  })

  it('아무 답변도 없으면 첫 번째 질문이 가장 먼저 만난 미답변이다', () => {
    const result = computeAnswerState(questions, {})

    expect(result.currentAnswered).toEqual([false, false, false])
    expect(result.firstUnansweredId).toBe('q1')
  })

  it('일부만 답했으면 질문 순서상 가장 먼저 만난 미답변을 알려준다', () => {
    const result = computeAnswerState(questions, { q1: 'a', q3: 'c' })

    expect(result.currentAnswered).toEqual([true, false, true])
    expect(result.firstUnansweredId).toBe('q2')
  })

  it('가장 먼저 만난 미답변은 answers 객체의 순서가 아니라 질문 순서로 정한다', () => {
    const result = computeAnswerState(questions, { q3: 'c', q2: 'b' })

    expect(result.firstUnansweredId).toBe('q1')
  })

  it('공백만 있는 답변은 답변하지 않은 것으로 본다', () => {
    const result = computeAnswerState(questions, { q1: '   ', q2: '\n\t', q3: 'c' })

    expect(result.currentAnswered).toEqual([false, false, true])
    expect(result.firstUnansweredId).toBe('q1')
  })

  it('빈 문자열 답변은 답변하지 않은 것으로 본다', () => {
    const result = computeAnswerState(questions, { q1: '', q2: 'b', q3: 'c' })

    expect(result.currentAnswered).toEqual([false, true, true])
    expect(result.firstUnansweredId).toBe('q1')
  })

  it('질문 목록에 없는 id의 답변은 무시한다', () => {
    const result = computeAnswerState(questions, { q1: 'a', q2: 'b', q3: 'c', other: 'x' })

    expect(result.currentAnswered).toEqual([true, true, true])
    expect(result.firstUnansweredId).toBeNull()
  })

  it('currentAnswered의 길이는 질문 개수와 같다', () => {
    expect(computeAnswerState(questions, { q1: 'a' }).currentAnswered).toHaveLength(questions.length)
  })
})
