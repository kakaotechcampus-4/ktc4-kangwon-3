import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import Button from '@/components/common/Button'

describe('Button - className', () => {
  it('넘겨준 className을 기본 스타일에 더한다', () => {
    render(<Button text="확인" onClick={() => {}} className="w-full md:w-auto" />)

    const button = screen.getByRole('button', { name: '확인' })
    expect(button).toHaveClass('w-full', 'md:w-auto')
    expect(button).toHaveClass('rounded-xl')
  })

  it('기본 스타일과 충돌하는 클래스는 넘겨준 쪽이 이긴다 (self-start → self-stretch)', () => {
    render(<Button text="확인" onClick={() => {}} className="self-stretch" />)

    const button = screen.getByRole('button', { name: '확인' })
    expect(button).toHaveClass('self-stretch')
    expect(button).not.toHaveClass('self-start')
  })

  it('className을 주지 않으면 기본 스타일 그대로다', () => {
    render(<Button text="확인" onClick={() => {}} />)

    expect(screen.getByRole('button', { name: '확인' })).toHaveClass('self-start')
  })
})
