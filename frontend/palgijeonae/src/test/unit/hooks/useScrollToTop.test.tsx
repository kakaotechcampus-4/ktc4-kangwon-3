import { act, renderHook } from '@testing-library/react'
import type { ReactNode } from 'react'
import { MemoryRouter, useNavigate } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { useScrollToTop } from '@/hooks/useScrollToTop'

// 훅과 함께 navigate를 돌려받아, 테스트가 화면 이동을 직접 일으킨다.
function renderScrollToTop(initialEntries: string[], initialIndex?: number) {
  return renderHook(
    () => {
      useScrollToTop()
      return useNavigate()
    },
    {
      wrapper: ({ children }: { children: ReactNode }) => (
        <MemoryRouter initialEntries={initialEntries} initialIndex={initialIndex}>
          {children}
        </MemoryRouter>
      ),
    },
  )
}

describe('useScrollToTop', () => {
  let scrollTo: ReturnType<typeof vi.spyOn>

  beforeEach(() => {
    scrollTo = vi.spyOn(window, 'scrollTo').mockImplementation(() => {})
  })

  afterEach(() => {
    scrollTo.mockRestore()
  })

  it('처음 렌더할 때는 스크롤을 움직이지 않는다 (새로고침은 브라우저 복원에 맡긴다)', () => {
    renderScrollToTop(['/a'])

    expect(scrollTo).not.toHaveBeenCalled()
  })

  it('다른 경로로 이동하면 맨 위로 올린다', () => {
    const { result } = renderScrollToTop(['/a'])

    act(() => result.current('/b'))

    expect(scrollTo).toHaveBeenCalledTimes(1)
    expect(scrollTo).toHaveBeenCalledWith(0, 0)
  })

  it('이동 기록을 대체하는 이동(replace)에도 맨 위로 올린다', () => {
    const { result } = renderScrollToTop(['/a'])

    act(() => result.current('/b', { replace: true }))

    expect(scrollTo).toHaveBeenCalledTimes(1)
    expect(scrollTo).toHaveBeenCalledWith(0, 0)
  })

  it('뒤로 가기와 앞으로 가기에는 올리지 않는다 (브라우저 스크롤 복원에 맡긴다)', () => {
    const { result } = renderScrollToTop(['/a', '/b'], 1)

    act(() => result.current(-1))
    expect(scrollTo).not.toHaveBeenCalled()

    act(() => result.current(1))
    expect(scrollTo).not.toHaveBeenCalled()
  })

  it('이동한 뒤 뒤로 가면 이동할 때 한 번만 올리고, 뒤로 갈 때는 올리지 않는다', () => {
    const { result } = renderScrollToTop(['/a'])

    act(() => result.current('/b'))
    act(() => result.current(-1))

    expect(scrollTo).toHaveBeenCalledTimes(1)
  })

  it('해시만 바뀌는 이동(목차 링크)은 올리지 않는다', () => {
    const { result } = renderScrollToTop(['/a'])

    act(() => result.current('/a#article-1'))

    expect(scrollTo).not.toHaveBeenCalled()
  })

  it('쿼리만 바뀌는 이동은 올리지 않는다', () => {
    const { result } = renderScrollToTop(['/a'])

    act(() => result.current('/a?page=2'))

    expect(scrollTo).not.toHaveBeenCalled()
  })
})
