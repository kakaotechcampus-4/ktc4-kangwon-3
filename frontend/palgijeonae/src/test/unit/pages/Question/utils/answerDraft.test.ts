import { afterEach, describe, expect, it, vi } from 'vitest'

import {
  clearAllAnswerDrafts,
  clearAnswerDraft,
  loadAnswerDraft,
  pickAnswersForQuestions,
  saveAnswerDraft,
} from '@/pages/Question/utils/answerDraft'

afterEach(() => {
  vi.restoreAllMocks()
})

describe('답변 임시 저장 - 저장과 복원', () => {
  it('저장한 답변을 같은 상품·회차에서 그대로 불러온다', () => {
    saveAnswerDraft('p1', 1, { q1: '네', q2: '아니요' })

    expect(loadAnswerDraft('p1', 1)).toEqual({ q1: '네', q2: '아니요' })
  })

  it('저장 키는 question-draft:{상품}:{회차} 형태다', () => {
    saveAnswerDraft('p1', 2, { q1: '네' })

    expect(sessionStorage.getItem('question-draft:p1:2')).toBe(JSON.stringify({ q1: '네' }))
  })

  it('다른 회차나 다른 상품의 임시 저장은 불러오지 않는다', () => {
    saveAnswerDraft('p1', 1, { q1: '네' })

    expect(loadAnswerDraft('p1', 2)).toEqual({})
    expect(loadAnswerDraft('p2', 1)).toEqual({})
  })

  it('저장된 것이 없으면 빈 객체다', () => {
    expect(loadAnswerDraft('p1', 1)).toEqual({})
  })

  it.each(['not json', '[]', '"text"', 'null', '123'])('저장된 값이 올바른 형태가 아니면 빈 객체다: %s', (raw) => {
    sessionStorage.setItem('question-draft:p1:1', raw)

    expect(loadAnswerDraft('p1', 1)).toEqual({})
  })

  it('문자열이 아닌 답변 값은 버린다', () => {
    sessionStorage.setItem('question-draft:p1:1', JSON.stringify({ q1: '네', q2: 3, q3: null }))

    expect(loadAnswerDraft('p1', 1)).toEqual({ q1: '네' })
  })

  it('모든 답변이 비어 있거나 공백뿐이면 저장하지 않고 기존 저장도 지운다', () => {
    saveAnswerDraft('p1', 1, { q1: '네' })

    saveAnswerDraft('p1', 1, { q1: '', q2: '   ' })

    expect(sessionStorage.getItem('question-draft:p1:1')).toBeNull()
  })
})

describe('답변 임시 저장 - 삭제', () => {
  it('한 상품·회차의 임시 저장만 지운다', () => {
    saveAnswerDraft('p1', 1, { q1: '네' })
    saveAnswerDraft('p1', 2, { q2: '아니요' })

    clearAnswerDraft('p1', 1)

    expect(loadAnswerDraft('p1', 1)).toEqual({})
    expect(loadAnswerDraft('p1', 2)).toEqual({ q2: '아니요' })
  })

  it('모든 상품·회차의 임시 저장을 지우고 다른 저장값은 건드리지 않는다', () => {
    saveAnswerDraft('p1', 1, { q1: '네' })
    saveAnswerDraft('p2', 2, { q2: '아니요' })
    sessionStorage.setItem('other-key', 'keep')

    clearAllAnswerDrafts()

    expect(loadAnswerDraft('p1', 1)).toEqual({})
    expect(loadAnswerDraft('p2', 2)).toEqual({})
    expect(sessionStorage.getItem('other-key')).toBe('keep')
  })
})

describe('답변 임시 저장 - 저장소를 쓸 수 없을 때', () => {
  it('읽기·쓰기·삭제가 실패해도 오류를 던지지 않는다', () => {
    vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
      throw new Error('blocked')
    })
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new Error('blocked')
    })
    vi.spyOn(Storage.prototype, 'removeItem').mockImplementation(() => {
      throw new Error('blocked')
    })

    expect(loadAnswerDraft('p1', 1)).toEqual({})
    expect(() => saveAnswerDraft('p1', 1, { q1: '네' })).not.toThrow()
    expect(() => clearAnswerDraft('p1', 1)).not.toThrow()
    expect(() => clearAllAnswerDrafts()).not.toThrow()
  })
})

describe('pickAnswersForQuestions', () => {
  it('현재 회차 질문에 없는 questionId의 답변은 버린다', () => {
    expect(pickAnswersForQuestions({ q1: '네', ghost: '지난 질문' }, ['q1', 'q2'])).toEqual({ q1: '네' })
  })
})
