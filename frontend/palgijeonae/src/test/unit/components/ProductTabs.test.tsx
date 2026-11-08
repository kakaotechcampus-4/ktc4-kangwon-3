import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import ProductTabs from '@/components/common/ProductTabs'
import { setMobileViewport } from '@/test/utils/viewport'

const LONG_NAME = '가나다라마바사아자차카타'

describe('ProductTabs - 말줄임', () => {
  it('데스크톱에서는 상품명을 10글자까지 보여주고 넘으면 ...를 붙인다', () => {
    render(<ProductTabs productNames={[LONG_NAME]} selected={0} onSelect={() => {}} />)

    expect(screen.getByRole('tab', { name: '가나다라마바사아자차...' })).toBeInTheDocument()
  })

  it('모바일에서는 상품명을 8글자까지 보여주고 넘으면 ...를 붙인다', () => {
    setMobileViewport()
    render(<ProductTabs productNames={[LONG_NAME]} selected={0} onSelect={() => {}} />)

    expect(screen.getByRole('tab', { name: '가나다라마바사아...' })).toBeInTheDocument()
  })

  it('한도 이하의 이름은 모바일에서도 그대로 보여준다', () => {
    setMobileViewport()
    render(<ProductTabs productNames={['가나다라마바사아']} selected={0} onSelect={() => {}} />)

    expect(screen.getByRole('tab', { name: '가나다라마바사아' })).toBeInTheDocument()
  })
})
