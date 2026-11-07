import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

import Button from '@/components/common/Button'

// 테스트 환경(jsdom, Testing Library, jest-dom 매처, user-event, `@` alias)이 동작하는지 확인하는 최소 테스트.
describe('테스트 환경', () => {
  it('컴포넌트를 렌더하고 사용자 클릭을 처리한다', async () => {
    const onClick = vi.fn()
    render(<Button text="확인" onClick={onClick} />)

    const button = screen.getByRole('button', { name: '확인' })
    expect(button).toBeInTheDocument()

    await userEvent.click(button)
    expect(onClick).toHaveBeenCalledTimes(1)
  })

  it('비활성화된 버튼은 클릭되지 않는다', async () => {
    const onClick = vi.fn()
    render(<Button text="확인" onClick={onClick} disabled />)

    await userEvent.click(screen.getByRole('button', { name: '확인' }))
    expect(onClick).not.toHaveBeenCalled()
  })
})
