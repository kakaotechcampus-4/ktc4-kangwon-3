import '@testing-library/jest-dom/vitest'

import { useAuthStore } from '@/store/useAuthStore'

import { requestLog } from './mocks/requestLog'
import { server } from './mocks/server'

// API는 MSW로 모킹한다. 핸들러가 없는 요청은 실수로 실제 네트워크에 나가지 않도록 오류로 처리한다.
beforeAll(() => server.listen({ onUnhandledFrame: 'error' }))
afterAll(() => server.close())

// 브라우저 API 스텁. 호출 인자를 검증하려고 mock으로 바꾸고, 테스트가 끝나면 원래 구현으로 되돌린다.
// - URL.createObjectURL / revokeObjectURL: 이미지 미리보기 (고정 주소를 반환해서 어떤 파일로 만들고 해제했는지 검증)
// - window.alert: jsdom은 구현하지 않아 오류를 출력하므로, 안내 문구를 호출 인자로 검증한다.
// - Element.scrollIntoView: jsdom에 없어서 호출하면 TypeError가 난다. (미답변 질문으로 스크롤할 때 쓴다)
// FormData는 기본 구현을 쓰고, FileReader는 앱이 쓰지 않아 스텁하지 않는다.
const originalCreateObjectURL = URL.createObjectURL
const originalRevokeObjectURL = URL.revokeObjectURL
const originalAlert = window.alert
const originalScrollIntoView = Element.prototype.scrollIntoView

beforeEach(() => {
  URL.createObjectURL = vi.fn(() => 'blob:mock-object-url')
  URL.revokeObjectURL = vi.fn()
  window.alert = vi.fn()
  Element.prototype.scrollIntoView = vi.fn()
})

afterEach(() => {
  URL.createObjectURL = originalCreateObjectURL
  URL.revokeObjectURL = originalRevokeObjectURL
  window.alert = originalAlert
  Element.prototype.scrollIntoView = originalScrollIntoView

  // 테스트 사이에 상태가 새지 않게 초기화한다: 응답 오버라이드, 요청 기록, 인증 스토어
  server.resetHandlers()
  requestLog.clear()
  useAuthStore.setState(useAuthStore.getInitialState(), true)
})
