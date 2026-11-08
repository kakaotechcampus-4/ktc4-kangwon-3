import { renderHook } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import { useEscapeKey } from '@/hooks/useEscapeKey'

describe('useEscapeKey', () => {
  it('활성화되어 있으면 Esc를 눌렀을 때 콜백을 호출한다', async () => {
    const onEscape = vi.fn()
    renderHook(() => useEscapeKey(true, onEscape))

    await userEvent.keyboard('{Escape}')

    expect(onEscape).toHaveBeenCalledTimes(1)
  })

  it('Esc가 아닌 키는 무시한다', async () => {
    const onEscape = vi.fn()
    renderHook(() => useEscapeKey(true, onEscape))

    await userEvent.keyboard('{Enter}a')

    expect(onEscape).not.toHaveBeenCalled()
  })

  it('비활성화되어 있으면 Esc를 눌러도 호출하지 않는다', async () => {
    const onEscape = vi.fn()
    renderHook(() => useEscapeKey(false, onEscape))

    await userEvent.keyboard('{Escape}')

    expect(onEscape).not.toHaveBeenCalled()
  })

  it('사용이 끝나면 키 감지를 해제한다', async () => {
    const onEscape = vi.fn()
    const { unmount } = renderHook(() => useEscapeKey(true, onEscape))
    unmount()

    await userEvent.keyboard('{Escape}')

    expect(onEscape).not.toHaveBeenCalled()
  })
})
