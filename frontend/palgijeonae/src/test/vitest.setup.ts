import '@testing-library/jest-dom/vitest'

// 이미지 미리보기용 URL.createObjectURL / revokeObjectURL 스텁. (호출 인자·해제 여부를 검증하려고 고정값 mock을 쓴다)
// FormData는 기본 구현을 쓰고, FileReader는 앱이 쓰지 않아 스텁하지 않는다.
const originalCreateObjectURL = URL.createObjectURL
const originalRevokeObjectURL = URL.revokeObjectURL

beforeEach(() => {
  URL.createObjectURL = vi.fn(() => 'blob:mock-object-url')
  URL.revokeObjectURL = vi.fn()
})

afterEach(() => {
  URL.createObjectURL = originalCreateObjectURL
  URL.revokeObjectURL = originalRevokeObjectURL
})
