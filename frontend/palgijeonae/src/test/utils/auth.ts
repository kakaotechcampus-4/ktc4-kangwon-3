import { useAuthStore } from '@/store/useAuthStore'

// 인증 스토어의 시나리오별 상태. 렌더하기 전에 setAuthState로 설정한다. (테스트가 끝나면 vitest.setup.ts가 초기 상태로 되돌린다)
export const authScenarios = {
  // 앱 최초 로드 후 세션 복구(reissue)가 아직 끝나지 않은 상태
  restoring: { isAuthReady: false, isLoggedIn: false, accessToken: null },
  // 복구가 끝났고 로그인하지 않은 상태
  loggedOut: { isAuthReady: true, isLoggedIn: false, accessToken: null },
  // 복구가 끝났고 로그인한 상태
  loggedIn: { isAuthReady: true, isLoggedIn: true, accessToken: 'test-access-token' },
} as const

export type AuthScenario = keyof typeof authScenarios

export function setAuthState(scenario: AuthScenario): void {
  useAuthStore.setState(authScenarios[scenario])
}
