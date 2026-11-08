import { act, renderHook } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import { useIsMobile } from '@/hooks/useIsMobile'

// 기본 matchMedia 스텁(vitest.setup.ts)은 항상 matches: false 이고 change 이벤트를 보내지 않아서, 이 테스트에서 직접 바꿔 쓴다.
function stubMatchMedia(initialMatches: boolean) {
  let matches = initialMatches
  const listeners = new Set<() => void>()

  window.matchMedia = vi.fn((query: string) => ({
    get matches() {
      return matches
    },
    media: query,
    addEventListener: (_type: string, listener: () => void) => listeners.add(listener),
    removeEventListener: (_type: string, listener: () => void) => listeners.delete(listener),
  })) as unknown as typeof window.matchMedia

  return {
    resize(nextMatches: boolean) {
      matches = nextMatches
      listeners.forEach((listener) => listener())
    },
    listenerCount: () => listeners.size,
  }
}

describe('useIsMobile', () => {
  it('화면 너비가 767px 이하이면 true이고, 그보다 넓으면 false이다', () => {
    stubMatchMedia(true)
    expect(renderHook(() => useIsMobile()).result.current).toBe(true)

    stubMatchMedia(false)
    expect(renderHook(() => useIsMobile()).result.current).toBe(false)
  })

  it('768px 미만 기준의 미디어 쿼리를 사용한다', () => {
    stubMatchMedia(false)
    renderHook(() => useIsMobile())
    expect(window.matchMedia).toHaveBeenCalledWith('(max-width: 767px)')
  })

  it('창 크기나 방향이 바뀌면 값이 갱신된다', () => {
    const screen = stubMatchMedia(false)
    const { result } = renderHook(() => useIsMobile())

    act(() => screen.resize(true))
    expect(result.current).toBe(true)

    act(() => screen.resize(false))
    expect(result.current).toBe(false)
  })

  it('사용이 끝나면 변경 감지를 해제한다', () => {
    const screen = stubMatchMedia(false)
    const { unmount } = renderHook(() => useIsMobile())
    expect(screen.listenerCount()).toBe(1)

    unmount()
    expect(screen.listenerCount()).toBe(0)
  })
})
