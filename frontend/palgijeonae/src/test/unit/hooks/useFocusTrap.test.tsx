import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useRef } from 'react'
import { describe, expect, it } from 'vitest'

import { useFocusTrap } from '@/hooks/useFocusTrap'

// 가둘 영역은 "트리거 버튼 + 패널" 두 곳이고, 그 바깥에도 Tab으로 갈 수 있는 요소가 있다.
function Harness({ enabled = true }: { enabled?: boolean }) {
  const triggerRef = useRef<HTMLButtonElement>(null)
  const panelRef = useRef<HTMLDivElement>(null)
  useFocusTrap(enabled, [triggerRef, panelRef])

  return (
    <>
      <a href="#before">바깥 앞</a>
      <button ref={triggerRef} type="button">트리거</button>
      <div ref={panelRef}>
        <a href="#one">첫째</a>
        <button type="button" disabled>비활성</button>
        <button type="button">마지막</button>
      </div>
      <a href="#after">바깥 뒤</a>
    </>
  )
}

describe('useFocusTrap', () => {
  it('마지막 요소에서 Tab을 누르면 첫 요소(트리거)로 돌아온다', async () => {
    const user = userEvent.setup()
    render(<Harness />)
    screen.getByRole('button', { name: '마지막' }).focus()

    await user.tab()

    expect(screen.getByRole('button', { name: '트리거' })).toHaveFocus()
  })

  it('첫 요소(트리거)에서 Shift+Tab을 누르면 마지막 요소로 간다', async () => {
    const user = userEvent.setup()
    render(<Harness />)
    screen.getByRole('button', { name: '트리거' }).focus()

    await user.tab({ shift: true })

    expect(screen.getByRole('button', { name: '마지막' })).toHaveFocus()
  })

  it('중간에서는 평소처럼 다음 요소로 이동하고, 비활성 요소는 건너뛴다', async () => {
    const user = userEvent.setup()
    render(<Harness />)
    screen.getByRole('link', { name: '첫째' }).focus()

    await user.tab()

    expect(screen.getByRole('button', { name: '마지막' })).toHaveFocus()
  })

  it('포커스가 영역 밖에 있으면 Tab으로 영역 안으로 끌어온다', async () => {
    const user = userEvent.setup()
    render(<Harness />)
    screen.getByRole('link', { name: '바깥 뒤' }).focus()

    await user.tab()

    expect(screen.getByRole('button', { name: '트리거' })).toHaveFocus()
  })

  it('Shift+Tab으로 영역 밖에서 돌아올 때는 마지막 요소로 보낸다', async () => {
    const user = userEvent.setup()
    render(<Harness />)
    screen.getByRole('link', { name: '바깥 앞' }).focus()

    await user.tab({ shift: true })

    expect(screen.getByRole('button', { name: '마지막' })).toHaveFocus()
  })

  it('비활성화되어 있으면 Tab 이동에 관여하지 않는다', async () => {
    const user = userEvent.setup()
    render(<Harness enabled={false} />)
    screen.getByRole('button', { name: '마지막' }).focus()

    await user.tab()

    expect(screen.getByRole('link', { name: '바깥 뒤' })).toHaveFocus()
  })
})
