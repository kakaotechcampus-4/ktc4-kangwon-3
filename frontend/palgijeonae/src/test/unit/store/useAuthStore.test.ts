import { describe, expect, it } from 'vitest'

import { loadAnswerDraft, saveAnswerDraft } from '@/pages/Question/utils/answerDraft'
import { useAuthStore } from '@/store/useAuthStore'

describe('useAuthStore - logout', () => {
  it('로그인 정보를 지운다', () => {
    useAuthStore.getState().login('access-token')

    useAuthStore.getState().logout()

    expect(useAuthStore.getState()).toMatchObject({ accessToken: null, isLoggedIn: false, isAuthReady: true })
  })

  it('작성 중이던 추가 질문 답변 임시 저장을 모두 지우고, 다른 저장값은 남긴다', () => {
    saveAnswerDraft('p1', 1, { q1: '네' })
    saveAnswerDraft('p2', 2, { q2: '아니요' })
    sessionStorage.setItem('other-key', 'keep')

    useAuthStore.getState().logout()

    expect(loadAnswerDraft('p1', 1)).toEqual({})
    expect(loadAnswerDraft('p2', 2)).toEqual({})
    expect(sessionStorage.getItem('other-key')).toBe('keep')
  })
})
