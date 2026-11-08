import '@testing-library/jest-dom/vitest'

import { cleanup, configure } from '@testing-library/react'

import { useAuthStore } from '@/store/useAuthStore'

import { requestLog } from './mocks/requestLog'
import { server } from './mocks/server'

// findBy*/waitFor의 기본 대기(1초)는 전체 테스트를 병렬로 돌릴 때 각 파일의 첫 렌더(무거운 화면)에서 모자랄 수 있다.
// 기다리는 조건이 맞으면 바로 끝나므로, 느린 환경(CI·부하)에서만 여유가 된다.
configure({ asyncUtilTimeout: 5000 })

// API는 MSW로 모킹한다. 핸들러가 없는 요청은 실수로 실제 네트워크에 나가지 않도록 오류로 처리한다.
beforeAll(() => server.listen({ onUnhandledFrame: 'error' }))
afterAll(() => server.close())

// 브라우저 API 스텁. 호출 인자를 검증하려고 mock으로 바꾸고, 테스트가 끝나면 원래 구현으로 되돌린다.
// - URL.createObjectURL / revokeObjectURL: 이미지 미리보기 (고정 주소를 반환해서 어떤 파일로 만들고 해제했는지 검증)
// - window.alert: jsdom은 구현하지 않아 오류를 출력하므로, 안내 문구를 호출 인자로 검증한다.
// - window.confirm: 같은 이유. 기본은 "확인"(true)이고, 취소 시나리오는 테스트에서 mockReturnValue(false)로 바꾼다.
// - Element.scrollIntoView: jsdom에 없어서 호출하면 TypeError가 난다. (미답변 질문으로 스크롤할 때 쓴다)
// - window.matchMedia: jsdom에 없다. 진행 카드의 상태 전환 애니메이션이 "동작 줄이기" 설정을 확인할 때 쓴다. (기본은 설정 꺼짐)
// - Element.animate: jsdom에 없다. 상태 전환 애니메이션이 호출하고, 정리할 때 cancel을 부른다.
// FormData는 기본 구현을 쓰고, FileReader는 앱이 쓰지 않아 스텁하지 않는다.
const originalCreateObjectURL = URL.createObjectURL
const originalRevokeObjectURL = URL.revokeObjectURL
const originalAlert = window.alert
const originalConfirm = window.confirm
const originalScrollIntoView = Element.prototype.scrollIntoView
const originalMatchMedia = window.matchMedia
const originalAnimate = Element.prototype.animate

beforeEach(() => {
  URL.createObjectURL = vi.fn(() => 'blob:mock-object-url')
  URL.revokeObjectURL = vi.fn()
  window.alert = vi.fn()
  window.confirm = vi.fn(() => true)
  Element.prototype.scrollIntoView = vi.fn()
  window.matchMedia = vi.fn((query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: vi.fn(),
    removeListener: vi.fn(),
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    dispatchEvent: vi.fn(() => false),
  }))
  Element.prototype.animate = vi.fn(() => ({ cancel: vi.fn() }) as unknown as Animation)
})

afterEach(() => {
  // 스텁을 되돌리기 전에 화면부터 내린다. (남아 있으면 useIsMobile이 사라진 matchMedia를 부른다)
  cleanup()

  URL.createObjectURL = originalCreateObjectURL
  URL.revokeObjectURL = originalRevokeObjectURL
  window.alert = originalAlert
  window.confirm = originalConfirm
  Element.prototype.scrollIntoView = originalScrollIntoView
  window.matchMedia = originalMatchMedia
  Element.prototype.animate = originalAnimate

  // 테스트 사이에 상태가 새지 않게 초기화한다: 응답 오버라이드, 요청 기록, 인증 스토어
  server.resetHandlers()
  requestLog.clear()
  useAuthStore.setState(useAuthStore.getInitialState(), true)
})
