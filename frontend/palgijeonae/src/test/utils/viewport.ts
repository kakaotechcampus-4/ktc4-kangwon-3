import { vi } from 'vitest'

// 기본 matchMedia 스텁(vitest.setup.ts)은 데스크톱(matches: false)이다. 모바일 폭이 필요한 테스트에서 호출해 바꿔 쓴다. (테스트가 끝나면 vitest.setup.ts가 되돌린다)
export function setMobileViewport() {
  window.matchMedia = vi.fn((query: string) => ({
    matches: true,
    media: query,
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
  })) as unknown as typeof window.matchMedia
}
