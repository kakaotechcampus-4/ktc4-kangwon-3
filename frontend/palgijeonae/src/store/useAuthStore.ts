import { create } from 'zustand'

import { clearAllAnswerDrafts } from '@/pages/Question/utils/answerDraft'

interface AuthState {
    accessToken: string | null
    isLoggedIn: boolean
    // 앱 최초 로드 시 세션 복구(reissue) 시도가 끝났는지 여부.
    // 끝나기 전에는 isLoggedIn이 기본값(false)이라, 이 값으로 로그인 여부에 따라 갈리는 화면을 잠깐 숨겨 깜빡임을 막는다.
    isAuthReady: boolean
    login: (accessToken: string) => void
    logout: () => void
    markAuthReady: () => void
}

export const useAuthStore = create<AuthState>((set) => ({
    accessToken: null,
    isLoggedIn: false,
    isAuthReady: false,
    login: (accessToken) => set({ accessToken, isLoggedIn: true, isAuthReady: true }),
    // 직접 로그아웃, 토큰 만료로 인한 강제 로그아웃, 회원 탈퇴가 모두 이 동작을 거친다.
    logout: () => {
        clearAllAnswerDrafts()
        set({ accessToken: null, isLoggedIn: false, isAuthReady: true })
    },
    markAuthReady: () => set({ isAuthReady: true }),
}))
