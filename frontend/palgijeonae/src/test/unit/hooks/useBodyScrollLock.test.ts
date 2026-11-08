import { renderHook } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'

import { useBodyScrollLock } from '@/hooks/useBodyScrollLock'

describe('useBodyScrollLock', () => {
  afterEach(() => {
    document.body.style.overflow = ''
  })

  it('잠금이 켜져 있는 동안 body 스크롤을 막는다', () => {
    renderHook(() => useBodyScrollLock(true))

    expect(document.body.style.overflow).toBe('hidden')
  })

  it('잠금이 꺼져 있으면 body를 건드리지 않는다', () => {
    renderHook(() => useBodyScrollLock(false))

    expect(document.body.style.overflow).toBe('')
  })

  it('잠금이 끝나면 원래 overflow 값으로 되돌린다', () => {
    document.body.style.overflow = 'scroll'
    const { unmount } = renderHook(() => useBodyScrollLock(true))
    expect(document.body.style.overflow).toBe('hidden')

    unmount()

    expect(document.body.style.overflow).toBe('scroll')
  })
})
